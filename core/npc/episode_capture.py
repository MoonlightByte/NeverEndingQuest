"""Phase 1d orchestration: capture a canonical episode at a location-close boundary.

Ties the pieces together per the blind-review resolutions:
  R3 presence  -> derive the visit's witness union by scanning the engine-authored
                  "Party NPCs:" stamps across the segment (covers combat turns too).
  R1 identity  -> resolve each present companion name -> identity UUID via
                  RelationshipStore.ensure_identity BEFORE extraction; skip any that
                  cannot resolve; FAIL LOUD (never commit a witness-less episode).
  R2 boundary  -> episodeId coordinate uses the close-time world clock (idempotent
                  within a visit, distinct across revisits; never a content hash).
  R4 hot-path  -> the sync core is offloaded fire-and-forget by capture_* _async so
                  the player-blocking location-close seam is never gated on a model
                  call; the whole thing is best-effort and never mutates history.

Everything is gated by NPC_VOICE_ENABLED at the call site and fail-open here.
"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

from core.npc.episode_extraction import extract_episode, flatten_scene
from core.npc.episode_store import EpisodeStore
from core.npc.relationship_store import (
    RelationshipStore,
    game_day_ordinal,
    record_store_health,
)
from utils.capture.multi_model_capture import capture_and_fanout
from utils.encoding_utils import safe_json_load

_LOGGER = logging.getLogger(__name__)
_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="npc-episode")

# Leaving-location id from a transition marker: "Location transition: X (A01) to Y (B02)"
_TRANSITION_FROM_ID = re.compile(r"Location transition:\s*.+?\(([A-Za-z]+\d+)\)\s+to\s")


def segment_witness_names(messages: Sequence[Mapping[str, Any]]) -> List[str]:
    """Union of companion names present across the segment, read ONLY from the
    engine-authored 'Party NPCs: ... Party stats:' field in DM notes (never prose)."""
    names: List[str] = []
    for message in messages:
        content = message.get("content") if isinstance(message, Mapping) else None
        if not isinstance(content, str) or "Party NPCs: " not in content:
            continue
        start = content.find("Party NPCs: ") + len("Party NPCs: ")
        end = content.find(" Party stats:", start)
        roster = content[start:end] if end > start else content[start : start + 500]
        for part in roster.split(","):
            name = part.strip()
            paren = name.find(" (")
            if paren > 0:
                name = name[:paren].strip()
            if name and name not in names:
                names.append(name)
    return names


def resolve_present_companions(
    names: Sequence[str],
    party_tracker_data: Mapping[str, Any],
    *,
    path_manager: Any,
    rel_store: RelationshipStore,
    json_loader: Callable[[str], Any] = safe_json_load,
) -> List[Dict[str, str]]:
    """Resolve companion display names -> identity UUIDs (R1). Skip unresolved."""
    world = party_tracker_data.get("worldConditions", {})
    world = world if isinstance(world, Mapping) else {}
    module = str(party_tracker_data.get("module") or "")
    location_id = str(world.get("currentLocationId") or "")
    present: List[Dict[str, str]] = []
    seen_ids = set()
    for name in names:
        try:
            path = path_manager.get_character_path(name)
            sheet = json_loader(path)
            if not isinstance(sheet, dict):
                continue
            sheet_name = str(sheet.get("name") or name)
            npc_id = rel_store.ensure_identity(
                kind="npc",
                display_name=sheet_name,
                sheet_path=path,
                module=module,
                location_id=location_id,
                active=None,
            )
            if npc_id and npc_id not in seen_ids:
                seen_ids.add(npc_id)
                present.append({"name": sheet_name, "id": npc_id})
        except Exception as error:  # noqa: BLE001 - best-effort resolution
            _LOGGER.debug("companion identity resolve failed for %r: %r", name, error)
            continue
    return present


def location_close_position(
    conversation_history: Sequence[Mapping[str, Any]], transition_index: int
) -> int:
    """Ordinal of this location-close within the module = count of 'Location
    transition:' markers up to and including transition_index (R2).

    Position is stable and reconstructable IDENTICALLY from the live history and
    the archive (both preserve transition markers), and is distinct per visit, so
    the coordinate episodeId converges between live capture and module-leave
    consolidation -- never a content hash.
    """
    count = 0
    upper = min(transition_index + 1, len(conversation_history))
    for i in range(upper):
        message = conversation_history[i]
        content = message.get("content") if isinstance(message, Mapping) else None
        if (
            isinstance(message, Mapping)
            and message.get("role") == "user"
            and isinstance(content, str)
            and "Location transition:" in content
        ):
            count += 1
    return count


def boundary_turn_id_for_position(position: int) -> str:
    return "close-%d" % position


def capture_location_episode(
    *,
    leaving_location_name: str,
    leaving_location_id: str,
    segment_messages: Sequence[Mapping[str, Any]],
    party_tracker_data: Mapping[str, Any],
    path_manager: Any,
    boundary_turn_id: str,
    player_name: str = "",
    provider: Optional[str] = None,
    derived_from: str = "location_summary",
    episode_store: Optional[EpisodeStore] = None,
    rel_store: Optional[RelationshipStore] = None,
    json_loader: Callable[[str], Any] = safe_json_load,
) -> Optional[str]:
    """Synchronous, testable core. Returns the committed episodeId or None.
    Never mutates conversation history; never raises."""
    try:
        names = segment_witness_names(segment_messages)
        if not names:
            return None  # no companions in this segment -> nothing to remember
        store = episode_store or EpisodeStore()
        if store.read_only:
            return None  # loud latch already recorded at construction
        rel = rel_store or RelationshipStore()
        present = resolve_present_companions(
            names, party_tracker_data,
            path_manager=path_manager, rel_store=rel, json_loader=json_loader,
        )
        if not present:
            record_store_health(
                "episode_no_witnesses",
                detail="present names unresolved: %s" % ", ".join(names[:5]),
            )
            return None
        scene = flatten_scene(segment_messages)
        result = extract_episode(
            scene, present, player_name=player_name, provider=provider,
            capture_fn=capture_and_fanout,
        )
        if result is None:
            return None
        if not result.get("witness_ids"):
            record_store_health("episode_no_witnesses", detail="extraction produced no witnesses")
            return None
        world = party_tracker_data.get("worldConditions", {})
        world = world if isinstance(world, Mapping) else {}
        module = str(party_tracker_data.get("module") or "")
        episode_id = store.commit_episode(
            module=module,
            location_id=leaving_location_id or str(world.get("currentLocationId") or ""),
            location_name=leaving_location_name,
            game_day=game_day_ordinal(world),
            boundary_turn_id=boundary_turn_id,
            derived_from=derived_from,
            **result,
        )
        # Phase 2: derive each witness's POV overlay from the committed canonical
        # episode (code-only). Fail-open; POV failure never undoes the canonical write.
        if episode_id:
            try:
                from core.npc.pov_overlay import derive_pov_episodes
                stored = store.get_episode(episode_id)
                if stored:
                    for pov_npc_id, pov_rows in derive_pov_episodes(stored).items():
                        rel.upsert_pov_episodes(pov_npc_id, pov_rows)
            except Exception as pov_error:  # noqa: BLE001
                _LOGGER.debug("pov overlay derivation failed: %r", pov_error)
        return episode_id
    except Exception as error:  # noqa: BLE001 - fail-open; capture never breaks a turn
        _LOGGER.debug("location episode capture failed: %r", error)
        return None


def leaving_location_id_from_marker(transition_content: str) -> str:
    match = _TRANSITION_FROM_ID.search(transition_content or "")
    return match.group(1) if match else ""


def _count_transition_markers(conversation_history: Sequence[Mapping[str, Any]]) -> int:
    return sum(
        1
        for m in conversation_history
        if isinstance(m, Mapping)
        and m.get("role") == "user"
        and isinstance(m.get("content"), str)
        and "Location transition:" in m["content"]
    )


def consolidate_module_episodes(
    conversation_history: Sequence[Mapping[str, Any]],
    party_tracker_data: Mapping[str, Any],
    *,
    path_manager: Any,
    player_name: str = "",
    provider: Optional[str] = None,
    episode_store: Optional[EpisodeStore] = None,
    rel_store: Optional[RelationshipStore] = None,
) -> Optional[str]:
    """Module-leave consolidation (R10): capture the FINAL location.

    Live per-location capture already covers every location the party LEFT (each
    got a transition-out from full-fidelity raw turns). The final location -- where
    the module ends without a transition-out -- is the one live capture structurally
    misses; its raw turns are still present at module completion. This captures it
    idempotently (coordinate = the (N+1)th close) and fail-open. Older locations in
    the archive are already compressed summaries and already have their episodes, so
    they are intentionally not re-derived here. Runs AFTER the T038 summary commits.
    """
    try:
        last_marker = -1
        for i, message in enumerate(conversation_history):
            if (
                isinstance(message, Mapping)
                and message.get("role") == "user"
                and isinstance(message.get("content"), str)
                and "Location transition:" in message["content"]
            ):
                last_marker = i
        final_segment = [
            m
            for m in conversation_history[last_marker + 1 :]
            if isinstance(m, Mapping) and m.get("role") != "system"
        ]
        if not final_segment:
            return None
        world = party_tracker_data.get("worldConditions", {})
        world = world if isinstance(world, Mapping) else {}
        position = _count_transition_markers(conversation_history) + 1
        return capture_location_episode(
            leaving_location_name=str(world.get("currentLocation") or "Unknown location"),
            leaving_location_id=str(world.get("currentLocationId") or ""),
            segment_messages=final_segment,
            party_tracker_data=party_tracker_data,
            path_manager=path_manager,
            boundary_turn_id=boundary_turn_id_for_position(position),
            player_name=player_name,
            provider=provider,
            derived_from="module_consolidation",
            episode_store=episode_store,
            rel_store=rel_store,
        )
    except Exception as error:  # noqa: BLE001 - fail-open; never break module completion
        _LOGGER.debug("module consolidation failed: %r", error)
        return None


def capture_location_episode_async(**kwargs: Any) -> None:
    """Fire-and-forget offload (R4): the player-blocking location-close seam is
    never gated on the extraction model call. Failures are swallowed."""
    try:
        _EXECUTOR.submit(capture_location_episode, **kwargs)
    except Exception as error:  # noqa: BLE001 - never let scheduling break a turn
        _LOGGER.debug("episode capture could not be scheduled: %r", error)
