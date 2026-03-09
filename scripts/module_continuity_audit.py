#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Module continuity audit for continuity contract v1.

Checks additive continuity metadata in `module_context.json` and reports
blocking errors/warnings in machine-readable JSON for readiness tooling.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


REQUIRED_KEYS = [
    "continuity_version",
    "entry_state_variants",
    "cross_module_refs",
    "standalone_fallback",
]


def _load_json(path: Path) -> Tuple[Dict[str, Any], str]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            return {}, f"JSON root is not an object: {path}"
        return payload, ""
    except Exception as exc:
        return {}, f"Failed to read {path}: {exc}"


def _resolve_module_path(module: str = "", module_path: str = "") -> Path:
    if module_path:
        return Path(module_path)
    if module:
        return Path("modules") / module
    raise ValueError("Provide --module or --module-path")


def _list_known_modules(base_modules_dir: Path) -> List[str]:
    if not base_modules_dir.exists():
        return []
    out: List[str] = []
    for entry in base_modules_dir.iterdir():
        if entry.is_dir() and (entry / "areas").exists():
            out.append(entry.name)
    return out


def audit_module_continuity(module_dir: Path, strict: bool = False) -> Dict[str, Any]:
    module_context_path = module_dir / "module_context.json"
    module_plot_path = module_dir / "module_plot.json"

    blocking_errors: List[str] = []
    warnings: List[str] = []

    if not module_dir.exists():
        blocking_errors.append(f"Module directory not found: {module_dir}")
        return {
            "status": "fail",
            "module": module_dir.name,
            "module_path": str(module_dir),
            "continuity_version": None,
            "required_keys_present": [],
            "missing_required_keys": REQUIRED_KEYS,
            "blocking_errors": blocking_errors,
            "warnings": warnings,
            "strict": strict,
            "exit_code": 1,
        }

    module_context, err = _load_json(module_context_path)
    if err:
        blocking_errors.append(err)

    module_plot, plot_err = _load_json(module_plot_path)
    if plot_err:
        warnings.append(plot_err)

    continuity = module_context.get("continuity")
    if not isinstance(continuity, dict):
        continuity = {}

    required_keys_present = [key for key in REQUIRED_KEYS if continuity.get(key) is not None]
    missing_required = [key for key in REQUIRED_KEYS if key not in required_keys_present]

    if missing_required:
        msg = f"Missing required continuity keys: {missing_required}"
        if strict:
            blocking_errors.append(msg)
        else:
            warnings.append(msg)

    continuity_version = continuity.get("continuity_version")
    if continuity_version is not None and continuity_version != "v1":
        warnings.append(f"Unexpected continuity_version '{continuity_version}' (expected 'v1')")

    # entry_state_variants validation
    variants = continuity.get("entry_state_variants")
    if variants is not None:
        expected_variant_keys = ["cold_start", "partial_context", "late_arc"]
        if not isinstance(variants, dict):
            msg = "entry_state_variants must be an object"
            if strict:
                blocking_errors.append(msg)
            else:
                warnings.append(msg)
        else:
            missing_variant_keys = [key for key in expected_variant_keys if key not in variants]
            if missing_variant_keys:
                msg = f"entry_state_variants missing keys: {missing_variant_keys}"
                if strict:
                    blocking_errors.append(msg)
                else:
                    warnings.append(msg)

    # cross_module_refs validation
    refs = continuity.get("cross_module_refs")
    normalized_refs_count = 0
    if refs is not None:
        if not isinstance(refs, list):
            msg = "cross_module_refs must be a list"
            if strict:
                blocking_errors.append(msg)
            else:
                warnings.append(msg)
        else:
            known_modules = set(_list_known_modules(module_dir.parent))
            for idx, ref in enumerate(refs):
                if not isinstance(ref, dict):
                    warnings.append(f"cross_module_refs[{idx}] is not an object")
                    continue
                normalized_refs_count += 1
                for req_key in ["target_module", "entity_id", "relation", "confidence"]:
                    if not ref.get(req_key):
                        warnings.append(f"cross_module_refs[{idx}] missing {req_key}")
                confidence = ref.get("confidence")
                if confidence and confidence not in ["high", "medium", "low"]:
                    warnings.append(
                        f"cross_module_refs[{idx}] confidence '{confidence}' is invalid (expected high|medium|low)"
                    )
                target_module = ref.get("target_module")
                if target_module and target_module not in known_modules:
                    warnings.append(
                        f"cross_module_refs[{idx}] target_module '{target_module}' not found in modules/"
                    )

    fallback = continuity.get("standalone_fallback")
    if fallback is not None and not isinstance(fallback, dict):
        msg = "standalone_fallback must be an object"
        if strict:
            blocking_errors.append(msg)
        else:
            warnings.append(msg)

    # plot-level optional outcome metadata checks
    branch_metadata = module_plot.get("branch_metadata") if isinstance(module_plot, dict) else None
    if branch_metadata and isinstance(branch_metadata, dict):
        outcomes = branch_metadata.get("outcomes")
        if isinstance(outcomes, list):
            for idx, outcome in enumerate(outcomes):
                if isinstance(outcome, dict) and "cross_module_impact" in outcome:
                    impact = outcome.get("cross_module_impact")
                    if not isinstance(impact, dict):
                        warnings.append(f"branch_metadata.outcomes[{idx}].cross_module_impact should be an object")

    status = "fail" if blocking_errors else ("degraded" if warnings else "pass")
    exit_code = 1 if blocking_errors else 0

    return {
        "status": status,
        "module": module_dir.name,
        "module_path": str(module_dir),
        "continuity_version": continuity_version,
        "required_keys_present": required_keys_present,
        "missing_required_keys": missing_required,
        "normalized_refs_count": normalized_refs_count,
        "blocking_errors": blocking_errors,
        "warnings": warnings,
        "strict": strict,
        "exit_code": exit_code,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit module continuity contract")
    parser.add_argument("--module", default="", help="Module slug (under modules/)")
    parser.add_argument("--module-path", default="", help="Explicit module path")
    parser.add_argument("--strict", action="store_true", default=False, help="Fail on missing required continuity keys")
    parser.add_argument("--json", action="store_true", default=False, help="Emit JSON")
    args = parser.parse_args()

    try:
        module_path = _resolve_module_path(module=args.module, module_path=args.module_path)
    except ValueError as exc:
        payload = {
            "status": "fail",
            "blocking_errors": [str(exc)],
            "warnings": [],
            "required_keys_present": [],
            "exit_code": 1,
        }
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"[ERROR] {exc}")
        return 1

    payload = audit_module_continuity(module_path, strict=args.strict)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"module={payload.get('module')} status={payload.get('status')} strict={payload.get('strict')}")
        if payload.get("blocking_errors"):
            print("blocking_errors:")
            for item in payload["blocking_errors"]:
                print(f"- {item}")
        if payload.get("warnings"):
            print("warnings:")
            for item in payload["warnings"]:
                print(f"- {item}")
    return int(payload.get("exit_code", 1))


if __name__ == "__main__":
    raise SystemExit(main())
