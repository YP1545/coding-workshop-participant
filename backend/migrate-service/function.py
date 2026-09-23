"""
Run the database migrations from inside the VPC.

Part of: backend / migrations.

Why this exists: Aurora is created without `publicly_accessible`, so it has no
public endpoint and `alembic upgrade head` cannot be run from a developer's
machine. The Lambdas sit in the same subnets and security groups, so they can
reach it — this one exists to do nothing but that.

Why it is not an endpoint: Terraform gives every discovered service a public
Function URL, and an internet-reachable "run the migrations" button is not
something this application should have. The handler refuses anything shaped like
an HTTP request, so the only way to trigger it is a direct

    aws lambda invoke --function-name <this>

which already requires AWS credentials with lambda:InvokeFunction. That is the
authorisation check; there is no second one to get wrong.

Deleting this directory and re-applying removes the function entirely, because
infra/locals.tf discovers services by globbing for requirements.txt.
"""

import logging
import os

from alembic import command
from alembic.config import Config

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Lambda unpacks the deployment package here and makes it the working directory,
# but the path is stated explicitly rather than assumed: alembic.ini's
# script_location is relative, and a surprise working directory would make it
# fail with a confusing "path doesn't exist" rather than a migration error.
TASK_ROOT = os.environ.get("LAMBDA_TASK_ROOT", os.path.dirname(os.path.abspath(__file__)))


def looks_like_http(event):
    """
    True when this arrived over the Function URL rather than a direct invoke.

    A Function URL event always carries requestContext.http; a direct invoke
    carries whatever payload the caller sent, which for this function is
    nothing. Checking the shape rather than a header means there is no secret
    to leak and nothing to misconfigure.
    """
    return isinstance(event, dict) and "requestContext" in event


def alembic_config():
    """Point Alembic at the migrations inside the deployment package."""
    config = Config(os.path.join(TASK_ROOT, "alembic.ini"))
    config.set_main_option("script_location", os.path.join(TASK_ROOT, "alembic"))
    return config


def current_revision(config):
    """
    The revision the database is on, or None if it has never been migrated.

    Read through Alembic's own machinery rather than querying alembic_version
    directly, so a database with no such table reports None instead of raising.
    """
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy import create_engine

    from db import database_url

    engine = create_engine(database_url())
    try:
        with engine.connect() as connection:
            return MigrationContext.configure(connection).get_current_revision()
    finally:
        engine.dispose()


def migrate():
    """Bring the database up to the latest migration."""
    config = alembic_config()

    before = current_revision(config)
    logger.info("Database is at revision %s", before)

    command.upgrade(config, "head")

    after = current_revision(config)
    logger.info("Database is now at revision %s", after)

    return {"action": "migrate", "before": before, "after": after, "changed": before != after}


def promote(email):
    """
    Make an existing account a facility admin.

    Why this exists: a fresh deployment has no way to create its first admin.
    Registration always produces an employee — deliberately, so nobody can sign
    up as an administrator — and PATCH /users/{id}/role requires an admin to
    call it. Without a way in from outside, the system cannot bootstrap itself.

    This is that way in, and it is deliberately the narrowest one: it promotes
    an account that already exists, it cannot create one, and it cannot set a
    password. Running it needs AWS credentials with lambda:InvokeFunction — a
    stronger check than any application role, and one no web request can reach.

    Args:
        email (str): the address of the account to promote.
    """
    from sqlalchemy import create_engine, func, select
    from sqlalchemy.orm import Session

    from db import database_url
    from models import User, UserRole

    engine = create_engine(database_url())
    try:
        with Session(engine) as session:
            wanted = email.strip().lower()
            account = session.scalar(select(User).where(func.lower(User.email) == wanted))

            if account is None:
                # Named plainly: this runs from a trusted context, and "no such
                # account" is the one thing the caller needs to know.
                return {"action": "promote", "email": wanted, "error": "no such account"}

            was = account.role.value
            account.role = UserRole.FACILITY_ADMIN
            session.commit()

            logger.info("Promoted %s from %s to facility_admin", wanted, was)
            return {"action": "promote", "email": wanted, "was": was, "now": "facility_admin"}
    finally:
        engine.dispose()


def seed_demo_data(password=None, reset=False):
    """
    Fill an empty database with the demo dataset.

    The password is generated here rather than taken from seed.py's default.
    That default is committed in this repository, and this database is behind a
    public URL — seeding with it would publish five working logins, one of them
    a facility admin, to anyone who reads the repo. The generated value is
    returned once and stored nowhere.

    Args:
        password (str, optional): use this instead of a generated one.
        reset (bool): required to seed a database that already has users, since
            seeding deletes every existing row first.
    """
    import secrets

    chosen = password or secrets.token_urlsafe(12)

    from sqlalchemy import select

    from db import session_scope
    from models import User
    import seed as seed_module

    # Set the module attribute rather than the environment variable.
    #
    # seed.py reads SEED_PASSWORD once, at import time. A Lambda container is
    # reused between invocations, so on the second call `import seed` is a
    # no-op and the module keeps whatever password the first call set — the
    # accounts get hashed with a password nobody was told, while the response
    # reports the one that was asked for. Assigning here works whether the
    # module was imported a moment ago or several invocations back.
    seed_module.SEED_PASSWORD = chosen

    with session_scope() as session:
        already_there = session.scalar(select(User).limit(1))
        if already_there and not reset:
            return {
                "action": "seed",
                "error": "database already has users; pass {\"reset\": true} to replace them",
            }

        if reset:
            logger.warning("Deleting all existing rows before seeding")
            seed_module.clear_all(session)

        counts = seed_module.seed(session)

    logger.info("Seeded the demo dataset")
    return {
        "action": "seed",
        "counts": counts,
        "password": chosen,
        "accounts": [
            "dana.admin@acme.inc      facility_admin",
            "sam.employee@acme.inc    employee",
            "priya.employee@acme.inc  employee",
            "alex.engineer@acme.inc   engineer (available)",
            "jo.engineer@acme.inc     engineer (busy)",
        ],
    }


def handler(event, context):
    """
    Run a maintenance task. Migrating is the default.

    Payloads:
        {}                                     migrate to head
        {"action": "promote", "email": "..."}  make an account a facility admin
        {"action": "seed"}                     fill an empty database with demo data
        {"action": "seed", "reset": true}      replace whatever is there

    Returns:
        dict: what was done, so an invocation that changed nothing is
            distinguishable from one that did.
    """
    if looks_like_http(event):
        # Deliberately a bare 404 rather than 403: telling the internet that a
        # migration runner exists here invites somebody to look for a way in.
        logger.warning("Refused an HTTP request to the migration runner")
        return {"statusCode": 404, "headers": {"content-type": "application/json"},
                "body": '{"detail":"Not found"}'}

    action = (event or {}).get("action", "migrate")

    if action == "migrate":
        return migrate()

    if action == "promote":
        email = (event or {}).get("email")
        if not email:
            return {"error": "promote needs an email"}
        return promote(email)

    if action == "seed":
        return seed_demo_data(
            password=(event or {}).get("password"),
            reset=bool((event or {}).get("reset")),
        )

    return {"error": f"unknown action '{action}'. Use 'migrate', 'promote' or 'seed'."}
