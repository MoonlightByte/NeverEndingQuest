"""Strict, atomic, revisioned persistence for private NPC relationship state."""

from __future__ import annotations

import copy
import json
import logging
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Tuple

from jsonschema import Draft202012Validator

from core.effects.clock import SECONDS_PER_DAY, scalar_from_calendar
from core.npc.relationship_rules import (
    DIMENSIONS,
    EVENT_DELTAS,
    apply_event_delta,
    baseline_from_pinned,
    clamp_state,
    decay_toward_baseline,
    event_delta,
)
from core.npc.voice_contracts import (
    NEGATIVE_AFFINITY_EVENT_TYPES,
    POSITIVE_AFFINITY_EVENT_TYPES,
    PROMPT_VERSION,
)
from utils.encoding_utils import safe_json_dump
from utils.path_transaction_lock import path_transaction_lock


_LOGGER = logging.getLogger(__name__)
SCHEMA_VERSION = 2
MIGRATION_VERSION = "companion-memory-v1"
DEFAULT_STATE_PATH = Path("data/companion_memories/npc_agent_state.json")
DEFAULT_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "npc_agent_state_schema.json"
PROJECT_IDENTITY_NAMESPACE = uuid.UUID("9b0f3d4d-bf49-5c2c-a8bb-4056bdc31fc1")
UNRESOLVED_TYPES = frozenset({"abandon", "betray", "rescue"})

# Loud, non-fail-open persistence signal. A read-only latch or a turn that commits
# zero writes despite an eligible packet must never be swallowed at debug level --
# that is exactly the "dead feature behind perfect narration" failure this project
# has already shipped once. Callers/tests can inspect these events; a startup guard
# Store-health evidence makes corrupt/unmigratable state loud to callers.
STORE_HEALTH_EVENTS: list[dict] = []
_MAX_HEALTH_EVENTS = 100


def record_store_health(event: str, *, path: str = "", detail: str = "") -> None:
    _LOGGER.error("NPC store health: %s path=%s %s", event, path, detail)
    STORE_HEALTH_EVENTS.append({"event": event, "path": path, "detail": detail})
    if len(STORE_HEALTH_EVENTS) > _MAX_HEALTH_EVENTS:
        del STORE_HEALTH_EVENTS[0]


@dataclass(frozen=True)
class EventApplication:
    event_id: str
    mutated: bool
    duplicate: bool = False
    read_only: bool = False


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )


def _text(value: Any, _limit: int = 0) -> str:
    return value.strip() if isinstance(value, str) else ""


def _text_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    result = []
    for item in value:
        candidate = _text(item)
        if candidate and candidate not in result:
            result.append(candidate)
    return result


def normalize_identity_seed(sheet_path: os.PathLike[str] | str) -> str:
    """Return a stable, root-relative, slash-normalized identity seed."""
    raw = os.fspath(sheet_path)
    normalized = os.path.normpath(raw)
    if os.path.isabs(normalized):
        try:
            normalized = os.path.relpath(normalized, os.getcwd())
        except ValueError:
            pass
    while normalized.startswith("./") or normalized.startswith(".\\"):
        normalized = normalized[2:]
    return normalized.replace("\\", "/").casefold()


def stable_identity_id(kind: str, sheet_path: os.PathLike[str] | str) -> str:
    if kind not in {"npc", "player"}:
        raise ValueError("identity kind must be npc or player")
    seed = normalize_identity_seed(sheet_path)
    if not seed or seed == ".":
        raise ValueError("identity seed must name a character sheet")
    return str(uuid.uuid5(PROJECT_IDENTITY_NAMESPACE, "%s:%s" % (kind, seed)))


def game_day_ordinal(world_conditions: Mapping[str, Any]) -> Optional[int]:
    """Convert an exact persisted calendar date to an ordinal, or return None."""
    if not isinstance(world_conditions, Mapping):
        return None
    if not all(name in world_conditions for name in ("year", "month", "day")):
        return None
    try:
        return scalar_from_calendar(dict(world_conditions)) // SECONDS_PER_DAY
    except (TypeError, ValueError):
        return None


def _neutral() -> Dict[str, float]:
    return {name: 0.0 for name in DIMENSIONS}


def new_state_document() -> Dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "revision": 0,
        "identities": {},
        "profiles": {},
        "relationships": {},
        "working": {},
        "lifecycle": {},
        "migrations": {},
        "episodes": {},
    }


def _migrate_v1_to_v2(document: Dict[str, Any]) -> Dict[str, Any]:
    """Additive: reserve the per-NPC episodes container; no data is dropped."""
    document.setdefault("episodes", {})
    document["schemaVersion"] = 2
    return document


# Ordered forward migrations keyed by the version they upgrade FROM. A stored
# document is rewritten on load up to SCHEMA_VERSION instead of being rejected as
# corrupt -- so a schema bump can never silently latch existing saves read-only.
_FORWARD_MIGRATIONS: Dict[int, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    1: _migrate_v1_to_v2,
}


