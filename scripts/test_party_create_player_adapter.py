#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Source-contract checks for /api/party/create_player fail-closed activation wiring."""

from pathlib import Path


def _load_route_source() -> str:
    project_root = Path(__file__).resolve().parents[1]
    route_file = project_root / "web" / "routes" / "tabletop_party_routes.py"
    return route_file.read_text(encoding="utf-8")


def _extract_create_route_function(source: str) -> str:
    start_marker = "def create_party_player() -> Any:"
    end_marker = "@app.route('/api/party/finalize_creation', methods=['POST'])"
    start_index = source.find(start_marker)
    end_index = source.find(end_marker)
    assert start_index != -1, "create_party_player route should exist"
    assert end_index != -1 and end_index > start_index, "finalize route marker should follow create route"
    return source[start_index:end_index]


def test_create_route_requires_marker_write_success() -> None:
    source = _load_route_source()
    function_source = _extract_create_route_function(source)

    assert "marker_saved = safe_write_json(CHARACTER_CREATION_MARKER" in function_source, (
        "Create route should capture marker write result"
    )
    assert "if not marker_saved:" in function_source, "Create route should fail closed on marker write failure"
    assert "Failed to activate character creation mode. Please try again." in function_source, (
        "Create route should return deterministic marker activation failure guidance"
    )
    assert "creation_marker_written = True" in function_source, "Create route should track post-marker activation state"


def test_create_route_aborts_if_post_marker_activation_fails() -> None:
    source = _load_route_source()
    function_source = _extract_create_route_function(source)

    assert "if creation_marker_written:" in function_source, (
        "Create route exception path should branch on post-marker activation state"
    )
    assert 'abort_character_creation_session(reason="web_create_player_route_error")' in function_source, (
        "Create route should abort stale session on post-marker activation failure"
    )


def main() -> None:
    test_create_route_requires_marker_write_success()
    print("[PASS] create_player route requires marker write success")

    test_create_route_aborts_if_post_marker_activation_fails()
    print("[PASS] create_player route aborts stale session after post-marker activation failures")

    print("[PASS] create_player route fail-closed adapter checks")


if __name__ == "__main__":
    main()
