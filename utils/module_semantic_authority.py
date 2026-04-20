# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Module Semantic Authority Helpers
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Deterministically derives additive publication-oriented semantic authority data
from authored module files.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from utils.file_operations import safe_read_json


_TITLE_PREFIX_TOKENS = {
    "the",
    "room",
    "brother",
    "father",
    "sister",
    "saint",
    "sir",
    "lady",
    "lord",
}

_DESTINATION_TERMINALS = {
    "place",
    "lodging",
    "sanctuary",
    "inn",
    "refuge",
    "hall",
    "chamber",
    "catacomb",
    "catacombs",
    "cathedral",
    "tower",
    "shrine",
    "camp",
    "cellar",
    "crypt",
    "road",
    "refectory",
    "keep",
}

_LEADING_PHRASE_STOPWORDS = {
    "the",
    "a",
    "an",
    "to",
    "toward",
    "towards",
    "at",
    "into",
    "in",
    "on",
}


def _normalize_phrase(value: Any) -> str:
    """Normalize free text for deterministic matching."""
    text = str(value or "").lower()
    text = text.replace("_", " ").replace("-", " ").replace("'", "")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _expand_phrase_variants(raw_phrase: str) -> List[str]:
    """Expand deterministic phrase variants for alias and destination mapping."""
    normalized = _normalize_phrase(raw_phrase)
    if not normalized:
        return []

    variants: Set[str] = {normalized}
    tokens = normalized.split()

    if tokens and tokens[0] == "the" and len(tokens) > 1:
        variants.add(" ".join(tokens[1:]))

    if len(tokens) >= 3 and tokens[0] == "room" and tokens[1].isdigit():
        variants.add(" ".join(tokens[2:]))

    trim_index = 0
    while trim_index < len(tokens) - 1 and tokens[trim_index] in _TITLE_PREFIX_TOKENS:
        trim_index += 1
        variants.add(" ".join(tokens[trim_index:]))

    return sorted(variant for variant in variants if len(variant) >= 3)


def _safe_list(value: Any) -> List[Any]:
    """Return list value or empty list."""
    return value if isinstance(value, list) else []


def _iter_area_payloads(module_dir: Path) -> List[Tuple[str, Dict[str, Any]]]:
    """Load authored area payloads, excluding backup mirrors."""
    area_dir = module_dir / "areas"
    if not area_dir.exists() or not area_dir.is_dir():
        return []

    payloads: List[Tuple[str, Dict[str, Any]]] = []
    for area_path in sorted(area_dir.glob("*.json")):
        if area_path.name.endswith("_BU.json"):
            continue
        payload = safe_read_json(str(area_path))
        if not isinstance(payload, dict):
            continue
        payloads.append((f"areas/{area_path.name}", payload))
    return payloads


def _extract_location_records(module_dir: Path) -> List[Dict[str, Any]]:
    """Extract canonical location records from area files."""
    records: List[Dict[str, Any]] = []
    for source_path, area_payload in _iter_area_payloads(module_dir):
        area_id = str(area_payload.get("areaId", "") or "").strip().upper()
        for index, location in enumerate(_safe_list(area_payload.get("locations"))):
            if not isinstance(location, dict):
                continue
            location_id = (
                str(location.get("locationId") or location.get("id") or "")
                .strip()
                .upper()
            )
            if not location_id:
                continue

            aliases = [
                str(alias).strip()
                for alias in _safe_list(location.get("aliases"))
                if str(alias).strip()
            ]
            records.append(
                {
                    "area_id": area_id,
                    "location_id": location_id,
                    "location_name": str(location.get("name", "") or "").strip(),
                    "source_room_title": str(
                        location.get("source_room_title", "") or ""
                    ).strip(),
                    "aliases": aliases,
                    "source_path": source_path,
                    "location": location,
                    "index": index,
                }
            )
    records.sort(
        key=lambda item: (item.get("location_id", ""), item.get("source_path", ""))
    )
    return records


