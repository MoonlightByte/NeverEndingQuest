# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""One lifecycle-aware character projection for gameplay and both web UIs."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Optional

from core.effects.clock import scalar_from_calendar, scalar_from_display_iso
from core.effects.effective import effective_sheet


def _projection_scalar(
    world_conditions: Optional[Mapping[str, Any]],
    now_scalar: Optional[int],
) -> Optional[int]:
    if type(now_scalar) is int:
        return now_scalar
    if not isinstance(world_conditions, Mapping):
        return None
    try:
        return scalar_from_calendar(dict(world_conditions))
    except ValueError:
        return None


def _expired_for_projection(effect: Any, now_scalar: Optional[int]) -> bool:
    if not isinstance(effect, Mapping):
        return False
    if effect.get("authoredBy") not in ("engine", "classifier"):
        return False
    rounds = effect.get("roundsRemaining")
    if type(rounds) is int:
        return rounds <= 0
    expiration = effect.get("expiration")
    if type(now_scalar) is not int or not isinstance(expiration, str):
        return False
    try:
        return now_scalar >= scalar_from_display_iso(expiration)
    except ValueError:
        # Invalid managed effects remain visible until the authoritative
        # lifecycle validator can report/repair them; a read must not guess.
        return False


def effective_character_projection(
    sheet: Mapping[str, Any],
    *,
    world_conditions: Optional[Mapping[str, Any]] = None,
    now_scalar: Optional[int] = None,
    include_ac_advisory: bool = False,
):
    """Return the shared effective view without mutating durable character data.

    An expired effect can remain briefly on disk until the lifecycle writer
    processes it. Readers omit that effect from this view, so combat snapshots,
    resolution, legacy UI, and React UI all agree during that window.
    """
    if not isinstance(sheet, Mapping):
        return sheet
    projected_input = deepcopy(dict(sheet))
    scalar = _projection_scalar(world_conditions, now_scalar)
    effects = projected_input.get("temporaryEffects")
    if isinstance(effects, list):
        projected_input["temporaryEffects"] = [
            deepcopy(effect)
            for effect in effects
            if not _expired_for_projection(effect, scalar)
        ]
    result = effective_sheet(projected_input)
    if include_ac_advisory:
        try:
            from core.validation.ac_validation import attach_ac_validation_advisory

            result = attach_ac_validation_advisory(result)
        except Exception:
            # Advisory availability can never change the effective game state.
            pass
    return result
