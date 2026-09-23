"""
The guarantees the database itself makes, independent of any endpoint.

Part of: backend / tests.

Why its own file: these rules hold even if an endpoint forgets them — a bad row
cannot be written by a script, a migration, or a future endpoint nobody has
thought of yet. Testing them through the API would only prove the API checks
them; this proves the database does.
"""

import uuid

import pytest
from sqlalchemy.exc import DataError, IntegrityError


@pytest.fixture
def session(services):
    """A database session, using the same code the services use."""
    from db import session_scope
    return session_scope


def test_email_must_be_an_acme_address(session):
    """A non-company address is refused by the CHECK constraint, not just the API."""
    from models import User

    with pytest.raises(IntegrityError):
        with session() as db:
            db.add(User(email="outsider@gmail.com", full_name="Outsider", password_hash="x"))


def test_email_is_unique_regardless_of_case(session):
    """
    "Bob@ACME.inc" cannot be registered alongside "bob@acme.inc".

    Plain UNIQUE is case-sensitive, so without the index on lower(email) these
    would be two accounts for one person — an account-confusion problem at
    sign-in. This is not in the original DDL; it was added deliberately.
    """
    from models import User

    address = f"case{uuid.uuid4().hex[:6]}@acme.inc"
    with session() as db:
        db.add(User(email=address, full_name="First", password_hash="x"))

    with pytest.raises(IntegrityError):
        with session() as db:
            db.add(User(email=address.upper().replace("@ACME.INC", "@ACME.inc"),
                        full_name="Impostor", password_hash="x"))


def test_status_must_be_one_of_the_five(session):
    """An invented status is refused by the enum type."""
    from sqlalchemy import text

    with pytest.raises((DataError, IntegrityError)):
        with session() as db:
            db.execute(text("UPDATE incidents SET status = 'sideways'"))


def test_deleting_a_building_with_floors_is_refused(session, admin, facility):
    """
    ON DELETE RESTRICT protects the location history.

    The API turns this into a 409; here it is the database refusing outright,
    which is what makes the API's answer trustworthy.
    """
    from models import Building

    with pytest.raises(IntegrityError):
        with session() as db:
            db.delete(db.get(Building, uuid.UUID(facility["building"]["id"])))


def test_deleting_an_incident_takes_its_notes_with_it(session, employee, incident):
    """
    ON DELETE CASCADE on notes.

    Notes describe one incident and nothing else, so orphaning them would
    serve nobody.
    """
    from sqlalchemy import select

    from models import Incident, IncidentNote

    employee.post("incidents", f"/incidents/{incident['id']}/notes", {"body": "A note"})
    incident_id = uuid.UUID(incident["id"])

    with session() as db:
        assert db.scalars(
            select(IncidentNote).where(IncidentNote.incident_id == incident_id)).all()
        db.delete(db.get(Incident, incident_id))

    with session() as db:
        assert db.scalars(
            select(IncidentNote).where(IncidentNote.incident_id == incident_id)).all() == []


def test_an_engineer_cannot_have_two_profiles(session, people):
    """The unique constraint on engineer_profiles.user_id."""
    from models import EngineerProfile

    with pytest.raises(IntegrityError):
        with session() as db:
            db.add(EngineerProfile(user_id=uuid.UUID(people["engineer_user"]["id"])))


def test_a_category_still_in_use_cannot_be_deleted(session, employee):
    """
    ON DELETE RESTRICT on incidents.category.

    Removing a category that incidents are filed under must be refused, not
    quietly take those incidents with it. This is the guarantee that replaced
    the enum type: the allowed values are data now, so the foreign key is what
    keeps an incident from pointing at a category that does not exist.
    """
    from models import IncidentCategory

    # File something under it first — the constraint only bites when the
    # category is actually referenced, and the test database starts empty.
    created, _ = employee.post(
        "incidents", "/incidents",
        {"title": "Dripping tap", "description": "Body.",
         "category": "plumbing", "priority": "low"},
    )
    assert created == 201

    with pytest.raises(IntegrityError):
        with session() as db:
            db.delete(db.get(IncidentCategory, "plumbing"))


def test_an_unused_category_can_be_deleted(session):
    """
    The mirror of the test above: RESTRICT blocks a category in use, not every
    category. A facility admin who adds one by mistake can remove it again.
    """
    from models import IncidentCategory

    with session() as db:
        db.add(IncidentCategory(slug="typo", name="Added by mistake", sort_order=99))

    with session() as db:
        db.delete(db.get(IncidentCategory, "typo"))

    with session() as db:
        assert db.get(IncidentCategory, "typo") is None
