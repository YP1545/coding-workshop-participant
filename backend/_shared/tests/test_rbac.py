"""
Who is allowed to do what.

Part of: backend / tests.

Why its own file: role checks fail silently. A missing one does not raise — the
request just succeeds for somebody who should have been refused. So every rule
gets an explicit negative test here, and the matrix at the bottom covers each
admin-only endpoint against each role that is not an admin.
"""

import pytest

# Endpoints only a facility admin may reach, as (service, method, path, body).
ADMIN_ONLY = [
    ("users", "GET", "/users", None),
    ("facilities", "POST", "/buildings", {"name": "Sneaky Tower"}),
    ("engineers", "POST", "/engineers", {"email": "new@acme.inc", "full_name": "New"}),
    ("incidents", "GET", "/assignment-requests", None),
]


@pytest.mark.parametrize("service,method,path,body", ADMIN_ONLY)
@pytest.mark.parametrize("persona", ["employee", "engineer"])
def test_admin_only_endpoints_refuse_everyone_else(request, persona, service, method, path, body):
    client = request.getfixturevalue(persona)

    status, _ = client.call(service, method, path, body)

    assert status == 403


@pytest.mark.parametrize("service,method,path,body", ADMIN_ONLY)
def test_admin_only_endpoints_refuse_anonymous_callers(anonymous, service, method, path, body):
    """401, not 403: the caller is not refused, they are unidentified."""
    status, _ = anonymous.call(service, method, path, body)

    assert status == 401


def test_anyone_signed_in_can_read_the_facility_tree(employee, engineer, facility):
    """An employee reporting a fault has to be able to pick their building."""
    for client in (employee, engineer):
        status, buildings = client.get("facilities", "/buildings")
        assert status == 200
        assert any(row["id"] == facility["building"]["id"] for row in buildings)


def test_an_employee_sees_only_their_own_incidents(employee, admin, incident):
    """Scoping is a WHERE clause, so the rows never leave the database."""
    admin.post("incidents", "/incidents", {"title": "Admin's own", "description": "d"})

    status, page = employee.get("incidents", "/incidents")

    assert status == 200
    assert all(row["reporter_id"] == incident["reporter_id"] for row in page["items"])


def test_a_filter_cannot_widen_what_an_employee_sees(employee, admin, people):
    """
    Asking for somebody else's incidents returns nothing, not everything.

    The scope is applied first and the filters narrow it further, so a crafted
    query string can only ever subtract.
    """
    admin.post("incidents", "/incidents", {"title": "Admin's own", "description": "d"})

    status, page = employee.get(
        "incidents", "/incidents", query={"reporter_id": people["admin_user"]["id"]})

    assert status == 200
    assert page["items"] == []
    assert page["total"] == 0


def test_another_persons_incident_is_reported_as_missing(employee, admin):
    """
    404 rather than 403.

    A 403 would confirm that an incident with that id exists, which is itself
    something an outsider should not be able to discover by guessing.
    """
    _, hidden = admin.post("incidents", "/incidents", {"title": "Private", "description": "d"})

    status, _ = employee.get("incidents", f"/incidents/{hidden['id']}")

    assert status == 404


def test_an_employee_cannot_delete_even_their_own_incident(employee, incident):
    """Deleting is an admin action: the record outlives the reporter's interest in it."""
    status, _ = employee.delete("incidents", f"/incidents/{incident['id']}")

    assert status == 403


def test_an_admin_cannot_change_their_own_role(admin, people):
    """
    Otherwise the last admin could demote themselves and lock everybody out of
    facility management, with no way back in through the API.
    """
    status, _ = admin.patch(
        "users", f"/users/{people['admin_user']['id']}/role", {"role": "employee"})

    assert status == 403


def test_an_engineer_can_only_change_their_own_availability(engineer, admin, people):
    """
    Two rules in one endpoint: not someone else's profile, and not the specialty.

    What somebody is qualified for is a management decision, so it stays with
    the admin even on the engineer's own profile.
    """
    own = people["engineer_profile"]["id"]

    status, _ = engineer.put("engineers", f"/engineers/{own}", {"availability": "busy"})
    assert status == 200

    status, _ = engineer.put("engineers", f"/engineers/{own}", {"specialty": "anything I like"})
    assert status == 403
