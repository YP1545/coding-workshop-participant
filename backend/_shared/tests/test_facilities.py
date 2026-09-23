"""
Buildings, floors and seats.

Part of: backend / tests.

Why its own file: the interesting behaviour here is what happens on delete. The
hierarchy protects itself — you cannot remove a building that still has floors —
and that has to surface as a useful 409 rather than a 500.
"""

import uuid


def test_creating_and_reading_a_building(admin):
    status, building = admin.post("facilities", "/buildings", {
        "name": f"HQ {uuid.uuid4().hex[:6]}", "address": "1 Innovation Way"})
    assert status == 201

    status, fetched = admin.get("facilities", f"/buildings/{building['id']}")
    assert status == 200
    assert fetched["name"] == building["name"]


def test_a_building_needs_a_name(admin):
    status, _ = admin.post("facilities", "/buildings", {"name": "   "})

    assert status == 400


def test_an_omitted_address_is_left_alone_and_null_clears_it(admin, facility):
    """
    The rule across the whole API: a field you do not send is unchanged.

    The alternative — treating "absent" as "clear it" — silently destroys data
    when a form sends only the fields somebody edited.
    """
    building = facility["building"]
    admin.put("facilities", f"/buildings/{building['id']}",
              {"name": building["name"], "address": "9 Test Way"})

    _, kept = admin.put("facilities", f"/buildings/{building['id']}", {"name": building["name"]})
    assert kept["address"] == "9 Test Way"

    _, cleared = admin.put("facilities", f"/buildings/{building['id']}",
                           {"name": building["name"], "address": None})
    assert cleared["address"] is None


def test_two_floors_in_one_building_cannot_share_a_name(admin, facility):
    status, _ = admin.post("facilities", f"/buildings/{facility['building']['id']}/floors",
                           {"name": facility["floor"]["name"]})

    assert status == 409


def test_a_floor_in_a_building_that_does_not_exist(admin):
    status, _ = admin.post("facilities", f"/buildings/{uuid.uuid4()}/floors", {"name": "L1"})

    assert status == 404


def test_two_seats_on_one_floor_cannot_share_a_label(admin, facility):
    status, _ = admin.post("facilities", f"/floors/{facility['floor']['id']}/seats",
                           {"label": facility["seat"]["label"]})

    assert status == 409


def test_a_building_with_floors_cannot_be_deleted(admin, facility):
    """
    409, not 500.

    PostgreSQL raises restrict_violation (SQLSTATE 23001) here, not
    foreign_key_violation — handling only the latter turned this into a 500.
    """
    status, error = admin.delete("facilities", f"/buildings/{facility['building']['id']}")

    assert status == 409
    assert "referenced" in error["detail"]


def test_a_floor_with_seats_cannot_be_deleted(admin, facility):
    status, _ = admin.delete("facilities", f"/floors/{facility['floor']['id']}")

    assert status == 409


def test_emptying_the_tree_from_the_bottom_works(admin, facility):
    """Seats, then floors, then the building — each step allowed once the one below is gone."""
    assert admin.delete("facilities", f"/seats/{facility['seat']['id']}")[0] == 204
    assert admin.delete("facilities", f"/floors/{facility['floor']['id']}")[0] == 204
    assert admin.delete("facilities", f"/buildings/{facility['building']['id']}")[0] == 204


def test_a_malformed_id_is_a_400_not_a_500(admin):
    """An id that is not a UUID is rejected before it reaches PostgreSQL."""
    status, _ = admin.get("facilities", "/buildings/not-a-uuid")

    assert status == 400
