"""Strict, atomic, revisioned persistence for the CANONICAL episode ledger.

One row = one real event at one location, the shared truth all companions
reference (so per-NPC POV can never contradict it or the DM). Mirrors
RelationshipStore's discipline: file lock, monotonic revision, whole-document
schema validation, atomic replace, a forward-migration chain, and a LOUD
read-only latch (shared health signal) instead of a silent swallow.

The episodeId is derived from STABLE COORDINATES (module|locationId|
boundaryTurnId), never from content -- so re-extracting a segment on a revisit,
or backfilling from an archive, is idempotent (same id -> update in place, no
duplicates). This honors "no content-hash as identity".
"""

from __future__ import annotations

import copy
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple

from jsonschema import Draft202012Validator

from core.npc.relationship_store import record_store_health
from utils.encoding_utils import safe_json_dump
from utils.path_transaction_lock import path_transaction_lock

_LOGGER = logging.getLogger(__name__)
EPISODE_SCHEMA_VERSION = 1
DEFAULT_LEDGER_PATH = Path("data/companion_memories/episode_ledger.json")
DEFAULT_LEDGER_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "schemas" / "episode_ledger_schema.json"
)
# Dedicated namespace so episode ids never collide with identity ids.
EPISODE_NAMESPACE = uuid.UUID("2f9c8b41-6d5e-5a7c-9f13-8e2a4b6c1d70")

VALID_SALIENT_KINDS = frozenset({
    "defeat", "near_death", "rescue", "protect", "sacrifice", "loss", "discovery",
    "vow", "betrayal", "victory", "defeat_suffered", "first_meeting", "reunion",
    "bond", "tender", "joke", "fear", "vulnerability", "habit", "gift", "confession",
})
VALID_DERIVED_FROM = frozenset({
    "location_summary", "combat_telemetry", "backfill", "module_consolidation",
})
_UUID_RE = uuid.UUID  # used via try/except in _is_uuid


def stable_episode_id(module: str, location_id: str, boundary_turn_id: str) -> str:
    seed = "%s|%s|%s" % (module or "", location_id or "", boundary_turn_id or "")
    return str(uuid.uuid5(EPISODE_NAMESPACE, seed))


def _is_uuid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def _text(value: Any, limit: int) -> str:
    return value.strip()[:limit] if isinstance(value, str) else ""


