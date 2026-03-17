# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Turn-synced world time helper.

Applies bounded world-time advancement based on elapsed real time between
accepted non-empty player turns.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from updates.update_world_time import update_world_time
from utils.file_operations import safe_read_json, safe_write_json


TURN_SYNC_TIMESTAMP_FIELD = "lastRealInputTimestamp"
DEFAULT_MAX_TURN_SYNC_MINUTES = 15


def _normalize_datetime(dt_value: datetime) -> datetime:
    """Normalize datetime to naive UTC for deterministic arithmetic."""
    if dt_value.tzinfo is not None:
        return dt_value.astimezone(timezone.utc).replace(tzinfo=None)
    return dt_value


def parse_iso_timestamp(value: Any) -> Optional[datetime]:
    """Parse persisted ISO timestamp and return normalized datetime."""
    if not isinstance(value, str):
        return None

    timestamp_text = value.strip()
    if not timestamp_text:
        return None

    if timestamp_text.endswith("Z"):
        timestamp_text = f"{timestamp_text[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(timestamp_text)
    except ValueError:
        return None

    return _normalize_datetime(parsed)


def compute_elapsed_minutes(last_ts: datetime, now_ts: datetime) -> int:
    """Return elapsed whole minutes between two timestamps."""
    normalized_last = _normalize_datetime(last_ts)
    normalized_now = _normalize_datetime(now_ts)
    elapsed_seconds = (normalized_now - normalized_last).total_seconds()
    if elapsed_seconds <= 0:
        return 0
    return int(elapsed_seconds // 60)


def clamp_elapsed_minutes(minutes: int, max_minutes: int = DEFAULT_MAX_TURN_SYNC_MINUTES) -> int:
    """Clamp elapsed minutes to a bounded deterministic range."""
    if minutes <= 0:
        return 0
    if max_minutes <= 0:
        return 0
    return min(minutes, max_minutes)


def _write_timestamp_marker(party_tracker_data: Dict[str, Any], marker_value: datetime) -> bool:
    """Persist timestamp marker into party tracker using atomic write helper."""
    world_conditions = party_tracker_data.get("worldConditions")
    if not isinstance(world_conditions, dict):
        world_conditions = {}
        party_tracker_data["worldConditions"] = world_conditions

    normalized_marker = _normalize_datetime(marker_value)
    world_conditions[TURN_SYNC_TIMESTAMP_FIELD] = normalized_marker.isoformat(timespec="seconds")
    return bool(safe_write_json("party_tracker.json", party_tracker_data))


def apply_turn_time_sync(
    now_ts: Optional[datetime] = None,
    max_minutes: int = DEFAULT_MAX_TURN_SYNC_MINUTES,
) -> Dict[str, Any]:
    """Apply bounded world-time sync for an accepted player turn."""
    result: Dict[str, Any] = {
        "applied_minutes": 0,
        "elapsed_minutes": 0,
        "seeded": False,
        "reset": False,
        "status": "no_op",
    }

    party_tracker_data = safe_read_json("party_tracker.json")
    if not isinstance(party_tracker_data, dict):
        result["status"] = "missing_party_tracker"
        return result

    world_conditions = party_tracker_data.get("worldConditions")
    if not isinstance(world_conditions, dict):
        world_conditions = {}
        party_tracker_data["worldConditions"] = world_conditions

    now_value = _normalize_datetime(now_ts or datetime.utcnow())
    previous_raw = world_conditions.get(TURN_SYNC_TIMESTAMP_FIELD)
    previous_ts = parse_iso_timestamp(previous_raw)

    if previous_ts is None:
        result["seeded"] = True
        result["reset"] = previous_raw is not None
        if _write_timestamp_marker(party_tracker_data, now_value):
            result["status"] = "seeded"
        else:
            result["status"] = "seed_failed"
        return result

    elapsed_minutes = compute_elapsed_minutes(previous_ts, now_value)
    result["elapsed_minutes"] = elapsed_minutes
    clamped_minutes = clamp_elapsed_minutes(elapsed_minutes, max_minutes=max_minutes)
    result["applied_minutes"] = clamped_minutes

    if clamped_minutes > 0:
        update_world_time(str(clamped_minutes))

    refreshed_party_tracker = safe_read_json("party_tracker.json")
    if not isinstance(refreshed_party_tracker, dict):
        result["status"] = "refresh_failed"
        return result

    if _write_timestamp_marker(refreshed_party_tracker, now_value):
        result["status"] = "applied" if clamped_minutes > 0 else "updated_marker"
    else:
        result["status"] = "marker_write_failed"

    return result
