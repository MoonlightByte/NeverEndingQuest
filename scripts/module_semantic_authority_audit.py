#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Module semantic-authority audit for publication substrate phase.

This validator reads additive `semantic_authority` payloads from module context
and reports deterministic pass/degraded/fail outcomes for uniqueness,
traceability, ambiguity, and contradiction classes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


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


def _resolve_module_path(module: str = "", module_path: str = "") -> Path:
    """Resolve module path from slug or explicit path."""
    if module_path:
        return Path(module_path)
    if module:
        return Path("modules") / module
    raise ValueError("Provide --module or --module-path")


def _safe_dict(value: Any) -> Dict[str, Any]:
    """Return dict value or empty dict."""
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    """Return list value or empty list."""
    return value if isinstance(value, list) else []


def _is_player_facing_phrase(row: Dict[str, Any]) -> bool:
    """Return True if phrase row is authored/player-facing for routing risk."""
    if bool(row.get("player_facing")):
        return True
    if bool(row.get("observed")):
        return True
    observation_count = row.get("observation_count")
    if isinstance(observation_count, int) and observation_count > 0:
        return True
    return False


def _add_blocker(
    blocker_class: str,
    message: str,
    context: Dict[str, Any],
    blocker_classes: List[str],
    blocking_errors: List[str],
    blocking_findings: List[Dict[str, Any]],
) -> None:
    """Append deterministic blocking finding in all output surfaces."""
    blocker_classes.append(blocker_class)
    blocking_errors.append(message)
    blocking_findings.append(
        {
            "class": blocker_class,
            "message": message,
            "context": context,
        }
    )


