# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Source-Anonymous Atom Builder
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Consumes chunked local book text (JSONL) and emits source-anonymous inspiration
atoms suitable for committable narrative systems.

Design goals:
- One-book-at-a-time processing
- No source prose in output
- No title/author/source metadata in output
- Fail-closed compliance checks for banned keys/terms
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Pattern, Set, Tuple


BANNED_KEYS_DEFAULT: Set[str] = {
    "title",
    "author",
    "series",
    "source",
    "source_id",
    "source_name",
    "source_title",
    "source_author",
    "chapter",
    "chapter_name",
    "quote",
    "quotes",
    "excerpt",
    "excerpt_text",
    "raw_text",
    "text",
    "content",
    "book",
    "novel",
}


BANNED_TERMS_DEFAULT: Set[str] = {
    "clive barker",
    "weaveworld",
    "cabal",
    "nightbreed",
    "everville",
    "the thief of always",
}


def utc_now_iso() -> str:
    """Return UTC timestamp in ISO8601 Z format."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def estimate_tokens(text: str) -> int:
    """Estimate token count using tiktoken when available."""
    try:
        import tiktoken  # type: ignore

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        words = len(re.findall(r"\S+", text))
        return int(words * 1.3)


def normalize_text(text: str) -> str:
    """Normalize text for matching."""
    lowered = text.lower()
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered.strip()


@dataclass
class AtomTemplate:
    """Template for abstract atom extraction."""

    atom_id: str
    atom_type: str
    label: str
    description: str
    keywords: Tuple[str, ...]
    min_hits: int = 2
    srd_compatibility: str = "compatible"


ATOM_TEMPLATES: Tuple[AtomTemplate, ...] = (
    AtomTemplate(
        atom_id="atom.hidden_refuge",
        atom_type="motif",
        label="Hidden refuge under ordinary world",
        description="A concealed community survives beneath or behind normal society.",
        keywords=(r"\bhidden\b", r"\bsecret\b", r"\bunderground\b|\bunderworld\b|\bcatacomb\b|\bmaze\b"),
    ),
    AtomTemplate(
        atom_id="atom.liminal_threshold",
        atom_type="scene_template",
        label="Liminal threshold crossing",
        description="Crossing a boundary shifts reality rules and raises narrative stakes.",
        keywords=(r"\bdoor\b|\bgate\b|\bthreshold\b", r"\bother world\b|\belsewhere\b|\bbelow\b|\bbeyond\b"),
    ),
    AtomTemplate(
        atom_id="atom.outcast_persecution",
        atom_type="faction_pattern",
        label="Outcast persecution cycle",
        description="An outsider group faces organized fear, hunt, and forced displacement.",
        keywords=(r"\bhunt\b|\bpurge\b|\bmob\b|\bcrusade\b", r"\boutcast\b|\boutsider\b|\bmonster\b|\bfreak\b"),
    ),
    AtomTemplate(
        atom_id="atom.masked_authority_predator",
        atom_type="archetype",
        label="Masked authority predator",
        description="A trusted public figure hides predatory violence behind social legitimacy.",
        keywords=(r"\bdoctor\b|\bpriest\b|\bofficer\b|\bauthority\b", r"\bbetray\b|\bmask\b|\bsecret\b|\bpredator\b|\bkill\b"),
    ),
    AtomTemplate(
        atom_id="atom.body_transformation",
        atom_type="motif",
        label="Body transformation pressure",
        description="Identity is expressed through physical transformation and altered embodiment.",
        keywords=(r"\btransform\b|\bchange\b|\bmetamorph\b|\bshape\b", r"\bflesh\b|\bskin\b|\bblood\b|\bbone\b"),
    ),
    AtomTemplate(
        atom_id="atom.desire_cost_bargain",
        atom_type="arc_shape",
        label="Desire-cost bargain",
        description="A character seeks belonging or power and pays escalating personal cost.",
        keywords=(r"\bdesire\b|\blonging\b|\bwant\b|\bhunger\b", r"\bcost\b|\bprice\b|\bsacrifice\b|\bloss\b"),
    ),
    AtomTemplate(
        atom_id="atom.rebirth_after_ordeal",
        atom_type="arc_shape",
        label="Rebirth after ordeal",
        description="A protagonist survives collapse and returns with a new role or burden.",
        keywords=(r"\bdeath\b|\bdie\b|\bdead\b", r"\breturn\b|\breborn\b|\bnew\b|\bbecome\b"),
    ),
    AtomTemplate(
        atom_id="atom.dread_tenderness",
        atom_type="tone",
        label="Dread balanced with tenderness",
        description="Scenes combine intimate vulnerability with high dread or horror pressure.",
        keywords=(r"\blove\b|\btouch\b|\btender\b|\bkiss\b", r"\bdread\b|\bterror\b|\bhorror\b|\bfear\b"),
    ),
    AtomTemplate(
        atom_id="atom.siege_at_dusk",
        atom_type="scene_template",
        label="Siege with time pressure",
        description="A confrontation escalates against a hard temporal boundary.",
        keywords=(r"\bsiege\b|\bassault\b|\battack\b", r"\bdusk\b|\bnightfall\b|\bbefore night\b|\btimed\b"),
    ),
    AtomTemplate(
        atom_id="atom.diaspora_after_exposure",
        atom_type="faction_pattern",
        label="Diaspora after exposure",
        description="After sanctuary failure, a faction fragments and scatters across regions.",
        keywords=(r"\bexposed\b|\bdiscovered\b|\bfound\b", r"\bscatter\b|\bflee\b|\bdisperse\b|\bdiaspora\b"),
    ),
    AtomTemplate(
        atom_id="atom.child_prophecy",
        atom_type="archetype",
        label="Child with unsettling foresight",
        description="A child figure carries prophetic or uncanny insight that redirects events.",
        keywords=(r"\bchild\b|\bgirl\b|\bboy\b", r"\bprophe\b|\bvision\b|\bforetell\b|\bsee\b"),
    ),
    AtomTemplate(
        atom_id="atom.world_below_memory",
        atom_type="motif",
        label="World-below memory vault",
        description="Buried spaces preserve memory, identity, and continuity against surface change.",
        keywords=(r"\bgrave\b|\bcrypt\b|\btomb\b", r"\bmemory\b|\bhistory\b|\brecord\b|\bremember\b"),
    ),
)


def compile_templates(templates: Iterable[AtomTemplate]) -> Dict[str, List[Pattern[str]]]:
    """Compile keyword regexes for each template."""
    compiled: Dict[str, List[Pattern[str]]] = {}
    for template in templates:
        compiled[template.atom_id] = [re.compile(pattern, re.IGNORECASE) for pattern in template.keywords]
    return compiled


def load_chunks_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Load chunk rows from JSONL file."""
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError as parse_error:
                raise ValueError(f"Invalid JSON at line {line_no}: {parse_error}") from parse_error
            if not isinstance(row, dict):
                raise ValueError(f"Invalid row type at line {line_no}: expected object")
            rows.append(row)
    return rows


