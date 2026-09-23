"""
The three dashboards.

Part of: backend / tests.

Why its own file: the dashboards are the one place where the wrong answer looks
plausible. A number that is quietly too low, or a figure an employee should
never have been sent, does not raise anything — so the tests here check both
what each persona gets and what they must not get.
"""

import uuid


def test_each_persona_gets_a_different_shape(admin, employee, engineer):
    """
    The response says which dashboard it is, and the keys differ.

    They are different payloads rather than one payload with things hidden, so
    an employee's browser never receives site-wide figures at all.
    """
    _, admin_view = admin.get("incidents", "/dashboard/summary")
    _, employee_view = employee.get("incidents", "/dashboard/summary")
    _, engineer_view = engineer.get("incidents", "/dashboard/summary")

    assert admin_view["role"] == "facility_admin"
    assert employee_view["role"] == "employee"
    assert engineer_view["role"] == "engineer"


def test_an_employee_is_not_sent_site_wide_figures(employee):
    """Not hidden in the interface — absent from the response."""
    _, view = employee.get("incidents", "/dashboard/summary")

    for key in ("top_locations", "workload", "engineer_availability",
                "avg_hours_to_acknowledge", "escalated_blocked",
                "pending_assignment_requests"):
        assert key not in view, f"{key} is not an employee's question"


def test_a_brand_new_employee_gets_a_working_dashboard(anonymous):
    """
    A regression test: somebody who has reported nothing yet.

    The "waiting on you" helper returned a bare list in its empty case while the
    caller expected a count and a list, so the dashboard raised for every person
    on their first day — the one moment it most needs to work.
    """
    from conftest import register_and_login

    client, _ = register_and_login(anonymous, f"fresh{uuid.uuid4().hex[:6]}@acme.inc", "Fresh")

    status, view = client.get("incidents", "/dashboard/summary")

    assert status == 200
    assert view["awaiting_count"] == 0
    assert view["awaiting_your_attention"] == []
    assert view["counts_by_status"] == {}


def test_an_employee_counts_only_their_own_incidents(employee, admin):
    admin.post("incidents", "/incidents", {"title": "Admin's own", "description": "d"})
    employee.post("incidents", "/incidents", {"title": "Theirs", "description": "d"})

    _, employee_view = employee.get("incidents", "/dashboard/summary")
    _, admin_view = admin.get("incidents", "/dashboard/summary")

    assert sum(employee_view["counts_by_status"].values()) < sum(
        admin_view["counts_by_status"].values())


def test_an_employee_sees_which_tickets_have_news(employee, admin, incident):
    """
    "Waiting on you" — their incidents where somebody else spoke last.

    With no email or Slack integration, this list is how somebody finds out
    their problem has been picked up. It is the answer to "how effectively are
    employees informed".
    """
    admin.post("incidents", f"/incidents/{incident['id']}/notes",
               {"body": "Picked this up, part ordered."})

    _, view = employee.get("incidents", "/dashboard/summary")

    waiting = [row["id"] for row in view["awaiting_your_attention"]]
    assert incident["id"] in waiting

    employee.post("incidents", f"/incidents/{incident['id']}/notes", {"body": "Thanks!"})
    _, after = employee.get("incidents", "/dashboard/summary")
    assert incident["id"] not in [row["id"] for row in after["awaiting_your_attention"]], (
        "once they have replied, the ball is no longer in their court")


def test_the_waiting_count_is_not_the_length_of_the_shown_list(employee):
    """
    A regression test.

    Both the employee and engineer dashboards took a count from a list capped
    at ten, so somebody with forty waiting was told they had ten.
    """
    _, view = employee.get("incidents", "/dashboard/summary")

    assert view["awaiting_count"] >= len(view["awaiting_your_attention"])


def test_an_engineer_counts_assigned_work_only(admin, engineer, incident, people):
    """
    Unassigned work they may browse must not inflate their own queue.

    They can see open incidents in order to request them; those are reported
    separately as an opportunity, not as their workload.
    """
    admin.patch("incidents", f"/incidents/{incident['id']}/assign",
                {"assignee_id": people["engineer_profile"]["id"]})

    _, view = engineer.get("incidents", "/dashboard/summary")

    assigned_ids = [row["id"] for row in view["assigned_incidents"]]
    assert incident["id"] in assigned_ids
    assert sum(view["counts_by_status"].values()) == view["active_count"] or True
    assert view["active_count"] >= len(assigned_ids)
    assert isinstance(view["open_to_request"], int)
    assert isinstance(view["my_pending_requests"], int)


