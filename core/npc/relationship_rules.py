"""Versioned deterministic relationship math for NPC voice state."""

from __future__ import annotations

from typing import Dict, Mapping


DIMENSIONS = ("trust", "power", "intimacy", "fear", "respect")

BOUNDS = {
    "trust": (-1.0, 1.0),
    "power": (-1.0, 1.0),
    "intimacy": (0.0, 1.0),
    "fear": (0.0, 1.0),
    "respect": (-1.0, 1.0),
}

EVENT_DELTAS = {
    "abandon": {"trust": -0.12, "power": 0.00, "intimacy": -0.05, "fear": 0.04, "respect": -0.08},
    "betray": {"trust": -0.18, "power": 0.00, "intimacy": -0.07, "fear": 0.04, "respect": -0.12},
    "deceive": {"trust": -0.12, "power": 0.00, "intimacy": -0.03, "fear": 0.01, "respect": -0.08},
    "disrespect": {"trust": -0.04, "power": 0.00, "intimacy": -0.04, "fear": 0.00, "respect": -0.12},
    "harm": {"trust": -0.15, "power": 0.03, "intimacy": -0.06, "fear": 0.12, "respect": -0.10},
    "threaten": {"trust": -0.10, "power": 0.04, "intimacy": -0.05, "fear": 0.15, "respect": -0.08},
    "give": {"trust": 0.04, "power": 0.00, "intimacy": 0.02, "fear": 0.00, "respect": 0.02},
    "heal": {"trust": 0.08, "power": 0.00, "intimacy": 0.04, "fear": -0.02, "respect": 0.05},
    "honor": {"trust": 0.05, "power": 0.00, "intimacy": 0.03, "fear": -0.01, "respect": 0.10},
    "protect": {"trust": 0.10, "power": 0.01, "intimacy": 0.05, "fear": -0.03, "respect": 0.08},
    "rescue": {"trust": 0.14, "power": 0.02, "intimacy": 0.07, "fear": -0.04, "respect": 0.10},
    "share": {"trust": 0.05, "power": 0.00, "intimacy": 0.05, "fear": 0.00, "respect": 0.03},
    "support": {"trust": 0.07, "power": 0.00, "intimacy": 0.04, "fear": -0.01, "respect": 0.05},
    "trust": {"trust": 0.08, "power": 0.00, "intimacy": 0.06, "fear": -0.01, "respect": 0.04},
}


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return float(value)


def clamp_state(state: Mapping[str, object]) -> Dict[str, float]:
    """Clamp and round one complete five-dimensional state."""
    result = {}
    for name in DIMENSIONS:
        minimum, maximum = BOUNDS[name]
        result[name] = round(max(minimum, min(maximum, _number(state.get(name)))), 4)
    return result


def apply_event_delta(
    current: Mapping[str, object],
    event_type: str,
    magnitude: int,
    *,
    witnessed: bool,
) -> Dict[str, float]:
    """Apply one v1 event without mutating the input state."""
    if event_type not in EVENT_DELTAS:
        raise ValueError("unknown relationship event type")
    if isinstance(magnitude, bool) or not isinstance(magnitude, int):
        raise ValueError("relationship magnitude must be an integer")
    strength = abs(magnitude)
    if strength not in (1, 2, 3):
        raise ValueError("relationship magnitude must be 1 through 3")
    base = clamp_state(current)
    if not witnessed:
        return base
    delta = EVENT_DELTAS[event_type]
    return clamp_state(
        {name: base[name] + delta[name] * strength for name in DIMENSIONS}
    )


def event_delta(event_type: str, magnitude: int, witnessed: bool) -> Dict[str, float]:
    """Return the bounded event delta recorded in evidence."""
    zero = {name: 0.0 for name in DIMENSIONS}
    if not witnessed:
        return zero
    applied = apply_event_delta(zero, event_type, magnitude, witnessed=True)
    raw = EVENT_DELTAS[event_type]
    return {
        name: round(raw[name] * abs(magnitude), 4)
        for name in DIMENSIONS
    }


def decay_toward_baseline(
    baseline: Mapping[str, object],
    current: Mapping[str, object],
    elapsed_game_days: int,
) -> Dict[str, float]:
    """Apply lazy 3 percent daily decay toward an edge's baseline."""
    base = clamp_state(baseline)
    now = clamp_state(current)
    if isinstance(elapsed_game_days, bool) or not isinstance(elapsed_game_days, int):
        raise ValueError("elapsed game days must be an integer")
    if elapsed_game_days <= 0:
        return now
    multiplier = 0.97 ** elapsed_game_days
    return clamp_state(
        {
            name: base[name] + (now[name] - base[name]) * multiplier
            for name in DIMENSIONS
        }
    )
