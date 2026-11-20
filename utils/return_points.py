"""Return points: where the party left each adventure (D-MODSWITCH-1, #2081).

campaign.json holds ``returnPoints`` = {<module folder id>: {"areaId",
"locationId", "locationName"}}. The completion commit that marks an adventure
visited writes the place the party left it (``record``); a later switch back
with no place named lands there when it still exists (``resolve``), else at
the adventure's declared entry. The name is a check only: an id that now names
a different place falls back to the entry. Nothing here looks a place up by
its name.

Public and small on purpose: a switch that does not go through the DM route
(a host's own screen) calls these in the same way. No model call, no network.
"""

import json
import os

CAMPAIGN_PATH = os.path.join("modules", "campaign.json")
KEY = "returnPoints"
FIELDS = ("areaId", "locationId", "locationName")


def module_key(name):
    """The folder form of a module name: stripped, spaces as underscores
    (the form INSTALLED MODULE REFERENCES uses). "" for a non-string."""
    if not isinstance(name, str):
        return ""
    return name.strip().replace(" ", "_")


def point_from_tracker(party_tracker, module=None):
    """The return point a party tracker stands at: {"areaId", "locationId",
    "locationName"}, or None unless all three are non-empty strings. With
    ``module``, also None unless the tracker is in that module (folder form),
    so a tracker already moved on never records its new place for the old
    module."""
    if not isinstance(party_tracker, dict):
        return None
    if module is not None and module_key(party_tracker.get("module")) != module_key(module):
        return None
    world = party_tracker.get("worldConditions")
    if not isinstance(world, dict):
        return None
    point = {
        "areaId": world.get("currentAreaId"),
        "locationId": world.get("currentLocationId"),
        "locationName": world.get("currentLocation"),
    }
    if not all(isinstance(value, str) and value.strip() for value in point.values()):
        return None
    return point


def record(campaign, module, point):
    """Set campaign[returnPoints][module_key(module)] = point in a campaign
    dict (pure: the caller writes campaign.json under its own campaign
    transaction). A non-dict returnPoints is replaced. Returns whether a
    point was recorded."""
    key = module_key(module)
    if not isinstance(campaign, dict) or not key or not isinstance(point, dict):
        return False
    if not all(isinstance(point.get(field), str) and point.get(field).strip() for field in FIELDS):
        return False
    points = campaign.get(KEY)
    if not isinstance(points, dict):
        points = {}
        campaign[KEY] = points
    points[key] = {field: point[field] for field in FIELDS}
    return True


def load(campaign_path=CAMPAIGN_PATH):
    """The saved return point dict from campaign.json, {} when the file, the
    key or a readable object is missing. A plain read: no recovery runs."""
    try:
        with open(campaign_path, "r", encoding="utf-8") as handle:
            campaign = json.load(handle)
    except (OSError, UnicodeError, ValueError):
        return {}
    points = campaign.get(KEY) if isinstance(campaign, dict) else None
    return points if isinstance(points, dict) else {}


def resolve(target_module, snapshot, campaign_path=CAMPAIGN_PATH):
    """The saved place for target_module as a destination projection
    {"currentAreaId", "currentArea", "currentLocationId", "currentLocation"},
    or None (the caller then uses the declared entry).

    ``snapshot`` is the target's build_active_module_snapshot. The point is
    used only when its location is one of the snapshot's nodes, not an
    invalid one, in the saved area, and still carries the saved name. Door
    and lock checks do not apply: like the declared entry, a return point is
    a placement, not a route."""
    point = load(campaign_path).get(module_key(target_module))
    if not isinstance(point, dict):
        return None
    if not all(isinstance(point.get(field), str) and point.get(field) for field in FIELDS):
        return None
    if not isinstance(snapshot, dict):
        return None
    nodes = snapshot.get("nodes")
    node = nodes.get(point["locationId"]) if isinstance(nodes, dict) else None
    if not isinstance(node, dict):
        return None
    if point["locationId"] in (snapshot.get("invalid_location_ids") or ()):
        return None
    if node.get("area_id") != point["areaId"] or node.get("location_name") != point["locationName"]:
        return None
    return {
        "currentAreaId": node["area_id"],
        "currentArea": node.get("area_name") or "",
        "currentLocationId": node["location_id"],
        "currentLocation": node["location_name"],
    }
