#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""NeverEndingQuest CLI - Continuity Cross-Module Reference Enrichment

Adds deterministic `continuity.cross_module_refs` entries for existing modules.

Default mode is dry-run; use `--apply` to persist updates.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from continuity_cross_ref_enrichment import enrich_continuity_cross_refs
from utils.file_operations import safe_read_json, safe_write_json


def _discover_modules(modules_root: Path) -> List[str]:
    if not modules_root.exists():
        return []
    out: List[str] = []
    for entry in modules_root.iterdir():
        if entry.is_dir() and (entry / "areas").exists():
            out.append(entry.name)
    return sorted(out)


def _run_module(module_slug: str, modules_root: Path, apply: bool, known_modules: List[str]) -> Dict[str, Any]:
    module_dir = modules_root / module_slug
    context_path = module_dir / "module_context.json"
    plot_path = module_dir / "module_plot.json"

    if not context_path.exists():
        return {
            "module": module_slug,
            "status": "error",
            "error": f"Missing module_context.json: {context_path}",
        }

    module_context = safe_read_json(str(context_path))
    module_plot = safe_read_json(str(plot_path)) if plot_path.exists() else {}

    if not isinstance(module_context, dict):
        return {
            "module": module_slug,
            "status": "error",
            "error": f"Invalid module_context payload for {module_slug}",
        }
    if not isinstance(module_plot, dict):
        module_plot = {}

    enrich_result = enrich_continuity_cross_refs(
        module_slug=module_slug,
        module_context=module_context,
        module_plot=module_plot,
        known_modules=known_modules,
    )

    changed = bool(enrich_result.get("changed", False))
    added_refs = enrich_result.get("added_refs", [])

    if not apply:
        return {
            "module": module_slug,
            "status": "planned" if changed else "unchanged",
            "added_count": len(added_refs),
            "added_refs": added_refs,
            "final_count": enrich_result.get("final_count", 0),
        }

    if changed:
        write_ok = safe_write_json(str(context_path), enrich_result.get("module_context", module_context))
        if not write_ok:
            return {
                "module": module_slug,
                "status": "error",
                "error": f"Failed writing {context_path}",
                "added_count": len(added_refs),
                "added_refs": added_refs,
            }

    return {
        "module": module_slug,
        "status": "updated" if changed else "unchanged",
        "added_count": len(added_refs),
        "added_refs": added_refs,
        "final_count": enrich_result.get("final_count", 0),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Enrich module continuity cross_module_refs")
    parser.add_argument("--module", action="append", default=[], help="Module slug (repeatable)")
    parser.add_argument("--all", action="store_true", default=False, help="Process all module folders")
    parser.add_argument("--apply", action="store_true", default=False, help="Persist changes")
    parser.add_argument("--json", action="store_true", default=False, help="Emit JSON")
    parser.add_argument("--modules-root", default="modules", help="Modules root path")
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    modules_root = Path(args.modules_root)
    known_modules = _discover_modules(modules_root)

    if args.module:
        targets = [slug for slug in args.module if (modules_root / slug).exists()]
    elif args.all or not args.module:
        targets = known_modules
    else:
        targets = []

    if not targets:
        payload = {
            "status": "fail",
            "error": "No target modules found",
            "results": [],
            "summary": {},
        }
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print("[ERROR] No target modules found")
        return 1

    results: List[Dict[str, Any]] = []
    for slug in sorted(targets):
        results.append(_run_module(slug, modules_root, args.apply, known_modules))

    summary = {
        "total": len(results),
        "updated": sum(1 for row in results if row.get("status") == "updated"),
        "planned": sum(1 for row in results if row.get("status") == "planned"),
        "unchanged": sum(1 for row in results if row.get("status") == "unchanged"),
        "errors": sum(1 for row in results if row.get("status") == "error"),
        "added_refs": sum(int(row.get("added_count", 0)) for row in results),
        "apply_mode": bool(args.apply),
    }

    payload = {
        "status": "pass" if summary["errors"] == 0 else "fail",
        "results": results,
        "summary": summary,
    }

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        mode = "APPLY" if args.apply else "DRY-RUN"
        print(f"CROSS-MODULE REF ENRICHMENT ({mode})")
        for row in results:
            print(f"- {row.get('module')}: {row.get('status')} added={row.get('added_count', 0)}")
        print(
            "summary: total={total} updated={updated} planned={planned} unchanged={unchanged} "
            "errors={errors} added_refs={added_refs}".format(**summary)
        )

    return 0 if summary["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
