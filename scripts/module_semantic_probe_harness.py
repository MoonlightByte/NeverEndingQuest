#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Standalone publication-time semantic probe harness.

Runs deterministic travel, handoff, and hidden-NPC discovery probes against
authored module semantics without invoking runtime AI flows.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.module_semantic_authority import build_module_semantic_authority


_LOCATION_SOURCE_PATTERN = re.compile(r"#locations\[([A-Za-z0-9_]+)\]")
_PLOT_SOURCE_PATTERN = re.compile(r"#plotPoints\[([^\]]+)\]")
_HANDOFF_HINT_PATTERN = re.compile(
    r"\b(handoff|escort|guide|follow|return on their own)\b"
)
_CANONICAL_TRAVEL_SOURCE_SUFFIXES = (
    ".name",
    ".aliases",
    ".source_room_title",
    ".title",
)
_TRAVEL_PHRASE_LEADING_STOPWORDS = {
    "and",
    "or",
    "but",
    "if",
    "after",
    "before",
    "also",
    "with",
    "without",
    "the",
    "a",
    "an",
    "to",
    "for",
    "from",
    "of",
    "in",
    "on",
    "at",
    "into",
    "toward",
    "towards",
    "via",
}


def _load_json(path: Path) -> Tuple[Dict[str, Any], str]:
    """Read JSON object payload from path."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            return {}, f"JSON root is not an object: {path}"
        return payload, ""
    except Exception as exc:
        return {}, f"Failed to read {path}: {exc}"


def _safe_dict(value: Any) -> Dict[str, Any]:
    """Return dict value or empty dict."""
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    """Return list value or empty list."""
    return value if isinstance(value, list) else []


def _resolve_module_path(module: str = "", module_path: str = "") -> Path:
    """Resolve module path from slug or explicit path."""
    if module_path:
        return Path(module_path)
    if module:
        return Path("modules") / module
    raise ValueError("Provide --module or --module-path")


def _lookup_plot_location(module_plot: Dict[str, Any], plot_id: str) -> str:
    """Resolve plot-point location id from module_plot payload."""
    for plot_point in _safe_list(module_plot.get("plotPoints")):
        if not isinstance(plot_point, dict):
            continue
        if str(plot_point.get("id", "") or "").strip() != plot_id:
            continue
        return str(plot_point.get("location", "") or "").strip().upper()
    return ""


def _expected_locations_from_sources(
    sources: List[str], module_plot: Dict[str, Any]
) -> List[str]:
    """Derive expected canonical location ids from source provenance."""
    location_ids: Set[str] = set()
    for source in sources:
        source_text = str(source or "").strip()
        if not source_text:
            continue

        location_match = _LOCATION_SOURCE_PATTERN.search(source_text)
        if location_match:
            location_ids.add(location_match.group(1).strip().upper())
            continue

        plot_match = _PLOT_SOURCE_PATTERN.search(source_text)
        if plot_match:
            plot_location = _lookup_plot_location(
                module_plot, plot_match.group(1).strip()
            )
            if plot_location:
                location_ids.add(plot_location)

    return sorted(location_ids)


def _is_canonical_travel_phrase(phrase: str, sources: List[str]) -> bool:
    """Return True when phrase/sources look like real player travel language."""
    tokens = str(phrase or "").split()
    if not tokens or len(tokens) > 4:
        return False
    if tokens[0] in _TRAVEL_PHRASE_LEADING_STOPWORDS:
        return False
    if any(any(character.isdigit() for character in token) for token in tokens):
        return False
    has_canonical_source = False
    for source in sources:
        source_text = str(source).strip()
        if source_text.endswith(_CANONICAL_TRAVEL_SOURCE_SUFFIXES):
            has_canonical_source = True
            break
    if not has_canonical_source:
        return False
    return True


def _derive_travel_probes(
    semantic_authority: Dict[str, Any],
    module_plot: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Derive travel fixtures from player-facing destination semantics."""
    probes: List[Dict[str, Any]] = []
    warnings: List[str] = []
    destination_phrases = _safe_dict(semantic_authority.get("destination_phrases"))

    for phrase, row in sorted(destination_phrases.items()):
        row_dict = _safe_dict(row)
        if not bool(row_dict.get("player_facing")):
            continue

        sources = [
            str(value).strip()
            for value in _safe_list(row_dict.get("sources"))
            if str(value).strip()
        ]
        if not _is_canonical_travel_phrase(phrase, sources):
            continue
        expected_location_ids = _expected_locations_from_sources(sources, module_plot)
        if not expected_location_ids:
            warnings.append(f"travel_probe_fixture_missing_expected_target:{phrase}")
            continue

        probes.append(
            {
                "id": f"travel.{phrase.replace(' ', '-')}",
                "type": "travel",
                "phrase": phrase,
                "status": str(row_dict.get("status", "") or "").strip().lower(),
                "resolved_location_id": str(row_dict.get("location_id", "") or "")
                .strip()
                .upper(),
                "candidate_location_ids": [
                    str(value).strip().upper()
                    for value in _safe_list(row_dict.get("candidate_location_ids"))
                    if str(value).strip()
                ],
                "expected_location_ids": expected_location_ids,
                "sources": sources,
            }
        )

    return probes, warnings


