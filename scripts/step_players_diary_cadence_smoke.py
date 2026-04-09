# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Manual smoke pass for players diary journal cadence hardening."""

import json
import os
import shutil
import sys
import tempfile
from unittest import mock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.ai.cumulative_summary import (
    build_transition_checkpoint_metadata,
    maybe_create_long_rest_journal_checkpoint,
    update_journal_with_summary,
)


def _write_json(path: str, payload: dict) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def _read_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    temp_dir = tempfile.mkdtemp(prefix="neq_diary_cadence_smoke_")
    previous_cwd = os.getcwd()
    os.chdir(temp_dir)
    try:
        party_tracker = {
            "module": "Night_of_the_Restless_Dead",
            "partyMembers": ["Acheron"],
            "active_character": "Acheron",
            "worldConditions": {
                "year": 1492,
                "month": "Ches",
                "day": 21,
                "time": "06:00:00",
                "currentLocation": "Ma's Watering Hole",
                "currentLocationId": "NIG01",
                "currentAreaId": "NIG001",
            },
        }
        os.makedirs("modules/logs", exist_ok=True)
        os.makedirs("characters", exist_ok=True)
        _write_json("party_tracker.json", party_tracker)
        _write_json("characters/acheron.json", {"name": "Acheron", "level": 1})
        _write_json("journal.json", {"entries": []})

        # Scenario 1: Transition checkpoint
        transition_metadata = build_transition_checkpoint_metadata(
            "Location transition: Priest's Lodging (NIG04) to Brother Lintar's Place (NIG08)",
            party_tracker,
            source_location="Priest's Lodging",
            source_location_id="NIG04",
        )
        transition_ok = update_journal_with_summary(
            "Transition checkpoint summary",
            party_tracker,
            "Priest's Lodging",
            checkpoint_metadata=transition_metadata,
        )

        # Scenario 2: Same-location long-rest checkpoint with meaningful delta
        conversation_history = [
            {
                "role": "user",
                "content": "Location transition: Ma's Watering Hole (NIG01) to Priest's Lodging (NIG04)",
            },
            {"role": "user", "content": "I investigate the altar for hidden clues."},
            {
                "role": "assistant",
                "content": "You uncover an etched sigil beneath the dust.",
            },
            {"role": "user", "content": "We take a long rest."},
        ]
        with mock.patch(
            "core.ai.cumulative_summary.generate_enhanced_summary_from_messages",
            return_value="Long-rest checkpoint summary",
        ):
            long_rest_result = maybe_create_long_rest_journal_checkpoint(
                conversation_history,
                party_tracker,
            )

        # Scenario 3: Rest success when journal generation degrades
        import core.ai.action_handler as action_handler

        action = {
            "action": "rest",
            "parameters": {"type": "long", "characters": ["Acheron"]},
        }
        rest_history = []
        with (
            mock.patch.object(
                action_handler,
                "_process_character_rest",
                return_value={
                    "character": "Acheron",
                    "rest_type": "long",
                    "hp_restored": 12,
                    "spell_slots_restored": 2,
                    "features_reset": [],
                    "exhaustion_reduced": False,
                },
            ),
            mock.patch(
                "core.ai.cumulative_summary.maybe_create_long_rest_journal_checkpoint",
                side_effect=RuntimeError("forced journal failure"),
            ),
        ):
            rest_result = action_handler.process_action(
                action,
                party_tracker,
                {},
                rest_history,
            )

        journal_entries = _read_json("journal.json").get("entries", [])

        checks = [
            (transition_ok is True, "transition checkpoint"),
            (
                long_rest_result.get("status") == "written",
                "same-location long-rest checkpoint",
            ),
            (
                rest_result.get("status") == "continue"
                and rest_result.get("needs_update") is True
                and len(rest_history) == 1,
                "rest success when journal degrades",
            ),
            (len(journal_entries) >= 2, "journal entry count"),
        ]

        failed = [label for passed, label in checks if not passed]
        if failed:
            for label in failed:
                print(f"[FAIL] {label}")
            return 1

        print("[PASS] transition checkpoint")
        print("[PASS] same-location long-rest checkpoint")
        print("[PASS] rest success when journal degrades")
        return 0
    finally:
        os.chdir(previous_cwd)
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
