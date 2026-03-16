#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Cross-adapter source-contract checks for shared DM creation core (Step 3.4)."""

from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (_project_root() / relative_path).read_text(encoding="utf-8")


def _extract_between(source: str, start_marker: str, end_marker: str) -> str:
    start_index = source.find(start_marker)
    end_index = source.find(end_marker)
    assert start_index != -1, f"Missing start marker: {start_marker}"
    assert end_index != -1 and end_index > start_index, f"Missing end marker: {end_marker}"
    return source[start_index:end_index]


def test_startup_adapter_uses_shared_core() -> None:
    source = _read("utils/startup_wizard.py")
    assert "build_dm_creation_prompt_bundle(" in source, "Startup adapter should use shared prompt builder"
    assert "finalize_character_creation_candidate(" in source, "Startup adapter should use shared finalizer"
    assert "persist_dm_created_character(" in source, "Startup adapter should use shared persistence helper"


def test_main_adapter_uses_shared_core() -> None:
    source = _read("main.py")
    function_source = _extract_between(
        source,
        "def handle_character_creation_response(response, party_tracker_data, conversation_history):",
        "def process_ai_response(response, party_tracker_data, location_data, conversation_history):",
    )
    assert "finalize_character_creation_candidate(" in function_source, "Main adapter should use shared finalizer"
    assert "persist_dm_created_character(" in function_source, "Main adapter should use shared persistence helper"


def test_finalize_route_adapter_uses_shared_core() -> None:
    source = _read("web/routes/tabletop_party_routes.py")
    function_source = _extract_between(
        source,
        "def finalize_character_creation() -> Any:",
        "@app.route('/api/party/creation_status', methods=['GET'])",
    )
    assert "finalize_character_creation_candidate(" in function_source, "Finalize route should use shared finalizer"
    assert "persist_dm_created_character(" in function_source, "Finalize route should use shared persistence helper"


def test_roll_your_own_and_add_existing_non_regression() -> None:
    source = _read("web/routes/tabletop_party_routes.py")

    # Roll Your Own route remains present
    assert "@app.route('/api/party/create_manual', methods=['POST'])" in source, "Roll Your Own route should remain present"
    assert "def create_manual_character() -> Any:" in source, "Roll Your Own handler should remain present"

    # Add Existing flow routes remain present
    assert "@app.route('/api/party/characters')" in source, "Add Existing candidate route should remain present"
    assert "def get_party_characters_list() -> Any:" in source, "Add Existing candidate handler should remain present"
    assert "@app.route('/api/party/add_character', methods=['POST'])" in source, "Add Existing add route should remain present"
    assert "def add_party_character() -> Any:" in source, "Add Existing add handler should remain present"

    # Roll Your Own should remain independent from shared DM interview finalizer
    create_manual_source = _extract_between(
        source,
        "def create_manual_character() -> Any:",
        "@app.route('/api/party/update_manual', methods=['POST'])",
    )
    assert "finalize_character_creation_candidate(" not in create_manual_source, (
        "Roll Your Own flow should not be migrated into shared DM interview finalizer"
    )


def main() -> None:
    test_startup_adapter_uses_shared_core()
    print("[PASS] startup adapter uses shared DM creation core")

    test_main_adapter_uses_shared_core()
    print("[PASS] main adapter uses shared DM creation core")

    test_finalize_route_adapter_uses_shared_core()
    print("[PASS] finalize route adapter uses shared DM creation core")

    test_roll_your_own_and_add_existing_non_regression()
    print("[PASS] roll-your-own and add-existing non-regression checks")

    print("[PASS] cross-adapter shared DM creation contract checks")


if __name__ == "__main__":
    main()
