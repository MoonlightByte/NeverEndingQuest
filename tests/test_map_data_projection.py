import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from web.map_projection import (
    project_map_payload,
    derive_revealed,
    resolve_area_path,
)


FORBIDDEN_KEYS = {
    "description",
    "encounters",
    "dmInstructions",
    "doors",
    "adventureSummary",
    "explorationState",
    "traps",
    "loot",
}


def _scan_forbidden(obj, path=""):
    """Recursively scan for forbidden keys. 'areaDescription' under data['area'] is allowed."""
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in FORBIDDEN_KEYS:
                found.append(f"{path}.{k}" if path else k)
            if k == "areaDescription" and path != "area":
                # areaDescription only allowed directly under 'area'
                found.append(f"{path}.{k}" if path else k)
            found.extend(_scan_forbidden(v, f"{path}.{k}" if path else k))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            found.extend(_scan_forbidden(item, f"{path}[{i}]"))
    return found


def make_area():
    """Synthetic area: 5 rooms A01..A05.

    Chain: A01 - A02 - A03 - A04, plus a hidden-hidden edge A04 - A05.
    A02 additionally connects to a nonexistent room 'A99'.

    Visited (via explorationState): A01, A02.
    Unvisited: A03, A04, A05.
    """
    return {
        "areaId": "A01",
        "areaName": "Test Area",
        "areaType": "dungeon",
        "terrain": "stone",
        "climate": "cool",
        "areaDescription": "A spooky test area.",
        "map": {
            "mapId": "MAP_5",
            "mapName": "Some Unstable Name",
            "rooms": [
                {
                    "id": "A01",
                    "name": "Entrance",
                    "type": "entrance",
                    "connections": ["A02"],
                    "coordinates": "X0Y0",
                },
                {
                    "id": "A02",
                    "name": "Hall",
                    "type": "hall",
                    "connections": ["A01", "A03", "A99"],
                    "coordinates": "X1Y0",
                },
                {
                    "id": "A03",
                    "name": "Chamber",
                    "type": "chamber",
                    "connections": ["A02", "A04"],
                    "coordinates": "X2Y0",
                },
                {
                    "id": "A04",
                    "name": "Vault",
                    "type": "vault",
                    "connections": ["A03", "A05"],
                    "coordinates": "X3Y0",
                },
                {
                    "id": "A05",
                    "name": "Secret Room",
                    "type": "secret",
                    "connections": ["A04"],
                    "coordinates": "X4Y0",
                },
            ],
        },
        "locations": [
            {"locationId": "A01", "explorationState": {"status": "visited"}, "description": "..."},
            {"locationId": "A02", "explorationState": {"status": "visited"}, "description": "..."},
            {"locationId": "A03", "explorationState": {"status": "unvisited"}, "description": "..."},
            {"locationId": "A04", "explorationState": {"status": "unvisited"}, "description": "..."},
            {"locationId": "A05", "explorationState": {"status": "unvisited"}, "description": "..."},
        ],
    }


def rooms_by_id(payload):
    return {r["id"]: r for r in payload["map"]["rooms"]}


def test_unvisited_rooms_have_no_name_or_type_revealed_do():
    area = make_area()
    revealed = {"A01", "A02"}
    payload = project_map_payload(area, revealed, current_loc="A01")
    rooms = rooms_by_id(payload)

    for rid in ("A01", "A02"):
        assert "name" in rooms[rid]
        assert "type" in rooms[rid]

    for rid in ("A03", "A04", "A05"):
        assert "name" not in rooms[rid]
        assert "type" not in rooms[rid]
        # id and coordinates always present
        assert "id" in rooms[rid]
        assert "coordinates" in rooms[rid]


def test_hidden_hidden_edge_dropped_and_revealed_hidden_edge_symmetric():
    area = make_area()
    revealed = {"A01", "A02"}
    payload = project_map_payload(area, revealed, current_loc="A01")
    rooms = rooms_by_id(payload)

    # A04 - A05 both hidden -> edge absent from both endpoints
    assert "A05" not in rooms["A04"]["connections"]
    assert "A04" not in rooms["A05"]["connections"]

    # A02 (revealed) - A03 (hidden) -> edge present and symmetric
    assert "A03" in rooms["A02"]["connections"]
    assert "A02" in rooms["A03"]["connections"]


def test_revealed_includes_current_loc_even_if_unvisited():
    area = make_area()
    # A04 is unvisited per explorationState, but is current location.
    visited = derive_revealed(area, current_loc="A04")
    assert "A04" in visited
    # A04 shouldn't be revealed on visited-status merit alone -- prove it by
    # computing revealed with a *different* current_loc and confirming A04
    # drops out (since none of its own evidence marks it visited).
    visited_without_a04_as_current = derive_revealed(area, current_loc="A01")
    assert "A04" not in visited_without_a04_as_current


