"""W5: seamless, resumable, one-time upgrade of an existing game to episodic memory.

When a running game first loads a build that has episodic memory, this detects that
the game has real history but no episodes yet and BACKFILLS each companion's memory
from the campaign's own prose (W4), behind a progress screen, resumable if interrupted,
and 100% backward compatible.

Design decisions:
- The resume marker is a SEPARATE file (`data/companion_memories/episodic_upgrade.json`),
  NOT a field inside the ledger doc. This deliberately AVOIDS the first-ever ledger
  schema migration (schemaVersion 1->2) whose failure would latch the store read-only
  and kill ALL capture. The marker is a brand-new file (no migration burden), added to
  the save manifest so it travels with save/restore, and skipped-if-absent so old saves
  still validate.
- Fail-open: a read-only store or any failure DISABLES the upgrade for the session and
  records a loud health event; the game always loads and plays. Backfill is idempotent
  (stable coordinates), so a partial/interrupted run simply resumes.
- Gated by NPC_VOICE_ENABLED at the seam. A fresh game (no history) is marked complete
  immediately so detection never re-runs.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Dict, List, Mapping, Optional

from core.npc.episode_backfill import (
    backfill_from_journal,
    backfill_from_summaries,
    build_companion_roster,
    build_location_name_map,
    load_character_dicts,
    load_module_area_dicts,
)
from core.npc.episode_store import EpisodeStore
from core.npc.relationship_store import RelationshipStore, record_store_health
from utils.encoding_utils import safe_json_load, safe_json_dump

_LOGGER = logging.getLogger(__name__)

MARKER_PATH = "data/companion_memories/episodic_upgrade.json"
UPGRADE_VERSION = 1
JOURNAL_PATH = "journal.json"
SUMMARIES_DIR = os.path.join("modules", "campaign_summaries")
CONVERSATION_PATH = os.path.join(
    "modules", "conversation_history", "conversation_history.json"
)


# ---- marker ---------------------------------------------------------------

def read_marker(path: str = MARKER_PATH) -> Dict[str, Any]:
    doc = safe_json_load(path)
    return doc if isinstance(doc, dict) else {}


def _write_marker(doc: Mapping[str, Any], path: str = MARKER_PATH) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        safe_json_dump(dict(doc), path, ensure_ascii=True)
    except Exception as error:  # noqa: BLE001 - marker failure never breaks the game
        _LOGGER.debug("episodic upgrade marker write failed: %r", error)


def is_complete(marker: Mapping[str, Any]) -> bool:
    return (
        isinstance(marker, Mapping)
        and marker.get("status") == "complete"
        and marker.get("version") == UPGRADE_VERSION
    )


# ---- detection ------------------------------------------------------------

def game_has_history(
    *, conversation_path: str = CONVERSATION_PATH, journal_path: str = JOURNAL_PATH,
    json_loader: Callable[[str], Any] = safe_json_load,
) -> bool:
    """Real play history exists if the conversation has >1 message or a non-empty
    journal exists. A brand-new game has neither."""
    convo = json_loader(conversation_path)
    if isinstance(convo, list) and len(convo) > 1:
        return True
    if isinstance(convo, dict) and len(convo.get("messages") or []) > 1:
        return True
    journal = json_loader(journal_path)
    if isinstance(journal, dict) and (journal.get("entries") or []):
        return True
    return False


def _load_summaries(summaries_dir: str, json_loader) -> List[Dict[str, Any]]:
    import glob
    out: List[Dict[str, Any]] = []
    for path in sorted(glob.glob(os.path.join(summaries_dir, "*.json"))):
        if ".backup" in os.path.basename(path):
            continue
        data = json_loader(path)
        if isinstance(data, dict) and data.get("summary"):
            out.append(data)
    return out


# ---- orchestration --------------------------------------------------------

def backfill_campaign(
    party_tracker_data: Mapping[str, Any],
    path_manager: Any,
    *,
    provider: Optional[str] = None,
    progress: Optional[Callable[[str, int, int, str], None]] = None,
    per_run_cap: Optional[int] = None,
    marker_path: str = MARKER_PATH,
    journal_path: str = JOURNAL_PATH,
    summaries_dir: str = SUMMARIES_DIR,
    episode_store: Optional[EpisodeStore] = None,
    rel_store: Optional[RelationshipStore] = None,
    json_loader: Callable[[str], Any] = safe_json_load,
    characters_dir: str = "characters",
) -> Dict[str, Any]:
    """Resumable, idempotent, fail-open campaign backfill. Returns a status dict.

    `progress(stage, done, total, message)`: stage in
    {'start','journal','summaries','complete','paused','disabled'}.
    """
    def emit(stage, done, total, message=""):
        if progress:
            try:
                progress(stage, done, total, message)
            except Exception:
                pass

    store = episode_store or EpisodeStore()
    rel = rel_store or RelationshipStore()
    if store.read_only or getattr(rel, "read_only", False):
        record_store_health(
            "episodic_upgrade_disabled_read_only",
            detail="episode/relationship store read-only; upgrade skipped this session",
        )
        emit("disabled", 0, 0, "memory store unavailable; skipped")
        return {"status": "disabled", "committed": 0}

    roster = build_companion_roster(load_character_dicts(characters_dir))
    if not roster:
        marker = {"version": UPGRADE_VERSION, "status": "complete",
                  "journalNextIndex": 0, "summariesDone": True, "committed": 0}
        _write_marker(marker, marker_path)
        emit("complete", 0, 0, "no companions to remember")
        return {"status": "complete", "committed": 0}

    module = str(party_tracker_data.get("module") or "").replace(" ", "_")
    module_dir = getattr(path_manager, "module_dir", None) or os.path.join("modules", module)
    name_to_id_map = build_location_name_map(load_module_area_dicts(module_dir))

    members = party_tracker_data.get("partyMembers") or []
    first = members[0] if members else ""
    player_name = (
        str(first.get("name") or "").strip() if isinstance(first, dict)
        else str(first or "").strip()
    )

    marker = read_marker(marker_path)
    if marker.get("version") != UPGRADE_VERSION:
        marker = {"version": UPGRADE_VERSION, "status": "in_progress",
                  "journalNextIndex": 0, "summariesDone": False, "committed": 0}
    committed = int(marker.get("committed", 0))

    emit("start", 0, 0, "recovering companion memories")

    # --- journal (the strong source) ---
    journal = json_loader(journal_path)
    journal = journal if isinstance(journal, dict) else {"entries": []}
    start_index = int(marker.get("journalNextIndex", 0))
    total_entries = len(journal.get("entries") or [])
    if start_index < total_entries:
        report = backfill_from_journal(
            journal, party_tracker_data,
            path_manager=path_manager, roster_names=roster,
            name_to_id_map=name_to_id_map, episode_store=store, rel_store=rel,
            player_name=player_name, provider=provider, json_loader=json_loader,
            # backfill_from_journal reports the ABSOLUTE entry index, so on a resumed
            # load the bar already shows cumulative progress (e.g. 41/277) -- do NOT
            # add start_index again.
            progress_cb=lambda done, total: emit("journal", done, total,
                                                 "recovering memories"),
            start_index=start_index, max_entries=per_run_cap,
        )
        committed += report["committed"]
        marker.update({"status": "in_progress", "journalNextIndex": report["next_index"],
                       "committed": committed})
        _write_marker(marker, marker_path)
        if report["next_index"] < total_entries:
            # hit the per-run cap: pause, resume next load
            emit("paused", report["next_index"], total_entries, "more memories next time")
            return {"status": "paused", "committed": committed,
                    "next_index": report["next_index"], "total": total_entries}

    # --- campaign summaries (coarse module-level) ---
    if not marker.get("summariesDone"):
        summaries = _load_summaries(summaries_dir, json_loader)
        if summaries:
            sreport = backfill_from_summaries(
                summaries, party_tracker_data,
                path_manager=path_manager, roster_names=roster,
                episode_store=store, rel_store=rel,
                player_name=player_name, provider=provider, json_loader=json_loader,
                progress_cb=lambda done, total: emit("summaries", done, total,
                                                     "recovering the saga"),
            )
            committed += sreport["committed"]
        marker["summariesDone"] = True
        marker["committed"] = committed

    marker["status"] = "complete"
    _write_marker(marker, marker_path)
    emit("complete", total_entries, total_entries, "companions remember the journey")
    return {"status": "complete", "committed": committed}


def check_and_run_episode_upgrade(
    party_tracker_data: Optional[Mapping[str, Any]] = None,
    path_manager: Any = None,
    *,
    provider: Optional[str] = None,
    progress: Optional[Callable[[str, int, int, str], None]] = None,
    per_run_cap: Optional[int] = None,
    marker_path: str = MARKER_PATH,
) -> Dict[str, Any]:
    """First-run detector + orchestrator, called ONCE at the startup seam beside the
    legacy check_and_initialize_on_startup. Gated by NPC_VOICE_ENABLED. Fail-open."""
    try:
        import config as _config
        if getattr(_config, "NPC_VOICE_ENABLED", False) is not True:
            return {"status": "disabled_flag"}

        marker = read_marker(marker_path)
        if is_complete(marker):
            return {"status": "already_complete"}

        if not game_has_history():
            # Fresh game -> mark complete so detection never re-runs; memory accrues
            # forward from live capture.
            _write_marker(
                {"version": UPGRADE_VERSION, "status": "complete",
                 "journalNextIndex": 0, "summariesDone": True, "committed": 0},
                marker_path,
            )
            return {"status": "fresh_game"}

        if party_tracker_data is None:
            party_tracker_data = safe_json_load("party_tracker.json") or {}
        if path_manager is None:
            from utils.module_path_manager import ModulePathManager
            module = str(party_tracker_data.get("module") or "").replace(" ", "_")
            path_manager = ModulePathManager(module) if module else ModulePathManager()

        return backfill_campaign(
            party_tracker_data, path_manager,
            provider=provider, progress=progress, per_run_cap=per_run_cap,
            marker_path=marker_path,
        )
    except Exception as error:  # noqa: BLE001 - upgrade never blocks startup
        _LOGGER.debug("episodic upgrade failed (non-fatal): %r", error)
        return {"status": "error"}


def default_progress(stage: str, done: int, total: int, message: str = "") -> None:
    """Terminal + web progress. Emits a DISTINCT event name (NOT compression_*, which
    the live compaction widget owns) so a cloned front-end bar can render it; also
    prints a terminal line for headless/terminal play."""
    try:
        from core.managers.status_manager import status_manager
        # paused/disabled also close the overlay via the complete event.
        event = {
            "start": "episodic_upgrade_start",
            "complete": "episodic_upgrade_complete",
            "paused": "episodic_upgrade_complete",
            "disabled": "episodic_upgrade_complete",
        }.get(stage, "episodic_upgrade_progress")
        status_manager.emit_compression_event(
            event, {"completed": done, "total": total, "message": message, "stage": stage}
        )
    except Exception:
        pass
    if stage in ("start", "complete", "paused", "disabled") or (total and done % 25 == 0):
        pct = (" %d/%d" % (done, total)) if total else ""
        print("[MEMORY] %s%s %s" % (stage, pct, message))
