"""
Searching incidents, and reading them a page at a time.

Part of: backend / tests.

Why its own file: paging is easy to get subtly wrong — a total that counts the
page instead of the match, a search that leaks past the caller's own incidents,
a wildcard character in the box behaving as a wildcard. Each of those is tested
here rather than assumed.
"""

import pytest


@pytest.fixture
def many_incidents(employee):
    """Twenty-five incidents, more than two pages of ten."""
    titles = []
    for number in range(25):
        title = f"Paged incident {number:02d}"
        employee.post("incidents", "/incidents", {"title": title, "description": "for paging"})
        titles.append(title)
    return titles


def test_a_page_reports_the_full_total(employee, many_incidents):
    """
    The total is how many match, not how many are on this page.

    Without that the frontend cannot say "page 1 of 3", and a count taken from
    the page length would always read 10.
    """
    status, page = employee.get("incidents", "/incidents", query={"limit": "10", "offset": "0"})

    assert status == 200
    assert len(page["items"]) == 10
    assert page["total"] >= 25
    assert page["limit"] == 10
    assert page["offset"] == 0


def test_the_pages_do_not_overlap(employee, many_incidents):
    _, first = employee.get("incidents", "/incidents", query={"limit": "10", "offset": "0"})
    _, second = employee.get("incidents", "/incidents", query={"limit": "10", "offset": "10"})

    first_ids = {row["id"] for row in first["items"]}
    second_ids = {row["id"] for row in second["items"]}

    assert first_ids and second_ids
    assert first_ids.isdisjoint(second_ids)


def test_reading_past_the_end_gives_an_empty_page_not_an_error(employee, many_incidents):
    status, page = employee.get("incidents", "/incidents",
                                query={"limit": "10", "offset": "10000"})

    assert status == 200
    assert page["items"] == []
    assert page["total"] >= 25, "the total still describes the whole match"


def test_search_matches_the_title(employee):
    employee.post("incidents", "/incidents", {
        "title": "Kettle in the third floor kitchen is dead", "description": "No power light."})

    status, page = employee.get("incidents", "/incidents", query={"search": "kettle"})

    assert status == 200
    assert page["total"] >= 1
    assert all("kettle" in row["title"].lower() or "kettle" in row["description"].lower()
               for row in page["items"])


def test_search_matches_the_description_too(employee):
    """Somebody searching for a symptom will not have used the words in the title."""
    employee.post("incidents", "/incidents", {
        "title": "Odd noise near reception", "description": "A high pitched whine from the vent."})

    _, page = employee.get("incidents", "/incidents", query={"search": "high pitched whine"})

    assert page["total"] >= 1


def test_search_ignores_case(employee):
    employee.post("incidents", "/incidents", {
        "title": "Projector bulb blown", "description": "Meeting room 2."})

    _, lower = employee.get("incidents", "/incidents", query={"search": "projector"})
    _, upper = employee.get("incidents", "/incidents", query={"search": "PROJECTOR"})

    assert lower["total"] == upper["total"] >= 1


def test_search_narrows_rather_than_widens(employee, admin):
    """
    A search cannot reach another person's incidents.

    The caller's scope is applied first and the search adds to it, so the box
    can only ever subtract from what they were already allowed to see.
    """
    admin.post("incidents", "/incidents", {
        "title": "Admin's own secret kettle", "description": "Not visible to the employee."})

    _, page = employee.get("incidents", "/incidents", query={"search": "secret kettle"})

    assert page["items"] == []
    assert page["total"] == 0


def test_search_works_alongside_the_filters(employee):
    employee.post("incidents", "/incidents", {
        "title": "Radiator cold in the annex", "description": "Nothing coming through.",
        "category": "hvac", "priority": "high"})
    employee.post("incidents", "/incidents", {
        "title": "Radiator valve missing a cap", "description": "Cosmetic only.",
        "category": "hvac", "priority": "low"})

    _, page = employee.get("incidents", "/incidents",
                           query={"search": "radiator", "priority": "high"})

    assert page["total"] == 1
    assert page["items"][0]["priority"] == "high"


def test_a_wildcard_in_the_search_box_is_treated_as_text(employee):
    """
    "%" means "anything" inside LIKE.

    Unescaped, a search for "%" would match every incident the caller can see —
    the opposite of narrowing — so the characters are escaped before use.
    """
    employee.post("incidents", "/incidents", {
        "title": "Humidity at 90% in the server room", "description": "Too damp."})

    _, everything = employee.get("incidents", "/incidents")
    _, literal = employee.get("incidents", "/incidents", query={"search": "90%"})
    _, wildcard = employee.get("incidents", "/incidents", query={"search": "%"})

    assert literal["total"] >= 1, "a percent sign in a real title is still findable"
    assert wildcard["total"] < everything["total"], (
        "unescaped, '%' would match every incident the caller can see — the "
        "opposite of narrowing")
    assert wildcard["total"] == literal["total"], (
        "'%' matches exactly the incidents containing a literal percent sign")


def test_a_search_that_matches_nothing_is_an_empty_page(employee):
    _, page = employee.get("incidents", "/incidents",
                           query={"search": "something nobody ever reported"})

    assert page["items"] == []
    assert page["total"] == 0


def test_an_over_long_search_term_is_refused(employee):
    status, _ = employee.get("incidents", "/incidents", query={"search": "x" * 500})

    assert status == 400


def create_incident(client, title):
    """Report an incident and return the payload the API sent back."""
    status, body = client.post(
        "incidents", "/incidents",
        {"title": title, "description": "Body.", "category": "other", "priority": "low"},
    )
    assert status == 201, body
    return body


def test_new_incidents_get_a_reference_from_the_database(employee):
    """
    Every incident gets a number, nobody chooses it, and nobody repeats it.

    The application never sets this field — the database default does — so two
    Lambdas inserting at the same moment cannot land on the same number.
    """
    references = [create_incident(employee, f"Numbered {n}")["reference"] for n in range(3)]

    assert all(reference.startswith("INC-") for reference in references)
    assert len(set(references)) == 3, "references must be unique"


def test_a_client_cannot_choose_its_own_reference(employee):
    """
    reference is on the way out only. Request models forbid unknown fields, so
    asking for a number is a 400 rather than something quietly ignored — which
    is what stops somebody claiming an existing incident's number.
    """
    status, _ = employee.post(
        "incidents", "/incidents",
        {"title": "Picking a number", "description": "Body.", "category": "other",
         "priority": "low", "reference": "INC-0001"},
    )
    assert status == 400


def test_searching_by_ticket_number_finds_exactly_that_incident(employee):
    """Somebody reads a number off a screen and types it into the box."""
    created = create_incident(employee, "Findable by number")

    status, page = employee.get(
        "incidents", "/incidents", query={"search": created["reference"]})

    assert status == 200
    assert page["total"] == 1
    assert page["items"][0]["reference"] == created["reference"]


def test_searching_by_the_digits_alone_also_finds_it(employee):
    """
    "42" should find INC-0042. Somebody reading a number aloud will not
    necessarily say the prefix, and demanding it would make the search feel
    broken for the most obvious thing anyone types into it.
    """
    created = create_incident(employee, "Findable by digits")
    digits = created["reference"].removeprefix("INC-").lstrip("0")

    status, page = employee.get("incidents", "/incidents", query={"search": digits})

    assert status == 200
    assert any(item["reference"] == created["reference"] for item in page["items"])
