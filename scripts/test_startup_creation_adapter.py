#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Source-contract checks for startup wizard shared finalization/persistence wiring (Step 3.2)."""

from pathlib import Path


def _load_startup_source() -> str:
    project_root = Path(__file__).resolve().parents[1]
    return (project_root / "utils" / "startup_wizard.py").read_text(encoding="utf-8")


def _extract_function(source: str, start_marker: str, end_marker: str) -> str:
    start_index = source.find(start_marker)
    end_index = source.find(end_marker)
    assert start_index != -1, f"Missing function start marker: {start_marker}"
    assert end_index != -1 and end_index > start_index, f"Missing function end marker: {end_marker}"
    return source[start_index:end_index]


def test_startup_imports_shared_finalization_and_persistence_services() -> None:
    source = _load_startup_source()
    assert "from utils.character_creator import finalize_character_creation_candidate, persist_dm_created_character" in source, (
        "startup_wizard should import shared finalization and persistence helpers"
    )


def test_ai_interview_uses_shared_finalization_contract() -> None:
    source = _load_startup_source()
    function_source = _extract_function(
        source,
        "def ai_character_interview(conversation, module, retry_count=0):",
        "def load_text_file(filename):",
    )

    assert "finalize_character_creation_candidate(" in function_source, "Startup interview should call shared finalizer"
    assert 'if finalize_status == "success":' in function_source, "Startup interview should handle success status"
    assert 'if finalize_status == "needs_retry":' in function_source, "Startup interview should handle retry status"
    assert 'if finalize_status == "error":' in function_source, "Startup interview should handle error status"
    assert "return None" in function_source, "Startup interview should fail closed on shared finalizer error"


def test_ai_interview_only_prints_raw_response_for_non_candidates() -> None:
    source = _load_startup_source()
    function_source = _extract_function(
        source,
        "def ai_character_interview(conversation, module, retry_count=0):",
        "def load_text_file(filename):",
    )

    assert 'if finalize_status != "not_candidate":' in function_source, (
        "Startup interview should only print raw AI output for non-candidate responses"
    )
    finalize_index = function_source.find("finalize_character_creation_candidate(")
    raw_print_index = function_source.find('print(f"\\nDungeon Master: {response}")')
    assert finalize_index != -1 and raw_print_index != -1 and finalize_index < raw_print_index, (
        "Startup interview must finalize-check before printing raw AI output"
    )


def test_create_new_character_uses_shared_persistence_contract() -> None:
    source = _load_startup_source()
    function_source = _extract_function(
        source,
        "def create_new_character(conversation, module):",
        "def create_fallback_character(module):",
    )

    assert "persist_dm_created_character(character_data)" in function_source, (
        "Startup character creation should persist through shared helper"
    )
    assert "audit_character_creation(" not in function_source, (
        "Startup adapter should not keep duplicate inline audit call"
    )


def test_startup_incomplete_lifecycle_contract_remains_present() -> None:
    source = _load_startup_source()
    assert "startup_incomplete=True" in source, "Startup incomplete lifecycle markers should remain"
    assert "startup_incomplete=False" in source, "Startup completion lifecycle marker should remain"
    assert "def update_party_tracker(module_name, character_name, startup_incomplete=None):" in source, (
        "startup tracker API contract should remain unchanged"
    )


def main() -> None:
    test_startup_imports_shared_finalization_and_persistence_services()
    print("[PASS] startup imports shared finalization and persistence services")

    test_ai_interview_uses_shared_finalization_contract()
    print("[PASS] startup interview uses shared finalization contract")

    test_ai_interview_only_prints_raw_response_for_non_candidates()
    print("[PASS] startup interview suppresses raw final JSON output")

    test_create_new_character_uses_shared_persistence_contract()
    print("[PASS] startup create_new_character uses shared persistence contract")

    test_startup_incomplete_lifecycle_contract_remains_present()
    print("[PASS] startup incomplete lifecycle contract remains present")

    print("[PASS] startup character creation adapter wiring checks")


if __name__ == "__main__":
    main()