def _build_location_alias_map(location_records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build deterministic location alias map with ambiguity diagnostics."""
    alias_index: Dict[str, Dict[str, Any]] = {}
    location_name_lookup: Dict[str, str] = {}

    for record in location_records:
        location_id = str(record.get("location_id", "") or "")
        location_name_lookup[location_id] = str(
            record.get("location_name", "") or location_id
        )
        source_path = str(record.get("source_path", "") or "")

        raw_phrases: List[Tuple[str, str]] = []
        location_name = str(record.get("location_name", "") or "").strip()
        if location_name:
            raw_phrases.append(
                (location_name, f"{source_path}#locations[{location_id}].name")
            )

        source_room_title = str(record.get("source_room_title", "") or "").strip()
        if source_room_title:
            raw_phrases.append(
                (
                    source_room_title,
                    f"{source_path}#locations[{location_id}].source_room_title",
                )
            )

        for alias in record.get("aliases", []):
            alias_value = str(alias).strip()
            if not alias_value:
                continue
            raw_phrases.append(
                (alias_value, f"{source_path}#locations[{location_id}].aliases")
            )

        for raw_phrase, source_ref in raw_phrases:
            for variant in _expand_phrase_variants(raw_phrase):
                row = alias_index.setdefault(
                    variant,
                    {
                        "location_ids": set(),
                        "sources": set(),
                    },
                )
                row["location_ids"].add(location_id)
                row["sources"].add(source_ref)

    location_aliases: Dict[str, Dict[str, Any]] = {}
    duplicate_aliases: List[Dict[str, Any]] = []

    for phrase in sorted(alias_index.keys()):
        row = alias_index[phrase]
        location_ids = sorted(row["location_ids"])
        sources = sorted(row["sources"])

        if len(location_ids) == 1:
            location_id = location_ids[0]
            location_aliases[phrase] = {
                "status": "resolved",
                "location_id": location_id,
                "location_name": location_name_lookup.get(location_id, location_id),
                "candidate_location_ids": location_ids,
                "sources": sources,
            }
        else:
            location_aliases[phrase] = {
                "status": "ambiguous",
                "candidate_location_ids": location_ids,
                "sources": sources,
            }
            duplicate_aliases.append(
                {
                    "phrase": phrase,
                    "candidate_location_ids": location_ids,
                    "sources": sources,
                }
            )

    return {
        "location_aliases": location_aliases,
        "duplicate_aliases": duplicate_aliases,
    }


def _append_evidence(
    evidence: List[Dict[str, Any]],
    text: Any,
    source: str,
    location_id: str,
    destination_eligible: bool = False,
) -> None:
    """Append deterministic evidence text row if value is non-empty text."""
    if not isinstance(text, str):
        return
    content = text.strip()
    if not content:
        return
    evidence.append(
        {
            "text": content,
            "normalized": _normalize_phrase(content),
            "source": source,
            "location_id": location_id,
            "destination_eligible": bool(destination_eligible),
        }
    )


def _collect_location_evidence(
    location_records: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Collect bounded destination/NPC evidence text from location payloads."""
    evidence: List[Dict[str, Any]] = []
    for record in location_records:
        location = (
            record.get("location") if isinstance(record.get("location"), dict) else {}
        )
        location_id = str(record.get("location_id", "") or "")
        source_path = str(record.get("source_path", "") or "")
        source_prefix = f"{source_path}#locations[{location_id}]"

        for field_name in ["name", "source_room_title", "description", "dmInstructions", "accessibility", "creatures"]:
            destination_eligible = field_name in {"name", "source_room_title"}
            _append_evidence(
                evidence,
                location.get(field_name),
                f"{source_prefix}.{field_name}",
                location_id,
                destination_eligible=destination_eligible,
            )

        for list_field in ["aliases", "plotHooks", "dcChecks"]:
            for item in _safe_list(location.get(list_field)):
                destination_eligible = list_field == "aliases"
                _append_evidence(
                    evidence,
                    item,
                    f"{source_prefix}.{list_field}",
                    location_id,
                    destination_eligible=destination_eligible,
                )

        for feature in _safe_list(location.get("features")):
            if not isinstance(feature, dict):
                continue
            _append_evidence(
                evidence,
                feature.get("name"),
                f"{source_prefix}.features.name",
                location_id,
                destination_eligible=False,
            )
            _append_evidence(
                evidence,
                feature.get("description"),
                f"{source_prefix}.features.description",
                location_id,
                destination_eligible=False,
            )

        for hook in _safe_list(location.get("investigation_hooks")):
            if not isinstance(hook, dict):
                continue
            for field_name in [
                "trigger",
                "description",
                "reward",
                "consequence",
                "cross_module_ref",
            ]:
                _append_evidence(
                    evidence,
                    hook.get(field_name),
                    f"{source_prefix}.investigation_hooks.{field_name}",
                    location_id,
                    destination_eligible=False,
                )
    return evidence


def _collect_plot_evidence(module_plot: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Collect bounded destination/NPC evidence text from module plot payload."""
    evidence: List[Dict[str, Any]] = []
    for plot_point in _safe_list(module_plot.get("plotPoints")):
        if not isinstance(plot_point, dict):
            continue
        plot_id = str(plot_point.get("id", "") or "").strip() or "plot_point"
        location_id = str(plot_point.get("location", "") or "").strip().upper()
        source_prefix = f"module_plot.json#plotPoints[{plot_id}]"
        for field_name in ["title", "description", "plotImpact"]:
            destination_eligible = field_name == "title"
            _append_evidence(
                evidence,
                plot_point.get(field_name),
                f"{source_prefix}.{field_name}",
                location_id,
                destination_eligible=destination_eligible,
            )
    return evidence


def _contains_travel_verb(normalized_text: str) -> bool:
    """Return True when text contains explicit travel intent verbs."""
    travel_markers = [
        "go to",
        "travel to",
        "head to",
        "return to",
        "enter ",
        "seek ",
        "find ",
    ]
    padded = f" {normalized_text} "
    return any(marker in padded for marker in travel_markers)


def _extract_canonical_anchor_phrases(
    normalized_text: str,
    location_aliases: Dict[str, Dict[str, Any]],
) -> List[str]:
    """Extract canonical destination aliases explicitly anchored in prose."""
    if not _contains_travel_verb(normalized_text):
        return []

    anchored: List[str] = []
    padded = f" {normalized_text} "
    for phrase in sorted(location_aliases.keys(), key=lambda value: len(value), reverse=True):
        if len(phrase) < 4:
            continue
        if f" {phrase} " not in padded:
            continue
        anchored.append(phrase)
    return anchored


def _extract_destination_phrase_candidates(normalized_text: str) -> List[str]:
    """Extract bounded destination-like phrases from normalized text."""
    tokens = normalized_text.split()
    if not tokens:
        return []

    candidates: Set[str] = set()
    for end_index, token in enumerate(tokens):
        if token not in _DESTINATION_TERMINALS:
            continue
        for window_size in range(2, 7):
            start_index = end_index - window_size + 1
            if start_index < 0:
                continue
            window_tokens = tokens[start_index : end_index + 1]
            while (
                len(window_tokens) > 1 and window_tokens[0] in _LEADING_PHRASE_STOPWORDS
            ):
                window_tokens = window_tokens[1:]
            phrase = " ".join(window_tokens).strip()
            if len(phrase) < 5:
                continue
            candidates.add(phrase)

    return sorted(candidates)


def _build_destination_phrase_map(
    location_aliases: Dict[str, Dict[str, Any]],
    evidence_rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build destination phrase map with resolved/ambiguous/unresolved classes."""
    phrase_rows: Dict[str, Dict[str, Any]] = {}

    for phrase, alias_row in location_aliases.items():
        phrase_rows[phrase] = {
            "candidate_location_ids": set(
                alias_row.get("candidate_location_ids") or []
            ),
            "sources": set(alias_row.get("sources") or []),
            "observed": False,
            "observed_count": 0,
        }

    for evidence in evidence_rows:
        normalized_text = str(evidence.get("normalized", "") or "")
        source = str(evidence.get("source", "") or "")
        if not normalized_text:
            continue
        destination_eligible = bool(evidence.get("destination_eligible", False))
        if destination_eligible:
            candidate_phrases = _extract_destination_phrase_candidates(normalized_text)
        else:
            candidate_phrases = _extract_canonical_anchor_phrases(
                normalized_text,
                location_aliases,
            )

        for phrase in candidate_phrases:
            row = phrase_rows.setdefault(
                phrase,
                {
                    "candidate_location_ids": set(),
                    "sources": set(),
                    "observed": False,
                    "observed_count": 0,
                },
            )
            row["observed"] = True
            row["observed_count"] = int(row.get("observed_count", 0) or 0) + 1
            row["sources"].add(source)

            alias_row = location_aliases.get(phrase)
            if isinstance(alias_row, dict):
                row["candidate_location_ids"].update(
                    alias_row.get("candidate_location_ids") or []
                )

    destination_phrases: Dict[str, Dict[str, Any]] = {}
    ambiguous: List[Dict[str, Any]] = []
    unresolved: List[Dict[str, Any]] = []

    for phrase in sorted(phrase_rows.keys()):
        row = phrase_rows[phrase]
        candidate_ids = sorted(row["candidate_location_ids"])
        sources = sorted(row["sources"])

        if len(candidate_ids) == 1:
            destination_phrases[phrase] = {
                "status": "resolved",
                "location_id": candidate_ids[0],
                "candidate_location_ids": candidate_ids,
                "sources": sources,
                "observed": bool(row["observed"]),
                "player_facing": bool(row["observed"]),
                "observation_count": int(row.get("observed_count", 0) or 0),
            }
        elif len(candidate_ids) > 1:
            destination_phrases[phrase] = {
                "status": "ambiguous",
                "candidate_location_ids": candidate_ids,
                "sources": sources,
                "observed": bool(row["observed"]),
                "player_facing": bool(row["observed"]),
                "observation_count": int(row.get("observed_count", 0) or 0),
            }
            ambiguous.append(
                {
                    "phrase": phrase,
                    "candidate_location_ids": candidate_ids,
                    "sources": sources,
                    "player_facing": bool(row["observed"]),
                }
            )
        else:
            destination_phrases[phrase] = {
                "status": "unresolved",
                "candidate_location_ids": [],
                "sources": sources,
                "observed": bool(row["observed"]),
                "player_facing": bool(row["observed"]),
                "observation_count": int(row.get("observed_count", 0) or 0),
            }
            unresolved.append(
                {
                    "phrase": phrase,
                    "sources": sources,
                    "player_facing": bool(row["observed"]),
                }
            )

    return {
        "destination_phrases": destination_phrases,
        "ambiguous_destination_phrases": ambiguous,
        "unresolved_destination_phrases": unresolved,
    }


def _extract_visible_npc_rows(
    location_records: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Extract visible NPC authority from location NPC arrays."""
    visible_rows: Dict[str, Dict[str, Any]] = {}
    for record in location_records:
        location = (
            record.get("location") if isinstance(record.get("location"), dict) else {}
        )
        location_id = str(record.get("location_id", "") or "")
        source_path = str(record.get("source_path", "") or "")
        source_ref = f"{source_path}#locations[{location_id}].npcs"
        for npc_entry in _safe_list(location.get("npcs")):
            if isinstance(npc_entry, dict):
                npc_name = str(npc_entry.get("name", "") or "").strip()
            else:
                npc_name = str(npc_entry or "").strip()
            if not npc_name:
                continue
            npc_slug = _normalize_phrase(npc_name)
            if not npc_slug:
                continue
            row = visible_rows.setdefault(
                npc_slug,
                {
                    "canonical_name": npc_name,
                    "visible_location_ids": set(),
                    "sources": set(),
                },
            )
            row["visible_location_ids"].add(location_id)
            row["sources"].add(source_ref)
            if len(npc_name) > len(str(row.get("canonical_name", "") or "")):
                row["canonical_name"] = npc_name
    return visible_rows


def _extract_module_npc_catalog(
    module_context: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """Extract canonical NPC catalog from module_context metadata."""
    catalog: Dict[str, Dict[str, Any]] = {}
    npc_payload = module_context.get("npcs")
    if not isinstance(npc_payload, dict):
        return catalog

    for npc_key, npc_entry in sorted(npc_payload.items()):
        if isinstance(npc_entry, dict):
            npc_name = str(npc_entry.get("name", "") or "").strip()
        else:
            npc_name = ""
        if not npc_name:
            npc_name = str(npc_key or "").replace("_", " ").strip()
        if not npc_name:
            continue
        npc_slug = _normalize_phrase(npc_name)
        if not npc_slug:
            continue
        catalog[npc_slug] = {
            "canonical_name": npc_name,
            "sources": {f"module_context.json#npcs.{npc_key}"},
        }
    return catalog


def _contains_phrase(normalized_text: str, normalized_phrase: str) -> bool:
    """Return True when phrase appears as bounded token sequence."""
    if not normalized_text or not normalized_phrase:
        return False
    return f" {normalized_phrase} " in f" {normalized_text} "


def _build_npc_scene_authority_map(
    module_context: Dict[str, Any],
    location_records: List[Dict[str, Any]],
    evidence_rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build visible and revealable NPC scene authority map."""
    module_catalog = _extract_module_npc_catalog(module_context)
    visible_rows = _extract_visible_npc_rows(location_records)

    all_npcs: Dict[str, Dict[str, Any]] = {}
    for npc_slug, row in module_catalog.items():
        all_npcs[npc_slug] = {
            "canonical_name": str(row.get("canonical_name", "") or npc_slug),
            "sources": set(row.get("sources") or []),
            "visible_location_ids": set(),
            "reveal_bindings": [],
            "authored_mention_sources": set(),
        }

    for npc_slug, row in visible_rows.items():
        authority = all_npcs.setdefault(
            npc_slug,
            {
                "canonical_name": str(row.get("canonical_name", "") or npc_slug),
                "sources": set(),
                "visible_location_ids": set(),
                "reveal_bindings": [],
                "authored_mention_sources": set(),
            },
        )
        authority["visible_location_ids"].update(
            row.get("visible_location_ids") or set()
        )
        authority["sources"].update(row.get("sources") or set())
        if len(str(row.get("canonical_name", "") or "")) > len(
            str(authority.get("canonical_name", "") or "")
        ):
            authority["canonical_name"] = str(
                row.get("canonical_name", "") or authority.get("canonical_name", "")
            )

    trailing_token_to_npcs: Dict[str, Set[str]] = {}
    for npc_slug in all_npcs.keys():
        tokens = npc_slug.split()
        if not tokens:
            continue
        trailing = tokens[-1]
        if len(trailing) < 4:
            continue
        trailing_token_to_npcs.setdefault(trailing, set()).add(npc_slug)

    for evidence in evidence_rows:
        location_id = str(evidence.get("location_id", "") or "").strip().upper()
        normalized_text = str(evidence.get("normalized", "") or "")
        source_ref = str(evidence.get("source", "") or "")
        if not location_id or not normalized_text:
            continue

        for npc_slug, authority in all_npcs.items():
            visible_ids = authority.get("visible_location_ids") or set()
            matched = _contains_phrase(normalized_text, npc_slug)
            if not matched:
                trailing = npc_slug.split()[-1] if npc_slug.split() else ""
                if (
                    trailing
                    and len(trailing) >= 4
                    and len(trailing_token_to_npcs.get(trailing, set())) == 1
                ):
                    matched = _contains_phrase(normalized_text, trailing)

            if not matched:
                continue

            authority.setdefault("authored_mention_sources", set()).add(source_ref)
            authority.setdefault("sources", set()).add(source_ref)

            if location_id in visible_ids:
                continue

            binding = {
                "location_id": location_id,
                "source": source_ref,
                "reason": "authored_text_reference",
            }
            existing_keys = {
                (entry.get("location_id"), entry.get("source"))
                for entry in authority.get("reveal_bindings", [])
                if isinstance(entry, dict)
            }
            if (binding["location_id"], binding["source"]) in existing_keys:
                continue
            authority.setdefault("reveal_bindings", []).append(binding)
            authority.setdefault("sources", set()).add(source_ref)

    npc_scene_authority: Dict[str, Dict[str, Any]] = {}
    missing_npc_authority: List[Dict[str, Any]] = []

    for npc_slug in sorted(all_npcs.keys()):
        authority = all_npcs[npc_slug]
        visible_location_ids = sorted(authority.get("visible_location_ids") or [])
        reveal_bindings = sorted(
            [
                {
                    "location_id": str(entry.get("location_id", "") or "")
                    .strip()
                    .upper(),
                    "source": str(entry.get("source", "") or ""),
                    "reason": str(
                        entry.get("reason", "authored_text_reference")
                        or "authored_text_reference"
                    ),
                }
                for entry in authority.get("reveal_bindings", [])
                if isinstance(entry, dict)
            ],
            key=lambda entry: (entry.get("location_id", ""), entry.get("source", "")),
        )
        sources = sorted(authority.get("sources") or [])
        authored_mention_sources = sorted(
            authority.get("authored_mention_sources") or []
        )
        canonical_name = str(authority.get("canonical_name", "") or npc_slug)

        npc_scene_authority[canonical_name] = {
            "name_slug": npc_slug,
            "visible_location_ids": visible_location_ids,
            "reveal_bindings": reveal_bindings,
            "sources": sources,
            "authored_mentions_count": len(authored_mention_sources),
            "authored_mention_sources": authored_mention_sources,
        }

        if not visible_location_ids and not reveal_bindings:
            missing_npc_authority.append(
                {
                    "npc": canonical_name,
                    "name_slug": npc_slug,
                    "sources": sources,
                    "authored_mentions_count": len(authored_mention_sources),
                    "authored_mention_sources": authored_mention_sources,
                }
            )

    return {
        "npc_scene_authority": npc_scene_authority,
        "missing_npc_authority": missing_npc_authority,
    }


def build_module_semantic_authority(
    module_slug: str,
    module_context: Dict[str, Any],
    module_plot: Dict[str, Any],
    module_dir: Path,
) -> Dict[str, Any]:
    """Build semantic-authority payload from authored module data."""
    location_records = _extract_location_records(module_dir)

    alias_result = _build_location_alias_map(location_records)
    location_aliases = alias_result["location_aliases"]

    evidence_rows = _collect_location_evidence(location_records)
    evidence_rows.extend(_collect_plot_evidence(module_plot))

    destination_result = _build_destination_phrase_map(location_aliases, evidence_rows)
    npc_result = _build_npc_scene_authority_map(
        module_context, location_records, evidence_rows
    )

    diagnostics = {
        "duplicate_location_aliases": alias_result["duplicate_aliases"],
        "ambiguous_destination_phrases": destination_result[
            "ambiguous_destination_phrases"
        ],
        "unresolved_destination_phrases": destination_result[
            "unresolved_destination_phrases"
        ],
        "missing_npc_authority": npc_result["missing_npc_authority"],
    }

    return {
        "version": "v1",
        "module_slug": module_slug,
        "location_aliases": location_aliases,
        "destination_phrases": destination_result["destination_phrases"],
        "npc_scene_authority": npc_result["npc_scene_authority"],
        "diagnostics": diagnostics,
        "summary": {
            "location_count": len(location_records),
            "location_alias_count": len(location_aliases),
            "destination_phrase_count": len(destination_result["destination_phrases"]),
            "npc_count": len(npc_result["npc_scene_authority"]),
            "ambiguous_destination_count": len(
                destination_result["ambiguous_destination_phrases"]
            ),
            "missing_npc_authority_count": len(npc_result["missing_npc_authority"]),
        },
    }


def enrich_module_semantic_authority(
    module_slug: str,
    module_context: Dict[str, Any],
    module_plot: Dict[str, Any],
    module_dir: Path,
) -> Dict[str, Any]:
    """Additively enrich module_context with semantic authority payload.

    Returns shape:
      {
        "status": "success|degraded|failed",
        "module_context": dict,
        "semantic_authority": dict,
        "changed": bool,
        "warnings": list[str],
        "errors": list[str],
      }
    """
    warnings: List[str] = []
    errors: List[str] = []

    try:
        semantic_authority = build_module_semantic_authority(
            module_slug=module_slug,
            module_context=module_context,
            module_plot=module_plot,
            module_dir=module_dir,
        )
    except Exception as exc:
        return {
            "status": "failed",
            "module_context": module_context,
            "semantic_authority": {},
            "changed": False,
            "warnings": [],
            "errors": [f"semantic_authority_enrichment_exception: {exc}"],
        }

    diagnostics = (
        semantic_authority.get("diagnostics")
        if isinstance(semantic_authority.get("diagnostics"), dict)
        else {}
    )
    ambiguous_destinations = (
        diagnostics.get("ambiguous_destination_phrases")
        if isinstance(diagnostics.get("ambiguous_destination_phrases"), list)
        else []
    )
    unresolved_destinations = (
        diagnostics.get("unresolved_destination_phrases")
        if isinstance(diagnostics.get("unresolved_destination_phrases"), list)
        else []
    )
    missing_npc_authority = (
        diagnostics.get("missing_npc_authority")
        if isinstance(diagnostics.get("missing_npc_authority"), list)
        else []
    )

    if ambiguous_destinations:
        warnings.append(
            f"semantic_authority_ambiguous_destination_phrases={len(ambiguous_destinations)}"
        )
    if unresolved_destinations:
        warnings.append(
            f"semantic_authority_unresolved_destination_phrases={len(unresolved_destinations)}"
        )
    if missing_npc_authority:
        warnings.append(
            f"semantic_authority_missing_npc_authority={len(missing_npc_authority)}"
        )

    existing = module_context.get("semantic_authority")
    changed = existing != semantic_authority
    module_context["semantic_authority"] = semantic_authority

    status = "degraded" if warnings else "success"
    if errors:
        status = "failed"

    return {
        "status": status,
        "module_context": module_context,
        "semantic_authority": semantic_authority,
        "changed": changed,
        "warnings": warnings,
        "errors": errors,
    }
