#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Focused regression checks for shared character-creation finalizer service."""

import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.character_creator import (
    FINALIZE_STATUS_ERROR,
    FINALIZE_STATUS_NEEDS_RETRY,
    FINALIZE_STATUS_NOT_CANDIDATE,
    FINALIZE_STATUS_SUCCESS,
    finalize_character_creation_candidate,
    persist_dm_created_character,
)


def _valid_payload() -> dict:
    return {
        "name": "Audit Tester",
        "race": "Human",
        "class": "Fighter",
        "background": "Soldier",
        "personality_traits": "Disciplined and focused.",
        "ideals": "Duty.",
        "bonds": "My unit.",
        "flaws": "I overcommit.",
        "backstory": "Former soldier seeking new purpose.",
        "backgroundFeature": {
            "name": "Military Rank",
            "description": "I can pull rank with soldiers.",
            "source": "SRD 5.2.1",
        },
    }


def test_valid_raw_json_success() -> None:
    raw = json.dumps(_valid_payload())
    mock_audit = SimpleNamespace(
        result_type="success",
        normalized_data={"name": "Audit Tester", "class": "Fighter"},
        missing_paths=[],
    )
    with patch("utils.character_creator._imported_audit_character_creation", return_value=mock_audit):
        result = finalize_character_creation_candidate(raw, source="test_finalizer_raw")

    assert result.get("status") == FINALIZE_STATUS_SUCCESS, "Valid raw JSON should succeed"
    assert isinstance(result.get("character_data"), dict), "Success should include normalized character data"
    assert result.get("character_data", {}).get("name") == "Audit Tester", "Success payload should preserve normalized character name"
    assert result.get("corrective_guidance") == "", "Success should not include corrective guidance"
    assert result.get("audit_result_type") == "success", "Success should expose audit success result type"
    assert result.get("missing_paths") == [], "Success should not include missing paths"
    assert result.get("error_message") == "", "Success should not include error message"


def test_valid_fenced_json_success() -> None:
    raw = "Narration preface\n```json\n" + json.dumps(_valid_payload()) + "\n```\nNarration epilogue"
    mock_audit = SimpleNamespace(
        result_type="success",
        normalized_data={"name": "Audit Tester", "class": "Fighter"},
        missing_paths=[],
    )
    with patch("utils.character_creator._imported_audit_character_creation", return_value=mock_audit):
        result = finalize_character_creation_candidate(raw, source="test_finalizer_fenced")

    assert result.get("status") == FINALIZE_STATUS_SUCCESS, "Valid fenced JSON should succeed"
    assert isinstance(result.get("character_data"), dict), "Success should include normalized character data"
    assert result.get("character_data", {}).get("name") == "Audit Tester", "Fenced JSON extraction should preserve parsed payload"
    assert result.get("audit_result_type") == "success", "Fenced success should expose audit success result type"
    assert result.get("missing_paths") == [], "Fenced success should not include missing paths"
    assert result.get("error_message") == "", "Fenced success should not include error message"


def test_malformed_json_needs_retry() -> None:
    raw = '{"name": "Broken",}'
    result = finalize_character_creation_candidate(raw, source="test_finalizer_malformed")

    assert result.get("status") == FINALIZE_STATUS_NEEDS_RETRY, "Malformed JSON should request retry"
    assert result.get("audit_result_type") == "json_decode_error", "Malformed parse should report json_decode_error"
    assert result.get("character_data") is None, "Malformed JSON should not return character data"
    assert result.get("missing_paths") == ["$"], "Malformed JSON should expose root missing path marker"
    assert result.get("error_message"), "Malformed JSON should include parse error details"
    assert "Output a single corrected JSON object" in result.get("corrective_guidance", ""), "Retry should include deterministic corrective guidance"


def test_audit_failure_needs_retry() -> None:
    raw = json.dumps(_valid_payload())
    mock_audit = SimpleNamespace(
        result_type="schema_error",
        normalized_data=None,
        missing_paths=["backstory"],
    )
    with patch("utils.character_creator._imported_audit_character_creation", return_value=mock_audit):
        result = finalize_character_creation_candidate(raw, source="test_finalizer_audit_fail")

    assert result.get("status") == FINALIZE_STATUS_NEEDS_RETRY, "Audit failure should request retry"
    assert result.get("character_data") is None, "Audit failure should not return character data"
    assert result.get("audit_result_type") == "schema_error", "Audit failure should include result type"
    assert result.get("missing_paths") == ["backstory"], "Audit failure should expose missing paths from audit result"
    assert result.get("error_message") == "", "Audit failure should not set unexpected error message"
    assert "backstory" in result.get("corrective_guidance", ""), "Retry guidance should surface missing field"


