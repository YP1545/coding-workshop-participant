"""
Reporting incidents, editing them, and the note thread.

Part of: backend / tests.

Why its own file: this is the product's core write path, and the rules that
matter most are about what a client may not set — the reporter, the status, the
assignee. Each of those is a way to put a false statement into the record.
"""

import uuid


def test_reporting_an_incident(employee, people):
    status, reported = employee.post("incidents", "/incidents", {
        "title": "Broken chair", "description": "The gas lift has given up.",
        "category": "furniture", "priority": "low"})

    assert status == 201
    assert reported["status"] == "open"
    assert reported["reporter_id"] == people["employee_user"]["id"]


def test_the_reporter_cannot_be_chosen_by_the_client(employee, people):
    """
    Sending reporter_id is a 400.

    While it was a request field, anybody could file a ticket in somebody
    else's name.
    """
    status, _ = employee.post("incidents", "/incidents", {
        "title": "Spoofed", "description": "d",
        "reporter_id": people["admin_user"]["id"]})

    assert status == 400


def test_the_status_cannot_be_chosen_at_creation(employee):
    """Otherwise an incident could arrive already resolved, with no history."""
    status, _ = employee.post("incidents", "/incidents", {
        "title": "Pre-resolved", "description": "d", "status": "resolved"})

    assert status == 400


def test_the_assignee_cannot_be_set_through_the_edit_endpoint(employee, incident, people):
    """
    Assignment has its own endpoint, which stamps assigned_at and clears the
    pending requests. Allowing it here would skip all of that.
    """
    status, _ = employee.put("incidents", f"/incidents/{incident['id']}", {
        "title": "t", "description": "d",
        "assignee_id": people["engineer_profile"]["id"]})

    assert status == 400


def test_a_title_and_description_are_required(employee):
    status, _ = employee.post("incidents", "/incidents", {"description": "no title"})

    assert status == 400


def test_a_very_long_title_is_refused(employee):
    """Unbounded text is a way to push megabytes into the database."""
    status, _ = employee.post("incidents", "/incidents", {
        "title": "x" * 500, "description": "d"})

    assert status == 400


def test_a_location_that_does_not_exist_is_a_404(employee):
    """Named at the field that caused it, rather than a generic conflict."""
    status, error = employee.post("incidents", "/incidents", {
        "title": "Nowhere", "description": "d", "building_id": str(uuid.uuid4())})

    assert status == 404
    assert "Building" in error["detail"]


def test_editing_leaves_untouched_fields_alone(employee, incident, facility):
    """
    A regression test.

    Editing once wiped the location whenever the form did not resend it, while
    keeping the category — two different rules for omitted fields in one
    endpoint, and the destructive one was silent.
    """
    employee.put("incidents", f"/incidents/{incident['id']}", {
        "title": incident["title"], "description": incident["description"],
        "building_id": facility["building"]["id"]})

    _, renamed = employee.put("incidents", f"/incidents/{incident['id']}", {
        "title": "Renamed", "description": incident["description"]})

    assert renamed["building_id"] == facility["building"]["id"]
    assert renamed["category"] == incident["category"]


def test_filters_are_applied(employee):
    employee.post("incidents", "/incidents", {
        "title": "Network fault", "description": "d", "category": "network", "priority": "urgent"})

    status, page = employee.get("incidents", "/incidents",
                                query={"category": "network", "priority": "urgent"})

    assert status == 200
    assert page["items"]
    assert all(row["category"] == "network" and row["priority"] == "urgent"
               for row in page["items"])


def test_a_filter_value_that_is_not_allowed_is_a_400(employee):
    """
    A value that is not a real option is refused rather than guessed at.

    "0" is accepted and means False — FastAPI parses the usual boolean spellings
    and never guesses, which is the behaviour that matters. A word that is not a
    boolean at all, a status that does not exist, and a negative page size are
    all rejected.
    """
    status, page = employee.get("incidents", "/incidents", query={"escalated": "0"})
    assert status == 200
    assert all(row["escalated"] is False for row in page["items"])

    assert employee.get("incidents", "/incidents", query={"escalated": "maybe"})[0] == 400
    assert employee.get("incidents", "/incidents", query={"status": "sideways"})[0] == 400
    assert employee.get("incidents", "/incidents", query={"limit": "-1"})[0] == 400


