#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Source-contract checks for main.py character creation adapter wiring (Step 3.1)."""

from pathlib import Path


def _load_main_source() -> str:
    project_root = Path(__file__).resolve().parents[1]
    return (project_root / "main.py").read_text(encoding="utf-8")


def _extract_handle_creation_function(source: str) -> str:
    start_marker = "def handle_character_creation_response(response, party_tracker_data, conversation_history):"
    end_marker = "def process_ai_response(response, party_tracker_data, location_data, conversation_history):"
    start_index = source.find(start_marker)
    end_index = source.find(end_marker)

    assert start_index != -1, "handle_character_creation_response function must exist"
    assert end_index != -1 and end_index > start_index, "process_ai_response marker must exist after handler"

    return source[start_index:end_index]


def test_main_imports_shared_creation_services() -> None:
    source = _load_main_source()
    assert "finalize_character_creation_candidate" in source, "main.py should import shared finalization service"
    assert "persist_dm_created_character" in source, "main.py should import shared persistence helper"
    assert "abort_character_creation_session" in source, "main.py should import shared creation abort helper"
    assert "recover_poisoned_creation_session_on_startup" in source, "main.py should import startup recovery helper"


def test_handle_creation_uses_shared_finalizer_and_persistence() -> None:
    source = _load_main_source()
    function_source = _extract_handle_creation_function(source)

    assert "finalize_character_creation_candidate(" in function_source, "Handler should call shared finalizer"
    assert "persist_dm_created_character(" in function_source, "Handler should call shared persistence helper"


def test_handle_creation_removes_inline_audit_logic() -> None:
    source = _load_main_source()
    function_source = _extract_handle_creation_function(source)

    assert "audit_character_creation(" not in function_source, "Inline audit call should be removed from main adapter"
    assert "AUDIT_RESULT_SUCCESS" not in function_source, "Inline audit result branching should be removed"
    assert "safe_json_dump(character_data, char_path)" not in function_source, "Inline character file save should be removed"


def test_handle_creation_preserves_retry_and_non_candidate_behavior() -> None:
    source = _load_main_source()
    function_source = _extract_handle_creation_function(source)

    assert 'if finalize_status == "not_candidate":' in function_source, "Handler should preserve non-candidate fast return"
    assert 'if finalize_status == "needs_retry":' in function_source, "Handler should preserve correction loop path"
    assert 'conversation_history.append({"role": "user", "content": corrective_note})' in function_source, "Retry path should append corrective note"
    assert "Character JSON incomplete. Creation mode remains active." in function_source, "Retry path should preserve user-visible guidance"
    assert 'return "needs_retry"' in function_source, "Retry path should return structured retry status"


def test_handle_creation_returns_structured_statuses() -> None:
    source = _load_main_source()
    function_source = _extract_handle_creation_function(source)

    assert 'return "not_candidate"' in function_source, "Handler should return not_candidate status"
    assert 'return "needs_retry"' in function_source, "Handler should return needs_retry status"
    assert 'return "finalized"' in function_source, "Handler should return finalized status"
    assert 'return "error"' in function_source, "Handler should return error status"


def test_main_loop_reenters_creation_retry_flow() -> None:
    source = _load_main_source()

    assert 'elif final_result == "creation_retry":' in source, "Main loop should recognize creation retry signal"
    assert 'valid_response_received = False' in source, "Creation retry should re-open the outer AI loop"
    assert 'abort_character_creation_session(reason="final_json_retry_exhausted")' in source, (
        "Retry exhaustion should abort and clean the creation session"
    )
    assert 'elif final_result == "creation_error":' in source, "Main loop should recognize creation error signal"
    assert 'abort_character_creation_session(reason="creation_terminal_error")' in source, (
        "Terminal creation errors should abort and clean the creation session"
    )


def test_main_game_loop_recovers_poisoned_creation_session_on_startup() -> None:
    source = _load_main_source()

    assert 'recovery_result = recover_poisoned_creation_session_on_startup()' in source, (
        "main_game_loop should run poisoned creation recovery during startup"
    )
    assert 'if recovery_result.get("recovered"):' in source, (
        "main_game_loop should branch on successful poisoned-session recovery"
    )


def main() -> None:
    test_main_imports_shared_creation_services()
    print("[PASS] main imports shared creation services")

    test_handle_creation_uses_shared_finalizer_and_persistence()
    print("[PASS] handler uses shared finalizer and persistence")

    test_handle_creation_removes_inline_audit_logic()
    print("[PASS] handler removed inline audit/save logic")

    test_handle_creation_preserves_retry_and_non_candidate_behavior()
    print("[PASS] handler preserves retry and non-candidate behavior")

    test_handle_creation_returns_structured_statuses()
    print("[PASS] handler returns structured creation statuses")

    test_main_loop_reenters_creation_retry_flow()
    print("[PASS] main loop re-enters creation retry flow")

    test_main_game_loop_recovers_poisoned_creation_session_on_startup()
    print("[PASS] main game loop recovers poisoned creation sessions on startup")

    print("[PASS] main character creation adapter wiring checks")


if __name__ == "__main__":
    main()