def test_no_forbidden_keys_anywhere_in_payload():
    area = make_area()
    revealed = {"A01", "A02"}
    payload = project_map_payload(area, revealed, current_loc="A01")

    offenders = _scan_forbidden(payload)
    assert offenders == []

    # areaDescription is allowed, but only directly under payload['area']
    assert payload["area"]["areaDescription"] == "A spooky test area."


def test_legacy_module_location_without_exploration_state_but_with_summary_is_visited():
    area = make_area()
    # Simulate a legacy location: no explorationState, but non-empty adventureSummary.
    for loc in area["locations"]:
        if loc["locationId"] == "A03":
            del loc["explorationState"]
            loc["adventureSummary"] = "The party passed through here."

    revealed = derive_revealed(area, current_loc="A01")
    assert "A03" in revealed


def test_nonexistent_connection_dropped_and_revealed_intersected_with_real_rooms():
    area = make_area()
    revealed = {"A01", "A02", "A99", "GHOST"}
    payload = project_map_payload(area, revealed, current_loc="A01")
    rooms = rooms_by_id(payload)

    # A99 doesn't exist as a room; connection to it must be dropped from A02.
    assert "A99" not in rooms["A02"]["connections"]

    # revealed list in payload must be intersected with real room ids present in the map.
    assert payload["revealed"] == sorted({"A01", "A02"})


def test_map_id_and_name_come_from_area_not_embedded_map():
    area = make_area()
    payload = project_map_payload(area, {"A01"}, current_loc="A01")
    assert payload["map"]["mapId"] == "A01"
    assert payload["map"]["mapId"] != "MAP_5"
    assert payload["map"]["mapName"] == area["areaName"]


def test_request_map_data_socket_handler_registered():
    # Public has no hosted-mode event allowlist (that's a private/edition-only
    # concept); just confirm the handler is wired up in web_interface.py.
    web_interface_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "web",
        "web_interface.py",
    )
    with open(web_interface_path, "r", encoding="utf-8") as f:
        contents = f.read()
    assert "@socketio.on('request_map_data')" in contents


def test_none_current_loc_does_not_enter_revealed_or_crash_sort():
    area = make_area()
    revealed = derive_revealed(area, current_loc=None)
    # Only genuinely-visited rooms (A01, A02) should be revealed -- None must
    # not be added to the set.
    assert None not in revealed
    assert revealed == {"A01", "A02"}

    # project_map_payload's sorted(revealed & known_room_ids) must not raise
    # TypeError from mixing None with strings, and must not treat a room
    # lacking an "id" key as revealed via `None == None`.
    payload = project_map_payload(area, revealed, current_loc=None)
    assert None not in payload["revealed"]
    assert payload["currentLocationId"] is None


def test_none_current_loc_does_not_reveal_room_missing_id_key():
    area = make_area()
    # A room dict with no "id" key at all -- its room.get("id") is None,
    # which must never be treated as "revealed" just because current_loc is
    # also None.
    area["map"]["rooms"].append({
        "name": "Should Not Leak",
        "type": "secret",
        "connections": [],
        "coordinates": "X9Y9",
    })
    revealed = derive_revealed(area, current_loc=None)
    payload = project_map_payload(area, revealed, current_loc=None)

    # The id-less room must simply be dropped from the projected rooms
    # (guarded by `if not room_id: continue`), never emitted with its real
    # name/type.
    names_leaked = [r.get("name") for r in payload["map"]["rooms"] if r.get("name") == "Should Not Leak"]
    assert names_leaked == []


def test_non_dict_room_entries_are_skipped_without_crashing():
    area = make_area()
    # Malformed data: a non-dict entry in map.rooms should be skipped, not
    # crash the projection with AttributeError.
    area["map"]["rooms"].append("not-a-room-dict")
    area["map"]["rooms"].append(None)

    revealed = {"A01", "A02"}
    payload = project_map_payload(area, revealed, current_loc="A01")
    ids = [r["id"] for r in payload["map"]["rooms"]]
    assert ids == ["A01", "A02", "A03", "A04", "A05"]


# --- resolve_area_path -------------------------------------------------

def test_resolve_area_path_valid_id_resolves():
    path = resolve_area_path("Keep_of_Doom", "A01")
    assert path.endswith("A01.json")
    assert "Keep_of_Doom" in path


def test_resolve_area_path_rejects_traversal_module_name():
    with pytest.raises(ValueError):
        resolve_area_path("../../etc", "A01")


@pytest.mark.parametrize("bad_area_id", ["G001_BU", "g001", "A01/..", "", None])
def test_resolve_area_path_rejects_bad_area_ids(bad_area_id):
    with pytest.raises(ValueError):
        resolve_area_path("Keep_of_Doom", bad_area_id)


def test_resolve_area_path_rejects_empty_module():
    with pytest.raises(ValueError):
        resolve_area_path("", "A01")
    with pytest.raises(ValueError):
        resolve_area_path(None, "A01")
