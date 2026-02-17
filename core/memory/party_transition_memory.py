# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Party Transition Memory - PC leave/return lifecycle helpers.
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Provides write-only lifecycle event recording for PC retirement and return
transitions using canonical entity identity and role_transition memory events.
"""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from utils.enhanced_logger import error, info

from core.memory.memory_db import (
    DEFAULT_MEMORY_DB_PATH,
    create_memory_event,
    create_memory_link,
)


def _utc_now_iso() -> str:
    """Return UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_name(value: str) -> str:
    """Normalize a character/entity name for IDs and matching."""
    try:
        from updates.update_character_info import normalize_character_name

        return normalize_character_name(value)
    except Exception:
        import re

        lowered = str(value).strip().lower()
        return re.sub(r"[^a-z0-9_]+", "_", lowered).strip("_")


def _connect(db_path: str) -> sqlite3.Connection:
    """Create SQLite connection with sane defaults."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _resolve_or_create_entity(
    conn: sqlite3.Connection,
    character_name: str,
    entity_kind: str = "character",
) -> Optional[str]:
    """Resolve canonical entity ID for a character, creating if necessary.

    Uses normalized name as entity_id (canonical identity). Does not create
duplicate entities for the same character name.

    Args:
        conn: SQLite connection
        character_name: Display name of the character
        entity_kind: Entity kind (default "character")

    Returns:
        entity_id string if successful, None on failure
    """
    try:
        normalized_id = _normalize_name(character_name)
        if not normalized_id:
            error(
                f"MEMORY_TRANSITION: Cannot resolve entity for empty character name",
                category="memory_ingest",
            )
            return None

        now_ts = _utc_now_iso()

        # Upsert entity (ON CONFLICT UPDATE preserves existing, updates timestamp)
        conn.execute(
            """
            INSERT INTO entities (entity_id, display_name, entity_kind, is_retired, created_at, updated_at, metadata_json)
            VALUES (?, ?, ?, 0, ?, ?, ?)
            ON CONFLICT(entity_id) DO UPDATE SET
                display_name = excluded.display_name,
                updated_at = excluded.updated_at
            """,
            (normalized_id, character_name, entity_kind, now_ts, now_ts, json.dumps({"source": "party_transition"})),
        )

        # Ensure alias exists for display name
        conn.execute(
            """
            INSERT OR IGNORE INTO entity_aliases (entity_id, alias_name, alias_type, source, created_at)
            VALUES (?, ?, 'name', 'party_transition', ?)
            """,
            (normalized_id, character_name, now_ts),
        )

        return normalized_id
    except Exception as entity_error:
        error(
            f"MEMORY_TRANSITION: Entity resolution failed for '{character_name}': {entity_error}",
            exception=entity_error,
            category="memory_ingest",
        )
        return None


def _get_remaining_party_entity_ids(
    party_tracker: Dict[str, Any],
    exclude_character: str,
) -> List[str]:
    """Extract entity IDs of remaining party members for witness linking.

    Args:
        party_tracker: Party tracker data structure
        exclude_character: Character name to exclude (the transitioning PC)

    Returns:
        List of normalized entity IDs for remaining party participants
    """
    remaining: List[str] = []
    seen_ids = set()
    exclude_normalized = _normalize_name(exclude_character)

    # Party members (players)
    for member_name in party_tracker.get("partyMembers", []) or []:
        normalized = _normalize_name(str(member_name))
        if normalized and normalized != exclude_normalized and normalized not in seen_ids:
            remaining.append(normalized)
            seen_ids.add(normalized)

    # Party NPC companions
    for npc_entry in party_tracker.get("partyNPCs", []) or []:
        npc_name = ""
        if isinstance(npc_entry, dict):
            npc_name = str(npc_entry.get("name", "")).strip()
        else:
            npc_name = str(npc_entry).strip()

        normalized = _normalize_name(npc_name)
        if normalized and normalized != exclude_normalized and normalized not in seen_ids:
            remaining.append(normalized)
            seen_ids.add(normalized)

    return remaining


def _build_retirement_summary(character_name: str, departure_text: str) -> str:
    """Build narrative summary for retirement transition event.

    If departure_text is provided, incorporates it into the summary.
    If blank, creates a narrative-neutral summary compatible with mysterious departure.

    Args:
        character_name: Name of the retiring PC
        departure_text: Optional departure description provided by user/DM

    Returns:
        Summary text for the role_transition event
    """
    if departure_text and str(departure_text).strip():
        return f"{character_name} retired from the party. Departure: {str(departure_text).strip()}"
    return f"{character_name} retired from the party (departure circumstances unrecorded)"


def _build_return_summary(character_name: str) -> str:
    """Build narrative summary for return transition event.

    Args:
        character_name: Name of the returning PC

    Returns:
        Summary text for the role_transition event
    """
    return f"{character_name} returned to the party"


def _create_role_transition_event(
    entity_id: str,
    summary: str,
    transition_type: str,
    db_path: str,
) -> Optional[str]:
    """Create a role_transition memory event with identity_core priority.

    Args:
        entity_id: Canonical entity ID for the transitioning character
        summary: Event summary text
        transition_type: "retirement" or "return"
        db_path: Path to memory database

    Returns:
        event_id if successful, None on failure
    """
    try:
        event_id = f"evt_transition_{entity_id}_{transition_type}_{uuid.uuid4().hex[:16]}"
        event_ts = _utc_now_iso()

        event_payload = {
            "event_id": event_id,
            "event_ts": event_ts,
            "event_type": "role_transition",
            "summary": summary,
            "detail_json": json.dumps({
                "transition_type": transition_type,
                "entity_id": entity_id,
            }),
            "importance": 95,
            "persistence_class": "identity_core",
            "decay_profile": "none",
            "modality_tags_json": json.dumps(["identity", "continuity", "milestone"]),
            "reinforcement_count": 0,
            "priority_active_pc": True,
            "pinned": True,
            "created_at": event_ts,
        }

        create_memory_event(db_path, event_payload)
        return event_id
    except Exception as event_error:
        error(
            f"MEMORY_TRANSITION: Failed to create {transition_type} event for {entity_id}: {event_error}",
            exception=event_error,
            category="memory_ingest",
        )
        return None


def _link_transition_entities(
    event_id: str,
    actor_entity_id: str,
    witness_entity_ids: List[str],
    db_path: str,
) -> int:
    """Create memory links for transition event: actor + witnesses.

    Args:
        event_id: The transition event ID
        actor_entity_id: Entity ID of the transitioning PC (linked as 'actor')
        witness_entity_ids: Entity IDs of remaining party members (linked as 'witness')
        db_path: Path to memory database

    Returns:
        Number of links created
    """
    links_created = 0

    try:
        # Link transitioning PC as actor
        actor_link_id = create_memory_link(
            db_path,
            {
                "event_id": event_id,
                "entity_id": actor_entity_id,
                "link_role": "actor",
                "link_salience": 1.0,
                "metadata_json": json.dumps({"role": "transitioning_pc"}),
            },
        )
        if actor_link_id:
            links_created += 1

        # Link remaining party members as witnesses
        for witness_id in witness_entity_ids:
            witness_link_id = create_memory_link(
                db_path,
                {
                    "event_id": event_id,
                    "entity_id": witness_id,
                    "link_role": "witness",
                    "link_salience": 0.5,
                    "metadata_json": json.dumps({"role": "remaining_party_member"}),
                },
            )
            if witness_link_id:
                links_created += 1

        return links_created
    except Exception as link_error:
        error(
            f"MEMORY_TRANSITION: Failed to create links for event {event_id}: {link_error}",
            exception=link_error,
            category="memory_ingest",
        )
        return links_created


def record_pc_retirement(
    character_name: str,
    party_tracker: Dict[str, Any],
    departure_text: str = "",
) -> Dict[str, Any]:
    """Record a PC retirement (leave) transition in world memory.

    Creates a role_transition event with identity_core persistence and links
