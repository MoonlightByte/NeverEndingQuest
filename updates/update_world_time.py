# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

from datetime import datetime, timedelta
import json
from utils.encoding_utils import safe_json_load, safe_json_dump


_CLOCK_FIELDS = ("time", "day", "month", "year")


def calculate_world_time_fields(world_conditions, minutes):
    """Return exact owned clock values without reading or writing a file."""
    current_time = datetime.strptime(world_conditions["time"], "%H:%M:%S")
    current_day = world_conditions["day"]
    current_month = world_conditions.get("month", "Springmonth")
    current_year = world_conditions.get("year", 1492)
    time_estimate_minutes = int(minutes)
    updated_time = current_time + timedelta(minutes=time_estimate_minutes)
    days_passed = (updated_time.date() - current_time.date()).days
    new_day = current_day + days_passed
    new_month = current_month
    new_year = current_year
    months = [
        "Firstmonth", "Coldmonth", "Thawmonth", "Springmonth",
        "Bloommonth", "Sunmonth", "Heatmonth", "Harvestmonth",
        "Autumnmonth", "Fademonth", "Frostmonth", "Yearend"
    ]
    while new_day > 28:
        new_day -= 28
        try:
            month_index = (months.index(new_month) + 1) % 12
            new_month = months[month_index]
            if month_index == 0:
                new_year += 1
        except ValueError:
            new_month = "Springmonth"
    return {
        "time": updated_time.strftime("%H:%M:%S"),
        "day": new_day,
        "month": new_month,
        "year": new_year,
    }


def apply_staged_world_time(before, after):
    """Patch only the four clock fields using exact three-way recovery."""
    party_tracker_data = safe_json_load("party_tracker.json")
    if not isinstance(party_tracker_data, dict):
        raise RuntimeError("party tracker is unavailable")
    world = party_tracker_data.get("worldConditions")
    if not isinstance(world, dict):
        raise RuntimeError("party tracker world conditions are unavailable")
    current = {field: world.get(field) for field in _CLOCK_FIELDS}
    if current == after:
        return "already_committed"
    if current != before:
        return "blocked_conflict"
    for field in _CLOCK_FIELDS:
        world[field] = after[field]
    safe_json_dump(party_tracker_data, "party_tracker.json", indent=4)
    verified = safe_json_load("party_tracker.json")
    verified_world = verified.get("worldConditions", {}) if isinstance(verified, dict) else {}
    if {field: verified_world.get(field) for field in _CLOCK_FIELDS} != after:
        raise IOError("world clock verification failed")
    return "committed"

def update_world_time(time_estimate_str):
    # Read the party tracker data from the JSON file with safe encoding
    party_tracker_data = safe_json_load("party_tracker.json")
    if party_tracker_data is None:
        print("Error: Could not load party_tracker.json")
        return

    try:
        time_estimate_minutes = int(time_estimate_str)
    except (TypeError, ValueError):
        print("Invalid time estimate. Skipping world time update.")
        return
    before = {
        field: party_tracker_data["worldConditions"].get(field)
        for field in _CLOCK_FIELDS
    }
    after = calculate_world_time_fields(
        party_tracker_data["worldConditions"], time_estimate_minutes
    )
    current_time = datetime.strptime(before["time"], "%H:%M:%S")
    days_passed = after["day"] - before["day"]
    current_month = before["month"]
    new_month = after["month"]
    new_year = after["year"]
    new_day = after["day"]
    updated_time = datetime.strptime(after["time"], "%H:%M:%S")
    party_tracker_data["worldConditions"].update(after)

    # Save the updated party tracker data to the JSON file with safe encoding
    safe_json_dump(party_tracker_data, "party_tracker.json", indent=4)

    # Debug print line in orange color
    if current_month != new_month:
        print(f"\033[38;5;208mCurrent Time: {current_time.strftime('%H:%M:%S')}, Time Advanced: {time_estimate_minutes} minutes, New Time: {updated_time.strftime('%H:%M:%S')}, Date: {new_year} {new_month} {new_day}\033[0m")
    else:
        print(f"\033[38;5;208mCurrent Time: {current_time.strftime('%H:%M:%S')}, Time Advanced: {time_estimate_minutes} minutes, New Time: {updated_time.strftime('%H:%M:%S')}, Days Passed: {days_passed}\033[0m")
