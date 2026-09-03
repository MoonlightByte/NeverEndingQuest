"""Phase 1d orchestration: capture a canonical episode at a location-close boundary.

Ties the pieces together per the blind-review resolutions:
  R3 presence  -> derive the visit's witness union by scanning the engine-authored
                  "Party NPCs:" stamps across the segment (covers combat turns too).
  R1 identity  -> resolve each present companion name -> identity UUID via
                  RelationshipStore.ensure_identity BEFORE extraction; skip any that
                  cannot resolve; FAIL LOUD (never commit a witness-less episode).
  R2 boundary  -> episodeId coordinate uses the close-time world clock (idempotent
                  within a visit, distinct across revisits; never a content hash).
  R4 hot-path  -> the sync core is offloaded by capture_*_async, registered before
                  submit as a lifecycle child, and remains discoverable through its
                  sidecar commit. Ordinary play does not wait; Reset fences/reaps it.

Everything is always on at the call site and degrades loudly when no owning lifecycle
scope exists; extraction failure never breaks the gameplay turn.
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
        if end > start:
            roster = content[start:end]
        else:
            line_end = content.find("\n", start)
            roster = content[start:] if line_end < 0 else content[start:line_end]
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


def _resolve_player_id(player_name, party_tracker_data, path_manager, rel_store, json_loader):
    """Resolve the player's identity UUID (needed to reinforce the NPC->player edge)."""
    if not player_name:
        return None
    try:
        path = path_manager.get_character_path(player_name)
        sheet = json_loader(path)
        name = (sheet.get("name") if isinstance(sheet, dict) else None) or player_name
        world = party_tracker_data.get("worldConditions", {})
        world = world if isinstance(world, Mapping) else {}
        return rel_store.ensure_identity(
            kind="player", display_name=str(name), sheet_path=path,
            module=str(party_tracker_data.get("module") or ""),
            location_id=str(world.get("currentLocationId") or ""), active=None,
        )
    except Exception:
        return None


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
    advisory_scope: Any = None,
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
            capture_fn=capture_and_fanout, advisory_scope=advisory_scope,
        )
        if result is None:
            return None
        if not result.get("witness_ids"):
            record_store_health("episode_no_witnesses", detail="extraction produced no witnesses")
            return None
        world = party_tracker_data.get("worldConditions", {})
        world = world if isinstance(world, Mapping) else {}
        return _commit_and_overlay(
            store, rel, result,
            module=str(party_tracker_data.get("module") or ""),
            location_id=leaving_location_id or str(world.get("currentLocationId") or ""),
            location_name=leaving_location_name,
            world=world,
            boundary_turn_id=boundary_turn_id,
            derived_from=derived_from,
            player_name=player_name,
            party_tracker_data=party_tracker_data,
            path_manager=path_manager,
            json_loader=json_loader,
        )
    except Exception as error:  # noqa: BLE001 - fail-open; capture never breaks a turn
        _LOGGER.debug("location episode capture failed: %r", error)
        return None


def _commit_and_overlay(
    store: EpisodeStore,
    rel: RelationshipStore,
    result: Mapping[str, Any],
    *,
    module: str,
    location_id: str,
    location_name: str,
    world: Mapping[str, Any],
    boundary_turn_id: str,
    derived_from: str,
    player_name: str,
    party_tracker_data: Mapping[str, Any],
    path_manager: Any,
    json_loader: Callable[[str], Any],
) -> Optional[str]:
    """Commit one canonical episode then derive POV overlays + relationship baseline.
    Shared by location-close, module-consolidation, and combat capture. Fail-open:
    a POV/baseline failure never undoes the canonical write."""
    episode_id = store.commit_episode(
        module=module,
        location_id=location_id,
        location_name=location_name,
        game_day=game_day_ordinal(world),
        boundary_turn_id=boundary_turn_id,
        derived_from=derived_from,
        **result,
    )
    if episode_id:
        try:
            from core.npc.pov_overlay import derive_pov_episodes
            stored = store.get_episode(episode_id)
            if stored:
                pov_by_npc = derive_pov_episodes(stored)
                for pov_npc_id, pov_rows in pov_by_npc.items():
                    rel.upsert_pov_episodes(pov_npc_id, pov_rows)
                # Phase 5: elevate each witness's NPC->player relationship baseline
                # from their accumulated pinned memories, so the bond deepens+sticks.
                player_id = _resolve_player_id(
                    player_name, party_tracker_data, path_manager, rel, json_loader
                )
                if player_id:
                    game_day = game_day_ordinal(world)
                    for pov_npc_id in pov_by_npc:
                        rel.reinforce_baseline_from_pov(
                            pov_npc_id, player_id, game_day=game_day
                        )
        except Exception as pov_error:  # noqa: BLE001
            _LOGGER.debug("pov overlay/baseline derivation failed: %r", pov_error)
    return episode_id


