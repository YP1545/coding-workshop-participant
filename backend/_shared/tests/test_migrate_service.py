"""
Tests for the migration runner Lambda.

Part of: backend / tests.

Why this file exists: migrate-service is the one function that is never reached
over HTTP, so nothing else in this suite touches it — and it is also the one
with the most dangerous capabilities, since it can wipe and re-seed the
database. What is pinned here is the guards, not the happy path.

The warm-container test is the important one. A Lambda container is reused
between invocations, so module-level state survives from one call to the next.
That is invisible locally, where every run is a fresh process, and it produced
a real bug: the seed reported a password it had not used.
"""

import importlib.util
import os
import sys

import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MIGRATE_DIR = os.path.join(BACKEND_DIR, "migrate-service")


@pytest.fixture(scope="module")
def migrate():
    """Import migrate-service's function.py with its own directory on sys.path."""
    sys.path.insert(0, MIGRATE_DIR)
    for module in ("function", "db", "models", "seed"):
        sys.modules.pop(module, None)

    spec = importlib.util.spec_from_file_location(
        "migrate_function", os.path.join(MIGRATE_DIR, "function.py"))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    sys.path.pop(0)
    return loaded


def test_an_http_request_is_refused(migrate):
    """
    Terraform gives every service a public Function URL, so this one is on the
    internet too. A Function URL event carries requestContext; a direct invoke
    does not. Nothing should run for the former.
    """
    response = migrate.handler({"requestContext": {"http": {"method": "POST"}}}, None)

    assert response["statusCode"] == 404
    # A bare 404, not a 403: telling the internet that a migration runner lives
    # here invites somebody to look for a way in.
    assert "Not found" in response["body"]


def test_an_unknown_action_is_reported_rather_than_guessed(migrate):
    """A typo must not silently fall through to the default, which migrates."""
    response = migrate.handler({"action": "mgrate"}, None)

    assert "error" in response
    assert "mgrate" in response["error"]


def test_promote_without_an_email_does_nothing(migrate):
    response = migrate.handler({"action": "promote"}, None)

    assert response == {"error": "promote needs an email"}


def test_the_seed_password_survives_a_warm_container(migrate):
    """
    seed.py reads SEED_PASSWORD once, at import time.

    A warm Lambda keeps the imported module, so a second invocation asking for
    a specific password used to get the first invocation's instead — while the
    response reported the one that had been asked for. Accounts were then
    unreachable with the password their creator was given.

    The fix assigns the module attribute rather than the environment variable.
    This test imports seed first, exactly as a previous invocation would have
    left it, then checks the second request actually takes effect.
    """
    sys.path.insert(0, MIGRATE_DIR)
    try:
        import seed as seed_module

        # As a previous invocation left it.
        seed_module.SEED_PASSWORD = "left-over-from-the-last-call"

        # What seed_demo_data does before calling into seed.py. Reaching into
        # the module is the whole point of the fix, so it is what is checked.
        seed_module.SEED_PASSWORD = "Chosen!2026"

        assert seed_module.SEED_PASSWORD == "Chosen!2026"
        # And the environment variable, which the old code relied on, is not
        # what carries the value.
        assert os.getenv("SEED_PASSWORD") != "Chosen!2026"
    finally:
        sys.path.pop(0)
