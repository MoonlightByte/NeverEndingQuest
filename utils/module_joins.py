# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""Cross-module joins (C12): the way between two modules the party has
crossed, kept in world_registry.json under ``joins`` (owner O5).

A join is written by code from the DM's own module switch, the first time
the party crosses between two modules (an unordered pair; at most one join
per pair):

    {"gateway": {"module": A, "location": <the place the party left>},
     "entry": {"module": B, "location": <the place it arrived at>},
     "minutes": <the switch's updateTime, the journey's time (owner O4)>,
     "operationId": <the switch's checkpoint>}

Its route, ``gateway`` to ``entry`` both ways, is declared to the engine only
in the switch's own requests (core/nql/travel.py), so in-module paths and
destinations never cross a module. Ends are compared by value.
"""
import os
from typing import Any, Dict, List, Optional, Tuple

from utils.encoding_utils import safe_json_dump, safe_json_load
from utils.enhanced_logger import info, warning

REGISTRY = os.path.join("modules", "world_registry.json")

# A route's ticks are seconds, 1..1e9 (WORLD_MAP.md); a join is whole minutes.
MAX_MINUTES = 1000000000 // 60


def place(module: str, location: str) -> str:
    return "loc:%s/%s" % (str(module).replace(" ", "_"), location)


def _end(value: Any) -> Optional[Tuple[str, str]]:
    if not isinstance(value, dict):
        return None
    module, location = value.get("module"), value.get("location")
    if not isinstance(module, str) or not module or not isinstance(location, str) or not location:
        return None
    return module.replace(" ", "_"), location


def valid(join: Any) -> bool:
    if not isinstance(join, dict):
        return False
    gateway, entry = _end(join.get("gateway")), _end(join.get("entry"))
    minutes = join.get("minutes")
    return (gateway is not None and entry is not None and gateway[0] != entry[0]
            and type(minutes) is int and 1 <= minutes <= MAX_MINUTES)


def joins(root: str = ".") -> List[Dict[str, Any]]:
    """The registry's valid joins, in order."""
    registry = safe_json_load(os.path.join(root, REGISTRY))
    found = registry.get("joins") if isinstance(registry, dict) else None
    return [j for j in found or [] if valid(j)] if isinstance(found, list) else []


def modules_of(join: Dict[str, Any]) -> Tuple[str, str]:
    return _end(join["gateway"])[0], _end(join["entry"])[0]


def between(a: str, b: str, root: str = ".") -> Optional[Dict[str, Any]]:
    """The join of the unordered module pair (a, b), or None."""
    pair = {str(a).replace(" ", "_"), str(b).replace(" ", "_")}
    return next((j for j in joins(root) if set(modules_of(j)) == pair), None)


def route(join: Dict[str, Any]) -> Tuple[str, str, int]:
    """(gateway place, entry place, ticks): the join's engine route."""
    gateway, entry = _end(join["gateway"]), _end(join["entry"])
    return place(*gateway), place(*entry), join["minutes"] * 60


def journey_minutes(estimate: Any) -> Optional[int]:
    """The DM's updateTime estimate as a join's minutes, or None."""
    try:
        minutes = int(estimate)
    except (TypeError, ValueError):
        return None
    return min(max(minutes, 1), MAX_MINUTES)


def proposed(source_module: str, source_location: str, target_module: str, target_location: str,
             estimate: Any, operation_id: str) -> Optional[Dict[str, Any]]:
    """The join a first crossing writes, or None when it cannot be one."""
    join = {
        "gateway": {"module": str(source_module).replace(" ", "_"), "location": str(source_location or "")},
        "entry": {"module": str(target_module).replace(" ", "_"), "location": str(target_location or "")},
        "minutes": journey_minutes(estimate),
        "operationId": str(operation_id or ""),
    }
    return join if valid(join) else None


def record(join: Dict[str, Any], root: str = ".") -> bool:
    """Write the join when its module pair has none. Under the module refresh
    lock, as the registry's other writers; every other key is kept. Returns
    whether the registry holds a join for the pair afterwards."""
    from utils.module_refresh_lock import module_refresh_lock
    if not valid(join):
        return False
    path = os.path.join(root, REGISTRY)
    with module_refresh_lock() as acquired:
        if not acquired:
            warning("JOIN: the registry is busy; the join %s is not recorded (the next crossing records it)"
                    % (modules_of(join),), category="location_transitions")
            return False
        registry = safe_json_load(path)
        if not isinstance(registry, dict):
            warning("JOIN: world_registry.json is unreadable; the join is not recorded",
                    category="location_transitions")
            return False
        existing = registry.get("joins")
        existing = existing if isinstance(existing, list) else []
        pair = set(modules_of(join))
        if any(valid(j) and set(modules_of(j)) == pair for j in existing):
            return True
        registry["joins"] = existing + [join]
        safe_json_dump(registry, path)
    gateway, entry, ticks = route(join)
    info("JOIN: recorded %s <-> %s, %d min" % (gateway, entry, join["minutes"]),
         category="location_transitions")
    return True
