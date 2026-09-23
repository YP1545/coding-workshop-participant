"""
PostgreSQL engine and session management shared by every backend service.

Part of: backend / core (infrastructure).

Why its own file: all four Lambda services talk to the same database and need
identical connection rules — credentials from the environment that
infra/locals.tf injects, TLS everywhere except a developer's machine, and one
engine reused across warm invocations. Putting those rules here means a
connection fix is made once and synced out (see sync.sh) instead of being
edited in four places that then drift apart.

This file is the canonical copy. Do not edit the copies inside the service
directories — edit here and run ./sync.sh.
"""

import os
from contextlib import contextmanager
from functools import lru_cache
from urllib.parse import quote_plus

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

# Lambda containers are single-threaded and frozen between invocations, so a
# large pool is wasted memory. But a pool of exactly one with no overflow makes
# any second concurrent session (a nested session_scope, a test fixture, the
# seed script) block until it times out, so a little headroom is kept.
# pool_pre_ping catches connections Aurora dropped while the container slept,
# pool_recycle stays under the usual idle-timeout window, and pool_timeout makes
# exhaustion fail in seconds instead of hanging until the Lambda's 300s limit.
POOL_SIZE = 1
POOL_MAX_OVERFLOW = 2
POOL_TIMEOUT_SECONDS = 10
POOL_RECYCLE_SECONDS = 280


def is_local() -> bool:
    """
    True when running against the LocalStack/local Postgres stack.

    infra/locals.tf sets IS_LOCAL per environment; it is the single switch that
    decides whether TLS is required, so it is read here rather than sniffed
    from the hostname.
    """
    return os.getenv("IS_LOCAL", "false").lower() == "true"


def database_url() -> str:
    """
    Build the SQLAlchemy connection URL from the injected environment variables.

    The password is percent-encoded because Aurora's generated master passwords
    may contain characters that would otherwise terminate the URL early.
    Deployed connections append sslmode=require: Aurora accepts plaintext
    connections inside the VPC, so without this the traffic would silently be
    unencrypted rather than fail loudly.
    """
    user = quote_plus(os.getenv("POSTGRES_USER", "postgres"))
    password = quote_plus(os.getenv("POSTGRES_PASS", "postgres123"))
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    name = os.getenv("POSTGRES_NAME", "postgres")

    url = f"postgresql+psycopg://{user}:{password}@{host}:{port}/{name}"
    return url if is_local() else f"{url}?sslmode=require"


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """
    Return the process-wide engine, created on first use.

    Cached so a warm Lambda container reuses its connection instead of paying
    TCP + TLS setup on every request. The URL is never logged: it carries the
    database password.
    """
    return create_engine(
        database_url(),
        pool_size=POOL_SIZE,
        max_overflow=POOL_MAX_OVERFLOW,
        pool_timeout=POOL_TIMEOUT_SECONDS,
        pool_pre_ping=True,
        pool_recycle=POOL_RECYCLE_SECONDS,
        future=True,
    )


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    """Return the process-wide session factory bound to the cached engine."""
    return sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)


@contextmanager
def session_scope():
    """
    Yield a session that commits on success and rolls back on any exception.

    Route handlers use this so a failed request can never leave a half-applied
    transaction behind on a connection the next invocation will reuse.

    Yields:
        Session: an open SQLAlchemy session.
    """
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