def _migrate_document(document: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Bring a document up to SCHEMA_VERSION via the forward chain.

    Returns the migrated document, the unchanged document if already current, or
    None if a version gap has no registered migrator (unknown/future version).
    """
    version = document.get("schemaVersion")
    if not isinstance(version, int):
        return None
    if version == SCHEMA_VERSION:
        return document
    working = copy.deepcopy(document)
    guard = 0
    while working.get("schemaVersion") != SCHEMA_VERSION:
        current = working.get("schemaVersion")
        migrator = _FORWARD_MIGRATIONS.get(current)
        if migrator is None:
            return None
        working = migrator(working)
        guard += 1
        if guard > len(_FORWARD_MIGRATIONS) + 1:
            return None
    return working


def _relationship_key(subject_id: str, counterparty_id: str) -> str:
    return "%s|%s" % (subject_id, counterparty_id)


def _new_relationship(
    subject_id: str,
    counterparty_id: str,
    game_day: Optional[int],
) -> Dict[str, Any]:
    return {
        "subjectId": subject_id,
        "counterpartyId": counterparty_id,
        "baseline": _neutral(),
        "current": _neutral(),
        "lastDecayDay": game_day,
        "evidence": [],
        # appliedEventIds is the EXACT applied-event membership list (value ids).
        # Legacy edges may also carry appliedEventHistory (a retired probabilistic
        # bitmap that could silently drop colliding events) and evidenceHashChain
        # (a retired tamper-evidence digest chain). Both are tolerated on load but
        # never written or consulted for new edges.
        "appliedEventIds": [],
        "aggregateCounts": {},
    }


def _identity_names(identity: Mapping[str, Any]) -> set[str]:
    names = {_text(identity.get("displayName"), 100)}
    names.update(
        _text(value, 100)
        for value in identity.get("aliases", [])
        if isinstance(value, str)
    )
    return {name for name in names if name}


def _canonical_name_tokens(name: Any) -> Tuple[str, ...]:
    """Canonical identity form for VALUE comparison at the identity boundary:
    lowercase alphanumeric tokens (same canonicalization family as
    normalize_character_name in updates/update_character_info.py). Deterministic
    -- no fuzzy/ratio matching."""
    if not isinstance(name, str):
        return ()
    return tuple(t for t in re.split(r"[^a-z0-9]+", name.strip().lower()) if t)


def _legacy_name_matches_identity(legacy_name: str, identity: Mapping[str, Any]) -> bool:
    """True when the legacy file's npc_name canonically resolves to this identity.
    Rule (deterministic, value-level): canonical token tuples are equal, OR the
    legacy tokens are a non-empty SUBSET of one registered name's tokens (real
    files say "Kira" while the roster identity is "Scout Kira")."""
    legacy_tokens = _canonical_name_tokens(legacy_name)
    if not legacy_tokens:
        return False
    legacy_set = set(legacy_tokens)
    for registered_name in _identity_names(identity):
        registered_tokens = _canonical_name_tokens(registered_name)
        if legacy_tokens == registered_tokens:
            return True
        if legacy_set and legacy_set <= set(registered_tokens):
            return True
    return False


# Per-NPC POV overlay (Phase 2). The canonical episode ledger holds the shared truth;
# these rows are the cheap per-NPC delta (how THIS npc holds it), code-derived.
POV_TAGS = frozenset({
    "proud", "triumphant", "traumatic", "tender", "guilty", "grieving", "resentful",
    "afraid", "grateful", "protective", "amused", "smitten", "longing", "heartbroken",
})


def _sanitize_pov_episode(value: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(value, Mapping):
        return None
    episode_id = value.get("episodeId")
    try:
        uuid.UUID(str(episode_id))
    except (ValueError, AttributeError, TypeError):
        return None
    if value.get("povTag") not in POV_TAGS:
        return None
    try:
        salience = max(0.0, min(1.0, round(float(value.get("salienceScore", 0.0)), 4)))
    except (TypeError, ValueError):
        salience = 0.0
    return {
        "episodeId": str(episode_id),
        "povTag": value["povTag"],
        "salienceScore": salience,
        "pinned": bool(value.get("pinned")),
        "personalLine": _text(value.get("personalLine"), 160),
        "linkedEvidenceIds": _text_list(value.get("linkedEvidenceIds")),
    }


class RelationshipStore:
    """One path-scoped sidecar with fail-closed writes and fail-open reads."""

    def __init__(
        self,
        path: os.PathLike[str] | str = DEFAULT_STATE_PATH,
        *,
        schema_path: os.PathLike[str] | str = DEFAULT_SCHEMA_PATH,
    ) -> None:
        self.path = Path(path)
        self.schema_path = Path(schema_path)
        schema = json.loads(self.schema_path.read_text(encoding="ascii"))
        self._validator = Draft202012Validator(schema)
        self._read_only_reason: Optional[str] = None
        if self.path.exists():
            document = self._read_existing()
            if document is None:
                self._latch_read_only("corrupt_or_unsupported")

    def _latch_read_only(self, reason: str) -> None:
        self._read_only_reason = reason
        record_store_health("read_only_latch", path=str(self.path), detail=reason)

    @property
    def read_only(self) -> bool:
        return self._read_only_reason is not None

    @property
    def read_only_reason(self) -> Optional[str]:
        return self._read_only_reason

    def _validate(self, document: Mapping[str, Any]) -> bool:
        if document.get("schemaVersion") != SCHEMA_VERSION:
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
        if self._validate(candidate):
            return candidate
        return None

    def snapshot(self) -> Dict[str, Any]:
        value = self._read_existing() if self.path.exists() else None
        return copy.deepcopy(value if value is not None else new_state_document())

    def _mutate(
        self,
        callback: Callable[[Dict[str, Any]], Tuple[bool, Any]],
    ) -> Tuple[bool, Any]:
        if self.read_only:
            return False, None
        try:
            while True:
                with path_transaction_lock(
                    self.path,
                    suffix=".npc-agent.lock",
                    timeout_seconds=5.0,
                ) as acquired:
                    if acquired is None:
                        # B2-ii: busy = WAIT, never a dropped write (see episode_store).
                        record_store_health(
                            "relationship_lock_waiting", path=str(self.path)
                        )
                        continue
                    if self.path.exists():
                        current = self._read_existing()
                        if current is None:
                            self._latch_read_only("corrupt_or_unsupported")
                            return False, None
                    else:
                        current = new_state_document()
                    candidate = copy.deepcopy(current)
                    changed, result = callback(candidate)
                    if not changed:
                        return False, result
                    candidate["revision"] = current["revision"] + 1
                    if not self._validate(candidate):
                        record_store_health(
                            "relationship_schema_rejected", path=str(self.path)
                        )
                        return False, result
                    try:
                        safe_json_dump(candidate, self.path, ensure_ascii=True)
                    except Exception:
                        record_store_health("relationship_write_failed", path=str(self.path))
                        return False, result
                    return True, result
        except Exception:
            record_store_health("relationship_mutate_failed", path=str(self.path))
            return False, None

    def _resolve_existing_identity(
        self,
        document: Mapping[str, Any],
        *,
        kind: str,
        display_name: str,
        sheet_path: str,
    ) -> Optional[str]:
        identities = document["identities"]
        normalized_path = normalize_identity_seed(sheet_path)
        path_matches = [
            identity_id
            for identity_id, identity in identities.items()
            if identity.get("kind") == kind
            and normalize_identity_seed(identity.get("sheetPath", ""))
            == normalized_path
        ]
        if len(path_matches) == 1:
            return path_matches[0]
        # Name fallback for identities with no distinct sheet path. Match only the
        # CURRENT displayName -- never a historical alias -- and never bind onto an
        # identity that already owns a DIFFERENT sheet path. Matching a retired alias
        # or a same-named-but-different-sheet character silently merges two distinct
        # NPCs' histories (issue #164 / finding M28).
        name_matches = []
        for identity_id, identity in identities.items():
            if identity.get("kind") != kind:
                continue
            if _text(identity.get("displayName"), 100) != display_name:
                continue
            existing_path = normalize_identity_seed(identity.get("sheetPath", ""))
            if existing_path and existing_path != normalized_path:
                continue
            name_matches.append(identity_id)
        if len(name_matches) == 1:
            return name_matches[0]
        if len(path_matches) > 1 or len(name_matches) > 1:
            raise ValueError("ambiguous stable identity")
        return None

    def ensure_identity(
        self,
        *,
        kind: str,
        display_name: str,
        sheet_path: os.PathLike[str] | str,
        module: str = "",
        location_id: str = "",
        active: Optional[bool] = True,
    ) -> str:
        display_name = _text(display_name, 100)
        normalized_path = normalize_identity_seed(sheet_path)
        if not display_name:
            raise ValueError("identity display name is required")
        proposed_id = stable_identity_id(kind, normalized_path)
        snapshot = self.snapshot()
        try:
            existing_id = self._resolve_existing_identity(
                snapshot,
                kind=kind,
                display_name=display_name,
                sheet_path=normalized_path,
            )
        except ValueError:
            raise
        identity_id = existing_id or proposed_id
        if self.read_only:
            return identity_id

        def update(document: Dict[str, Any]) -> Tuple[bool, str]:
            resolved = self._resolve_existing_identity(
                document,
                kind=kind,
                display_name=display_name,
                sheet_path=normalized_path,
            )
            selected_id = resolved or identity_id
            identity = document["identities"].get(selected_id)
            if identity is None:
                document["identities"][selected_id] = {
                    "kind": kind,
                    "displayName": display_name,
                    "aliases": [],
                    "sheetPath": normalized_path,
                    "identitySeed": normalized_path,
                    "active": True if active is None else bool(active),
                    "lastModule": _text(module, 160),
                    "lastLocationId": _text(location_id, 120),
                }
                if kind == "npc":
                    document["lifecycle"][selected_id] = {
                        "status": "active" if active is not False else "inactive",
                        "events": [],
                    }
                return True, selected_id
            before = copy.deepcopy(identity)
            old_name = identity["displayName"]
            if old_name != display_name and old_name not in identity["aliases"]:
                identity["aliases"].append(old_name)
                identity["aliases"] = identity["aliases"][-32:]
            identity["displayName"] = display_name
            identity["sheetPath"] = normalized_path
            if active is not None:
                identity["active"] = bool(active)
            identity["lastModule"] = _text(module, 160)
            identity["lastLocationId"] = _text(location_id, 120)
            lifecycle_changed = False
            if kind == "npc":
                lifecycle = document["lifecycle"].setdefault(
                    selected_id, {"status": "active", "events": []}
                )
                if active is not None:
                    prior_lifecycle_status = lifecycle.get("status")
                    lifecycle["status"] = "active" if active else "inactive"
                    lifecycle_changed = lifecycle["status"] != prior_lifecycle_status
            return before != identity or lifecycle_changed, selected_id

        _changed, actual_id = self._mutate(update)
        return actual_id or identity_id

    def _ensure_edge(
        self,
        document: Dict[str, Any],
        subject_id: str,
        counterparty_id: str,
        game_day: Optional[int],
    ) -> Tuple[Dict[str, Any], bool]:
        if subject_id == counterparty_id:
            raise ValueError("relationship endpoints must differ")
        if (
            subject_id not in document["identities"]
            or counterparty_id not in document["identities"]
        ):
            raise ValueError("relationship endpoints must be registered identities")
        key = _relationship_key(subject_id, counterparty_id)
        if key not in document["relationships"]:
            document["relationships"][key] = _new_relationship(
                subject_id, counterparty_id, game_day
            )
            return document["relationships"][key], True
        return document["relationships"][key], False

    @staticmethod
    def _apply_decay(edge: Dict[str, Any], game_day: Optional[int]) -> bool:
        if game_day is None:
            return False
        last_day = edge.get("lastDecayDay")
        if last_day is None:
            edge["lastDecayDay"] = game_day
            return True
        if game_day <= last_day:
            return False
        edge["current"] = decay_toward_baseline(
            edge["baseline"], edge["current"], game_day - last_day
        )
        edge["lastDecayDay"] = game_day
        return True

    def get_relationship(
        self,
        subject_id: str,
        counterparty_id: str,
        *,
        game_day: Optional[int] = None,
    ) -> Dict[str, Any]:
        holder: Dict[str, Any] = {}

        def update(document: Dict[str, Any]) -> Tuple[bool, None]:
            edge, created = self._ensure_edge(
                document, subject_id, counterparty_id, game_day
            )
            decayed = self._apply_decay(edge, game_day)
            holder["edge"] = copy.deepcopy(edge)
            return created or decayed, None

        if self.read_only:
            snapshot = self.snapshot()
            edge = snapshot["relationships"].get(
                _relationship_key(subject_id, counterparty_id)
            )
            return copy.deepcopy(
                edge or _new_relationship(subject_id, counterparty_id, game_day)
            )
        self._mutate(update)
        return holder.get(
            "edge", _new_relationship(subject_id, counterparty_id, game_day)
        )

    def get_profile(self, npc_id: str) -> Optional[Dict[str, Any]]:
        """Return one validated persisted profile without exposing live state."""
        profile = self.snapshot()["profiles"].get(npc_id)
        return copy.deepcopy(profile) if isinstance(profile, dict) else None

    def store_profile(self, npc_id: str, profile: Mapping[str, Any]) -> bool:
        """Atomically replace one profile after whole-document validation."""
        candidate = copy.deepcopy(dict(profile)) if isinstance(profile, Mapping) else {}

        def update(document: Dict[str, Any]) -> Tuple[bool, None]:
            identity = document["identities"].get(npc_id)
            if not identity or identity.get("kind") != "npc":
                return False, None
            if document["profiles"].get(npc_id) == candidate:
                return False, None
            document["profiles"][npc_id] = candidate
            return True, None

        mutated, _ = self._mutate(update)
        return mutated

    def _event_id(
        self,
        source_turn_id: str,
        subject_id: str,
        counterparty_id: str,
        event: Mapping[str, Any],
        prompt_version: str,
    ) -> str:
        # Value-tuple identity (no digest): the lossless canonical-JSON encoding
        # of exactly the fields that identify this event application.
        return "evt|" + _canonical_json(
            [
                "relationship-event/v2",
                source_turn_id,
                subject_id,
                counterparty_id,
                prompt_version,
            ]
        )

    def _validate_event(
        self,
        document: Mapping[str, Any],
        subject_id: str,
        counterparty_id: str,
        event: Mapping[str, Any],
    ) -> None:
        if set(event) != {"actor", "target", "eventType", "magnitude", "witnessed"}:
            raise ValueError("relationship event keys are invalid")
        subject = document["identities"].get(subject_id)
        counterparty = document["identities"].get(counterparty_id)
        if not subject or not counterparty or subject.get("kind") != "npc":
            raise ValueError("relationship event identity direction is invalid")
        if event["actor"] not in _identity_names(counterparty):
            raise ValueError("relationship event actor is not the counterparty")
        if event["target"] not in _identity_names(subject):
            raise ValueError("relationship event target is not the focal NPC")
        event_type = event["eventType"]
        magnitude = event["magnitude"]
        if event_type not in EVENT_DELTAS:
            raise ValueError("relationship event type is invalid")
        if (
            isinstance(magnitude, bool)
            or not isinstance(magnitude, int)
            or abs(magnitude) not in (1, 2, 3)
        ):
            raise ValueError("relationship event magnitude is invalid")
        if event_type in POSITIVE_AFFINITY_EVENT_TYPES and magnitude < 0:
            raise ValueError("positive relationship event has negative magnitude")
        if event_type in NEGATIVE_AFFINITY_EVENT_TYPES and magnitude > 0:
            raise ValueError("negative relationship event has positive magnitude")
        if not isinstance(event["witnessed"], bool):
            raise ValueError("relationship witnessed flag is invalid")

    @staticmethod
    def _prune_evidence(edge: Dict[str, Any]) -> None:
        """Keep every accepted evidence row and every exact applied event ID."""
        records = edge["evidence"]
        prior_applied = list(dict.fromkeys(
            value for value in edge.get("appliedEventIds", [])
            if isinstance(value, str) and value
        ))
        record_ids = [
            record["eventId"]
            for record in records
            if record["kind"] == "typedEvent"
        ]
        edge["appliedEventIds"] = list(dict.fromkeys(prior_applied + record_ids))

    @staticmethod
    def _sanitize_advisory(value: Any) -> Optional[Dict[str, Any]]:
        """Normalize one accepted say/do/want advisory beat without data loss."""
        if not isinstance(value, Mapping):
            return None
        beat = {
            "say": _text(value.get("say"), 240),
            "do": _text(value.get("do"), 200),
            "want": _text(value.get("want"), 200),
            "thought": _text(value.get("thought"), 300),
            "beatId": _text(value.get("beatId"), 120),
            "stale": bool(value.get("stale")),
        }
        if not (beat["say"] or beat["do"] or beat["want"] or beat["thought"]):
            return None
        return beat

    @staticmethod
    def _set_working(
        document: Dict[str, Any],
        npc_id: str,
        working: Optional[Mapping[str, Any]],
    ) -> bool:
        if not working:
            return False
        source_turn = _text(working.get("sourceTurn"), 120)
        intent = _text(working.get("currentPrivateIntent"), 300)
        if not source_turn or not intent:
            return False
        candidate = {
            "currentPrivateIntent": intent,
            "sourceTurn": source_turn,
            "currentGoalReference": _text(working.get("currentGoalReference"), 300),
            "openQuestion": _text(working.get("openQuestion"), 240),
            "moodTags": list(dict.fromkeys(
                _text(value, 60)
                for value in working.get("moodTags", [])
                if _text(value, 60)
            )),
            "expiresAfterTurn": working.get("expiresAfterTurn")
            if isinstance(working.get("expiresAfterTurn"), int)
            and not isinstance(working.get("expiresAfterTurn"), bool)
            and working.get("expiresAfterTurn") >= 0
            else None,
            "sceneId": _text(working.get("sceneId"), 240),
        }
        # M7: persist the accepted say/do/want advisory beat and its complete
        # duplicate-free history.
        existing = document["working"].get(npc_id)
        existing = existing if isinstance(existing, dict) else {}
        advisory = RelationshipStore._sanitize_advisory(working.get("advisory"))
        if advisory is not None:
            candidate["advisory"] = advisory
            history = [
                row for row in existing.get("advisoryHistory", [])
                if isinstance(row, dict)
            ]
            if not history or history[-1] != advisory:
                history = history + [advisory]
            candidate["advisoryHistory"] = history
        else:
            # An advisory-less working refresh never erases persisted beats.
            if isinstance(existing.get("advisory"), dict):
                candidate["advisory"] = existing["advisory"]
            if isinstance(existing.get("advisoryHistory"), list):
                candidate["advisoryHistory"] = existing["advisoryHistory"]
        if existing == candidate:
            return False
        document["working"][npc_id] = candidate
        return True

    def apply_event(
        self,
        *,
        subject_id: str,
        counterparty_id: str,
        event: Mapping[str, Any],
        source_turn_id: str,
        evidence_summary: str,
        game_day: Optional[int],
        module: str,
        location_id: str,
        packet_hash: str,
        prompt_version: str = PROMPT_VERSION,
        topic_ids: Iterable[str] = (),
        working: Optional[Mapping[str, Any]] = None,
    ) -> EventApplication:
        source_turn_id = _text(source_turn_id, 120)
        evidence_summary = _text(evidence_summary, 240)
        if not source_turn_id or not evidence_summary:
            raise ValueError("relationship event source and evidence are required")
        snapshot = self.snapshot()
        self._validate_event(snapshot, subject_id, counterparty_id, event)
        event_id = self._event_id(
            source_turn_id,
            subject_id,
            counterparty_id,
            event,
            prompt_version,
        )
        if self.read_only:
            return EventApplication(event_id, False, read_only=True)
        disposition = {"duplicate": False}

        def update(document: Dict[str, Any]) -> Tuple[bool, str]:
            self._validate_event(document, subject_id, counterparty_id, event)
            edge, created = self._ensure_edge(
                document, subject_id, counterparty_id, game_day
            )
            prior_source = next(
                (
                    record
                    for record in edge["evidence"]
                    if record.get("kind") == "typedEvent"
                    and record.get("sourceTurnId") == source_turn_id
                ),
                None,
            )
            if prior_source is not None:
                disposition["duplicate"] = True
                return False, prior_source["eventId"]
            # Exact value membership. A replayed PRE-migration event mints a
            # value id that cannot match its old digest id, but the
            # sourceTurnId value comparison above already deduplicates it.
            if event_id in edge["appliedEventIds"]:
                disposition["duplicate"] = True
                return False, event_id
            changed = created or self._apply_decay(edge, game_day)
            witnessed = event["witnessed"]
            before = copy.deepcopy(edge["current"])
            edge["current"] = apply_event_delta(
                edge["current"],
                event["eventType"],
                event["magnitude"],
                witnessed=witnessed,
            )
            delta = event_delta(
                event["eventType"], event["magnitude"], witnessed
            )
            record = {
                "kind": "typedEvent",
                "eventId": event_id,
                "actorId": counterparty_id,
                "targetId": subject_id,
                "actor": event["actor"],
                "target": event["target"],
                "eventType": event["eventType"],
                "magnitude": abs(event["magnitude"]),
                "witnessed": witnessed,
                "applied": witnessed,
                "delta": delta,
                "summary": evidence_summary,
                "sourceTurnId": source_turn_id,
                "promptVersion": _text(prompt_version, 80),
                # packetHash retired (content digests are banned as identity);
                # always written empty, legacy hex values tolerated on load.
                "packetHash": "",
                "gameDay": game_day,
                "module": _text(module, 160),
                "locationId": _text(location_id, 120),
                "topicIds": list(dict.fromkeys(
                    _text(value, 240) for value in topic_ids if _text(value, 240)
                )),
                "unresolved": event["eventType"] in UNRESOLVED_TYPES,
                # sourceHash retired (digest identity is banned); kept as an
                # empty legacy-schema field for old-file compatibility.
                "sourceHash": "",
            }
            edge["evidence"].append(record)
            edge["appliedEventIds"].append(event_id)
            self._prune_evidence(edge)
            changed = True
            changed = self._set_working(document, subject_id, working) or changed
            return changed or before != edge["current"], event_id

        mutated, _result = self._mutate(update)
        return EventApplication(
            event_id,
            mutated,
            duplicate=disposition["duplicate"],
            read_only=self.read_only,
        )

    def update_working(
        self,
        npc_id: str,
        *,
        source_turn_id: str,
        thought: str,
        current_goal_reference: str = "",
        open_question: str = "",
        mood_tags: Iterable[str] = (),
        expires_after_turn: Optional[int] = None,
        scene_id: str = "",
        advisory: Optional[Mapping[str, Any]] = None,
    ) -> bool:
        working = {
            "currentPrivateIntent": thought,
            "sourceTurn": source_turn_id,
            "currentGoalReference": current_goal_reference,
            "openQuestion": open_question,
            "moodTags": list(mood_tags),
            "expiresAfterTurn": expires_after_turn,
            "sceneId": scene_id,
            "advisory": advisory,
        }

        def update(document: Dict[str, Any]) -> Tuple[bool, None]:
            if npc_id not in document["identities"]:
                return False, None
            return self._set_working(document, npc_id, working), None

        mutated, _ = self._mutate(update)
        return mutated

    def get_working(
        self,
        npc_id: str,
        *,
        scene_id: str = "",
        current_turn: Optional[int] = None,
    ) -> Dict[str, Any]:
        snapshot = self.snapshot()
        value = snapshot["working"].get(npc_id)
        if not isinstance(value, dict):
            return {}
        expired = (
            current_turn is not None
            and value["expiresAfterTurn"] is not None
            and current_turn > value["expiresAfterTurn"]
        )
        scene_changed = bool(
            scene_id and value["sceneId"] and scene_id != value["sceneId"]
        )
        if not expired and not scene_changed:
            return copy.deepcopy(value)

        def clear(document: Dict[str, Any]) -> Tuple[bool, None]:
            return document["working"].pop(npc_id, None) is not None, None

        self._mutate(clear)
        return {}

    def retrieve_evidence(
        self,
        subject_id: str,
        counterparty_id: str,
        *,
        present_actor_ids: Iterable[str],
        entity_ids: Iterable[str],
        limit: int = 3,
    ) -> list[Dict[str, Any]]:
        edge = self.snapshot()["relationships"].get(
            _relationship_key(subject_id, counterparty_id)
        )
        if not edge:
            return []
        relevant_ids = set(present_actor_ids) | set(entity_ids)

        def rank(record: Mapping[str, Any]) -> tuple:
            record_ids = {
                record.get("actorId"),
                record.get("targetId"),
                *record.get("topicIds", []),
            }
            intersects = bool(relevant_ids.intersection(record_ids))
            unresolved = (
                bool(record.get("unresolved"))
                or record.get("eventType") in UNRESOLVED_TYPES
            )
            game_day = record.get("gameDay")
            return (
                0 if intersects else 1,
                0 if unresolved else 1,
                -int(record.get("magnitude", 0)),
                -(game_day if isinstance(game_day, int) else -1),
                record.get("eventId", ""),
            )

        return [
            copy.deepcopy(record)
            for record in sorted(edge["evidence"], key=rank)[: max(0, min(limit, 3))]
        ]

    def migrate_legacy_identity(
        self,
        npc_id: str,
        counterparty_id: str,
        *,
        game_day: Optional[int],
    ) -> bool:
        if self.read_only:
            return False
        snapshot = self.snapshot()
        identity = snapshot["identities"].get(npc_id)
        if not identity or identity.get("kind") != "npc":
            return False
        memory_dir = self.path.parent
        matches = []
        for candidate in sorted(memory_dir.glob("*_memories.json")):
            if candidate.name in {"npc_agent_state.json", "memory_config.json"}:
                continue
            try:
                raw = candidate.read_bytes()
                value = json.loads(raw.decode("utf-8"))
            except (OSError, UnicodeError, ValueError, TypeError):
                continue
            if not isinstance(value, dict):
                continue
            legacy_name = _text(value.get("npc_name"), 100)
            if not legacy_name:
                continue
            # Identity boundary: resolve the legacy file's npc name ONCE against
            # the registered roster identities by canonical VALUE comparison
            # (real legacy files say "Kira"; the roster identity is "Scout Kira").
            # Exactly-one match imports; zero or ambiguous = skip LOUDLY, never guess.
            matching_ids = [
                identity_id
                for identity_id, registered in snapshot["identities"].items()
                if registered.get("kind") == "npc"
                and _legacy_name_matches_identity(legacy_name, registered)
            ]
            if matching_ids == [npc_id]:
                matches.append((candidate, raw, value))
            elif len(matching_ids) != 1:
                # Loud health record, deduped per store instance so per-turn
                # migration sweeps do not spam the log.
                warned = getattr(self, "_migration_match_warned", None)
                if warned is None:
                    warned = set()
                    self._migration_match_warned = warned
                if candidate.name not in warned:
                    warned.add(candidate.name)
                    record_store_health(
                        "legacy_import_unresolved_identity",
                        path=str(candidate),
                        detail="npc_name=%r matched %d roster identities (need exactly 1); skipped"
                        % (legacy_name, len(matching_ids)),
                    )
        if len(matches) != 1:
            return False
        source_path, _raw_bytes, legacy = matches[0]
        # Migration-record identity = the ACTUAL source values (lossless
        # canonical-JSON string), never a digest. A legacy record that only has
        # the retired sourceHash digest is tolerated but treated as
        # non-matching, so migration re-runs ONCE; the per-memory value dedup
        # below makes that re-run idempotent (nothing double-applies).
        source_canonical = _canonical_json(legacy)
        migration_key = "%s|%s" % (MIGRATION_VERSION, npc_id)
        old_migration = snapshot["migrations"].get(migration_key)
        if old_migration and old_migration.get("sourceCanonical") == source_canonical:
            return False

        def update(document: Dict[str, Any]) -> Tuple[bool, None]:
            prior = document["migrations"].get(migration_key)
            if prior and prior.get("sourceCanonical") == source_canonical:
                return False, None
            edge, _created = self._ensure_edge(
                document, npc_id, counterparty_id, game_day
            )
            raw_state = legacy.get("current_emotional_state")
            imported_state = clamp_state(
                raw_state if isinstance(raw_state, dict) else {}
            )
            if not edge["evidence"] and not edge["appliedEventIds"]:
                edge["baseline"] = imported_state
                edge["current"] = copy.deepcopy(imported_state)
                edge["lastDecayDay"] = game_day
            subject = document["identities"][npc_id]
            counterparty = document["identities"][counterparty_id]
            imported_count = 0
            # Dedup imported memories by their exact values (canonical-JSON
            # string of the memory object). Records written before this upgrade
            # only carry the retired sourceHash digest, so their sourceTurnId
            # (the memory's own stable id value) is the value-comparison
            # fallback -- a re-run migration never double-applies them.
            existing_values = {
                record.get("sourceCanonical")
                for record in edge["evidence"]
                if record.get("sourceCanonical")
            }
            existing_turn_ids = {
                record["sourceTurnId"]
                for record in edge["evidence"]
                if record["kind"] == "legacyEvidence" and record.get("sourceTurnId")
            }
            for index, memory in enumerate(legacy.get("core_memories", [])):
                if not isinstance(memory, dict):
                    continue
                memory_canonical = _canonical_json(memory)
                source_turn_id = _text(memory.get("id"), 120) or "legacy-%d" % index
                if memory_canonical in existing_values or source_turn_id in existing_turn_ids:
                    continue
                summary = _text(
                    memory.get("journal_excerpt")
                    or memory.get("context")
                    or "Imported legacy companion memory.",
                    240,
                ) or "Imported legacy companion memory."
                try:
                    velocity = float(memory.get("emotional_velocity", 0.0))
                except (TypeError, ValueError):
                    velocity = 0.0
                magnitude = max(0, min(3, int(round(abs(velocity) * 3))))
                # Value-tuple id from the same stable inputs (no digest).
                event_id = "migration|" + _canonical_json(
                    [MIGRATION_VERSION, npc_id, memory]
                )
                edge["evidence"].append(
                    {
                        "kind": "legacyEvidence",
                        "eventId": event_id,
                        "actorId": counterparty_id,
                        "targetId": npc_id,
                        "actor": counterparty["displayName"],
                        "target": subject["displayName"],
                        "eventType": None,
                        "magnitude": magnitude,
                        "witnessed": False,
                        "applied": False,
                        "delta": _neutral(),
                        "summary": summary,
                        "sourceTurnId": source_turn_id,
                        "promptVersion": "",
                        # packetHash retired; empty legacy-schema field only.
                        "packetHash": "",
                        "gameDay": None,
                        "module": "",
                        "locationId": _text(memory.get("location"), 120),
                        "topicIds": [],
                        "unresolved": False,
                        # sourceHash retired; sourceCanonical is the lossless
                        # value fingerprint used for import dedup.
                        "sourceHash": "",
                        "sourceCanonical": memory_canonical,
                    }
                )
                existing_values.add(memory_canonical)
                existing_turn_ids.add(source_turn_id)
                imported_count += 1
            self._prune_evidence(edge)
            behavior = legacy.get("behavioral_model")
            behavior_hint = _canonical_json(behavior) if isinstance(behavior, dict) else ""
            try:
                relative_source = source_path.relative_to(Path.cwd()).as_posix()
            except ValueError:
                relative_source = source_path.as_posix()
            document["migrations"][migration_key] = {
                "version": MIGRATION_VERSION,
                "npcId": npc_id,
                "sourcePath": relative_source,
                # sourceCanonical replaces the retired sourceHash digest as the
                # migration-record identity (full-value comparison).
                "sourceCanonical": source_canonical,
                "status": "migrated",
                "legacyBehaviorHint": behavior_hint,
                "migratedEvidence": imported_count,
            }
            return True, None

        mutated, _ = self._mutate(update)
        return mutated

    def _lifecycle_event(
        self,
        *,
        kind: str,
        source_turn_id: str,
        module: str,
        location_id: str,
        cause: str = "",
        departure_kind: str = "",
        destination: str = "",
        return_hook: str = "",
        game_day: Optional[int] = None,
        invited_by: str = "",
        terms: str = "",
        personal_objective: str = "",
        red_lines: Iterable[str] = (),
        compensation: str = "",
        expected_duration: str = "",
        prior_status: str = "unknown",
        unresolved_obligations: Iterable[str] = (),
    ) -> Dict[str, Any]:
        return {
            "kind": kind,
            "sourceTurnId": _text(source_turn_id, 120),
            "module": _text(module, 160),
            "locationId": _text(location_id, 120),
            "cause": _text(cause, 240),
            "departureKind": _text(departure_kind, 80),
            "destination": _text(destination, 160),
            "returnHook": _text(return_hook, 240),
            "gameDay": game_day if type(game_day) is int and game_day >= 0 else None,
            "invitedBy": _text(invited_by, 100),
            "terms": _text(terms, 240),
            "personalObjective": _text(personal_objective, 240),
            "redLines": _text_list(red_lines),
            "compensation": _text(compensation, 160),
            "expectedDuration": _text(expected_duration, 160),
            "priorStatus": prior_status
            if prior_status in {"new", "active", "inactive", "unknown"}
            else "unknown",
            "unresolvedObligations": _text_list(unresolved_obligations),
        }

    def mark_joined(
        self,
        npc_id: str,
        player_id: str,
        *,
        game_day: Optional[int],
        module: str,
        location_id: str,
        source_turn_id: str,
        lifecycle_context: Optional[Mapping[str, Any]] = None,
    ) -> str:
        """Record a first arrival through the canonical locked arrival mutation."""
        return self._mark_arrived(
            npc_id,
            player_id,
            game_day=game_day,
            module=module,
            location_id=location_id,
            source_turn_id=source_turn_id,
            lifecycle_context=lifecycle_context,
        )

    def _mark_arrived(
        self,
        npc_id: str,
        player_id: str,
        *,
        game_day: Optional[int],
        module: str,
        location_id: str,
        source_turn_id: str,
        lifecycle_context: Optional[Mapping[str, Any]],
    ) -> str:
        """Apply one receipt-idempotent join/rejoin under the store lock."""
        context = lifecycle_context if isinstance(lifecycle_context, Mapping) else {}

        def update(document: Dict[str, Any]) -> Tuple[bool, str]:
            selected = document["identities"].get(npc_id)
            if not selected or player_id not in document["identities"]:
                return False, "join"
            lifecycle_state = document["lifecycle"].setdefault(
                npc_id, {"status": "active", "events": []}
            )
            events = lifecycle_state["events"]
            if (
                source_turn_id
                and events
                and events[-1].get("kind") in {"join", "rejoin"}
                and events[-1].get("sourceTurnId") == source_turn_id
                and selected.get("active") is True
            ):
                return False, events[-1]["kind"]
            prior_status = (
                "inactive"
                if selected.get("active") is False
                or lifecycle_state.get("status") == "inactive"
                else "active"
                if events
                else "new"
            )
            kind = "rejoin" if prior_status == "inactive" else "join"
            event = self._lifecycle_event(
                kind=kind,
                source_turn_id=source_turn_id,
                module=module,
                location_id=location_id,
                cause=_text(context.get("reason"), 240) or "unknown",
                game_day=game_day,
                invited_by=_text(context.get("invitedBy"), 100) or "unknown",
                terms=_text(context.get("terms"), 240),
                personal_objective=_text(context.get("personalObjective"), 240),
                red_lines=context.get("redLines", []),
                compensation=_text(context.get("compensation"), 160),
                expected_duration=_text(context.get("expectedDuration"), 160)
                or "unknown",
                prior_status=prior_status,
            )
            edge, edge_created = self._ensure_edge(
                document, npc_id, player_id, game_day
            )
            decayed = self._apply_decay(edge, game_day)
            changed = edge_created or decayed
            lifecycle_state["events"] = events + [event]
            changed = True
            if selected.get("active") is not True:
                selected["active"] = True
                changed = True
            selected["lastModule"] = _text(module, 160)
            selected["lastLocationId"] = _text(location_id, 120)
            lifecycle_state["status"] = "active"
            if kind == "rejoin" and document["working"].pop(npc_id, None) is not None:
                changed = True
            return changed, kind

        _mutated, result = self._mutate(update)
        return result or "join"

    def mark_departed(
        self,
        npc_id: str,
        *,
        module: str,
        location_id: str,
        cause: str,
        departure_kind: str,
        destination: str,
        return_hook: str,
        source_turn_id: str = "",
        unresolved_obligations: Iterable[str] = (),
        game_day: Optional[int] = None,
    ) -> bool:
        event = self._lifecycle_event(
            kind="depart",
            source_turn_id=source_turn_id,
            module=module,
            location_id=location_id,
            cause=cause,
            departure_kind=departure_kind,
            destination=destination,
            return_hook=return_hook,
            game_day=game_day,
            prior_status="active",
            unresolved_obligations=unresolved_obligations,
        )

        def update(document: Dict[str, Any]) -> Tuple[bool, None]:
            identity = document["identities"].get(npc_id)
            if not identity:
                return False, None
            lifecycle = document["lifecycle"].setdefault(
                npc_id, {"status": "active", "events": []}
            )
            if (
                lifecycle["events"]
                and lifecycle["events"][-1] == event
                and not identity["active"]
            ):
                return False, None
            identity["active"] = False
            identity["lastModule"] = _text(module, 160)
            identity["lastLocationId"] = _text(location_id, 120)
            lifecycle["status"] = "inactive"
            lifecycle["events"] = lifecycle["events"] + [event]
            document["working"].pop(npc_id, None)
            return True, None

        mutated, _ = self._mutate(update)
        return mutated

    def mark_module_transition(
        self,
        *,
        module: str,
        location_id: str,
        source_turn_id: str,
        game_day: Optional[int] = None,
    ) -> bool:
        """Move active lifecycle context without touching affinity or profiles."""
        event = self._lifecycle_event(
            kind="module",
            source_turn_id=source_turn_id,
            module=module,
            location_id=location_id,
            game_day=game_day,
            prior_status="active",
        )

        def update(document: Dict[str, Any]) -> Tuple[bool, None]:
            changed = False
            for npc_id, identity in document["identities"].items():
                if identity.get("kind") != "npc" or not identity.get("active"):
                    continue
                lifecycle = document["lifecycle"].setdefault(
                    npc_id, {"status": "active", "events": []}
                )
                if identity.get("lastModule") != _text(module, 160):
                    identity["lastModule"] = _text(module, 160)
                    changed = True
                if identity.get("lastLocationId") != _text(location_id, 120):
                    identity["lastLocationId"] = _text(location_id, 120)
                    changed = True
                if not lifecycle["events"] or lifecycle["events"][-1] != event:
                    lifecycle["events"] = lifecycle["events"] + [event]
                    changed = True
                lifecycle["status"] = "active"
                if document["working"].pop(npc_id, None) is not None:
                    changed = True
            return changed, None

        mutated, _ = self._mutate(update)
        return mutated

    def mark_rejoined(
        self,
        npc_id: str,
        player_id: str,
        *,
        game_day: Optional[int],
        module: str,
        location_id: str,
        source_turn_id: str,
        lifecycle_context: Optional[Mapping[str, Any]] = None,
    ) -> str:
        """Record a return through the canonical locked arrival mutation."""
        return self._mark_arrived(
            npc_id,
            player_id,
            game_day=game_day,
            module=module,
            location_id=location_id,
            source_turn_id=source_turn_id,
            lifecycle_context=lifecycle_context,
        )

    def get_pov_episodes(self, npc_id: str) -> list[Dict[str, Any]]:
        """The NPC's POV overlay rows, pinned first then by salience desc."""
        rows = self.snapshot().get("episodes", {}).get(npc_id, [])
        return [copy.deepcopy(r) for r in rows if isinstance(r, dict)]

    def upsert_pov_episodes(
        self, npc_id: str, pov_episodes: Iterable[Mapping[str, Any]]
    ) -> bool:
        """Idempotently write every per-NPC POV row in deterministic order."""
        sanitized = [
            row for row in (_sanitize_pov_episode(e) for e in pov_episodes) if row
        ]
        if not sanitized or not isinstance(npc_id, str) or not npc_id:
            return False

        def update(document: Dict[str, Any]) -> Tuple[bool, None]:
            episodes = document.setdefault("episodes", {})
            by_id: Dict[str, Dict[str, Any]] = {}
            for row in episodes.get(npc_id, []):
                if isinstance(row, dict) and isinstance(row.get("episodeId"), str):
                    by_id[row["episodeId"]] = row
            for row in sanitized:
                by_id[row["episodeId"]] = row
            rows = list(by_id.values())
            pinned = [r for r in rows if r.get("pinned")]
            non_pinned = sorted(
                (r for r in rows if not r.get("pinned")),
                key=lambda r: (r.get("salienceScore", 0.0), r["episodeId"]),
                reverse=True,
            )
            merged = sorted(
                pinned + non_pinned,
                key=lambda r: (not r.get("pinned"), -r.get("salienceScore", 0.0), r["episodeId"]),
            )
            if merged == episodes.get(npc_id, []):
                return False, None
            if merged:
                episodes[npc_id] = merged
            else:
                episodes.pop(npc_id, None)
            return True, None

        changed, _ = self._mutate(update)
        return changed

    def reinforce_baseline_from_pov(
        self, npc_id: str, player_id: str, *, game_day: Optional[int] = None
    ) -> bool:
        """Phase 5: set the NPC->player BASELINE to (preserved persona/legacy base) +
        (contribution from the NPC's PINNED POV episodes). The persona base is captured
        ONCE into `personaBaseline` (from the pre-episodic baseline, e.g. a legacy-
        migrated emotional state) and never overwritten, so this deepens the bond
        without clobbering imported relationship state (backward-compat). Pure/
        idempotent -- baseline is a function of personaBaseline + the pinned set, so
        re-runs are no-ops. Elevating the baseline makes decay settle the bond at a
        memory-justified level -- bonds deepen and STICK, finally moving the intimacy/
        fear axes that per-turn deltas leave dead (M27)."""
        if not (isinstance(npc_id, str) and npc_id and isinstance(player_id, str) and player_id):
            return False
        pov = self.snapshot().get("episodes", {}).get(npc_id, [])
        if not any(isinstance(e, dict) and e.get("pinned") for e in pov):
            return False
        pov_contribution = baseline_from_pinned(pov)

        def update(document: Dict[str, Any]) -> Tuple[bool, None]:
            if npc_id not in document["identities"] or player_id not in document["identities"]:
                return False, None
            edge, _created = self._ensure_edge(document, npc_id, player_id, game_day)
            # Preserve the persona/legacy base: capture the pre-episodic baseline ONCE
            # and ADD the POV contribution on top, rather than overwriting it. A
            # legacy-migrated baseline (from the character's imported emotional state)
            # is therefore never clobbered. Idempotent: baseline is a pure function of
            # personaBaseline + the current pinned set.
            persona = edge.get("personaBaseline")
            first_time = persona is None
            if first_time:
                persona = copy.deepcopy(edge.get("baseline") or _neutral())
            combined = clamp_state({
                axis: float(persona.get(axis, 0.0)) + float(pov_contribution.get(axis, 0.0))
                for axis in DIMENSIONS
            })
            if not first_time and edge.get("baseline") == combined:
                return False, None
            if first_time:
                edge["personaBaseline"] = persona
            edge["baseline"] = combined
            return True, None

        changed, _ = self._mutate(update)
        return changed
