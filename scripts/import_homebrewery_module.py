# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest CLI - Homebrewery Module Import
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Manual ingest CLI for Homebrewery markdown adventure sources.
Supports both AI-driven and deterministic import paths with dry-run mode.

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

# 1. Standard library imports
import argparse
import json
import os
import sys
from pathlib import Path

# 2. Third-party imports

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 3. Internal module imports (grouped by layer)
try:
    from core.importers.homebrewery_importer import import_homebrewery_adventure_to_module
    IMPORTER_AVAILABLE = True
except Exception as import_error:
    IMPORTER_AVAILABLE = False
    IMPORT_ERROR_MSG = str(import_error)


def _create_parser():
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        prog="import_homebrewery_module",
        description="Import Homebrewery markdown adventure into NEQ module artifacts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/import_homebrewery_module.py --source adventure.md
  python scripts/import_homebrewery_module.py --source adventure.md --module-slug My_Adventure --strict
  python scripts/import_homebrewery_module.py --source adventure.md --dry-run --deterministic

Exit codes:
  0 - Success
  1 - Quarantined (validation failed)
  2 - Error (runtime/usage error)
        """,
    )

    parser.add_argument(
        "--source",
        type=str,
        required=True,
        help="Path to Homebrewery markdown source file",
    )

    parser.add_argument(
        "--module-slug",
        type=str,
        default=None,
        help="Override generated module slug (default: derived from title)",
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        default=True,
        help="Enable strict validation (quarantine on failure) [default: True]",
    )

    parser.add_argument(
        "--no-strict",
        dest="strict",
        action="store_false",
        help="Disable strict validation mode",
    )

    parser.add_argument(
        "--no-llm",
        action="store_true",
        default=False,
        help="Disable LLM enrichment (placeholder for future phases)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Parse and summarize without writing module artifacts",
    )

    parser.add_argument(
        "--deterministic",
        action="store_true",
        default=False,
        help="Use deterministic parser path instead of AI-driven generation",
    )

    parser.add_argument(
        "--output-root",
        type=str,
        default="modules",
        help="Output directory for generated module [default: modules]",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output result as JSON (machine-readable)",
    )

    return parser


def main():
    """Main CLI entrypoint for Homebrewery module import."""
    # Create parser first (works even with missing deps)
    parser = _create_parser()

    # Handle --help before checking imports so help works even with missing deps
    if "--help" in sys.argv or "-h" in sys.argv:
        parser.print_help()
        sys.exit(0)

    # Now check if importer is available
    if not IMPORTER_AVAILABLE:
        print(f"[ERROR] Importer dependencies not available: {IMPORT_ERROR_MSG}", file=sys.stderr)
        print("Note: Some features require 'openai' package to be installed.", file=sys.stderr)
        sys.exit(2)

    args = parser.parse_args()

    # Enforce deterministic mode for dry-run to guarantee no writes
    if args.dry_run and not args.deterministic:
        if args.json:
            print(json.dumps({
                "status": "error",
                "exit_code": 2,
                "error": "--dry-run requires --deterministic to guarantee no artifact writes",
            }, indent=2))
        else:
            print("[ERROR] --dry-run requires --deterministic to guarantee no artifact writes", file=sys.stderr)
            print("Usage: --dry-run --deterministic", file=sys.stderr)
        sys.exit(2)

    # Validate source file exists
    source_path = Path(args.source)
    if not source_path.exists():
        error_result = {
            "status": "error",
            "exit_code": 2,
            "error": f"Source file not found: {args.source}",
        }
        if args.json:
            print(json.dumps(error_result, indent=2))
        else:
            print(f"[ERROR] Source file not found: {args.source}", file=sys.stderr)
        sys.exit(2)

    # Run import
    try:
        result = import_homebrewery_adventure_to_module(
            source_path=str(source_path),
            module_slug=args.module_slug,
            output_root=args.output_root,
            strict=args.strict,
            llm_enrich=not args.no_llm,
            use_deterministic=args.deterministic,
            dry_run=args.dry_run,
        )
    except Exception as e:
        error_result = {
            "status": "error",
            "exit_code": 2,
            "error": str(e),
        }
        if args.json:
            print(json.dumps(error_result, indent=2))
        else:
            print(f"[ERROR] Import failed: {e}", file=sys.stderr)
        sys.exit(2)

    # Handle dry-run special output
    if args.dry_run:
        dry_run_summary = {
            "status": "dry_run",
            "source": str(source_path),
            "module_slug": result.get("module_slug"),
            "would_generate": len(result.get("artifacts", [])),
            "validation": result.get("validation", {}),
            "note": "Dry run completed. No files were written.",
        }
        if args.json:
            print(json.dumps(dry_run_summary, indent=2))
        else:
            print("=" * 60)
            print("DRY RUN SUMMARY")
            print("=" * 60)
            print(f"Source: {source_path}")
            print(f"Module slug: {dry_run_summary['module_slug']}")
            print(f"Would generate: {dry_run_summary['would_generate']} artifacts")
            validation = dry_run_summary.get("validation", {})
            print(f"Validation would pass: {validation.get('passed', False)}")
            if validation.get("errors"):
                print("Validation errors:")
                for err in validation["errors"][:5]:
                    print(f"  - {err}")
            print("-" * 60)
            print("No files were written.")
        sys.exit(0)

    # Determine exit code based on result status
    status = result.get("status", "error")
    if status == "success":
        exit_code = 0
    elif status == "quarantined":
        exit_code = 1
    else:
        exit_code = 2

    # Build output payload
    output = {
        "status": status,
        "exit_code": exit_code,
        "module_slug": result.get("module_slug"),
        "artifacts_count": len(result.get("artifacts", [])),
        "artifacts": result.get("artifacts", []),
        "validation": result.get("validation", {}),
    }

    if result.get("quarantine_reason"):
        output["quarantine_reason"] = result["quarantine_reason"]

    # Print output
    if args.json:
        print(json.dumps(output, indent=2))
    else:
        print("=" * 60)
        print(f"IMPORT RESULT: {status.upper()}")
        print("=" * 60)
        print(f"Module slug: {output['module_slug']}")
        print(f"Artifacts generated: {output['artifacts_count']}")
        validation = output.get("validation", {})
        print(f"Validation passed: {validation.get('passed', False)}")
        if validation.get("failed_count"):
            print(f"Validation failures: {validation['failed_count']}")
        if output.get("quarantine_reason"):
            print(f"Quarantine reason: {output['quarantine_reason']}")
        if validation.get("errors"):
            print("Errors:")
            for err in validation["errors"][:10]:
                print(f"  - {err}")
        print("-" * 60)
        if exit_code == 0:
            print("[OK] Import completed successfully")
        elif exit_code == 1:
            print("[QUARANTINED] Module failed validation and was quarantined")
        else:
            print("[ERROR] Import failed")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