def combat_witness_names(
    encounter_data: Mapping[str, Any], party_tracker_data: Mapping[str, Any]
) -> List[str]:
    """Present companions in a fight, read from the AUTHORITATIVE combat roster
    (encounter_data['creatures'] type=='npc') -- stronger than the DM notes stamp,
    which combat turns may not carry. Never prose."""
    names: List[str] = []
    creatures = encounter_data.get("creatures", []) if isinstance(encounter_data, Mapping) else []
    for creature in creatures:
        if isinstance(creature, Mapping) and creature.get("type") == "npc":
            name = str(creature.get("name") or "").strip()
            if name and name not in names:
                names.append(name)
    return names


def _norm_name(value: Any) -> str:
    return str(value or "").strip().casefold()


def _combat_near_death_facts(
    encounter_data: Mapping[str, Any], present: Sequence[Mapping[str, str]]
) -> List[Dict[str, Any]]:
    """R8, CODE-derived (never inferred from prose): for each resolved present
    companion, read the fight's low-water-mark HP (creature['combatMinHitPoints'],
    tracked from the authoritative character-sheet HP in sync_active_encounter) and,
    if it crossed <= max(1, 10% of maxHP), synthesize a near_death salient fact.
    Subject id is the resolved witness identity so recall/POV attribute it."""
    creatures_by_name: Dict[str, Mapping[str, Any]] = {}
    for creature in encounter_data.get("creatures", []) or []:
        if isinstance(creature, Mapping) and creature.get("type") == "npc":
            creatures_by_name[_norm_name(creature.get("name"))] = creature
    facts: List[Dict[str, Any]] = []
    for companion in present:
        creature = creatures_by_name.get(_norm_name(companion.get("name")))
        if not creature:
            continue
        low = creature.get("combatMinHitPoints")
        max_hp = creature.get("maxHitPoints")
        if not isinstance(low, (int, float)) or not isinstance(max_hp, (int, float)) or max_hp <= 0:
            continue
        if low <= max(1, 0.1 * max_hp):
            facts.append({
                "kind": "near_death",
                "subject": {"id": companion.get("id"), "label": companion.get("name")},
                "oneLine": "%s dropped to %d of %d HP" % (
                    companion.get("name"), int(low), int(max_hp)),
            })
    return facts


