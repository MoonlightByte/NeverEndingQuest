# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Deterministic temporary-effect mechanics.

Models may propose effect objects, but this package owns their validation,
arithmetic, duration transitions, and presentation overlays.  The package is
deliberately free of provider calls and filesystem writes.
"""

from core.effects.clock import (
    calendar_from_scalar,
    display_iso_from_scalar,
    scalar_from_calendar,
    scalar_from_display_iso,
)
from core.effects.effective import (
    effective_sheet,
    modifier_total,
    storage_delta_from_effective,
)
from core.effects.lifecycle import (
    apply_effect_ops,
    plan_expirations,
    plan_rest_clears,
)
from core.effects.model import (
    EFFECTS_PIPELINE_VERSION,
    effect_identity,
    normalize_effect,
    validate_effect,
)

__all__ = (
    "EFFECTS_PIPELINE_VERSION",
    "apply_effect_ops",
    "calendar_from_scalar",
    "display_iso_from_scalar",
    "effect_identity",
    "effective_sheet",
    "modifier_total",
    "normalize_effect",
    "plan_expirations",
    "plan_rest_clears",
    "scalar_from_calendar",
    "scalar_from_display_iso",
    "storage_delta_from_effective",
    "validate_effect",
)
