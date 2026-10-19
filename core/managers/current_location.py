# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""One reader for the party's current location (#448).

The current area file is read once, as strict UTF-8, and the location is found
by the tracker's currentLocationId. Every failure has a name: the file is
missing, unreadable (not readable, not UTF-8, not JSON, or no locations list),
or does not hold the location; or the tracker names no location. A sharing
violation is retried as for party_tracker.json. A missing active module still
raises ActiveModuleUnavailable, as everywhere since #448.
"""

import json
from dataclasses import dataclass
from typing import Optional

from utils.enhanced_logger import debug, warning
from utils.module_path_manager import ModulePathManager
from utils.transient_filesystem import (
    is_transient_filesystem_error,
    read_bytes_preserving_errors,
    retry_transient_filesystem,
)

OK = "ok"
MISSING = "missing"
UNREADABLE = "unreadable"
NOT_FOUND = "not_found"
NO_LOCATION = "no_location"


@dataclass(frozen=True)
class CurrentLocationRead:
    status: str
    area_id: Optional[str] = None
    location_id: Optional[str] = None
    area_file: Optional[str] = None
    area: Optional[dict] = None
    location: Optional[dict] = None
    detail: str = ""
    busy: bool = False


def read_current_location(party_tracker_data) -> CurrentLocationRead:
    """Read the current location named by the tracker; never raises for a bad area file."""
    world = (party_tracker_data or {}).get("worldConditions") or {}
    area_id = world.get("currentAreaId")
    location_id = world.get("currentLocationId")
    if not area_id or not location_id:
        return CurrentLocationRead(NO_LOCATION, area_id, location_id,
                                   detail="the party tracker names no current area and location id")
    module_name = ((party_tracker_data or {}).get("module") or "").replace(" ", "_")
    area_file = ModulePathManager(module_name).get_area_path(area_id)

    def failed(status, detail):
        return CurrentLocationRead(status, area_id, location_id, area_file, detail=detail)

    try:
        raw = retry_transient_filesystem(lambda: read_bytes_preserving_errors(area_file))
    except FileNotFoundError:
        return failed(MISSING, f"{area_file} does not exist")
    except OSError as e:
        return CurrentLocationRead(UNREADABLE, area_id, location_id, area_file,
                                   detail=f"{area_file} could not be read ({e})",
                                   busy=is_transient_filesystem_error(e))
    try:
        area = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError as e:
        return failed(UNREADABLE, f"{area_file} is not valid UTF-8 (byte {e.start})")
    except ValueError as e:
        return failed(UNREADABLE, f"{area_file} is not valid JSON ({e})")
    if not isinstance(area, dict) or not isinstance(area.get("locations"), list):
        return failed(UNREADABLE, f"{area_file} has no locations list")
    location = next((loc for loc in area["locations"]
                     if isinstance(loc, dict) and loc.get("locationId") == location_id), None)
    if location is None:
        return failed(NOT_FOUND, f"location {location_id} is not in {area_file}")
    return CurrentLocationRead(OK, area_id, location_id, area_file, area, location)


def current_location_data(party_tracker_data, *, consumer, wait=None) -> Optional[dict]:
    """The current location's data, or None after one line naming why.

    With ``wait`` (a no-argument callable), a busy area file waits and is read
    again, with no deadline and nothing logged per retry; a stop the wait
    raises propagates (B1)."""
    read = read_current_location(party_tracker_data)
    while read.busy and wait is not None:
        wait()
        read = read_current_location(party_tracker_data)
    if read.status == OK:
        return read.location
    line = f"LOCATION: {consumer}: the current location is {read.status}: {read.detail}"
    if read.status == NO_LOCATION:
        debug(line, category="location_transitions")
    else:
        warning(line, category="location_transitions")
    return None