the transitioning PC as actor and remaining party members as witnesses.

    Non-destructive: Does not delete or purge any prior events or links.

    Args:
        character_name: Name of the retiring PC
        party_tracker: Party tracker data structure containing partyMembers and partyNPCs
        departure_text: Optional departure description (narrative-neutral if blank)
        Uses default memory database path from memory_db.DEFAULT_MEMORY_DB_PATH.

    Returns:
        Dict with status, event_id, entity_id, and links_created on success.
        Dict with status "error", message, and event_id None on failure.

    Example success return:
        {
            "status": "success",
            "event_id": "evt_transition_acheron_retirement_a1b2c3d4e5f67890",
            "entity_id": "acheron",
            "links_created": 3
        }

    Example failure return:
        {
            "status": "error",
            "message": "Entity resolution failed for 'Unknown Character'",
            "event_id": None
        }
    """
    if not character_name or not str(character_name).strip():
        return {
            "status": "error",
            "message": "Character name is required",
            "event_id": None,
            "entity_id": None,
            "links_created": 0,
        }

    db_path = DEFAULT_MEMORY_DB_PATH
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = _connect(db_path)

        # Resolve or create canonical entity for the retiring PC
        entity_id = _resolve_or_create_entity(conn, character_name)
        if not entity_id:
            return {
                "status": "error",
                "message": f"Entity resolution failed for '{character_name}'",
                "event_id": None,
                "entity_id": None,
                "links_created": 0,
            }

        # Mark entity as retired in entities table
        now_ts = _utc_now_iso()
        conn.execute(
            "UPDATE entities SET is_retired = 1, updated_at = ? WHERE entity_id = ?",
            (now_ts, entity_id),
        )

        # Create end_ts on current active role
        conn.execute(
            """
            UPDATE entity_roles
            SET end_ts = ?
            WHERE entity_id = ? AND end_ts IS NULL
            """,
            (now_ts, entity_id),
        )

        # Commit entity updates before creating event
        conn.commit()

        # Build summary and create transition event
        summary = _build_retirement_summary(character_name, departure_text)
        event_id = _create_role_transition_event(entity_id, summary, "retirement", db_path)

        if not event_id:
            return {
                "status": "error",
                "message": f"Failed to create retirement event for '{character_name}'",
                "event_id": None,
                "entity_id": entity_id,
                "links_created": 0,
            }

        # Get remaining party members for witness links
        witness_ids = _get_remaining_party_entity_ids(party_tracker, character_name)

        # Create actor and witness links
        links_created = _link_transition_entities(event_id, entity_id, witness_ids, db_path)

        info(
            f"MEMORY_TRANSITION: Recorded retirement for '{character_name}' (event={event_id}, links={links_created})",
            category="memory_ingest",
        )

        return {
            "status": "success",
            "event_id": event_id,
            "entity_id": entity_id,
            "links_created": links_created,
        }

    except Exception as retirement_error:
        error(
            f"MEMORY_TRANSITION: Retirement recording failed for '{character_name}': {retirement_error}",
            exception=retirement_error,
            category="memory_ingest",
        )
        return {
            "status": "error",
            "message": str(retirement_error),
            "event_id": None,
            "entity_id": None,
            "links_created": 0,
        }
    finally:
        if conn is not None:
            conn.close()


def record_pc_return(
    character_name: str,
    party_tracker: Dict[str, Any],
) -> Dict[str, Any]:
    """Record a PC return (rejoin) transition in world memory.

    Creates a role_transition event with identity_core persistence and links