def test_the_page_size_is_capped(employee):
    """
    Asking for more than the cap is refused, not quietly trimmed.

    Without a cap, "?limit=1000000" is a free table scan. FastAPI enforces the
    bound declared on the query parameter and answers 400, which tells a client
    its request was wrong rather than silently returning something else.
    """
    assert employee.get("incidents", "/incidents", query={"limit": "999999"})[0] == 400

    status, page = employee.get("incidents", "/incidents", query={"limit": "200"})
    assert status == 200
    assert len(page["items"]) <= 200


def test_a_note_is_attributed_to_the_caller(employee, incident, people):
    status, note = employee.post("incidents", f"/incidents/{incident['id']}/notes",
                                 {"body": "Still not fixed."})

    assert status == 201
    assert note["author_id"] == people["employee_user"]["id"]


def test_the_note_author_cannot_be_chosen(employee, incident, people):
    """A thread where anybody can sign anybody's name is worthless as a record."""
    status, _ = employee.post("incidents", f"/incidents/{incident['id']}/notes",
                              {"body": "x", "author_id": people["admin_user"]["id"]})

    assert status == 400


def test_notes_read_oldest_first(employee, incident):
    employee.post("incidents", f"/incidents/{incident['id']}/notes", {"body": "First"})
    employee.post("incidents", f"/incidents/{incident['id']}/notes", {"body": "Second"})

    status, notes = employee.get("incidents", f"/incidents/{incident['id']}/notes")

    assert status == 200
    assert [note["body"] for note in notes] == ["First", "Second"]


def test_an_engineer_may_read_unassigned_work_but_not_comment_on_it(engineer, incident):
    """
    Reading and writing are different questions.

    An engineer browsing open work needs to read it to decide whether to ask
    for it. The thread belongs to the reporter, the assigned engineer and the
    admins — otherwise every engineer could chime in on every job in the site.
    """
    assert engineer.get("incidents", f"/incidents/{incident['id']}")[0] == 200

    status, _ = engineer.post("incidents", f"/incidents/{incident['id']}/notes",
                              {"body": "butting in"})

    assert status == 403


def test_an_assigned_engineer_can_comment(admin, engineer, incident, people):
    admin.patch("incidents", f"/incidents/{incident['id']}/assign",
                {"assignee_id": people["engineer_profile"]["id"]})

    status, _ = engineer.post("incidents", f"/incidents/{incident['id']}/notes",
                              {"body": "On my way."})

    assert status == 201


# --- Categories -------------------------------------------------------------


def test_the_category_list_comes_from_the_database(employee):
    """The nine seeded categories are returned in dropdown order."""
    status, categories = employee.get("incidents", "/categories")

    assert status == 200
    slugs = [row["slug"] for row in categories]
    assert "hvac" in slugs and "other" in slugs
    # sort_order, not alphabetical — the list is arranged, not sorted.
    orders = [row["sort_order"] for row in categories]
    assert orders == sorted(orders)


def test_an_unknown_category_is_a_400_that_says_what_is_allowed(employee):
    """
    The allowed values live in a table now, so Pydantic cannot check them.
    Without the handler's lookup this would fail on the foreign key and surface
    as a vague 409 about "a referenced record" — useless to a caller.
    """
    status, body = employee.post(
        "incidents", "/incidents",
        {"title": "Filed under nonsense", "description": "Body.",
         "category": "not_a_category", "priority": "low"},
    )

    assert status == 400
    assert "not_a_category" in body["detail"]
    assert "hvac" in body["detail"], "the message should name what is allowed"


def test_a_category_added_to_the_table_is_immediately_usable(services, employee):
    """
    This is the reason the enum became a table: inserting a row is all it takes.

    No migration, no redeploy — the category can be listed, filed under, and
    filtered by as soon as it exists. This test inserts the row the way a
    facility admin would, straight into the table, and then uses the API.
    """
    from db import session_scope
    from models import IncidentCategory

    with session_scope() as db:
        db.add(IncidentCategory(slug="grounds", name="Grounds and landscaping", sort_order=95))

    listed, categories = employee.get("incidents", "/categories")
    assert listed == 200
    assert "grounds" in [row["slug"] for row in categories]

    created, incident = employee.post(
        "incidents", "/incidents",
        {"title": "Hedge blocking the fire door", "description": "Body.",
         "category": "grounds", "priority": "high"},
    )
    assert created == 201, incident
    assert incident["category"] == "grounds"

    found, page = employee.get("incidents", "/incidents", query={"category": "grounds"})
    assert found == 200
    assert page["total"] == 1

