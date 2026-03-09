#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""NeverEndingQuest - Continuity Cross-Module Reference Enrichment Helpers

Deterministically derive `continuity.cross_module_refs` candidates from module
context and plot text. This is an additive helper for ingest/remediation
workflows and does not mutate files directly.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Set


MODULE_ALIASES: Dict[str, List[str]] = {
    "Keep_of_Doom": ["keep of doom", "harrow's hollow", "harrows hollow"],
    "Night_of_the_Restless_Dead": [
        "night of the restless dead",
        "restless dead",
        "ma's watering hole",
    ],
    "The_Pumpkin_Kings_Curse": [
        "pumpkin king",
        "pumpkin king's curse",
        "greenfields vale",
        "first tithe",
        "harvest curse",
    ],
    "The_Thornwood_Watch": [
        "thornwood",
        "thornwood watch",
        "withered hart",
        "malarok",
        "voidstone",
    ],
}


MODULE_ENTITY_HINTS: Dict[str, List[Dict[str, Any]]] = {
    "Keep_of_Doom": [
        {
            "entity_id": "scout_elen",
            "relation": "reference",
            "keywords": ["scout elen", "harrow's hollow", "harrows hollow"],
            "notes": "Narrative handoff references Scout Elen and Harrow's Hollow.",
        },
        {
            "entity_id": "shadow_relic",
            "relation": "artifact_link",
            "keywords": ["shadow relic", "keep of doom"],
            "notes": "Shadow relic thread echoes in adjacent module lore.",
        },
    ],
    "Night_of_the_Restless_Dead": [
        {
            "entity_id": "sister_miriam_bramble",
            "relation": "reference",
            "keywords": ["miriam", "bramble", "restless dead"],
            "notes": "Cult lineage and Bramble thread connect to adjacent modules.",
        },
        {
            "entity_id": "necromantic_ring",
            "relation": "artifact_link",
            "keywords": ["necromantic ring", "counter ritual", "father aldric", "mas watering hole"],
            "notes": "Ring/cult artifact thread continues across linked content.",
        },
    ],
    "The_Pumpkin_Kings_Curse": [
        {
            "entity_id": "pumpkin_king",
            "relation": "antagonist",
            "keywords": ["pumpkin king", "harvest", "first tithe"],
            "notes": "Pumpkin King and harvest pact are shared continuity anchors.",
        },
        {
            "entity_id": "bramble_lineage",
            "relation": "reference",
            "keywords": ["bramble", "greenfields vale", "miriam"],
            "notes": "Bramble family lineage appears in linked module arcs.",
        },
    ],
    "The_Thornwood_Watch": [
        {
            "entity_id": "scout_elen_handoff",
            "relation": "reference",
            "keywords": ["scout elen", "harrows hollow", "harrow's hollow"],
            "notes": "Scout Elen handoff thread links Thornwood outcomes to Keep of Doom entry.",
        },
        {
            "entity_id": "malarok",
            "relation": "reference",
            "keywords": ["malarok", "voidstone", "old hunger", "thornwood"],
            "notes": "Malarok/old debt threads bridge northern and southern arcs.",
        },
        {
            "entity_id": "withered_hart",
            "relation": "ally",
            "keywords": ["withered hart", "split covenant", "southern vale"],
            "notes": "Withered Hart lore links to wider covenant/debt continuity.",
        },
    ],
}


def _normalize_text(value: str) -> str:
    lowered = value.lower()
    lowered = lowered.replace("_", " ")
    lowered = lowered.replace("-", " ")
    lowered = lowered.replace("'", "")
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered


def _collect_strings(payload: Any) -> List[str]:
    out: List[str] = []
    if isinstance(payload, dict):
        for value in payload.values():
            out.extend(_collect_strings(value))
    elif isinstance(payload, list):
        for value in payload:
            out.extend(_collect_strings(value))
    elif isinstance(payload, str):
        text = payload.strip()
        if text:
            out.append(text)
    return out


def _module_display_name(module_slug: str) -> str:
    return module_slug.replace("_", " ")


def _discover_known_modules(modules_root: Path = Path("modules")) -> List[str]:
    if not modules_root.exists():
        return []
    out: List[str] = []
    for entry in modules_root.iterdir():
        if entry.is_dir() and (entry / "areas").exists():
            out.append(entry.name)
    return sorted(out)