def score_templates(
    chunks: List[Dict[str, Any]],
    templates: Iterable[AtomTemplate],
    compiled: Dict[str, List[Pattern[str]]],
) -> List[Dict[str, Any]]:
    """Score templates against chunk text and build atom candidates."""
    total_chunks = len(chunks)
    candidates: List[Dict[str, Any]] = []

    for template in templates:
        chunk_hits = 0
        total_keyword_hits = 0
        matched_keyword_slots = 0

        for chunk in chunks:
            text = normalize_text(str(chunk.get("text", "")))
            if not text:
                continue

            per_chunk_slot_hits = 0
            per_chunk_total = 0

            for regex in compiled[template.atom_id]:
                hits = len(regex.findall(text))
                if hits > 0:
                    per_chunk_slot_hits += 1
                    per_chunk_total += hits

            if per_chunk_total > 0:
                chunk_hits += 1
                total_keyword_hits += per_chunk_total
                matched_keyword_slots = max(matched_keyword_slots, per_chunk_slot_hits)

        if total_keyword_hits < template.min_hits:
            continue

        coverage = (chunk_hits / total_chunks) if total_chunks > 0 else 0.0
        weight = min(
            0.95,
            0.42
            + 0.10 * matched_keyword_slots
            + 0.04 * math.log1p(total_keyword_hits)
            + 0.18 * coverage,
        )

        candidates.append(
            {
                "atom_id": template.atom_id,
                "atom_type": template.atom_type,
                "label": template.label,
                "description": template.description,
                "weight": round(weight, 2),
                "srd_compatibility": template.srd_compatibility,
                "evidence": {
                    "total_keyword_hits": total_keyword_hits,
                    "chunk_hits": chunk_hits,
                    "chunk_coverage": round(coverage, 3),
                    "matched_keyword_slots": matched_keyword_slots,
                },
            }
        )

    candidates.sort(
        key=lambda item: (
            float(item.get("weight", 0.0)),
            int(item.get("evidence", {}).get("total_keyword_hits", 0)),
            str(item.get("atom_id", "")),
        ),
        reverse=True,
    )
    return candidates


def trim_atoms(candidates: List[Dict[str, Any]], max_atoms: int) -> List[Dict[str, Any]]:
    """Limit atom count and strip evidence for publish-safe payload."""
    selected = candidates[:max_atoms]
    trimmed: List[Dict[str, Any]] = []
    for item in selected:
        trimmed.append(
            {
                "atom_id": item["atom_id"],
                "atom_type": item["atom_type"],
                "label": item["label"],
                "description": item["description"],
                "weight": item["weight"],
                "srd_compatibility": item["srd_compatibility"],
            }
        )
    return trimmed


def build_builder_pack(atoms: List[Dict[str, Any]], max_lines: int = 8) -> Dict[str, Any]:
    """Build compact prompt pack for module builder use."""
    lines: List[str] = []
    for atom in atoms[:max_lines]:
        line = f"- {atom['label']}: {atom['description']}"
        lines.append(line)
    joined = "\n".join(lines)
    return {
        "lines": lines,
        "line_count": len(lines),
        "token_estimate": estimate_tokens(joined),
    }