def capture_combat_episode(
    *,
    conversation_history: Sequence[Mapping[str, Any]],
    encounter_data: Mapping[str, Any],
    party_tracker_data: Mapping[str, Any],
    path_manager: Any = None,
    player_name: str = "",
    provider: Optional[str] = None,
    episode_store: Optional[EpisodeStore] = None,
    rel_store: Optional[RelationshipStore] = None,
    json_loader: Callable[[str], Any] = safe_json_load,
    advisory_scope: Any = None,
) -> Optional[str]:
    """W2: capture one combat episode from the raw combat transcript at combat exit,
    BEFORE the transcript is archived/cleared. Presence + near-death come from the
    authoritative encounter roster, not prose. Synchronous core; fail-open; never
    raises; never mutates the transcript."""
    try:
        if not isinstance(encounter_data, Mapping):
            return None
        names = combat_witness_names(encounter_data, party_tracker_data)
        if not names:
            return None  # no companions in the fight -> nothing to remember
        store = episode_store or EpisodeStore()
        if store.read_only:
            return None
        rel = rel_store or RelationshipStore()
        if path_manager is None:
            from utils.module_path_manager import ModulePathManager
            module_name = str(party_tracker_data.get("module") or "").replace(" ", "_")
            path_manager = ModulePathManager(module_name) if module_name else ModulePathManager()
        present = resolve_present_companions(
            names, party_tracker_data,
            path_manager=path_manager, rel_store=rel, json_loader=json_loader,
        )
        if not present:
            record_store_health(
                "episode_no_witnesses",
                detail="combat present unresolved: %s" % ", ".join(names[:5]),
            )
            return None
        scene = flatten_scene([
            m for m in conversation_history
            if isinstance(m, Mapping) and m.get("role") != "system"
        ])
        result = extract_episode(
            scene, present, player_name=player_name, provider=provider,
            capture_fn=capture_and_fanout, advisory_scope=advisory_scope,
        )
        if result is None:
            return None
        result = dict(result)
        # Presence is authoritative from the roster: every resolved combat companion
        # is a witness even if extraction under-listed them.
        witness_ids = set(result.get("witness_ids") or [])
        witness_ids |= {c["id"] for c in present if c.get("id")}
        result["witness_ids"] = list(witness_ids)
        # R8: append code-derived near-death facts (never from prose).
        near_death = _combat_near_death_facts(encounter_data, present)
        if near_death:
            result["salient_facts"] = list(result.get("salient_facts") or []) + near_death
        if not result.get("witness_ids"):
            record_store_health("episode_no_witnesses", detail="combat extraction produced no witnesses")
            return None
        world = party_tracker_data.get("worldConditions", {})
        world = world if isinstance(world, Mapping) else {}
        encounter_id = str(encounter_data.get("encounterId") or "").replace("/", "_")
        if not encounter_id:
            return None
        return _commit_and_overlay(
            store, rel, result,
            module=str(party_tracker_data.get("module") or ""),
            location_id=str(world.get("currentLocationId") or ""),
            location_name=str(world.get("currentLocation") or "Unknown location"),
            world=world,
            boundary_turn_id="combat-%s" % encounter_id,
            derived_from="combat_telemetry",
            player_name=player_name,
            party_tracker_data=party_tracker_data,
            path_manager=path_manager,
            json_loader=json_loader,
        )
    except Exception as error:  # noqa: BLE001 - fail-open; capture never breaks combat exit
        _LOGGER.debug("combat episode capture failed: %r", error)
        return None


def _submit_episode_capture(worker, beat_id: str, kwargs: Mapping[str, Any]) -> None:
    """Publish one T108 child before submit and finish it after sidecar commit."""
    from utils.capture.live_provider_call import (
        get_active_welcome_scope,
        get_live_turn_scope,
        open_advisory_scopes,
    )

    parent = get_live_turn_scope() or get_active_welcome_scope()
    children = open_advisory_scopes(
        parent,
        beat_id,
        1,
        completion_required=True,
    )
    if not children:
        record_store_health(
            "episode_capture_missing_lifecycle_authority",
            detail=beat_id,
        )
        return
    advisory_scope = children[0]
    worker_kwargs = dict(kwargs)
    worker_kwargs["advisory_scope"] = advisory_scope

    def run() -> None:
        try:
            worker(**worker_kwargs)
        finally:
            advisory_scope.finish()

    try:
        _EXECUTOR.submit(run)
    except Exception as error:  # noqa: BLE001 - scheduling cannot strand the child
        advisory_scope.finish()
        _LOGGER.debug("episode capture could not be scheduled: %r", error)


def capture_combat_episode_async(**kwargs: Any) -> None:
    """Register then offload combat extraction against one stable snapshot."""
    encounter = kwargs.get("encounter_data")
    encounter_id = encounter.get("encounterId") if isinstance(encounter, Mapping) else ""
    _submit_episode_capture(
        capture_combat_episode,
        "T108-combat-%s" % (encounter_id or "unknown"),
        kwargs,
    )


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
    """Register then offload location extraction against one stable snapshot."""
    _submit_episode_capture(
        capture_location_episode,
        "T108-location-%s" % (kwargs.get("boundary_turn_id") or "unknown"),
        kwargs,
    )
