"""
Keeping the engineer rota in step with people's roles.

Part of: backend / tests.

Why its own file: the role and the engineer profile are two different records,
and the interesting behaviour is how they stay consistent. Promoting somebody
has to put them on the rota; demoting them has to take them off it — without
destroying the record of what they worked on, which is what deleting the
profile would do.
"""

import uuid

import pytest


@pytest.fixture
def newcomer(anonymous, admin):
    """Somebody who registered themselves, as an employee."""
    from conftest import register_and_login

    client, account = register_and_login(
        anonymous, f"newcomer{uuid.uuid4().hex[:6]}@acme.inc", "New Comer")
    return {"client": client, "account": account}


def roster_ids(admin):
    """The engineer profiles the rota currently lists."""
    _, engineers = admin.get("engineers", "/engineers")
    return {row["user_id"] for row in engineers}


def test_promoting_puts_them_on_the_rota(admin, newcomer):
    """
    The role dropdown is the only control, so it has to do the whole job.

    Changing the role alone would leave them holding the title with no profile,
    which means no incident could ever be assigned to them.
    """
    person = newcomer["account"]
    assert person["id"] not in roster_ids(admin)

    status, updated = admin.patch("users", f"/users/{person['id']}/role", {"role": "engineer"})

    assert status == 200
    assert updated["role"] == "engineer"
    assert person["id"] in roster_ids(admin)


def test_demoting_takes_them_off_the_rota(admin, newcomer):
    """The symptom this was written for: they stayed visible after demotion."""
    person = newcomer["account"]
    admin.patch("users", f"/users/{person['id']}/role", {"role": "engineer"})
    assert person["id"] in roster_ids(admin)

    admin.patch("users", f"/users/{person['id']}/role", {"role": "employee"})

    assert person["id"] not in roster_ids(admin)


def test_demoting_keeps_the_record_of_what_they_fixed(admin, employee, newcomer, incident):
    """
    The reason demotion hides rather than deletes.

    incidents.assignee_id points at the profile with ON DELETE SET NULL, so
    deleting it on demotion would erase who resolved every incident they ever
    closed — a routine admin action quietly destroying history.
    """
    person = newcomer["account"]
    admin.patch("users", f"/users/{person['id']}/role", {"role": "engineer"})
    _, roster = admin.get("engineers", "/engineers")
    profile_id = next(row["id"] for row in roster if row["user_id"] == person["id"])

    admin.patch("incidents", f"/incidents/{incident['id']}/assign", {"assignee_id": profile_id})
    admin.patch("users", f"/users/{person['id']}/role", {"role": "employee"})

    _, after = admin.get("incidents", f"/incidents/{incident['id']}")
    assert after["assignee_id"] == profile_id, "their past work still shows who had it"


def test_re_promoting_brings_back_the_same_profile(admin, newcomer):
    """Their specialty and availability survive a demotion, rather than being retyped."""
    person = newcomer["account"]
    admin.patch("users", f"/users/{person['id']}/role", {"role": "engineer"})

    _, roster = admin.get("engineers", "/engineers")
    profile = next(row for row in roster if row["user_id"] == person["id"])
    admin.put("engineers", f"/engineers/{profile['id']}", {"specialty": "Lifts and access"})

    admin.patch("users", f"/users/{person['id']}/role", {"role": "employee"})
    admin.patch("users", f"/users/{person['id']}/role", {"role": "engineer"})

    _, roster_again = admin.get("engineers", "/engineers")
    restored = next(row for row in roster_again if row["user_id"] == person["id"])
    assert restored["id"] == profile["id"], "the same profile, not a new one"
    assert restored["specialty"] == "Lifts and access"


def test_work_cannot_be_given_to_somebody_who_is_no_longer_an_engineer(
        admin, newcomer, incident):
    """
    The profile still exists, so its existence is not enough to justify an
    assignment — the role has to be checked too.
    """
    person = newcomer["account"]
    admin.patch("users", f"/users/{person['id']}/role", {"role": "engineer"})
    _, roster = admin.get("engineers", "/engineers")
    profile_id = next(row["id"] for row in roster if row["user_id"] == person["id"])

    admin.patch("users", f"/users/{person['id']}/role", {"role": "employee"})

    status, error = admin.patch("incidents", f"/incidents/{incident['id']}/assign",
                                {"assignee_id": profile_id})

    assert status == 409
    assert "no longer an engineer" in error["detail"]


def test_promoting_twice_does_not_create_a_second_profile(admin, newcomer):
    person = newcomer["account"]
    admin.patch("users", f"/users/{person['id']}/role", {"role": "engineer"})
    admin.patch("users", f"/users/{person['id']}/role", {"role": "facility_admin"})
    admin.patch("users", f"/users/{person['id']}/role", {"role": "engineer"})

    _, roster = admin.get("engineers", "/engineers")
    theirs = [row for row in roster if row["user_id"] == person["id"]]

    assert len(theirs) == 1