def _build_aliases(module_slug: str) -> List[str]:
    aliases: Set[str] = set(MODULE_ALIASES.get(module_slug, []))
    aliases.add(module_slug)
    aliases.add(_module_display_name(module_slug))

    display = _module_display_name(module_slug)
    without_the = re.sub(r"^the\s+", "", display, flags=re.IGNORECASE)
    aliases.add(without_the)

    normalized: List[str] = []
    for alias in aliases:
        token = _normalize_text(alias)
        if len(token) >= 4:
            normalized.append(token)
    return sorted(set(normalized))


def _match_count(text_blob: str, phrases: List[str]) -> int:
    count = 0
    for phrase in phrases:
        if phrase and phrase in text_blob:
            count += 1
    return count


def _derive_candidate_refs(
    module_slug: str,
    text_blob: str,
    known_modules: List[str],
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    for target_module in known_modules:
        if target_module == module_slug:
            continue

        alias_hits = _match_count(text_blob, _build_aliases(target_module))

        hint_rows = MODULE_ENTITY_HINTS.get(target_module, [])
        hint_matches = 0
        for hint in hint_rows:
            keywords = [_normalize_text(item) for item in hint.get("keywords", [])]
            key_hits = _match_count(text_blob, keywords)
            if key_hits <= 0:
                continue

            hint_matches += 1
            confidence = "high" if key_hits >= 2 else "medium"
            candidates.append(
                {
                    "target_module": target_module,
                    "entity_id": hint.get("entity_id", f"{target_module.lower()}_continuity_echo"),
                    "relation": hint.get("relation", "reference"),
                    "confidence": confidence,
                    "notes": hint.get(
                        "notes",
                        f"Inferred from narrative references to {_module_display_name(target_module)}.",
                    ),
                }
            )

        if alias_hits > 0 and hint_matches == 0:
            candidates.append(
                {
                    "target_module": target_module,
                    "entity_id": f"{target_module.lower()}_continuity_echo",
                    "relation": "reference",
                    "confidence": "medium" if alias_hits >= 2 else "low",
                    "notes": (
                        f"Inferred from {alias_hits} narrative mention(s) of "
                        f"{_module_display_name(target_module)}."
                    ),
                }
            )

    return candidates


def enrich_continuity_cross_refs(
    module_slug: str,
    module_context: Dict[str, Any],
    module_plot: Dict[str, Any],
    known_modules: List[str] | None = None,
) -> Dict[str, Any]:
    """Additive enrichment for `continuity.cross_module_refs`.

    Returns shape:
      {
        "status": "success",
        "module_context": dict,
        "changed": bool,
        "added_refs": list[dict],
        "existing_count": int,
        "final_count": int,
      }
    """
    if known_modules is None:
        known_modules = _discover_known_modules()

    continuity = module_context.get("continuity")
    if not isinstance(continuity, dict):
        continuity = {}
        module_context["continuity"] = continuity

    existing_refs = continuity.get("cross_module_refs")
    if not isinstance(existing_refs, list):
        existing_refs = []
        continuity["cross_module_refs"] = existing_refs

    string_pool = _collect_strings(module_context) + _collect_strings(module_plot)
    text_blob = _normalize_text("\n".join(string_pool))

    candidates = _derive_candidate_refs(module_slug, text_blob, known_modules)
    existing_keys = {
        (
            str(ref.get("target_module", "")).strip(),
            str(ref.get("entity_id", "")).strip(),
            str(ref.get("relation", "")).strip(),
        )
        for ref in existing_refs
        if isinstance(ref, dict)
    }

    added_refs: List[Dict[str, Any]] = []
    for ref in candidates:
        key = (
            str(ref.get("target_module", "")).strip(),
            str(ref.get("entity_id", "")).strip(),
            str(ref.get("relation", "")).strip(),
        )
        if key in existing_keys:
            continue
        existing_refs.append(ref)
        added_refs.append(ref)
        existing_keys.add(key)

    confidence_rank = {"high": 0, "medium": 1, "low": 2}
    existing_refs.sort(
        key=lambda row: (
            str(row.get("target_module", "")),
            confidence_rank.get(str(row.get("confidence", "low")), 3),
            str(row.get("entity_id", "")),
        )
    )

    return {
        "status": "success",
        "module_context": module_context,
        "changed": len(added_refs) > 0,
        "added_refs": added_refs,
        "existing_count": len(existing_refs) - len(added_refs),
        "final_count": len(existing_refs),
    }
