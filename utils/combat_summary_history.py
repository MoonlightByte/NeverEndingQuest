# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Combat Summary History - Historical Combat Record Helpers
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

HISTORICAL_COMBAT_PREFIX = "[COMBAT CONCLUDED - HISTORICAL RECORD]"
HISTORICAL_COMBAT_SUFFIX = (
    "[END OF COMBAT RECORD - Please continue the narrative after this combat]"
)
HISTORICAL_COMBAT_REWARD_GUARD = (
    "IMPORTANT: All XP, treasure, currency, items, and other rewards mentioned "
    "above have already been distributed by the combat system. Do NOT award them again."
)


def build_historical_combat_summary_message(summary_text: str) -> str:
    """Wrap a combat summary in a historical-only no-replay guard."""
    normalized_summary = str(summary_text or "").strip()
    if not normalized_summary:
        normalized_summary = "Combat concluded."

    return (
        f"{HISTORICAL_COMBAT_PREFIX}\n"
        f"{normalized_summary}\n"
        f"{HISTORICAL_COMBAT_SUFFIX}\n\n"
        f"{HISTORICAL_COMBAT_REWARD_GUARD}"
    )
