#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Source-contract checks for /api/party/finalize_creation shared-finalizer wiring."""

from pathlib import Path


def _load_route_source() -> str:
    project_root = Path(__file__).resolve().parents[1]
    route_file = project_root / "web" / "routes" / "tabletop_party_routes.py"
    return route_file.read_text(encoding="utf-8")


def _extract_finalize_route_function(source: str) -> str:
    start_marker = "def finalize_character_creation() -> Any:"
    end_marker = "@app.route('/api/party/creation_status', methods=['GET'])"
    start_index = source.find(start_marker)
    end_index = source.find(end_marker)
    assert start_index != -1, "finalize_character_creation route should exist"
    assert end_index != -1 and end_index > start_index, "creation_status route marker should follow finalize route"
    return source[start_index:end_index]


def test_route_imports_shared_services() -> None:
    source = _load_route_source()
    assert "finalize_character_creation_candidate" in source, "Route module should import shared finalization service"
    assert "persist_dm_created_character" in source, "Route module should import shared persistence helper"


def test_finalize_route_uses_shared_services() -> None:
    source = _load_route_source()
    function_source = _extract_finalize_route_function(source)

    assert "finalize_character_creation_candidate(" in function_source, "Finalize route should call shared finalizer"
    assert "persist_dm_created_character(" in function_source, "Finalize route should call shared persistence helper"


def test_finalize_route_removed_duplicate_inline_ownership() -> None:
    source = _load_route_source()
    function_source = _extract_finalize_route_function(source)

    assert "audit_character_creation(" not in function_source, "Inline audit call should be removed from finalize route"
    assert "safe_write_json(char_path" not in function_source, "Inline character save should be removed from finalize route"


def test_finalize_route_http_contract_paths_present() -> None:
    source = _load_route_source()
    function_source = _extract_finalize_route_function(source)

    assert "'Character data required'" in function_source, "Finalize route should retain 400 input guard"
    assert "}), 400" in function_source, "Finalize route should keep explicit 400 response paths"
    assert "}), 500" in function_source, "Finalize route should keep explicit 500 response paths"
    assert "'message': f'Character {character_name} created successfully!'" in function_source, (
        "Finalize route should keep success payload contract"
    )


def main() -> None:
    test_route_imports_shared_services()
    print("[PASS] route imports shared finalizer and persistence services")

    test_finalize_route_uses_shared_services()
    print("[PASS] finalize route uses shared finalizer and persistence helper")

    test_finalize_route_removed_duplicate_inline_ownership()
    print("[PASS] finalize route removed duplicate inline ownership")

    test_finalize_route_http_contract_paths_present()
    print("[PASS] finalize route keeps HTTP adapter response paths")

    print("[PASS] finalize_creation route shared-adapter wiring checks")


if __name__ == "__main__":
    main()
