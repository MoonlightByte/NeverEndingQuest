# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Bulk Module Validation Script

Validates all modules (ingested or downloaded) using schema validation,
gameplay audit, and continuity audit.

Usage:
    python validate_modules_bulk.py
    python validate_modules_bulk.py --module The_Pumpkin_Kings_Curse
    python validate_modules_bulk.py --all
    python validate_modules_bulk.py --json

Exit codes:
    0 - All modules passed validation
    1 - One or more modules failed validation
    2 - Execution error (e.g., jsonschema not installed)
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Any, Set, Optional


def _load_world_registry(modules_dir: Path) -> Set[str]:
    """Load registered module slugs from world_registry.json."""
    registry_path = modules_dir / "world_registry.json"
    if not registry_path.exists():
        return set()
    
    try:
        with open(registry_path, 'r') as f:
            data = json.load(f)
        modules = data.get("modules", {})
        return set(modules.keys())
    except Exception as e:
        print(f"[WARNING] Could not load world_registry.json: {e}")
        return set()


def _discover_module_like_dirs(modules_dir: Path) -> Set[str]:
    """Discover module-like directories under modules/."""
    exclude = {
        "ingest", "conversation_history", "campaign_summaries", "backups",
        ".git", "__pycache__", "template", "example", ".DS_Store",
        "logs", "encounters", "campaign_archives"
    }
    
    candidates = set()
    if not modules_dir.exists():
        return candidates
    
    for entry in modules_dir.iterdir():
        if not entry.is_dir():
            continue
        if entry.name in exclude or entry.name.startswith('.'):
            continue
        
        # Check if it looks like a module (has areas/ with JSON files)
        areas_dir = entry / "areas"
        if areas_dir.exists() and any(areas_dir.glob("*.json")):
            candidates.add(entry.name)
    
    return candidates


def _resolve_targets(modules_dir: Path, explicit_modules: Optional[List[str]] = None, all_modules: bool = False, json_mode: bool = False) -> List[str]:
    """Resolve which modules to validate based on arguments."""
    if explicit_modules:
        # Validate only explicitly requested modules
        targets = []
        for slug in explicit_modules:
            module_path = modules_dir / slug
            if module_path.exists():
                targets.append(slug)
            elif not json_mode:
                print(f"[WARNING] Module not found: {slug}")
        return sorted(targets)
    
    if all_modules:
        # Default resolver: registry + autodetected, de-duplicated
        registered = _load_world_registry(modules_dir)
        discovered = _discover_module_like_dirs(modules_dir)
        # Only include registry modules that exist on disk
        registered_existing = {slug for slug in registered if (modules_dir / slug).exists()}
        targets = registered_existing | discovered
        return sorted(targets)
    
    # Default: no explicit selection, use all-modules behavior
    registered = _load_world_registry(modules_dir)
    discovered = _discover_module_like_dirs(modules_dir)
    # Only include registry modules that exist on disk
    registered_existing = {slug for slug in registered if (modules_dir / slug).exists()}
    targets = registered_existing | discovered
    return sorted(targets)


def _run_schema_validation(module_slug: str, modules_dir: Path) -> Dict[str, Any]:
    """Run schema validation for a single module."""
    script_path = Path(__file__).parent.parent / "core" / "validation" / "validate_module_files.py"
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path), "--module", module_slug, "--json"],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        # Try to parse JSON output
        if result.stdout:
            try:
                data = json.loads(result.stdout)
                return {
                    "success": result.returncode == 0,
                    "exit_code": result.returncode,
                    "data": data,
                    "stderr": result.stderr if result.stderr else None
                }
            except json.JSONDecodeError:
                return {
                    "success": False,
                    "exit_code": result.returncode,
                    "error": "Invalid JSON output from validator",
                    "stdout": result.stdout[:500],
                    "stderr": result.stderr if result.stderr else None
                }
        else:
            return {
                "success": False,
                "exit_code": result.returncode,
                "error": "No output from validator",
                "stderr": result.stderr if result.stderr else None
            }
    
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Validation timed out after 120s"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Execution error: {str(e)}"
        }


def _run_gameplay_audit(module_slug: str, modules_dir: Path) -> Dict[str, Any]:
    """Run gameplay audit for a single module."""
    script_path = Path(__file__).parent / "audit_module_gameplay.py"
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path), "--module", module_slug, "--json"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        # Try to parse JSON output
        if result.stdout:
            try:
                data = json.loads(result.stdout)
                return {
                    "success": result.returncode == 0,
                    "exit_code": result.returncode,
                    "data": data,
                    "stderr": result.stderr if result.stderr else None
                }
            except json.JSONDecodeError:
                return {
                    "success": False,
                    "exit_code": result.returncode,
                    "error": "Invalid JSON output from audit",
                    "stdout": result.stdout[:500],
                    "stderr": result.stderr if result.stderr else None
                }
        else:
            return {
                "success": False,
                "exit_code": result.returncode,
                "error": "No output from audit",
                "stderr": result.stderr if result.stderr else None
            }
    
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Audit timed out after 60s"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Execution error: {str(e)}"
        }


