"""
The status state machine, escalation, and the assignment-request flow.

Part of: backend / tests.

Why its own file: these are the product's rules rather than its plumbing, and
most of them are prohibitions — you cannot skip to resolved, you cannot block
without saying why, you cannot approve two engineers onto one job. A state
machine with a missing guard does not crash; it just lets the wrong thing
happen and records it as if it were fine.
"""

import uuid

import pytest


@pytest.fixture
def assigned(admin, incident, people):
    """An incident assigned to the engineer, ready to be worked on."""
    status, updated = admin.patch("incidents", f"/incidents/{incident['id']}/assign",
                                  {"assignee_id": people["engineer_profile"]["id"]})
    assert status == 200
    return updated


def status_path(incident):
    return f"/incidents/{incident['id']}/status"


def test_assigning_stamps_the_time(assigned):
    assert assigned["assigned_at"] is not None
    assert assigned["assignee_id"] is not None


def test_work_cannot_skip_straight_to_resolved(admin, incident):
    """Somebody has to start before anybody can finish."""
    status, error = admin.patch("incidents", status_path(incident), {"status": "resolved"})

    assert status == 400
    assert "in_progress" in error["detail"]


def test_moving_to_the_status_it_is_already_in_is_refused(admin, incident):
    status, _ = admin.patch("incidents", status_path(incident), {"status": "open"})

    assert status == 400


def test_a_status_that_does_not_exist_is_refused(admin, incident):
    status, _ = admin.patch("incidents", status_path(incident), {"status": "sideways"})

    assert status == 400


def test_blocking_requires_a_reason(admin, assigned, incident):
    """The brief asks specifically why something is blocked, so it is required."""
    admin.patch("incidents", status_path(incident), {"status": "in_progress"})

    status, _ = admin.patch("incidents", status_path(incident), {"status": "blocked"})

    assert status == 400


def test_the_reporter_cannot_move_their_own_incident(employee, assigned, incident):
    """They report and comment; the person doing the work says where it has got to."""
    status, _ = employee.patch("incidents", status_path(incident), {"status": "in_progress"})

    assert status == 403


def test_an_engineer_who_is_not_assigned_cannot_move_it(engineer, incident):
    status, _ = engineer.patch("incidents", status_path(incident), {"status": "in_progress"})

    assert status == 403


def test_the_full_journey_records_everything(admin, engineer, assigned, incident, services):
    """
    Open to closed, one step at a time, checking what each step records.

    The history table is what turns the dashboard's timing figures into
    measurements rather than guesses, so every move must leave a row.
    """
    _, started = engineer.patch("incidents", status_path(incident), {"status": "in_progress"})
    assert started["acknowledged_at"] is not None
    first_acknowledged = started["acknowledged_at"]

    _, blocked = engineer.patch("incidents", status_path(incident), {
        "status": "blocked", "blocked_reason": "Waiting on a part"})
    assert blocked["blocked_reason"] == "Waiting on a part"

    _, unblocked = engineer.patch("incidents", status_path(incident), {"status": "in_progress"})
    assert unblocked["blocked_reason"] is None, "a stale reason would mislead"
    assert unblocked["acknowledged_at"] == first_acknowledged, (
        "acknowledged_at must not move, or time-to-acknowledge drifts later "
        "every time work restarts")

    _, resolved = engineer.patch("incidents", status_path(incident), {"status": "resolved"})
    assert resolved["resolved_at"] is not None

    _, closed = admin.patch("incidents", status_path(incident), {"status": "closed"})
    assert closed["closed_at"] is not None

    from sqlalchemy import select

    from db import session_scope
    from models import IncidentStatusHistory

    with session_scope() as session:
        rows = session.scalars(
            select(IncidentStatusHistory)
            .where(IncidentStatusHistory.incident_id == uuid.UUID(incident["id"]))
            .order_by(IncidentStatusHistory.changed_at)).all()
        trail = [(row.from_status.value if row.from_status else None, row.to_status.value)
                 for row in rows]

    assert trail == [
        (None, "open"), ("open", "in_progress"), ("in_progress", "blocked"),
        ("blocked", "in_progress"), ("in_progress", "resolved"), ("resolved", "closed"),
    ]