def _derive_handoff_probes(
    module_context: Dict[str, Any], module_root: Path
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Derive escort/handoff fixtures from continuity cross-module refs."""
    probes: List[Dict[str, Any]] = []
    warnings: List[str] = []
    continuity = _safe_dict(module_context.get("continuity"))
    refs = _safe_list(continuity.get("cross_module_refs"))

    for index, ref in enumerate(refs):
        ref_dict = _safe_dict(ref)
        entity_id = str(ref_dict.get("entity_id", "") or "").strip()
        relation = str(ref_dict.get("relation", "") or "").strip()
        notes = str(ref_dict.get("notes", "") or "").strip()
        probe_text = f"{entity_id} {relation} {notes}".lower()
        if not _HANDOFF_HINT_PATTERN.search(probe_text):
            continue

        target_module = str(ref_dict.get("target_module", "") or "").strip()
        probes.append(
            {
                "id": f"handoff.{entity_id or f'ref-{index}'}",
                "type": "handoff",
                "entity_id": entity_id,
                "relation": relation,
                "target_module": target_module,
                "target_module_exists": bool(
                    target_module and (module_root / target_module).exists()
                ),
                "notes": notes,
            }
        )

    if not probes:
        warnings.append("handoff_probe_fixture_missing")

    return probes, warnings


def _derive_hidden_npc_probes(
    semantic_authority: Dict[str, Any],
    module_plot: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Derive hidden/revealable NPC discovery probes."""
    probes: List[Dict[str, Any]] = []
    warnings: List[str] = []
    npc_scene_authority = _safe_dict(semantic_authority.get("npc_scene_authority"))

    for npc_name, row in sorted(npc_scene_authority.items()):
        row_dict = _safe_dict(row)
        reveal_bindings = [
            entry
            for entry in _safe_list(row_dict.get("reveal_bindings"))
            if isinstance(entry, dict)
        ]
        authored_mentions_count = row_dict.get("authored_mentions_count")
        if not isinstance(authored_mentions_count, int):
            authored_mentions_count = 0
        authored_mention_sources = [
            str(value).strip()
            for value in _safe_list(row_dict.get("authored_mention_sources"))
            if str(value).strip()
        ]
        visible_location_ids = [
            str(value).strip().upper()
            for value in _safe_list(row_dict.get("visible_location_ids"))
            if str(value).strip()
        ]

        if not reveal_bindings and not visible_location_ids and authored_mentions_count <= 0:
            continue

        # Visible NPC authority is sufficient baseline authority.
        if visible_location_ids and not reveal_bindings:
            continue

        expected_location_ids = _expected_locations_from_sources(
            authored_mention_sources, module_plot
        )
        if authored_mentions_count > 0 and not expected_location_ids:
            warnings.append(
                f"hidden_npc_probe_fixture_missing_expected_target:{npc_name}"
            )

        probes.append(
            {
                "id": f"hidden_npc.{str(row_dict.get('name_slug', npc_name)).replace(' ', '-')}",
                "type": "hidden_npc",
                "npc": npc_name,
                "name_slug": str(row_dict.get("name_slug", "") or "").strip(),
                "visible_location_ids": visible_location_ids,
                "reveal_location_ids": sorted(
                    {
                        str(entry.get("location_id", "") or "").strip().upper()
                        for entry in reveal_bindings
                        if str(entry.get("location_id", "") or "").strip()
                    }
                ),
                "expected_location_ids": expected_location_ids,
                "authored_mentions_count": authored_mentions_count,
                "authored_mention_sources": authored_mention_sources,
            }
        )

    if not probes:
        warnings.append("hidden_npc_probe_fixture_missing")

    return probes, warnings


def _evaluate_travel_probe(probe: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate one travel probe."""
    result = dict(probe)
    expected_location_ids = probe.get("expected_location_ids") or []
    expected_location_id = (
        expected_location_ids[0] if len(expected_location_ids) == 1 else ""
    )
    result["expected_location_id"] = expected_location_id
    result["status_detail"] = ""

    if len(expected_location_ids) > 1:
        result["status"] = "degraded"
        result["failure_class"] = "travel_fixture_ambiguous_expected_target"
        result["status_detail"] = "Fixture resolves to multiple expected location ids"
        return result

    if probe.get("status") == "resolved":
        if (
            expected_location_id
            and probe.get("resolved_location_id") != expected_location_id
        ):
            result["status"] = "fail"
            result["failure_class"] = "travel_misrouted_destination_phrase"
            result["status_detail"] = (
                "Resolved location does not match expected location"
            )
        else:
            result["status"] = "pass"
            result["failure_class"] = ""
            result["status_detail"] = "Resolved location matches expected destination"
        return result

    if probe.get("status") == "ambiguous":
        result["status"] = "fail"
        result["failure_class"] = "travel_ambiguous_destination_phrase"
        result["status_detail"] = "Player-facing destination phrase is ambiguous"
        return result

    if probe.get("status") == "unresolved":
        result["status"] = "fail"
        result["failure_class"] = "travel_unresolved_destination_phrase"
        result["status_detail"] = "Player-facing destination phrase is unresolved"
        return result

    result["status"] = "fail"
    result["failure_class"] = "travel_invalid_destination_status"
    result["status_detail"] = "Destination phrase carries invalid status"
    return result


def _evaluate_handoff_probe(probe: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate one escort/handoff probe."""
    result = dict(probe)
    if not str(probe.get("entity_id", "") or "").strip():
        result["status"] = "fail"
        result["failure_class"] = "handoff_entity_missing"
        result["status_detail"] = "Continuity handoff reference is missing entity_id"
        return result

    if not str(probe.get("target_module", "") or "").strip():
        result["status"] = "fail"
        result["failure_class"] = "handoff_target_missing"
        result["status_detail"] = (
            "Continuity handoff reference is missing target_module"
        )
        return result

    if not bool(probe.get("target_module_exists")):
        result["status"] = "fail"
        result["failure_class"] = "handoff_target_module_absent"
        result["status_detail"] = "Continuity handoff target module does not exist"
        return result

    result["status"] = "pass"
    result["failure_class"] = ""
    result["status_detail"] = "Continuity handoff target is supported"
    return result


def _evaluate_hidden_npc_probe(probe: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate one hidden/revealable NPC discovery probe."""
    result = dict(probe)
    expected_location_ids = probe.get("expected_location_ids") or []
    reveal_location_ids = probe.get("reveal_location_ids") or []
    visible_location_ids = probe.get("visible_location_ids") or []

    if (
        probe.get("authored_mentions_count", 0) > 0
        and not reveal_location_ids
        and not visible_location_ids
    ):
        result["status"] = "fail"
        result["failure_class"] = "hidden_npc_missing_authority"
        result["status_detail"] = (
            "Authored hidden or revealable NPC has no reveal location"
        )
        return result

    if visible_location_ids and not reveal_location_ids:
        result["status"] = "pass"
        result["failure_class"] = ""
        result["status_detail"] = "Visible NPC authority present"
        return result

    if expected_location_ids and reveal_location_ids:
        if not set(expected_location_ids).intersection(set(reveal_location_ids)):
            result["status"] = "fail"
            result["failure_class"] = "hidden_npc_target_mismatch"
            result["status_detail"] = (
                "Reveal targets do not match authored discovery context"
            )
            return result

    if probe.get("authored_mentions_count", 0) > 0 and not expected_location_ids:
        result["status"] = "degraded"
        result["failure_class"] = "hidden_npc_fixture_missing_expected_target"
        result["status_detail"] = "Probe fixture lacks expected location context"
        return result

    result["status"] = "pass"
    result["failure_class"] = ""
    result["status_detail"] = (
        "Revealable NPC authority aligns with authored discovery context"
    )
    return result


def run_module_semantic_probes(module_dir: Path) -> Dict[str, Any]:
    """Run standalone semantic publication probes for one module."""
    module_context_path = module_dir / "module_context.json"
    module_plot_path = module_dir / "module_plot.json"

    blocking_errors: List[str] = []
    warnings: List[str] = []
    probes: List[Dict[str, Any]] = []

    if not module_dir.exists():
        return {
            "module": module_dir.name,
            "module_path": str(module_dir),
            "status": "fail",
            "summary": {},
            "probes": [],
            "blocking_errors": [f"Module directory not found: {module_dir}"],
            "warnings": [],
            "exit_code": 1,
        }

    module_context, context_error = _load_json(module_context_path)
    module_plot, plot_error = _load_json(module_plot_path)
    if context_error:
        blocking_errors.append(context_error)
    if plot_error:
        blocking_errors.append(plot_error)
    if blocking_errors:
        return {
            "module": module_dir.name,
            "module_path": str(module_dir),
            "status": "fail",
            "summary": {},
            "probes": [],
            "blocking_errors": blocking_errors,
            "warnings": warnings,
            "exit_code": 1,
        }

    semantic_authority = module_context.get("semantic_authority")
    if not isinstance(semantic_authority, dict):
        semantic_authority = build_module_semantic_authority(
            module_slug=module_dir.name,
            module_context=module_context,
            module_plot=module_plot,
            module_dir=module_dir,
        )
        warnings.append("semantic_authority_derived_in_memory_for_probe_run")

    travel_probes, travel_warnings = _derive_travel_probes(
        semantic_authority, module_plot
    )
    handoff_probes, handoff_warnings = _derive_handoff_probes(
        module_context, module_dir.parent
    )
    hidden_npc_probes, hidden_npc_warnings = _derive_hidden_npc_probes(
        semantic_authority, module_plot
    )

    warnings.extend(travel_warnings)
    warnings.extend(handoff_warnings)
    warnings.extend(hidden_npc_warnings)

    for probe in travel_probes:
        probes.append(_evaluate_travel_probe(probe))
    for probe in handoff_probes:
        probes.append(_evaluate_handoff_probe(probe))
    for probe in hidden_npc_probes:
        probes.append(_evaluate_hidden_npc_probe(probe))

    pass_count = sum(1 for probe in probes if probe.get("status") == "pass")
    fail_count = sum(1 for probe in probes if probe.get("status") == "fail")
    degraded_count = sum(1 for probe in probes if probe.get("status") == "degraded")

    for probe in probes:
        if probe.get("status") == "fail":
            blocking_errors.append(
                f"{probe.get('failure_class')}: {probe.get('id')} - {probe.get('status_detail')}"
            )
        elif probe.get("status") == "degraded":
            warnings.append(
                f"{probe.get('failure_class')}: {probe.get('id')} - {probe.get('status_detail')}"
            )

    status = (
        "fail" if fail_count else ("degraded" if degraded_count or warnings else "pass")
    )
    return {
        "module": module_dir.name,
        "module_path": str(module_dir),
        "status": status,
        "summary": {
            "probe_count": len(probes),
            "pass_count": pass_count,
            "fail_count": fail_count,
            "degraded_count": degraded_count,
            "travel_probe_count": len(travel_probes),
            "handoff_probe_count": len(handoff_probes),
            "hidden_npc_probe_count": len(hidden_npc_probes),
        },
        "probes": probes,
        "blocking_errors": blocking_errors,
        "warnings": warnings,
        "exit_code": 1 if fail_count else 0,
    }


def main() -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Run semantic publication probes")
    parser.add_argument("--module", default="", help="Module slug (under modules/)")
    parser.add_argument("--module-path", default="", help="Explicit module path")
    parser.add_argument(
        "--json", action="store_true", default=False, help="Emit JSON output"
    )
    args = parser.parse_args()

    try:
        module_path = _resolve_module_path(
            module=args.module, module_path=args.module_path
        )
    except ValueError as exc:
        payload = {
            "status": "fail",
            "summary": {},
            "probes": [],
            "blocking_errors": [str(exc)],
            "warnings": [],
            "exit_code": 1,
        }
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"[ERROR] {exc}")
        return 1

    payload = run_module_semantic_probes(module_path)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"module={payload.get('module')} status={payload.get('status')}")
        print(f"summary={payload.get('summary')}")
        if payload.get("blocking_errors"):
            print("blocking_errors:")
            for message in payload["blocking_errors"]:
                print(f"- {message}")
        if payload.get("warnings"):
            print("warnings:")
            for message in payload["warnings"]:
                print(f"- {message}")
    return int(payload.get("exit_code", 1))


if __name__ == "__main__":
    raise SystemExit(main())
