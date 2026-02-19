#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Unit-style assertions for character creation audit result classes."""

from copy import deepcopy
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.character_creation_audit import (
    AUDIT_RESULT_COMPLETENESS_ERROR,
    AUDIT_RESULT_SCHEMA_ERROR,
    AUDIT_RESULT_SUCCESS,
    audit_character_creation,
)


def _base_payload() -> dict:
    return {
        "name": "Audit Tester",
        "race": "Human",
        "class": "Fighter",
        "background": "Soldier",
        "personality_traits": "Disciplined and focused.",
        "ideals": "Duty.",
        "bonds": "My unit.",
        "flaws": "I overcommit.",
        "backgroundFeature": {
            "name": "Military Rank",
            "description": "I can pull rank with soldiers.",
            "source": "SRD 5.2.1",
        },
    }


def main() -> None:
    good_payload = _base_payload()
    success_result = audit_character_creation(good_payload, source="test", enable_enrichment=False)
    assert success_result.result_type == AUDIT_RESULT_SUCCESS, "Expected success result"

    schema_error_payload = deepcopy(good_payload)
    schema_error_payload["level"] = "invalid"
    schema_result = audit_character_creation(schema_error_payload, source="test", enable_enrichment=False)
    assert schema_result.result_type == AUDIT_RESULT_SCHEMA_ERROR, "Expected schema_error result"

    completeness_payload = deepcopy(good_payload)
    completeness_payload["personality_traits"] = ""
    completeness_result = audit_character_creation(completeness_payload, source="test", enable_enrichment=False)
    assert completeness_result.result_type == AUDIT_RESULT_COMPLETENESS_ERROR, "Expected completeness_error result"

    print("[PASS] character_creation_audit deterministic result classes validated")


if __name__ == "__main__":
    main()
