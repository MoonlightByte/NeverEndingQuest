# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Web Extension - Start Game Preflight Helper
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

from pathlib import Path
from typing import Any, Dict, List

from core.validation.validate_module_files import ModuleValidator
from utils.enhanced_logger import debug, error, info, warning
from utils.file_operations import safe_read_json


def _build_payload(
    status: str,
    module_name: str,
    reference_failed: int,
    reference_errors: List[str],
    message: str,
) -> Dict[str, Any]:
    """Build deterministic start-game preflight payload."""
    return {
        "status": status,
        "module": module_name,
        "reference_failed": reference_failed,
        "reference_errors": reference_errors,
        "message": message,
    }


def _run_module_validation(module_path: Path) -> tuple[int, List[str]]:
    """Run validation and return normalized reference_integrity result.

    Returns:
        tuple of (failed_count, list_of_error_messages)
    """
    validator = ModuleValidator(module_path, ".")
    validator.run_all_validations()

    ref_int = validator.results.get("reference_integrity", {})
    failed_count = int(ref_int.get("failed", 0) or 0)
    errors = ref_int.get("errors", [])

    if not isinstance(errors, list):
        errors = [str(errors)]
    errors = [str(item) for item in errors]

    return failed_count, errors


def _attempt_remediation(module_name: str, module_path: Path) -> bool:
    """Execute one monster reference closure attempt.

    Args:
        module_name: Normalized module name
        module_path: Path to module directory

    Returns:
        True if closure attempt completed (regardless of resolution),
        False if attempt failed to complete.
    """
    try:
        info(
            f"Remediation attempt starting: module={module_name}",
            category="module_validation",
        )

        # Lazy import to avoid module-level OpenAI dependency issues
        from core.generators.module_generator import ModuleGenerator
        generator = ModuleGenerator()
        module_dir = str(module_path)

        # Execute exactly one closure attempt
        closure_report = generator._ensure_monster_reference_closure(
            module_name, module_dir
        )

        unresolved_after = closure_report.get("unresolved", 0)
        generated = closure_report.get("generated", 0)

        info(
            f"Remediation complete: module={module_name} generated={generated} unresolved={unresolved_after}",
            category="module_validation",
        )
        return True

    except Exception as exc:
        warning(
            f"Remediation attempt failed: module={module_name} error={exc}",
            category="module_validation",
        )
        return False


def run_start_game_module_preflight() -> Dict[str, Any]:
    """Run module validation preflight for start_game with one remediation attempt.

    Terminal status contract (MUST):
    - "pass": Initial validation success, no remediation needed.
    - "repaired_pass": Initial validation failed, one remediation attempted,
      and re-validation passed.
    - "fail": Any terminal failure condition including missing party tracker,
      missing module, unresolved references after remediation, or unexpected errors.

    Payload keys:
    - status: one of "pass" | "repaired_pass" | "fail"
    - module: normalized module slug or empty string
    - reference_failed: integer unresolved count
    - reference_errors: list of unresolved-reference messages
    - message: concise operator-facing text (actionable on fail)

    One-attempt remediation:
    1) Initial validation
    2) If unresolved present, attempt closure exactly once
    3) Re-validate immediately
    4) Return terminal status based on post-remediation result
    """
    try:
        party_tracker = safe_read_json("party_tracker.json")
        if not party_tracker:
            warning(
                "Start-game preflight: party_tracker.json missing or unreadable",
                category="module_validation",
            )
            return _build_payload(
                status="fail",
                module_name="",
                reference_failed=0,
                reference_errors=[],
                message="[SYSTEM] Module preflight failed: party tracker missing or unreadable. Ensure a campaign is active.",
            )

        raw_module = str(party_tracker.get("module", "")).strip()
        if not raw_module:
            warning(
                "Start-game preflight: no module set in party tracker",
                category="module_validation",
            )
            return _build_payload(
                status="fail",
                module_name="",
                reference_failed=0,
                reference_errors=[],
                message="[SYSTEM] Module preflight failed: no active module selected. Select a module in Settings before starting.",
            )

        module_name = raw_module.replace(" ", "_")
        module_path = Path("modules") / module_name
        if not module_path.exists():
            warning(
                f"Start-game preflight: module path missing: {module_path}",
                category="module_validation",
            )
            return _build_payload(
                status="fail",
                module_name=module_name,
                reference_failed=0,
                reference_errors=[],
                message=(
                    f"[SYSTEM] Module preflight failed: module '{module_name}' not found. "
                    "Verify module installation or select a different module."
                ),
            )

        # Step 1: Initial validation
        failed_count, errors = _run_module_validation(module_path)

        # Step 2: One-attempt remediation if needed
        if failed_count > 0:
            debug(
                f"Start-game preflight initial validation failed: module={module_name} unresolved={failed_count}",
                category="module_validation",
            )

            remediation_completed = _attempt_remediation(module_name, module_path)

            if remediation_completed:
                # Step 3: Re-validate after remediation
                debug(
                    f"Start-game preflight re-validating after remediation: module={module_name}",
                    category="module_validation",
                )
                failed_count, errors = _run_module_validation(module_path)

                if failed_count == 0:
                    info(
                        f"Start-game preflight remediation succeeded: module={module_name}",
                        category="module_validation",
                    )
                    # Return repaired_pass status - remediation fixed the issue
                    return _build_payload(
                        status="repaired_pass",
                        module_name=module_name,
                        reference_failed=0,
                        reference_errors=[],
                        message=f"[SYSTEM] Module preflight repaired and passed for {module_name}.",
                    )
                else:
                    debug(
                        f"Start-game preflight still unresolved after remediation: module={module_name} unresolved={failed_count}",
                        category="module_validation",
                    )
            else:
                warning(
                    f"Start-game preflight remediation attempt failed: module={module_name}",
                    category="module_validation",
                )

            # Return fail status - unresolved references remain after remediation
            return _build_payload(
                status="fail",
                module_name=module_name,
                reference_failed=failed_count,
                reference_errors=errors,
                message=(
                    f"[SYSTEM] Module preflight failed for {module_name}: "
                    f"{failed_count} unresolved monster reference(s) after remediation. "
                    f"ACTION: Run 'python scripts/generate_missing_monsters.py {module_name}' "
                    f"to generate missing stat files, then retry Start Game."
                ),
            )

        info(
            f"Start-game preflight pass: module={module_name}",
            category="module_validation",
        )
        return _build_payload(
            status="pass",
            module_name=module_name,
            reference_failed=0,
            reference_errors=[],
            message=f"[SYSTEM] Module preflight passed for {module_name}.",
        )

    except Exception as exc:
        error(
            f"Start-game preflight unexpected error: {exc}",
            category="module_validation",
        )
        return _build_payload(
            status="fail",
            module_name="",
            reference_failed=0,
            reference_errors=[],
            message=(
                "[SYSTEM] Module preflight failed: unexpected error during validation. "
                "Check debug logs for details and retry Start Game."
            ),
        )