def test_unexpected_exception_returns_error() -> None:
    with patch("utils.character_creator._imported_audit_character_creation", side_effect=RuntimeError("forced error")):
        raw = json.dumps(_valid_payload())
        result = finalize_character_creation_candidate(raw, source="test_finalizer_error")

    assert result.get("status") == FINALIZE_STATUS_ERROR, "Unexpected exception should fail closed as error"
    assert result.get("character_data") is None, "Error result should not include character data"
    assert result.get("corrective_guidance") == "", "Error result should not include retry guidance"
    assert result.get("missing_paths") == [], "Error result should not include missing paths"
    assert "forced error" in result.get("error_message", ""), "Error result should include exception details"


def test_non_candidate_response_returns_not_candidate() -> None:
    result = finalize_character_creation_candidate("Not JSON output", source="test_non_candidate")

    assert result.get("status") == FINALIZE_STATUS_NOT_CANDIDATE, "Non-JSON response should not be treated as a finalization candidate"
    assert result.get("character_data") is None, "Non-candidate should not include character data"
    assert result.get("corrective_guidance") == "", "Non-candidate should not include retry guidance"
    assert result.get("audit_result_type") == "", "Non-candidate should not include audit result type"
    assert result.get("missing_paths") == [], "Non-candidate should not include missing paths"
    assert result.get("error_message") == "", "Non-candidate should not include error message"


def test_persist_dm_created_character_success() -> None:
    payload = _valid_payload()
    with tempfile.TemporaryDirectory() as temp_dir:
        result = persist_dm_created_character(payload, characters_dir=temp_dir)

        assert result.get("success") is True, "Valid character should persist successfully"
        assert result.get("filename") == "audit_tester.json", "Filename should follow deterministic normalization"
        assert os.path.exists(result.get("path", "")), "Persisted character file should exist"


def test_persist_dm_created_character_duplicate_rejected() -> None:
    payload = _valid_payload()
    with tempfile.TemporaryDirectory() as temp_dir:
        existing_path = os.path.join(temp_dir, "audit_tester.json")
        with open(existing_path, "w", encoding="utf-8") as file_handle:
            file_handle.write("{}")

        result = persist_dm_created_character(payload, characters_dir=temp_dir)

        assert result.get("success") is False, "Duplicate file should fail closed"
        assert result.get("error") == "character_file_exists", "Duplicate rejection should be deterministic"


def test_persist_dm_created_character_invalid_name_rejected() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        missing_name_result = persist_dm_created_character({}, characters_dir=temp_dir)
        blank_name_result = persist_dm_created_character({"name": "   "}, characters_dir=temp_dir)

        assert missing_name_result.get("success") is False, "Missing name should fail closed"
        assert missing_name_result.get("error") == "invalid_character_name", "Missing name error should be deterministic"
        assert blank_name_result.get("success") is False, "Blank name should fail closed"
        assert blank_name_result.get("error") == "invalid_character_name", "Blank name error should be deterministic"


def test_persist_dm_created_character_write_failure() -> None:
    payload = _valid_payload()
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch("utils.character_creator.safe_json_dump", side_effect=OSError("disk full")):
            result = persist_dm_created_character(payload, characters_dir=temp_dir)

        assert result.get("success") is False, "Write failures should fail closed"
        assert result.get("error", "").startswith("save_failed:"), "Write failures should include deterministic save_failed marker"


def main() -> None:
    test_valid_raw_json_success()
    print("[PASS] valid raw JSON finalization")

    test_valid_fenced_json_success()
    print("[PASS] valid fenced JSON finalization")

    test_malformed_json_needs_retry()
    print("[PASS] malformed JSON needs retry")

    test_audit_failure_needs_retry()
    print("[PASS] audit failure needs retry")

    test_unexpected_exception_returns_error()
    print("[PASS] unexpected exception fail-closed")

    test_non_candidate_response_returns_not_candidate()
    print("[PASS] non-candidate response")

    test_persist_dm_created_character_success()
    print("[PASS] shared persistence helper success")

    test_persist_dm_created_character_duplicate_rejected()
    print("[PASS] shared persistence helper duplicate rejection")

    test_persist_dm_created_character_invalid_name_rejected()
    print("[PASS] shared persistence helper invalid-name rejection")

    test_persist_dm_created_character_write_failure()
    print("[PASS] shared persistence helper write failure")

    print("[PASS] shared character creation finalizer regression checks")


if __name__ == "__main__":
    main()
