# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest World Narrative Ingest - Source-anonymous atom persistence
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0
"""

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Set, Tuple

from core.memory.memory_db import DEFAULT_MEMORY_DB_PATH


BANNED_KEYS: Set[str] = {
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


def _utc_now_iso() -> str:
    """Return UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _find_banned_keys(obj: Any, path: str = "$") -> List[str]:
    """Return object paths where banned key names are present."""
    hits: List[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_lower = str(key).strip().lower()
            child_path = f"{path}.{key}"
            if key_lower in BANNED_KEYS:
                hits.append(child_path)
            hits.extend(_find_banned_keys(value, child_path))
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            hits.extend(_find_banned_keys(value, f"{path}[{index}]"))
    return hits


def _find_banned_terms(obj: Any, banned_terms: Set[str], path: str = "$") -> List[Tuple[str, str]]:
    """Return (path, term) hits for banned term matches in string values."""
    hits: List[Tuple[str, str]] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            hits.extend(_find_banned_terms(value, banned_terms, f"{path}.{key}"))
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            hits.extend(_find_banned_terms(value, banned_terms, f"{path}[{index}]"))
    elif isinstance(obj, str):
        lowered = obj.lower()
        for term in banned_terms:
            if term and term.lower() in lowered:
                hits.append((path, term))
    return hits


def validate_source_anonymous_payload(payload: Dict[str, Any], banned_terms: Set[str]) -> Dict[str, Any]:
    """Validate payload for banned key names and banned terms."""
    key_hits = _find_banned_keys(payload)
    term_hits = _find_banned_terms(payload, banned_terms)
    return {
        "ok": not key_hits and not term_hits,
        "key_hits": key_hits,
        "term_hits": term_hits,
    }


def ingest_source_anonymous_atoms(
    payload: Dict[str, Any],
    db_path: str = DEFAULT_MEMORY_DB_PATH,
) -> Dict[str, Any]:
    """Upsert source-anonymous profile/atom rows and refresh atom statistics."""
    profile = payload.get("profile", {}) or {}
    atoms = payload.get("atoms", []) or []
    profile_id = str(profile.get("profile_id") or "").strip()
    profile_kind = str(profile.get("profile_kind") or "").strip()
    if not profile_id or not profile_kind:
        raise ValueError("Payload profile.profile_id and profile.profile_kind are required")
    if not isinstance(atoms, list) or not atoms:
        raise ValueError("Payload atoms must be a non-empty list")

    created_at = str(payload.get("generated_at") or _utc_now_iso())
    inserted_atoms = 0
    updated_atoms = 0

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        with conn:
            conn.execute(
                """
                INSERT INTO inspiration_profiles (profile_id, profile_kind, weights_json, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(profile_id) DO UPDATE SET
                    profile_kind = excluded.profile_kind,
                    weights_json = excluded.weights_json
                """,
                (profile_id, profile_kind, json.dumps({}), created_at),
            )

            for atom in atoms:
                atom_id = str(atom.get("atom_id") or "").strip()
                atom_type = str(atom.get("atom_type") or "").strip()
                label = str(atom.get("label") or "").strip()
                description = str(atom.get("description") or "").strip()
                srd = str(atom.get("srd_compatibility") or "unknown").strip() or "unknown"
                weight = float(atom.get("weight", 0.5))
                if not atom_id or not atom_type or not label or not description:
                    continue

                row = conn.execute(
                    "SELECT atom_id FROM inspiration_atoms WHERE atom_id = ?",
                    (atom_id,),
                ).fetchone()
                conn.execute(
                    """
                    INSERT INTO inspiration_atoms (
                        atom_id, profile_id, atom_type, label, description, weight, srd_compatibility, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(atom_id) DO UPDATE SET
                        profile_id = excluded.profile_id,
                        atom_type = excluded.atom_type,
                        label = excluded.label,
                        description = excluded.description,
                        weight = excluded.weight,
                        srd_compatibility = excluded.srd_compatibility
                    """,
                    (atom_id, profile_id, atom_type, label, description, weight, srd, created_at),
                )

                existing_stats = conn.execute(
                    "SELECT support_count, avg_weight, variance FROM atom_statistics WHERE atom_id = ?",
                    (atom_id,),
                ).fetchone()
                now = _utc_now_iso()
                if existing_stats:
                    support_count = int(existing_stats[0])
                    prev_avg = float(existing_stats[1])
                    prev_var = float(existing_stats[2])
                    new_support = support_count + 1
                    new_avg = ((prev_avg * support_count) + weight) / float(new_support)
                    delta = weight - prev_avg
                    new_var = ((support_count * prev_var) + (delta * (weight - new_avg))) / float(new_support)
                    conn.execute(
                        """
                        UPDATE atom_statistics
                        SET support_count = ?, avg_weight = ?, variance = ?, updated_at = ?
                        WHERE atom_id = ?
                        """,
                        (new_support, new_avg, max(0.0, new_var), now, atom_id),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO atom_statistics (atom_id, support_count, avg_weight, variance, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (atom_id, 1, weight, 0.0, now),
                    )

                if row:
                    updated_atoms += 1
                else:
                    inserted_atoms += 1

        return {
            "status": "success",
            "profile_id": profile_id,
            "atom_count": len(atoms),
            "atoms_inserted": inserted_atoms,
            "atoms_updated": updated_atoms,
        }
    finally:
        conn.close()