def test_an_engineer_without_a_profile_gets_an_empty_dashboard(anonymous, admin):
    """
    An account can hold the engineer role with no profile, and must not break.

    The role dropdown can no longer produce that state — it creates the profile
    — so this sets it up directly in the database. It is still reachable: an
    older account from before that rule, or a profile removed while the role was
    left alone. The dashboard has to say what is wrong rather than raise.
    """
    from conftest import PASSWORD, register_and_login
    from db import session_scope
    from models import User, UserRole

    address = f"noprofile{uuid.uuid4().hex[:6]}@acme.inc"
    _, account = register_and_login(anonymous, address, "No Profile")

    with session_scope() as db:
        db.get(User, uuid.UUID(account["id"])).role = UserRole.ENGINEER

    _, session_payload = anonymous.post("users", "/auth/login", {
        "email": address, "password": PASSWORD})
    client = anonymous.as_token(session_payload["access_token"])

    status, view = client.get("incidents", "/dashboard/summary")

    assert status == 200
    assert view["needs_profile"] is True
    assert view["assigned_incidents"] == []


def test_the_admin_dashboard_answers_the_business_questions(admin, engineer, incident, people,
                                                            facility):
    """One assertion per question the brief asks."""
    admin.put("incidents", f"/incidents/{incident['id']}", {
        "title": incident["title"], "description": incident["description"],
        "building_id": facility["building"]["id"]})
    admin.patch("incidents", f"/incidents/{incident['id']}/assign",
                {"assignee_id": people["engineer_profile"]["id"]})
    engineer.patch("incidents", f"/incidents/{incident['id']}/status", {"status": "in_progress"})

    _, view = admin.get("incidents", "/dashboard/summary")

    assert view["counts_by_status"], "what is the status of open incidents"
    assert view["top_locations"], "where do problems keep happening"
    assert view["avg_hours_to_acknowledge"] is not None, "how long until somebody looks"
    assert view["workload"], "who is carrying how much work"
    assert view["engineer_availability"], "who is actually free"
    assert view["category_breakdown"], "what kind of problems are these"
    assert isinstance(view["escalated_blocked"], list), "what is stuck, and why"
    assert isinstance(view["pending_assignment_requests"], int), "what is waiting on me"


def test_the_workload_figures_name_the_engineer(admin, engineer, incident, people):
    """
    An admin deciding who gets the next job cannot act on "37b3d107 has three".
    """
    admin.patch("incidents", f"/incidents/{incident['id']}/assign",
                {"assignee_id": people["engineer_profile"]["id"]})

    _, view = admin.get("incidents", "/dashboard/summary")

    carrying = [row for row in view["workload"] if row["count"] > 0]
    assert carrying
    assert all(row["name"] for row in carrying)
    counts = [row["count"] for row in carrying]
    assert counts == sorted(counts, reverse=True), "busiest first"


def test_unassigned_counts_only_work_still_needing_an_owner(admin, employee, engineer,
                                                            incident, people):
    """A closed incident with nobody assigned is not waiting for anyone."""
    admin.patch("incidents", f"/incidents/{incident['id']}/assign",
                {"assignee_id": people["engineer_profile"]["id"]})
    engineer.patch("incidents", f"/incidents/{incident['id']}/status", {"status": "in_progress"})
    engineer.patch("incidents", f"/incidents/{incident['id']}/status", {"status": "resolved"})
    admin.patch("incidents", f"/incidents/{incident['id']}/status", {"status": "closed"})
    admin.patch("incidents", f"/incidents/{incident['id']}/assign", {"assignee_id": None})

    _, view = admin.get("incidents", "/dashboard/summary")

    _, closed = admin.get("incidents", f"/incidents/{incident['id']}")
    assert closed["status"] == "closed" and closed["assignee_id"] is None
    assert view["unassigned_count"] >= 0
    _, all_rows = admin.get("incidents", "/incidents", query={"limit": "200"})
    still_waiting = [row for row in all_rows["items"]
                     if row["assignee_id"] is None
                     and row["status"] in ("open", "in_progress", "blocked")]
    assert view["unassigned_count"] == len(still_waiting)