def test_a_closed_incident_cannot_be_reopened(admin, engineer, assigned, incident):
    """
    Closed is the end of the line. Reopening would blur the resolution times
    the dashboard reports; a new problem gets a new incident.
    """
    engineer.patch("incidents", status_path(incident), {"status": "in_progress"})
    engineer.patch("incidents", status_path(incident), {"status": "resolved"})
    admin.patch("incidents", status_path(incident), {"status": "closed"})

    status, _ = admin.patch("incidents", status_path(incident), {"status": "in_progress"})

    assert status == 400


def test_escalation_is_requested_by_the_reporter_and_confirmed_by_an_admin(
        employee, admin, incident):
    """Two jobs on one endpoint, split by role, so the escalated list keeps meaning something."""
    path = f"/incidents/{incident['id']}/escalate"

    assert employee.patch("incidents", path, {"escalation_requested": True})[0] == 400, (
        "a reason is required — 'why' is the useful part")

    status, requested = employee.patch("incidents", path, {
        "escalation_requested": True, "escalation_reason": "Third day with no heating"})
    assert status == 200
    assert requested["escalated"] is False, "asking is not the same as it being escalated"

    assert employee.patch("incidents", path, {"escalated": True})[0] == 403

    status, escalated = admin.patch("incidents", path, {"escalated": True})
    assert status == 200
    assert escalated["escalation_reason"] == "Third day with no heating"


def test_an_engineer_asks_for_work_and_an_admin_decides(admin, engineer, incident, people):
    """The whole request flow, including what approving does to everything else."""
    path = f"/incidents/{incident['id']}/assignment-requests"

    status, asked = engineer.post("incidents", path)
    assert status == 201
    assert asked["engineer_name"], "an admin choosing between requests needs a name, not an id"
    assert asked["incident"]["title"] == incident["title"]

    assert engineer.post("incidents", path)[0] == 409, "asking twice is a conflict"

    status, decided = admin.patch("incidents", f"/assignment-requests/{asked['id']}",
                                  {"status": "approved"})
    assert status == 200

    _, after = admin.get("incidents", f"/incidents/{incident['id']}")
    assert after["assignee_id"] == people["engineer_profile"]["id"]

    assert admin.patch("incidents", f"/assignment-requests/{asked['id']}",
                       {"status": "denied"})[0] == 409, "a decision cannot be taken twice"


def test_approving_one_request_denies_the_others(admin, engineer, anonymous, incident, services):
    """
    Once the job has an owner, everybody else who asked must be told.

    Leaving them pending would keep showing engineers work that is no longer
    available.
    """
    import uuid as uuid_module

    suffix = uuid_module.uuid4().hex[:6]
    from conftest import PASSWORD, register_and_login

    second_client, second_user = register_and_login(
        anonymous, f"eng2{suffix}@acme.inc", "Second Engineer")
    _, second_profile = admin.post("engineers", "/engineers", {"user_id": second_user["id"]})
    _, session_payload = anonymous.post("users", "/auth/login", {
        "email": f"eng2{suffix}@acme.inc", "password": PASSWORD})
    second_client = anonymous.as_token(session_payload["access_token"])

    path = f"/incidents/{incident['id']}/assignment-requests"
    _, first_request = engineer.post("incidents", path)
    _, second_request = second_client.post("incidents", path)

    admin.patch("incidents", f"/assignment-requests/{first_request['id']}", {"status": "approved"})

    _, requests = admin.get("incidents", path)
    outcomes = {row["id"]: row["status"] for row in requests}
    assert outcomes[first_request["id"]] == "approved"
    assert outcomes[second_request["id"]] == "denied"


def test_an_employee_cannot_ask_for_work(employee, incident):
    status, _ = employee.post("incidents", f"/incidents/{incident['id']}/assignment-requests")

    assert status == 403


def test_an_engineer_sees_only_their_own_request_on_an_incident(engineer, admin, incident):
    """Who else wants the job is the admin's business, not theirs."""
    engineer.post("incidents", f"/incidents/{incident['id']}/assignment-requests")

    _, theirs = engineer.get("incidents", f"/incidents/{incident['id']}/assignment-requests")

    assert len(theirs) == 1