the returning PC as actor and current party members as witnesses.

    Non-destructive: Does not delete or purge any prior events or links.

    Args:
        character_name: Name of the returning PC
        party_tracker: Party tracker data structure containing partyMembers and partyNPCs
        Uses default memory database path from memory_db.DEFAULT_MEMORY_DB_PATH.

    Returns:
        Dict with status, event_id, entity_id, and links_created on success.
        Dict with status "error", message, and event_id None on failure.

    Example success return:
        {
            "status": "success",
            "event_id": "evt_transition_acheron_return_a1b2c3d4e5f67890",
            "entity_id": "acheron",
            "links_created": 3
        }

    Example failure return:
        {
            "status": "error",
            "message": "Entity resolution failed for 'Unknown Character'",
            "event_id": None
        }
    """
    if not character_name or not str(character_name).strip():
        return {
            "status": "error",
            "message": "Character name is required",
            "event_id": None,
            "entity_id": None,
            "links_created": 0,
        }

    db_path = DEFAULT_MEMORY_DB_PATH
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = _connect(db_path)

        # Resolve or create canonical entity for the returning PC
        entity_id = _resolve_or_create_entity(conn, character_name)
        if not entity_id:
            return {
                "status": "error",
                "message": f"Entity resolution failed for '{character_name}'",
                "event_id": None,
                "entity_id": None,
                "links_created": 0,
            }

        # Mark entity as not retired (active again)
        now_ts = _utc_now_iso()
        conn.execute(
            "UPDATE entities SET is_retired = 0, updated_at = ? WHERE entity_id = ?",
            (now_ts, entity_id),
        )

        # Create new active role entry (returning party member)
        conn.execute(
            """
            INSERT INTO entity_roles (entity_id, role, start_ts, end_ts, source, reason)
            VALUES (?, 'player', ?, NULL, 'party_transition', 'returned to party')
            """,
            (entity_id, now_ts),
        )

        # Commit entity updates before creating event
        conn.commit()

        # Build summary and create transition event
        summary = _build_return_summary(character_name)
        event_id = _create_role_transition_event(entity_id, summary, "return", db_path)

        if not event_id:
            return {
                "status": "error",
                "message": f"Failed to create return event for '{character_name}'",
                "event_id": None,
                "entity_id": entity_id,
                "links_created": 0,
            }

        # Get current party members for witness links (including any newly added)
        witness_ids = _get_remaining_party_entity_ids(party_tracker, character_name)

        # Create actor and witness links
        links_created = _link_transition_entities(event_id, entity_id, witness_ids, db_path)

        info(
            f"MEMORY_TRANSITION: Recorded return for '{character_name}' (event={event_id}, links={links_created})",
            category="memory_ingest",
        )

        return {
            "status": "success",
            "event_id": event_id,
            "entity_id": entity_id,
            "links_created": links_created,
        }

    except Exception as return_error:
        error(
            f"MEMORY_TRANSITION: Return recording failed for '{character_name}': {return_error}",
            exception=return_error,
            category="memory_ingest",
        )
        return {
            "status": "error",
            "message": str(return_error),
            "event_id": None,
            "entity_id": None,
            "links_created": 0,
        }
    finally:
        if conn is not None:
            conn.close()


def build_return_memory_pack(
    character_name: str,
    party_tracker: Dict[str, Any],
) -> Dict[str, Any]:
    """Build bounded continuity context pack for return narration.

    Composes transition lifecycle memory and social continuity memory
    using canonical entity identity. Returns deterministic bounded
    snippets suitable for narration context.

    Non-destructive: Does not delete or purge any prior events or links.

    Args:
        character_name: Name of the returning PC
        party_tracker: Party tracker data structure containing partyMembers and partyNPCs

    Returns:
        Dict with status, entity_id, transition_memories, social_memories,
        continuity_snippets, and counts on success.
        On failure: returns empty lists + error message with status "error".
    """
    from core.memory.memory_retrieval import (
        get_retirement_return_memories,
        get_context_memories,
    )

    if not character_name or not str(character_name).strip():
        return {
            "status": "error",
            "message": "Character name is required",
            "entity_id": None,
            "transition_memories": [],
            "social_memories": [],
            "continuity_snippets": [],
            "counts": {"transition": 0, "social": 0, "combined": 0},
        }

    entity_id = _normalize_name(character_name)
    if not entity_id:
        return {
            "status": "error",
            "message": f"Cannot normalize character name '{character_name}'",
            "entity_id": None,
            "transition_memories": [],
            "social_memories": [],
            "continuity_snippets": [],
            "counts": {"transition": 0, "social": 0, "combined": 0},
        }

    try:
        # Bounded transition memory retrieval (retirement/return history)
        transition_memories = get_retirement_return_memories(
            entity_id=entity_id,
            limit=8,
            enable_audit=False,
        )

        # Derive active entity scope from party_tracker for social context
        active_entities = _get_remaining_party_entity_ids(party_tracker, character_name)
        # Include the returning character for their own context
        if entity_id not in active_entities:
            active_entities.append(entity_id)

        # Bounded social continuity retrieval
        social_memories = []
        if active_entities:
            social_memories = get_context_memories(
                scene_type="social",
                active_entities=active_entities,
                limit=8,
                enable_audit=False,
            )

        # Combine and dedupe by event_id, keeping deterministic order
        seen_event_ids = set()
        continuity_snippets = []

        # Priority: transition memories first (lifecycle continuity)
        for mem in transition_memories:
            event_id = mem.get("event_id")
            if event_id and event_id not in seen_event_ids:
                continuity_snippets.append({
                    "event_id": event_id,
                    "event_ts": mem.get("event_ts", ""),
                    "event_type": mem.get("event_type", ""),
                    "summary": mem.get("summary", ""),
                    "source": "transition",
                })
                seen_event_ids.add(event_id)

        # Then social memories (relationship continuity)
        for mem in social_memories:
            event_id = mem.get("event_id")
            if event_id and event_id not in seen_event_ids:
                continuity_snippets.append({
                    "event_id": event_id,
                    "event_ts": mem.get("event_ts", ""),
                    "event_type": mem.get("event_type", ""),
                    "summary": mem.get("summary", ""),
                    "source": "social",
                })
                seen_event_ids.add(event_id)

        # Enforce combined bound
        if len(continuity_snippets) > 12:
            continuity_snippets = continuity_snippets[:12]

        counts = {
            "transition": len(transition_memories),
            "social": len(social_memories),
            "combined": len(continuity_snippets),
        }

        info(
            f"MEMORY_TRANSITION: Built return pack for '{character_name}' (entity={entity_id}, snippets={counts['combined']})",
            category="memory_retrieval",
        )

        return {
            "status": "success",
            "entity_id": entity_id,
            "transition_memories": transition_memories,
            "social_memories": social_memories,
            "continuity_snippets": continuity_snippets,
            "counts": counts,
        }

    except Exception as pack_error:
        error(
            f"MEMORY_TRANSITION: Failed to build return pack for '{character_name}': {pack_error}",
            exception=pack_error,
            category="memory_retrieval",
        )
        return {
            "status": "error",
            "message": str(pack_error),
            "entity_id": entity_id,
            "transition_memories": [],
            "social_memories": [],
            "continuity_snippets": [],
            "counts": {"transition": 0, "social": 0, "combined": 0},
        }
