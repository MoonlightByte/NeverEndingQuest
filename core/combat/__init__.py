# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Pure combat mechanics: intent validation, deterministic resolution,
copy-on-write application, and invariant checking.

This package performs NO file or network I/O. Sequencing authority
(rounds, cursors, turn claims, duplicate-turn prevention) lives in
core.managers.combat_state; this package owns what mechanically happens
inside a claimed turn.
"""

from core.combat.events import make_event_id, validate_event
from core.combat.resolver import (
    DeterministicRollSource,
    Rejection,
    Resolution,
    apply_resolution,
    check_invariants,
    resolve_adjudicated,
    resolve_intent,
    resolution_from_event,
    tick_effects,
    validate_intent,
)
from core.combat.pipeline import (
    CombatIntentError,
    CombatPlayerInputRequired,
    resolve_claimed_window,
)
from core.combat.rolls import PersistedPrerollSource, ensure_agentic_roll_reserve

__all__ = [
    "make_event_id",
    "validate_event",
    "DeterministicRollSource",
    "Rejection",
    "Resolution",
    "apply_resolution",
    "check_invariants",
    "resolve_adjudicated",
    "resolve_intent",
    "resolution_from_event",
    "tick_effects",
    "validate_intent",
    "CombatIntentError",
    "CombatPlayerInputRequired",
    "resolve_claimed_window",
    "PersistedPrerollSource",
    "ensure_agentic_roll_reserve",
]
