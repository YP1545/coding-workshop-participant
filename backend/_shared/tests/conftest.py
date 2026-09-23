"""
Shared test setup: a disposable database, and one client per persona.

Part of: backend / tests.

Why its own file: every test needs the same two things — a database that is
created fresh and thrown away, and a way to call an endpoint as a particular
person. Doing that once here means the tests themselves are about behaviour
rather than plumbing.

The database is created per run and dropped afterwards, so tests never touch
the development data and can never leave anything behind. That also means the
tests can be run repeatedly and in any order.
"""

import importlib.util
import json
import os
import subprocess
import sys
import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

SHARED_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.dirname(SHARED_DIR)

# Connection details for creating and dropping the test database. The tests
# themselves connect through the services' own db.py, using the environment.
ADMIN_DSN = "host={host} port={port} user={user} password={password} dbname=postgres".format(
    host=os.getenv("POSTGRES_HOST", "localhost"),
    port=os.getenv("POSTGRES_PORT", "5432"),
    user=os.getenv("POSTGRES_USER", "postgres"),
    password=os.getenv("POSTGRES_PASS", "postgres123"),
)

PASSWORD = "TestPassw0rd!"


@pytest.fixture(scope="session")
def database():
    """
    Create a database for this run, migrate it, and drop it at the end.

    Named with a random suffix so two runs cannot collide, and dropped in a
    finally block so a failing test still cleans up after itself.
    """
    name = f"acme_test_{uuid.uuid4().hex[:8]}"

    with psycopg.connect(ADMIN_DSN, autocommit=True) as connection:
        connection.execute(f'CREATE DATABASE "{name}"')

    # The services read these when they first open a connection, so they must
    # be set before any service module is imported.
    os.environ["IS_LOCAL"] = "true"
    os.environ["POSTGRES_NAME"] = name

    try:
        # The schema comes from the real migration, not from create_all. A test
        # database built a different way would not prove the migration works.
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=SHARED_DIR, check=True, capture_output=True,
        )
        yield name
    finally:
        with psycopg.connect(ADMIN_DSN, autocommit=True) as connection:
            connection.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s",
                (name,),
            )
            connection.execute(f'DROP DATABASE IF EXISTS "{name}"')


def load_service(name):
    """Import one service's function.py with its own directory first on sys.path."""
    sys.path.insert(0, os.path.join(BACKEND_DIR, name))
    for module in ("function", "app", "errors", "deps", "schemas", "db", "models", "auth",
                   "access", "workflow", "dashboard", "assignment_requests", "crud"):
        sys.modules.pop(module, None)
    spec = importlib.util.spec_from_file_location(
        f"{name}_function", os.path.join(BACKEND_DIR, name, "function.py"))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    sys.path.pop(0)
    return loaded


@pytest.fixture(scope="session")
def services(database):
    """
    A test client per service, sharing the test database.

    FastAPI's TestClient calls the application in-process — the same routing,
    validation and dependencies a real request goes through, without a server or
    a network. What it does not exercise is Mangum's event translation, which
    has its own test in test_lambda_entry.py.
    """
    return {
        "users": TestClient(load_service("users-service").app),
        "facilities": TestClient(load_service("facilities-service").app),
        "engineers": TestClient(load_service("engineers-service").app),
        "incidents": TestClient(load_service("incidents-service").app),
    }


class Client:
    """
    Calls a service as a particular person.

    Returns (status, payload) rather than raising, because most of these tests
    are about which status code comes back. The interface predates FastAPI and
    is kept so the tests read the same either way.
    """

    def __init__(self, services, token=None):
        self.services = services
        self.token = token

    def as_token(self, token):
        """A copy of this client signed in as somebody else."""
        return Client(self.services, token)

    def call(self, service, method, path, body=None, query=None):
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        # None values are dropped: a filter nobody set should not be sent at all.
        params = {k: v for k, v in (query or {}).items() if v is not None}

        response = self.services[service].request(
            method, path, json=body, params=params or None, headers=headers)

        payload = None
        if response.content:
            try:
                payload = response.json()
            except ValueError:
                payload = response.text
        return response.status_code, payload

    # Short forms, so a test reads like the request it is making.
    def get(self, service, path, query=None):
        return self.call(service, "GET", path, query=query)

    def post(self, service, path, body=None):
        return self.call(service, "POST", path, body)

    def put(self, service, path, body=None):
        return self.call(service, "PUT", path, body)

    def patch(self, service, path, body=None):
        return self.call(service, "PATCH", path, body)

    def delete(self, service, path):
        return self.call(service, "DELETE", path)