def find_banned_keys(obj: Any, banned_keys: Set[str], path: str = "$") -> List[str]:
    """Return paths where banned key names are present."""
    hits: List[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_lower = str(key).strip().lower()
            child_path = f"{path}.{key}"
            if key_lower in banned_keys:
                hits.append(child_path)
            hits.extend(find_banned_keys(value, banned_keys, child_path))
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            hits.extend(find_banned_keys(value, banned_keys, f"{path}[{index}]"))
    return hits


def find_banned_terms(obj: Any, banned_terms: Set[str], path: str = "$") -> List[Tuple[str, str]]:
    """Return (path, term) hits for banned term matches in string values."""
    hits: List[Tuple[str, str]] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            hits.extend(find_banned_terms(value, banned_terms, f"{path}.{key}"))
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            hits.extend(find_banned_terms(value, banned_terms, f"{path}[{index}]"))
    elif isinstance(obj, str):
        lowered = obj.lower()
        for term in banned_terms:
            if term and term.lower() in lowered:
                hits.append((path, term))
    return hits


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Build source-anonymous inspiration atoms from chunked local book text."
    )
    parser.add_argument("--chunks", required=True, help="Path to chunks JSONL")
    parser.add_argument("--output", required=True, help="Output JSON path for anonymous atoms")
    parser.add_argument("--profile-kind", default="dark_fantasy_horror", help="Anonymous profile kind label")
    parser.add_argument("--max-atoms", type=int, default=12, help="Maximum atoms to emit")
    parser.add_argument("--strict", action="store_true", help="Fail on banned key/term compliance violations")
    parser.add_argument(
        "--banned-terms-file",
        default=None,
        help="Optional newline-delimited local terms to ban in output",
    )
    return parser.parse_args()


def load_banned_terms(path: Optional[str]) -> Set[str]:
    """Load optional extra banned terms from file."""
    terms = set(BANNED_TERMS_DEFAULT)
    if not path:
        return terms

    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Banned terms file not found: {file_path}")

    with file_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            term = line.strip()
            if term and not term.startswith("#"):
                terms.add(term.lower())
    return terms


def main() -> int:
    """Run source-anonymous atom generation."""
    args = parse_args()

    chunks_path = Path(args.chunks)
    output_path = Path(args.output)
    max_atoms = int(args.max_atoms)
    if max_atoms <= 0:
        print("[ERROR] --max-atoms must be greater than 0")
        return 1

    if not chunks_path.exists():
        print(f"[ERROR] Chunks file not found: {chunks_path}")
        return 1

    banned_terms = load_banned_terms(args.banned_terms_file)

    print(f"[INFO] Loading chunks: {chunks_path}")
    chunks = load_chunks_jsonl(chunks_path)
    if not chunks:
        print("[ERROR] No chunks loaded")
        return 1

    compiled = compile_templates(ATOM_TEMPLATES)
    candidates = score_templates(chunks, ATOM_TEMPLATES, compiled)
    selected_atoms = trim_atoms(candidates, max_atoms=max_atoms)

    profile_id = f"profile.{args.profile_kind}"
    builder_pack = build_builder_pack(selected_atoms, max_lines=min(8, len(selected_atoms)))

    output: Dict[str, Any] = {
        "schema_version": "inspiration-anonymous/v1",
        "generated_at": utc_now_iso(),
        "source_anonymous": True,
        "profile": {
            "profile_id": profile_id,
            "profile_kind": args.profile_kind,
        },
        "atoms": selected_atoms,
        "builder_prompt_pack": builder_pack,
        "compliance": {
            "contains_source_text": False,
            "contains_source_identifiers": False,
            "strict_mode": bool(args.strict),
        },
    }

    key_hits = find_banned_keys(output, BANNED_KEYS_DEFAULT)
    term_hits = find_banned_terms(output, banned_terms)

    if key_hits:
        print("[ERROR] Banned key names detected in output:")
        for hit in key_hits:
            print(f"  - {hit}")
    if term_hits:
        print("[ERROR] Banned terms detected in output:")
        for path, term in term_hits:
            print(f"  - {term!r} at {path}")

    if args.strict and (key_hits or term_hits):
        print("[FAIL] Strict compliance mode blocked output.")
        return 2

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(output, handle, indent=2)

    print(f"[OK] Wrote anonymous atoms: {output_path}")
    print(f"[INFO] Atoms emitted: {len(selected_atoms)}")
    print(f"[INFO] Builder pack tokens~{builder_pack['token_estimate']}")

    if candidates:
        print("[INFO] Top scored candidates:")
        for candidate in candidates[:5]:
            evidence = candidate.get("evidence", {})
            print(
                f"  - {candidate['atom_id']} weight={candidate['weight']} "
                f"hits={evidence.get('total_keyword_hits', 0)} coverage={evidence.get('chunk_coverage', 0)}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