def _clamp01(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def new_ledger_document() -> Dict[str, Any]:
    return {
        "schemaVersion": EPISODE_SCHEMA_VERSION,
        "revision": 0,
        "ordinalCounter": 0,
        "episodes": {},
    }


# Forward migrations keyed by the version they upgrade FROM (empty at v1; the
# framework exists so a future bump rewrites-on-load rather than latching).
_FORWARD_MIGRATIONS: Dict[int, Callable[[Dict[str, Any]], Dict[str, Any]]] = {}


def _migrate_document(document: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    version = document.get("schemaVersion")
    if not isinstance(version, int):
        return None
    if version == EPISODE_SCHEMA_VERSION:
        return document
    working = copy.deepcopy(document)
    guard = 0
    while working.get("schemaVersion") != EPISODE_SCHEMA_VERSION:
        migrator = _FORWARD_MIGRATIONS.get(working.get("schemaVersion"))
        if migrator is None:
            return None
        working = migrator(working)
        guard += 1
        if guard > len(_FORWARD_MIGRATIONS) + 1:
            return None
    return working


def _sanitize_actor_ref(value: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(value, Mapping):
        return None
    label = _text(value.get("label"), 80)
    if not label:
        return None
    ref: Dict[str, Any] = {"label": label}
    if _is_uuid(value.get("id")):
        ref["id"] = value["id"]
    return ref


def _sanitize_salient_facts(value: Any) -> List[Dict[str, Any]]:
    facts: List[Dict[str, Any]] = []
    if not isinstance(value, (list, tuple)):
        return facts
    for item in value:
        if not isinstance(item, Mapping):
            continue
        kind = item.get("kind")
        subject = _sanitize_actor_ref(item.get("subject"))
        one_line = _text(item.get("oneLine"), 120)
        if kind not in VALID_SALIENT_KINDS or subject is None or not one_line:
            continue
        fact: Dict[str, Any] = {"kind": kind, "subject": subject, "oneLine": one_line}
        obj = _sanitize_actor_ref(item.get("object"))
        if obj is not None:
            fact["object"] = obj
        facts.append(fact)
        if len(facts) >= 8:
            break
    return facts


def _unique_capped(value: Any, *, limit_len: int, count: int) -> List[str]:
    result: List[str] = []
    if not isinstance(value, (list, tuple)):
        return result
    for item in value:
        text = _text(item, limit_len)
        if text and text not in result:
            result.append(text)
        if len(result) >= count:
            break
    return result


def _witness_ids(value: Any) -> List[str]:
    result: List[str] = []
    if not isinstance(value, (list, tuple)):
        return result
    for item in value:
        if _is_uuid(item) and item not in result:
            result.append(item)
        if len(result) >= 16:
            break
    return result


class EpisodeStore:
    """Path-scoped canonical episode ledger with fail-closed writes/fail-open reads."""

    def __init__(
        self,
        path: os.PathLike[str] | str = DEFAULT_LEDGER_PATH,
        *,
        schema_path: os.PathLike[str] | str = DEFAULT_LEDGER_SCHEMA_PATH,
    ) -> None:
        self.path = Path(path)
        self.schema_path = Path(schema_path)
        self._validator = Draft202012Validator(
            json.loads(self.schema_path.read_text(encoding="ascii"))
        )
        self._read_only_reason: Optional[str] = None
        if self.path.exists() and self._read_existing() is None:
            self._latch_read_only("corrupt_or_unsupported")

    def _latch_read_only(self, reason: str) -> None:
        self._read_only_reason = reason
        record_store_health("episode_read_only_latch", path=str(self.path), detail=reason)

    @property
    def read_only(self) -> bool:
        return self._read_only_reason is not None

    def _validate(self, document: Mapping[str, Any]) -> bool:
        if document.get("schemaVersion") != EPISODE_SCHEMA_VERSION:
            return False
        return next(self._validator.iter_errors(document), None) is None

    def _read_existing(self) -> Optional[Dict[str, Any]]:
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                value = json.load(handle)
        except (OSError, ValueError, TypeError):
            return None
        if not isinstance(value, dict):
            return None
        migrated = _migrate_document(value)
        candidate = migrated if migrated is not None else value
        return candidate if self._validate(candidate) else None

    def snapshot(self) -> Dict[str, Any]:
        value = self._read_existing() if self.path.exists() else None
        return copy.deepcopy(value if value is not None else new_ledger_document())

    def _mutate(
        self, callback: Callable[[Dict[str, Any]], Tuple[bool, Any]]
    ) -> Tuple[bool, Any]:
        if self.read_only:
            return False, None
        try:
            with path_transaction_lock(
                self.path, suffix=".episode-ledger.lock", timeout_seconds=5.0
            ) as acquired:
                if acquired is None:
                    return False, None
                if self.path.exists():
                    current = self._read_existing()
                    if current is None:
                        self._latch_read_only("corrupt_or_unsupported")
                        return False, None
                else:
                    current = new_ledger_document()
                candidate = copy.deepcopy(current)
                changed, result = callback(candidate)
                if not changed:
                    return False, result
                candidate["revision"] = current["revision"] + 1
                if not self._validate(candidate):
                    record_store_health(
                        "episode_write_invalid", path=str(self.path), detail="schema"
                    )
                    return False, result
                try:
                    safe_json_dump(candidate, self.path, ensure_ascii=True)
                except Exception:
                    record_store_health("episode_write_failed", path=str(self.path))
                    return False, result
                return True, result
        except Exception:
            record_store_health("episode_mutate_failed", path=str(self.path))
            return False, None

    def commit_episode(
        self,
        *,
        module: str,
        location_id: str,
        location_name: str,
        game_day: Optional[int],
        boundary_turn_id: str,
        headline: str,
        canonical_summary: str,
        salient_facts: Iterable[Mapping[str, Any]],
        entity_tags: Iterable[str],
        witness_ids: Iterable[str],
        intensity: float,
        derived_from: str = "location_summary",
        source_hash: str = "",
        prompt_version: str = "",
    ) -> Optional[str]:
        """Idempotently write one canonical episode; returns its episodeId or None.

        Keyed on stable coordinates: re-running the same segment updates the row in
        place (ordinal preserved) instead of duplicating it.
        """
        episode_id = stable_episode_id(module, location_id, boundary_turn_id)
        derived = derived_from if derived_from in VALID_DERIVED_FROM else "location_summary"
        source = source_hash if (isinstance(source_hash, str) and (source_hash == "" or (len(source_hash) == 64))) else ""
        game_day_value = game_day if isinstance(game_day, int) and game_day >= 0 else None

        def update(document: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
            episodes = document["episodes"]
            existing = episodes.get(episode_id)
            if existing is not None:
                ordinal = existing["ordinal"]
            else:
                ordinal = document["ordinalCounter"]
                document["ordinalCounter"] = ordinal + 1
            record = {
                "episodeId": episode_id,
                "ordinal": ordinal,
                "module": _text(module, 160),
                "locationId": _text(location_id, 120),
                "locationName": _text(location_name, 160),
                "gameDay": game_day_value,
                "boundaryTurnId": _text(boundary_turn_id, 120),
                "headline": _text(headline, 100),
                "canonicalSummary": _text(canonical_summary, 600),
                "salientFacts": _sanitize_salient_facts(salient_facts),
                "entityTags": _unique_capped(entity_tags, limit_len=60, count=12),
                "witnessIds": _witness_ids(witness_ids),
                "intensity": _clamp01(intensity),
                "derivedFrom": derived,
                "sourceHash": source,
                "promptVersion": _text(prompt_version, 40),
            }
            if existing == record:
                return False, episode_id
            episodes[episode_id] = record
            return True, episode_id

        _, result = self._mutate(update)
        # result is the id whether or not a write was needed (idempotent no-op still
        # resolves to the stable id); None only on a hard failure.
        return result if result is not None else (episode_id if not self.read_only else None)

    def get_episode(self, episode_id: str) -> Optional[Dict[str, Any]]:
        return self.snapshot()["episodes"].get(episode_id)

    def episodes_for_witness(self, npc_id: str) -> List[Dict[str, Any]]:
        rows = [
            episode
            for episode in self.snapshot()["episodes"].values()
            if npc_id in episode.get("witnessIds", [])
        ]
        rows.sort(key=lambda e: e.get("ordinal", 0))
        return rows