def audit_module_semantic_authority(module_dir: Path) -> Dict[str, Any]:
    """Audit semantic_authority payload for deterministic substrate quality."""
    module_context_path = module_dir / "module_context.json"

    blocking_errors: List[str] = []
    warnings: List[str] = []
    blocker_classes: List[str] = []
    blocking_findings: List[Dict[str, Any]] = []

    if not module_dir.exists():
        blocking_errors.append(f"Module directory not found: {module_dir}")
        return {
            "status": "fail",
            "module": module_dir.name,
            "module_path": str(module_dir),
            "blocking_errors": blocking_errors,
            "blocker_classes": ["module_path_missing"],
            "blocking_findings": [
                {
                    "class": "module_path_missing",
                    "message": blocking_errors[0],
                    "context": {"module_path": str(module_dir)},
                }
            ],
            "warnings": warnings,
            "summary": {},
            "exit_code": 1,
        }

    module_context, context_error = _load_json(module_context_path)
    if context_error:
        blocking_errors.append(context_error)
        return {
            "status": "fail",
            "module": module_dir.name,
            "module_path": str(module_dir),
            "blocking_errors": blocking_errors,
            "blocker_classes": ["module_context_missing"],
            "blocking_findings": [
                {
                    "class": "module_context_missing",
                    "message": blocking_errors[0],
                    "context": {"module_context_path": str(module_context_path)},
                }
            ],
            "warnings": warnings,
            "summary": {},
            "exit_code": 1,
        }

    semantic_authority = module_context.get("semantic_authority")
    if not isinstance(semantic_authority, dict):
        blocking_errors.append(
            "Missing semantic_authority payload in module_context.json"
        )
        return {
            "status": "fail",
            "module": module_dir.name,
            "module_path": str(module_dir),
            "blocking_errors": blocking_errors,
            "blocker_classes": ["semantic_authority_payload_missing"],
            "blocking_findings": [
                {
                    "class": "semantic_authority_payload_missing",
                    "message": blocking_errors[0],
                    "context": {"module_context_path": str(module_context_path)},
                }
            ],
            "warnings": warnings,
            "summary": {},
            "exit_code": 1,
        }

    version = str(semantic_authority.get("version", "") or "").strip()
    if not version:
        warnings.append("semantic_authority.version is missing")
    elif version != "v1":
        warnings.append(
            f"semantic_authority.version '{version}' is unexpected (expected v1)"
        )

    location_aliases = _safe_dict(semantic_authority.get("location_aliases"))
    if not location_aliases:
        warnings.append("semantic_authority.location_aliases is empty")

    destination_phrases = _safe_dict(semantic_authority.get("destination_phrases"))
    if not destination_phrases:
        warnings.append("semantic_authority.destination_phrases is empty")

    npc_scene_authority = _safe_dict(semantic_authority.get("npc_scene_authority"))
    if not npc_scene_authority:
        warnings.append("semantic_authority.npc_scene_authority is empty")

    ambiguous_destination_count = 0
    unresolved_destination_count = 0
    missing_npc_authority_count = 0

    for phrase, row in sorted(location_aliases.items()):
        row_dict = _safe_dict(row)
        status = str(row_dict.get("status", "") or "").strip().lower()
        candidate_ids = [
            str(value).strip().upper()
            for value in _safe_list(row_dict.get("candidate_location_ids"))
            if str(value).strip()
        ]
        sources = [
            str(value).strip()
            for value in _safe_list(row_dict.get("sources"))
            if str(value).strip()
        ]

        if not sources:
            warnings.append(f"location_aliases['{phrase}'] has no provenance sources")

        if status == "resolved":
            location_id = str(row_dict.get("location_id", "") or "").strip().upper()
            if not location_id:
                _add_blocker(
                    "semantic_payload_contradiction",
                    f"location_aliases['{phrase}'] resolved without location_id",
                    {"phrase": phrase, "field": "location_aliases"},
                    blocker_classes,
                    blocking_errors,
                    blocking_findings,
                )
            if len(candidate_ids) != 1:
                _add_blocker(
                    "semantic_payload_contradiction",
                    f"location_aliases['{phrase}'] resolved but candidate_location_ids count is {len(candidate_ids)}",
                    {
                        "phrase": phrase,
                        "field": "location_aliases",
                        "candidate_location_ids": candidate_ids,
                    },
                    blocker_classes,
                    blocking_errors,
                    blocking_findings,
                )
        elif status == "ambiguous":
            if len(candidate_ids) < 2:
                _add_blocker(
                    "semantic_payload_contradiction",
                    f"location_aliases['{phrase}'] ambiguous but candidate_location_ids count is {len(candidate_ids)}",
                    {
                        "phrase": phrase,
                        "field": "location_aliases",
                        "candidate_location_ids": candidate_ids,
                    },
                    blocker_classes,
                    blocking_errors,
                    blocking_findings,
                )
        elif status:
            warnings.append(
                f"location_aliases['{phrase}'] has unknown status '{status}'"
            )

    for phrase, row in sorted(destination_phrases.items()):
        row_dict = _safe_dict(row)
        status = str(row_dict.get("status", "") or "").strip().lower()
        candidate_ids = [
            str(value).strip().upper()
            for value in _safe_list(row_dict.get("candidate_location_ids"))
            if str(value).strip()
        ]
        sources = [
            str(value).strip()
            for value in _safe_list(row_dict.get("sources"))
            if str(value).strip()
        ]
        player_facing = _is_player_facing_phrase(row_dict)

        if not sources:
            warnings.append(
                f"destination_phrases['{phrase}'] has no provenance sources"
            )

        if status == "resolved":
            location_id = str(row_dict.get("location_id", "") or "").strip().upper()
            if not location_id:
                _add_blocker(
                    "semantic_payload_contradiction",
                    f"destination_phrases['{phrase}'] resolved without location_id",
                    {
                        "phrase": phrase,
                        "field": "destination_phrases",
                        "status": status,
                    },
                    blocker_classes,
                    blocking_errors,
                    blocking_findings,
                )
            if len(candidate_ids) != 1:
                _add_blocker(
                    "semantic_payload_contradiction",
                    f"destination_phrases['{phrase}'] resolved but candidate_location_ids count is {len(candidate_ids)}",
                    {
                        "phrase": phrase,
                        "field": "destination_phrases",
                        "status": status,
                        "candidate_location_ids": candidate_ids,
                    },
                    blocker_classes,
                    blocking_errors,
                    blocking_findings,
                )
        elif status == "ambiguous":
            ambiguous_destination_count += 1
            if len(candidate_ids) < 2:
                _add_blocker(
                    "semantic_payload_contradiction",
                    f"destination_phrases['{phrase}'] ambiguous but candidate_location_ids count is {len(candidate_ids)}",
                    {
                        "phrase": phrase,
                        "field": "destination_phrases",
                        "status": status,
                        "candidate_location_ids": candidate_ids,
                    },
                    blocker_classes,
                    blocking_errors,
                    blocking_findings,
                )
            elif player_facing:
                _add_blocker(
                    "ambiguous_destination_phrase",
                    f"Ambiguous destination phrase '{phrase}' cannot resolve uniquely",
                    {
                        "phrase": phrase,
                        "candidate_location_ids": candidate_ids,
                        "sources": sources,
                    },
                    blocker_classes,
                    blocking_errors,
                    blocking_findings,
                )
                _add_blocker(
                    "player_facing_phrase_collision",
                    f"Player-facing phrase collision for '{phrase}' across multiple valid locations",
                    {
                        "phrase": phrase,
                        "candidate_location_ids": candidate_ids,
                        "sources": sources,
                    },
                    blocker_classes,
                    blocking_errors,
                    blocking_findings,
                )
            else:
                warnings.append(
                    f"destination_phrases['{phrase}'] is ambiguous but not marked player-facing"
                )
        elif status == "unresolved":
            unresolved_destination_count += 1
            if candidate_ids:
                _add_blocker(
                    "semantic_payload_contradiction",
                    f"destination_phrases['{phrase}'] unresolved but candidate_location_ids is non-empty",
                    {
                        "phrase": phrase,
                        "field": "destination_phrases",
                        "status": status,
                        "candidate_location_ids": candidate_ids,
                    },
                    blocker_classes,
                    blocking_errors,
                    blocking_findings,
                )
            elif player_facing:
                _add_blocker(
                    "phase2_ambiguity_debt",
                    f"Unresolved destination phrase '{phrase}' classified as Phase 2 LLM ambiguity debt",
                    {"phrase": phrase, "sources": sources},
                    blocker_classes,
                    blocking_errors,
                    blocking_findings,
                )
            else:
                warnings.append(
                    f"destination_phrases['{phrase}'] is unresolved but not marked player-facing"
                )
        else:
            _add_blocker(
                "semantic_payload_contradiction",
                f"destination_phrases['{phrase}'] has invalid status '{status}'",
                {"phrase": phrase, "field": "destination_phrases", "status": status},
                blocker_classes,
                blocking_errors,
                blocking_findings,
            )

    for npc_name, row in sorted(npc_scene_authority.items()):
        row_dict = _safe_dict(row)
        name_slug = str(row_dict.get("name_slug", "") or "").strip()
        visible_location_ids = [
            str(value).strip().upper()
            for value in _safe_list(row_dict.get("visible_location_ids"))
            if str(value).strip()
        ]
        reveal_bindings = [
            entry
            for entry in _safe_list(row_dict.get("reveal_bindings"))
            if isinstance(entry, dict)
        ]
        sources = [
            str(value).strip()
            for value in _safe_list(row_dict.get("sources"))
            if str(value).strip()
        ]
        authored_mentions_count = row_dict.get("authored_mentions_count")
        if not isinstance(authored_mentions_count, int):
            authored_mentions_count = 0
        authored_mention_sources = [
            str(value).strip()
            for value in _safe_list(row_dict.get("authored_mention_sources"))
            if str(value).strip()
        ]

        if not name_slug:
            warnings.append(f"npc_scene_authority['{npc_name}'] missing name_slug")

        for binding_index, binding in enumerate(reveal_bindings):
            binding_location = str(binding.get("location_id", "") or "").strip().upper()
            binding_source = str(binding.get("source", "") or "").strip()
            if not binding_location:
                _add_blocker(
                    "semantic_payload_contradiction",
                    f"npc_scene_authority['{npc_name}'].reveal_bindings[{binding_index}] missing location_id",
                    {"npc": npc_name, "binding_index": binding_index},
                    blocker_classes,
                    blocking_errors,
                    blocking_findings,
                )
            if not binding_source:
                warnings.append(
                    f"npc_scene_authority['{npc_name}'].reveal_bindings[{binding_index}] missing source"
                )

        if not visible_location_ids and not reveal_bindings:
            missing_npc_authority_count += 1
            if authored_mentions_count > 0:
                _add_blocker(
                    "missing_npc_scene_authority",
                    f"NPC '{npc_name}' has authored presence but no deterministic scene authority path",
                    {
                        "npc": npc_name,
                        "authored_mentions_count": authored_mentions_count,
                        "authored_mention_sources": authored_mention_sources,
                    },
                    blocker_classes,
                    blocking_errors,
                    blocking_findings,
                )
            else:
                warnings.append(
                    f"npc_scene_authority['{npc_name}'] has no visible locations or reveal bindings"
                )

        if not sources:
            warnings.append(
                f"npc_scene_authority['{npc_name}'] has no provenance sources"
            )

    diagnostics = _safe_dict(semantic_authority.get("diagnostics"))
    diagnostics_missing_npc = _safe_list(diagnostics.get("missing_npc_authority"))
    diagnostics_ambiguous_destinations = _safe_list(
        diagnostics.get("ambiguous_destination_phrases")
    )
    diagnostics_unresolved_destinations = _safe_list(
        diagnostics.get("unresolved_destination_phrases")
    )
    diagnostics_normalized_shortforms = _safe_list(
        diagnostics.get("normalized_shortform_destination_phrases")
    )

    if (
        diagnostics_missing_npc
        and len(diagnostics_missing_npc) != missing_npc_authority_count
    ):
        warnings.append(
            "diagnostics.missing_npc_authority count does not match derived missing NPC authority count"
        )
    if (
        diagnostics_ambiguous_destinations
        and len(diagnostics_ambiguous_destinations) != ambiguous_destination_count
    ):
        warnings.append(
            "diagnostics.ambiguous_destination_phrases count does not match derived ambiguous destination count"
        )
    if (
        diagnostics_unresolved_destinations
        and len(diagnostics_unresolved_destinations) != unresolved_destination_count
    ):
        warnings.append(
            "diagnostics.unresolved_destination_phrases count does not match derived unresolved destination count"
        )

    normalized_shortform_count = 0
    for row in diagnostics_normalized_shortforms:
        row_dict = _safe_dict(row)
        phrase = str(row_dict.get("phrase", "") or "").strip()
        anchor_phrase = str(row_dict.get("anchor_phrase", "") or "").strip()
        location_id = str(row_dict.get("location_id", "") or "").strip().upper()
        if not phrase or not anchor_phrase or not location_id:
            warnings.append(
                "diagnostics.normalized_shortform_destination_phrases contains incomplete entry"
            )
            continue
        normalized_shortform_count += 1

    status = "fail" if blocking_errors else ("degraded" if warnings else "pass")
    exit_code = 1 if blocking_errors else 0

    return {
        "status": status,
        "module": module_dir.name,
        "module_path": str(module_dir),
        "version": version,
        "summary": {
            "location_alias_count": len(location_aliases),
            "destination_phrase_count": len(destination_phrases),
            "npc_scene_authority_count": len(npc_scene_authority),
            "ambiguous_destination_count": ambiguous_destination_count,
            "unresolved_destination_count": unresolved_destination_count,
            "missing_npc_authority_count": missing_npc_authority_count,
            "normalized_shortform_destination_count": normalized_shortform_count,
            "blocking_finding_count": len(blocking_findings),
            "warning_count": len(warnings),
        },
        "normalized_shortform_destination_phrases": diagnostics_normalized_shortforms,
        "blocker_classes": sorted(set(blocker_classes)),
        "blocking_findings": blocking_findings,
        "blocking_errors": blocking_errors,
        "warnings": warnings,
        "exit_code": exit_code,
    }


def main() -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Audit module semantic authority payload"
    )
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
            "blocking_errors": [str(exc)],
            "blocker_classes": ["invalid_cli_arguments"],
            "blocking_findings": [
                {
                    "class": "invalid_cli_arguments",
                    "message": str(exc),
                    "context": {},
                }
            ],
            "warnings": [],
            "summary": {},
            "exit_code": 1,
        }
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"[ERROR] {exc}")
        return 1

    payload = audit_module_semantic_authority(module_path)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"module={payload.get('module')} status={payload.get('status')}")
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
