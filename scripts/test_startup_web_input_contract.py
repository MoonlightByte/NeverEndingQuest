#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Source-contract checks for startup web-input raw-mode handling."""

from pathlib import Path


def _load_web_interface_source() -> str:
    project_root = Path(__file__).resolve().parents[1]
    return (project_root / "web" / "web_interface.py").read_text(encoding="utf-8")


def _extract_handler(source: str, start_marker: str, end_marker: str) -> str:
    start_index = source.find(start_marker)
    end_index = source.find(end_marker)
    assert start_index != -1, f"Missing handler start marker: {start_marker}"
    assert end_index != -1 and end_index > start_index, f"Missing handler end marker: {end_marker}"
    return source[start_index:end_index]


def test_handle_user_input_skips_character_tagging_during_startup_incomplete() -> None:
    source = _load_web_interface_source()
    handler_source = _extract_handler(
        source,
        "@socketio.on('user_input')",
        "@socketio.on('action')",
    )

    assert 'party_tracker = safe_json_load("party_tracker.json") or {}' in handler_source, (
        "Web input handler should load party tracker state"
    )
    assert 'startup_incomplete = party_tracker.get("startup_incomplete") is True' in handler_source, (
        "Web input handler should detect startup-incomplete onboarding state"
    )
    assert "if character_name and not startup_incomplete:" in handler_source, (
        "Web input handler should skip character tagging during startup onboarding"
    )
    assert "queued_input = user_input" in handler_source, (
        "Startup onboarding path should preserve raw input without character tagging"
    )
    assert "user_input_queue.put(queued_input)" in handler_source, (
        "Web input handler should queue the processed input"
    )


def test_handle_user_input_echoes_before_queueing() -> None:
    source = _load_web_interface_source()
    handler_source = _extract_handler(
        source,
        "@socketio.on('user_input')",
        "@socketio.on('action')",
    )

    emit_pos = handler_source.find("emit('game_output', message)")
    cache_pos = handler_source.find("add_to_message_cache(message)")
    queue_pos = handler_source.find("user_input_queue.put(queued_input)")

    assert emit_pos != -1, "Web input handler should echo the user input to chat"
    assert cache_pos != -1, "Web input handler should cache echoed user input"
    assert queue_pos != -1, "Web input handler should queue the processed user input"
    assert emit_pos < queue_pos, (
        "User input should be echoed before queueing so combat feedback cannot overtake it"
    )
    assert cache_pos < queue_pos, (
        "Cached user input should be recorded before queueing the processed input"
    )


def main() -> None:
    test_handle_user_input_skips_character_tagging_during_startup_incomplete()
    test_handle_user_input_echoes_before_queueing()
    print("[PASS] startup web input contract checks")


if __name__ == "__main__":
    main()
