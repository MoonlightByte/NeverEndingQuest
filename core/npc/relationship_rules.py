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


# --- Phase 5: relationship depth -----------------------------------------------
# A PINNED episode's emotional tag contributes to the NPC->player relationship
# BASELINE (not the momentary value), so decay settles the bond at a memory-justified
# level instead of returning to zero -- bonds deepen and STICK. The baseline is
# recomputed as a pure sum over the NPC's pinned POV episodes (idempotent), then
# clamped. This is what finally moves the intimacy/fear axes that ordinary per-turn
# deltas leave dead (finding M27).
_POVTAG_BASELINE_WEIGHTS = {
    "traumatic":   {"intimacy": 1.0, "fear": 1.0},
    "protective":  {"intimacy": 1.0, "respect": 0.5},
    "proud":       {"respect": 1.0, "intimacy": 0.5},
    "triumphant":  {"respect": 1.0},
    "tender":      {"intimacy": 1.0},
    "grateful":    {"intimacy": 1.0, "trust": 0.5},
    "grieving":    {"intimacy": 1.0},
    "resentful":   {"trust": -1.0, "fear": 0.5},
    "afraid":      {"fear": 1.0},
    "guilty":      {"intimacy": 0.5, "respect": -0.3},
    "amused":      {"intimacy": 0.3},
    "smitten":     {"intimacy": 1.0},
    "longing":     {"intimacy": 1.0},
    "heartbroken": {"intimacy": 0.5, "fear": 0.5},
}
_BASELINE_NUDGE = 0.08  # per unit-weight, per salience=1.0 pinned episode


def povtag_baseline_contribution(pov_tag, salience) -> Dict[str, float]:
    """Axis contribution a single pinned episode makes to the relationship baseline."""
    try:
        strength = max(0.0, min(1.0, float(salience)))
    except (TypeError, ValueError):
        strength = 0.0
    weights = _POVTAG_BASELINE_WEIGHTS.get(pov_tag, {})
    return {axis: weight * strength * _BASELINE_NUDGE for axis, weight in weights.items()}


def baseline_from_pinned(pov_episodes) -> Dict[str, float]:
    """Recompute the relationship baseline from an NPC's pinned POV episodes (pure,
    idempotent): sum per-axis contributions across pinned rows, then clamp to bounds."""
    total = {name: 0.0 for name in DIMENSIONS}
    for episode in pov_episodes:
        if not isinstance(episode, Mapping) or not episode.get("pinned"):
            continue
        for axis, delta in povtag_baseline_contribution(
            episode.get("povTag"), episode.get("salienceScore", 0.0)
        ).items():
            total[axis] += delta
    return clamp_state(total)
