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

from core.effects.clock import scalar_from_calendar
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


def _boundary_turn_id(world: Mapping[str, Any], segment_len: int) -> str:
    """Close-time world clock (R2): stable within a visit, advances across revisits.
    Falls back to a position token if the calendar is incomplete."""
    if isinstance(world, Mapping) and all(k in world for k in ("year", "month", "day")):
        try:
            return str(scalar_from_calendar(dict(world)))
        except (TypeError, ValueError):
            pass
    return "pos-%d" % segment_len


def capture_location_episode(
    *,
    leaving_location_name: str,
    leaving_location_id: str,
    segment_messages: Sequence[Mapping[str, Any]],
    party_tracker_data: Mapping[str, Any],
    path_manager: Any,
    player_name: str = "",
    provider: Optional[str] = None,
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
        return store.commit_episode(
            module=module,
            location_id=leaving_location_id or str(world.get("currentLocationId") or ""),
            location_name=leaving_location_name,
            game_day=game_day_ordinal(world),
            boundary_turn_id=_boundary_turn_id(world, len(segment_messages)),
            derived_from="location_summary",
            **result,
        )
    except Exception as error:  # noqa: BLE001 - fail-open; capture never breaks a turn
        _LOGGER.debug("location episode capture failed: %r", error)
        return None


def leaving_location_id_from_marker(transition_content: str) -> str:
    match = _TRANSITION_FROM_ID.search(transition_content or "")
    return match.group(1) if match else ""


def capture_location_episode_async(**kwargs: Any) -> None:
    """Fire-and-forget offload (R4): the player-blocking location-close seam is
    never gated on the extraction model call. Failures are swallowed."""
    try:
        _EXECUTOR.submit(capture_location_episode, **kwargs)
    except Exception as error:  # noqa: BLE001 - never let scheduling break a turn
        _LOGGER.debug("episode capture could not be scheduled: %r", error)
