#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Focused regression checks for shared DM character-creation prompt builder."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.character_creation_prompt_builder import build_dm_creation_prompt_bundle


def test_mid_campaign_prompt_contract() -> None:
    """Mid-campaign mode builds prompt with resolved placeholders."""
    bundle = build_dm_creation_prompt_bundle(
        mode="mid_campaign",
        module_name="The_Thornwood_Watch",
        character_name="Valerius",
        level=3,
        party_tracker={
            "partyMembers": ["Blairen", "Vitreol", "Chronos"],
            "worldConditions": {
                "currentLocation": "Rangers' Command Post",
                "currentArea": "Rangers' Outpost",
            },
        },
        is_mid_campaign=True,
        active_pc="Blairen",
        current_location="Rangers' Command Post",
    )

    system_prompt = bundle.get("system_prompt", "")
    assert system_prompt, "Mid-campaign system prompt should not be empty"
    assert "{module_name}" not in system_prompt, "module_name placeholder should be resolved"
    assert "{level_context}" not in system_prompt, "level_context placeholder should be resolved"
    assert "{experience_points}" not in system_prompt, "experience_points placeholder should be resolved"
    assert "{exp_next}" not in system_prompt, "exp_next placeholder should be resolved"
    assert "# SPDX" not in system_prompt, "Prompt header comments should not leak"
    assert "=== FINAL OUTPUT - COMPLETE JSON ===" in system_prompt, "Canonical final JSON contract should be present"
    assert "Begin by asking what kind of hero they want to become!" in system_prompt, "Prompt close should remain present"
    assert "MID-CAMPAIGN ADDITION:" in system_prompt, "Mid-campaign mode context should be present"
    assert "The party currently consists of: Blairen, Vitreol, Chronos." in system_prompt, "Party context should be present"
    assert "Blairen is currently the active party member at Rangers' Command Post." in system_prompt, "Active PC context should be present"
    assert "CHARACTER LEVEL: 3" in system_prompt, "Requested target level context should be present"
    assert "kickoff_user_prompt" in bundle, "Bundle must include kickoff_user_prompt key"


def test_startup_prompt_contract() -> None:
    """Startup mode builds canonical startup-aligned prompt bundle."""
    bundle = build_dm_creation_prompt_bundle(
        mode="startup",
        module_name="The Thornwood Watch",
        character_name="Starter",
        level=1,
    )

    system_prompt = bundle.get("system_prompt", "")
    kickoff_user_prompt = bundle.get("kickoff_user_prompt", "")

    assert system_prompt, "Startup system prompt should not be empty"
    assert kickoff_user_prompt, "Startup kickoff user prompt should not be empty"
    assert "CHARACTER SCHEMA:" in system_prompt, "Startup system prompt should embed schema guidance"
    assert "experience_points set to 0" in system_prompt, "Startup baseline level-1 contract should be preserved"
    assert "The Thornwood Watch adventure" in kickoff_user_prompt, "Kickoff prompt should include module name"
    assert "what kind of hero they want to become" in kickoff_user_prompt, "Startup kickoff hero framing should remain"
    assert "Let's get you started by finding out a little bit about you" in kickoff_user_prompt, "Startup kickoff phrase should remain"


def test_invalid_mode_fails_closed() -> None:
    """Invalid prompt mode should fail closed with ValueError."""
    try:
        build_dm_creation_prompt_bundle(
            mode="invalid-mode",
            module_name="Test",
            character_name="Tester",
        )
    except ValueError:
        return
    raise AssertionError("Invalid mode should raise ValueError")


def test_startup_wizard_uses_shared_prompt_builder() -> None:
    """Startup adapter should source prompts from shared builder, not inline block text."""
    project_root = Path(__file__).resolve().parents[1]
    startup_source = (project_root / "utils" / "startup_wizard.py").read_text(encoding="utf-8")

    assert "from utils.character_creation_prompt_builder import build_dm_creation_prompt_bundle" in startup_source, (
        "startup_wizard should import shared prompt builder"
    )
    assert "build_dm_creation_prompt_bundle(" in startup_source, (
        "startup_wizard should call shared prompt builder"
    )
    assert "base_system_content =" not in startup_source, (
        "legacy inline startup prompt block should be removed"
    )


def test_startup_wizard_creation_conversation_seed_contract() -> None:
    """Startup interview should still seed one system and one kickoff user message."""
    project_root = Path(__file__).resolve().parents[1]
    startup_source = (project_root / "utils" / "startup_wizard.py").read_text(encoding="utf-8")

    assert "creation_conversation = [" in startup_source, "Startup should initialize creation conversation"
    assert "{\"role\": \"system\", \"content\": enhanced_system_prompt}" in startup_source, (
        "Startup should seed system prompt entry"
    )
    assert "{\"role\": \"user\", \"content\": kickoff_user_prompt}" in startup_source, (
        "Startup should seed kickoff user prompt entry"
    )


def main() -> None:
    test_mid_campaign_prompt_contract()
    print("[PASS] mid-campaign prompt contract")

    test_startup_prompt_contract()
    print("[PASS] startup prompt contract")

    test_invalid_mode_fails_closed()
    print("[PASS] invalid mode fail-closed contract")

    test_startup_wizard_uses_shared_prompt_builder()
    print("[PASS] startup wizard shared prompt builder wiring")

    test_startup_wizard_creation_conversation_seed_contract()
    print("[PASS] startup wizard creation conversation seed contract")

    print("[PASS] shared character creation prompt builder regression checks")


if __name__ == "__main__":
    main()