def _run_continuity_audit(module_slug: str, modules_dir: Path) -> Dict[str, Any]:
    """Run continuity audit for a single module."""
    script_path = Path(__file__).parent / "module_continuity_audit.py"

    try:
        result = subprocess.run(
            [sys.executable, str(script_path), "--module", module_slug, "--json", "--strict"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.stdout:
            try:
                data = json.loads(result.stdout)
                return {
                    "success": result.returncode == 0,
                    "exit_code": result.returncode,
                    "data": data,
                    "stderr": result.stderr if result.stderr else None,
                }
            except json.JSONDecodeError:
                return {
                    "success": False,
                    "exit_code": result.returncode,
                    "error": "Invalid JSON output from continuity audit",
                    "stdout": result.stdout[:500],
                    "stderr": result.stderr if result.stderr else None,
                }
        return {
            "success": False,
            "exit_code": result.returncode,
            "error": "No output from continuity audit",
            "stderr": result.stderr if result.stderr else None,
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Continuity audit timed out after 60s",
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Execution error: {str(e)}",
        }


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Bulk validate modules using schema, gameplay, and continuity audits",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--module",
        help="Validate specific module(s) by slug (repeatable)",
        action="append",
        default=[]
    )
    parser.add_argument(
        "--all",
        help="Validate all detected modules (default if no module specified)",
        action="store_true"
    )
    parser.add_argument(
        "--json",
        help="Output combined JSON summary to stdout",
        action="store_true"
    )
    
    args = parser.parse_args()
    
    # Determine modules directory
    repo_root = Path(__file__).parent.parent
    modules_dir = repo_root / "modules"
    
    if not modules_dir.exists():
        print("[ERROR] modules/ directory not found")
        sys.exit(2)
    
    # Resolve targets
    if args.module:
        targets = _resolve_targets(modules_dir, explicit_modules=args.module, json_mode=args.json)
    elif args.all:
        targets = _resolve_targets(modules_dir, all_modules=True, json_mode=args.json)
    else:
        # Default: all-modules behavior
        targets = _resolve_targets(modules_dir, all_modules=True, json_mode=args.json)
    
    if not targets:
        print("[ERROR] No modules found to validate")
        sys.exit(2)
    
    # Validate each module
    results = {}
    any_failed = False
    
    for slug in targets:
        # Progress output only in human mode
        if not args.json:
            print(f"\n[{slug}] Validating...")
        
        # Run schema validation
        schema_result = _run_schema_validation(slug, modules_dir)
        
        # Run gameplay audit
        audit_result = _run_gameplay_audit(slug, modules_dir)

        # Run continuity audit
        continuity_result = _run_continuity_audit(slug, modules_dir)
        
        # Determine overall status
        schema_passed = schema_result.get("success", False) and schema_result.get("exit_code", 1) == 0
        audit_passed = audit_result.get("success", False) and audit_result.get("exit_code", 1) == 0
        
        has_blocking_errors = False
        if audit_result.get("data"):
            has_blocking_errors = bool(audit_result["data"].get("blocking_errors", []))
        
        continuity_passed = continuity_result.get("success", False) and continuity_result.get("exit_code", 1) == 0
        continuity_exec_error = continuity_result.get("error") is not None

        # Module fails if: schema fails OR audit has blocking errors OR continuity fails OR execution error
        schema_exec_error = schema_result.get("error") is not None
        audit_exec_error = audit_result.get("error") is not None
        module_failed = (
            not schema_passed
            or has_blocking_errors
            or not continuity_passed
            or schema_exec_error
            or audit_exec_error
            or continuity_exec_error
        )
        any_failed = any_failed or module_failed
        
        results[slug] = {
            "schema": {
                "passed": schema_passed,
                "exit_code": schema_result.get("exit_code"),
                "error": schema_result.get("error"),
                "data": schema_result.get("data")
            },
            "audit": {
                "passed": audit_passed and not has_blocking_errors,
                "exit_code": audit_result.get("exit_code"),
                "error": audit_result.get("error"),
                "has_blocking_errors": has_blocking_errors,
                "data": audit_result.get("data")
            },
            "continuity": {
                "passed": continuity_passed,
                "exit_code": continuity_result.get("exit_code"),
                "error": continuity_result.get("error"),
                "has_blocking_errors": bool((continuity_result.get("data") or {}).get("blocking_errors", [])),
                "data": continuity_result.get("data"),
            },
            "overall_passed": not module_failed
        }
        
        # Print human-readable status
        if not args.json:
            status = "[OK]" if not module_failed else "[FAIL]"
            print(f"  {status} Schema: {'PASS' if schema_passed else 'FAIL'}")
            print(f"  {status} Audit: {'PASS' if audit_passed and not has_blocking_errors else 'FAIL'}")
            print(f"  {status} Continuity: {'PASS' if continuity_passed else 'FAIL'}")
            if schema_result.get("error"):
                print(f"  Schema Error: {schema_result['error']}")
            if audit_result.get("error"):
                print(f"  Audit Error: {audit_result['error']}")
            if continuity_result.get("error"):
                print(f"  Continuity Error: {continuity_result['error']}")
    
    # Output summary
    if args.json:
        summary = {
            "modules": results,
            "summary": {
                "total": len(targets),
                "passed": sum(1 for r in results.values() if r["overall_passed"]),
                "failed": sum(1 for r in results.values() if not r["overall_passed"]),
                "all_passed": not any_failed
            }
        }
        print(json.dumps(summary, indent=2))
    else:
        print("\n" + "=" * 60)
        print("BULK VALIDATION SUMMARY")
        print("=" * 60)
        print(f"Total modules: {len(targets)}")
        print(f"Passed: {sum(1 for r in results.values() if r['overall_passed'])}")
        print(f"Failed: {sum(1 for r in results.values() if not r['overall_passed'])}")
        print(f"\nExit code: {'0 (PASS)' if not any_failed else '1 (FAIL)'}")
    
    return 0 if not any_failed else 1


if __name__ == "__main__":
    sys.exit(main())