@pytest.fixture
def anonymous(services):
    """A client with no token at all."""
    return Client(services)


def register_and_login(client, email, full_name):
    """Create an account and return a client signed in as it, plus the account."""
    status, account = client.post("users", "/auth/register", {
        "email": email, "password": PASSWORD, "full_name": full_name})
    assert status == 201, account
    status, session = client.post("users", "/auth/login", {
        "email": email, "password": PASSWORD})
    assert status == 200, session
    return client.as_token(session["access_token"]), account


@pytest.fixture(scope="session")
def people(services):
    """
    One account per persona, created once for the whole run.

    Session-scoped because creating them is slow (bcrypt is deliberately slow)
    and because no test changes them. Tests that need to change a person make
    their own.
    """
    client = Client(services)
    suffix = uuid.uuid4().hex[:6]

    # The first account is promoted to admin directly in the database: there is
    # no endpoint for making the first admin, which is correct — otherwise
    # anyone could.
    admin_client, admin = register_and_login(client, f"admin{suffix}@acme.inc", "Test Admin")
    sys.path.insert(0, os.path.join(BACKEND_DIR, "users-service"))
    from db import session_scope
    from models import User, UserRole
    with session_scope() as session:
        session.get(User, uuid.UUID(admin["id"])).role = UserRole.FACILITY_ADMIN
    sys.path.pop(0)

    # Signing in again picks up the new role.
    status, session_payload = client.post("users", "/auth/login", {
        "email": f"admin{suffix}@acme.inc", "password": PASSWORD})
    admin_client = client.as_token(session_payload["access_token"])

    employee_client, employee = register_and_login(client, f"emp{suffix}@acme.inc", "Test Employee")
    engineer_client, engineer_user = register_and_login(client, f"eng{suffix}@acme.inc", "Test Engineer")

    status, profile = admin_client.post("engineers", "/engineers", {
        "user_id": engineer_user["id"], "specialty": "Testing"})
    assert status == 201, profile

    # The role changed, so the engineer's token has to be reissued.
    status, session_payload = client.post("users", "/auth/login", {
        "email": f"eng{suffix}@acme.inc", "password": PASSWORD})
    engineer_client = client.as_token(session_payload["access_token"])

    return {
        "admin": admin_client, "admin_user": admin,
        "employee": employee_client, "employee_user": employee,
        "engineer": engineer_client, "engineer_user": engineer_user,
        "engineer_profile": profile,
    }


@pytest.fixture
def admin(people):
    """A client signed in as a facility admin."""
    return people["admin"]


@pytest.fixture
def employee(people):
    """A client signed in as an employee."""
    return people["employee"]


@pytest.fixture
def engineer(people):
    """A client signed in as an engineer who has a profile."""
    return people["engineer"]


@pytest.fixture
def facility(admin):
    """A building with one floor and one seat, created fresh per test."""
    suffix = uuid.uuid4().hex[:6]
    _, building = admin.post("facilities", "/buildings", {"name": f"Tower {suffix}"})
    _, floor = admin.post("facilities", f"/buildings/{building['id']}/floors", {"name": "Level 1"})
    _, seat = admin.post("facilities", f"/floors/{floor['id']}/seats", {"label": f"1-{suffix}"})
    return {"building": building, "floor": floor, "seat": seat}


@pytest.fixture
def incident(employee):
    """An open incident reported by the employee, created fresh per test."""
    status, reported = employee.post("incidents", "/incidents", {
        "title": "Meeting room AC blowing warm air",
        "description": "Level 2 south room has been at 27C since Monday.",
        "category": "hvac", "priority": "high"})
    assert status == 201, reported
    return reported
