#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""NeverEndingQuest - Continuity Contract Remediation Script

Backfills required continuity contract keys in module_context.json files.

Usage:
  python scripts/remediate_module_continuity.py --all
  python scripts/remediate_module_continuity.py --all --apply
  python scripts/remediate_module_continuity.py --module The_Pumpkin_Kings_Curse --apply

Default mode is dry-run (no writes). Use --apply to persist changes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.file_operations import safe_read_json, safe_write_json


REQUIRED_KEYS = [
    "continuity_version",
    "entry_state_variants",
    "cross_module_refs",
    "standalone_fallback",
]


def _discover_module_slugs(modules_root: Path) -> List[str]:
    """Discover module-like folders under modules/.

    A module-like folder must contain an `areas/` directory.
    """
    if not modules_root.exists():
        return []

    discovered: List[str] = []
    for entry in modules_root.iterdir():
        if not entry.is_dir():
            continue
        if entry.name.startswith("."):
            continue
        if (entry / "areas").exists():
            discovered.append(entry.name)
    return sorted(discovered)


def _default_variant(module_name: str, variant_key: str) -> Dict[str, Any]:
    if variant_key == "cold_start":
        summary = (
            f"Party enters {module_name} with no prior continuity context. "
            "Present the opening conflict and immediate objective clearly."
        )
    elif variant_key == "partial_context":
        summary = (
            f"Party enters {module_name} with partial prior context. "
            "Reinforce known clues before branch-critical decisions."
        )
    else:
        summary = (
            f"Party enters {module_name} in late-arc state. "
            "Provide compact recap and maintain path to a valid ending."
        )

    return {"summary": summary}


def _default_continuity(module_slug: str, module_name: str) -> Dict[str, Any]:
    return {
        "continuity_version": "v1",
        "entry_state_variants": {
            "cold_start": _default_variant(module_name, "cold_start"),
            "partial_context": _default_variant(module_name, "partial_context"),
            "late_arc": _default_variant(module_name, "late_arc"),
        },
        "cross_module_refs": [],
        "standalone_fallback": {
            "enabled": True,
            "clue_sources": ["module_context", "module_plot"],
            "notes": (
                f"{module_slug} remains fully playable as a standalone module "
                "when cross-module continuity is unavailable."
            ),
        },
    }


def remediate_module_context(module_context: Dict[str, Any], module_slug: str) -> Tuple[Dict[str, Any], List[str]]:
    """Backfill missing continuity keys while preserving authored values."""
    updates: List[str] = []
    module_name = str(
        module_context.get("module_name")
        or module_context.get("campaign_name")
        or module_slug.replace("_", " ")
    )

    continuity = module_context.get("continuity")
    if not isinstance(continuity, dict):
        continuity = {}
        module_context["continuity"] = continuity
        updates.append("continuity")

    defaults = _default_continuity(module_slug, module_name)

    if continuity.get("continuity_version") is None:
        continuity["continuity_version"] = defaults["continuity_version"]
        updates.append("continuity.continuity_version")

    variants = continuity.get("entry_state_variants")
    if not isinstance(variants, dict):
        continuity["entry_state_variants"] = defaults["entry_state_variants"]
        updates.append("continuity.entry_state_variants")
    else:
        for variant_key in ["cold_start", "partial_context", "late_arc"]:
            if variant_key not in variants or not isinstance(variants.get(variant_key), dict):
                variants[variant_key] = defaults["entry_state_variants"][variant_key]
                updates.append(f"continuity.entry_state_variants.{variant_key}")

    refs = continuity.get("cross_module_refs")
    if not isinstance(refs, list):
        continuity["cross_module_refs"] = defaults["cross_module_refs"]
        updates.append("continuity.cross_module_refs")

    fallback = continuity.get("standalone_fallback")
    if not isinstance(fallback, dict):
        continuity["standalone_fallback"] = defaults["standalone_fallback"]
        updates.append("continuity.standalone_fallback")
    else:
        if "enabled" not in fallback:
            fallback["enabled"] = True
            updates.append("continuity.standalone_fallback.enabled")
        if "clue_sources" not in fallback or not isinstance(fallback.get("clue_sources"), list):
            fallback["clue_sources"] = defaults["standalone_fallback"]["clue_sources"]
            updates.append("continuity.standalone_fallback.clue_sources")
        if "notes" not in fallback:
            fallback["notes"] = defaults["standalone_fallback"]["notes"]
            updates.append("continuity.standalone_fallback.notes")

    return module_context, updates


def _process_module(module_dir: Path, apply: bool) -> Dict[str, Any]:
    module_slug = module_dir.name
    context_path = module_dir / "module_context.json"

    if not context_path.exists():
        return {
            "module": module_slug,
            "status": "error",
            "error": f"Missing module_context.json: {context_path}",
            "updated_keys": [],
        }

    payload = safe_read_json(str(context_path))
    if not isinstance(payload, dict):
        return {
            "module": module_slug,
            "status": "error",
            "error": f"Invalid module_context payload: {context_path}",
            "updated_keys": [],
        }

    updated_payload, updates = remediate_module_context(payload, module_slug)
    if not updates:
        return {
            "module": module_slug,
            "status": "unchanged",
            "updated_keys": [],
        }

    if not apply:
        return {
            "module": module_slug,
            "status": "planned",
            "updated_keys": updates,
        }

    write_ok = safe_write_json(str(context_path), updated_payload)
    if not write_ok:
        return {
            "module": module_slug,
            "status": "error",
            "error": f"Failed atomic write: {context_path}",
            "updated_keys": updates,
        }

    return {
        "module": module_slug,
        "status": "updated",
        "updated_keys": updates,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backfill continuity contract keys in module_context.json")
    parser.add_argument("--module", action="append", default=[], help="Target module slug (repeatable)")
    parser.add_argument("--all", action="store_true", default=False, help="Target all module-like folders")
    parser.add_argument("--apply", action="store_true", default=False, help="Persist remediation changes")
    parser.add_argument("--json", action="store_true", default=False, help="Emit JSON output")
    parser.add_argument(
        "--modules-root",
        default="modules",
        help="Modules root directory (default: modules)",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    modules_root = Path(args.modules_root)
    if not modules_root.exists():
        payload = {
            "status": "error",
            "error": f"Modules root not found: {modules_root}",
            "results": [],
            "summary": {},
        }
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"[ERROR] {payload['error']}")
        return 1

    if args.module:
        targets = [slug for slug in args.module if (modules_root / slug).exists()]
    else:
        targets = _discover_module_slugs(modules_root)

    if not targets:
        payload = {
            "status": "error",
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
        result = _process_module(modules_root / slug, apply=args.apply)
        results.append(result)

    summary = {
        "total": len(results),
        "updated": sum(1 for item in results if item["status"] == "updated"),
        "planned": sum(1 for item in results if item["status"] == "planned"),
        "unchanged": sum(1 for item in results if item["status"] == "unchanged"),
        "errors": sum(1 for item in results if item["status"] == "error"),
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
        print(f"CONTINUITY REMEDIATION ({mode})")
        for item in results:
            if item["status"] in ["updated", "planned"]:
                print(f"- {item['module']}: {item['status']} ({len(item['updated_keys'])} key updates)")
            elif item["status"] == "unchanged":
                print(f"- {item['module']}: unchanged")
            else:
                print(f"- {item['module']}: error -> {item.get('error', 'unknown error')}")
        print(
            "summary: total={total} updated={updated} planned={planned} unchanged={unchanged} errors={errors}".format(
                **summary
            )
        )

    return 0 if summary["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
