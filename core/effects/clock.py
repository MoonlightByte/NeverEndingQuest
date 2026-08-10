# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""One game-time scalar with calculation and fantasy-display adapters."""

from datetime import datetime
import re


MONTHS = (
    "Firstmonth",
    "Coldmonth",
    "Thawmonth",
    "Springmonth",
    "Bloommonth",
    "Sunmonth",
    "Heatmonth",
    "Harvestmonth",
    "Autumnmonth",
    "Fademonth",
    "Frostmonth",
    "Yearend",
)
SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 60 * SECONDS_PER_MINUTE
SECONDS_PER_DAY = 24 * SECONDS_PER_HOUR
DAYS_PER_MONTH = 28
MONTHS_PER_YEAR = 12


class GameTimeError(ValueError):
    """Persisted fantasy calendar data cannot be converted safely."""


def fixed_duration_seconds(duration):
    """Return (durationKind, seconds) for one simple fixed rules duration."""
    if not isinstance(duration, str):
        return None
    match = re.fullmatch(
        r"\s*(?:concentration\s*,\s*)?(?:up to\s+)?"
        r"(\d+)\s+(minute|minutes|hour|hours|day|days)\s*",
        duration,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    amount = int(match.group(1))
    unit = match.group(2).lower()
    if unit.startswith("minute"):
        return "minutes", amount * SECONDS_PER_MINUTE
    if unit.startswith("hour"):
        return "hours", amount * SECONDS_PER_HOUR
    return "days", amount * SECONDS_PER_DAY


def _time_parts(value):
    parts = str(value or "00:00:00").split(":")
    if not 2 <= len(parts) <= 3:
        raise GameTimeError("game time must use HH:MM or HH:MM:SS")
    try:
        hour = int(parts[0])
        minute = int(parts[1])
        second = int(parts[2]) if len(parts) == 3 else 0
    except (TypeError, ValueError) as exc:
        raise GameTimeError("game time contains a non-integer component") from exc
    if not 0 <= hour <= 23 or not 0 <= minute <= 59 or not 0 <= second <= 59:
        raise GameTimeError("game time is outside the valid clock range")
    return hour, minute, second


def scalar_from_calendar(world_conditions):
    """Return absolute game seconds from persisted fantasy calendar fields."""
    if not isinstance(world_conditions, dict):
        raise GameTimeError("worldConditions must be an object")
    try:
        year = int(world_conditions.get("year", 1492))
        day = int(world_conditions.get("day", 1))
    except (TypeError, ValueError) as exc:
        raise GameTimeError("game year/day must be integers") from exc
    month = world_conditions.get("month", "Springmonth")
    if month not in MONTHS:
        raise GameTimeError("unknown fantasy month: %r" % month)
    if year < 1 or not 1 <= day <= DAYS_PER_MONTH:
        raise GameTimeError("game year/day is outside the supported calendar")
    hour, minute, second = _time_parts(world_conditions.get("time"))
    ordinal_days = (
        ((year * MONTHS_PER_YEAR) + MONTHS.index(month)) * DAYS_PER_MONTH
        + (day - 1)
    )
    return ordinal_days * SECONDS_PER_DAY + hour * 3600 + minute * 60 + second


def calendar_from_scalar(value):
    """Return persisted fantasy calendar fields for an absolute game second."""
    if type(value) is not int or value < 0:
        raise GameTimeError("game-time scalar must be a nonnegative integer")
    ordinal_days, day_seconds = divmod(value, SECONDS_PER_DAY)
    total_months, day_index = divmod(ordinal_days, DAYS_PER_MONTH)
    year, month_index = divmod(total_months, MONTHS_PER_YEAR)
    hour, remainder = divmod(day_seconds, 3600)
    minute, second = divmod(remainder, 60)
    return {
        "year": year,
        "month": MONTHS[month_index],
        "day": day_index + 1,
        "time": "%02d:%02d:%02d" % (hour, minute, second),
    }


def display_iso_from_scalar(value):
    """Render a fantasy-calendar deadline in the existing ISO string field."""
    calendar = calendar_from_scalar(value)
    month = MONTHS.index(calendar["month"]) + 1
    hour, minute, second = _time_parts(calendar["time"])
    return datetime(
        calendar["year"], month, calendar["day"], hour, minute, second
    ).isoformat()


def scalar_from_display_iso(value):
    """Convert the character-sheet ``expiration`` display value to scalar."""
    if not isinstance(value, str) or not value.strip():
        raise GameTimeError("effect expiration must be a nonempty ISO string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GameTimeError("effect expiration is not valid ISO time") from exc
    if not 1 <= parsed.month <= len(MONTHS) or parsed.day > DAYS_PER_MONTH:
        raise GameTimeError("effect expiration is outside the fantasy calendar")
    return scalar_from_calendar(
        {
            "year": parsed.year,
            "month": MONTHS[parsed.month - 1],
            "day": parsed.day,
            "time": parsed.strftime("%H:%M:%S"),
        }
    )
