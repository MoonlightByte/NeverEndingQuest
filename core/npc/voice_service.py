"""Best-effort T105 NPC voice service."""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import threading
import time
from collections import OrderedDict, deque
from concurrent.futures import FIRST_COMPLETED, Future, wait
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Deque, Dict, Iterable, Mapping, Optional, Tuple

import model_config
from core.ai import api_client
from core.npc.voice_contracts import (
    PROMPT_VERSION,
    RESPONSE_SCHEMA_VERSION,
    TASK_ID,
    ThoughtContractError,
    canonical_json,
    gemini_response_schema,
    validate_packet,
    validate_thought_response,
)
from utils.capture import multi_model_capture as capture_module
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite


register_callsite("T105", "core/npc/voice_service.py", 552)

TEMPERATURE = 0.6
MAX_ATTEMPTS = 2

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class VoiceTelemetryRecord:
    """One sanitized developer-only NPC voice diagnostic."""

    kind: str
    disposition: str
    batch_hash: str = ""
    npc_hash: str = ""
    request_kind: str = ""
    attempt: int = 0
    latency_ms: int = 0
    usage: Usage = Usage()
    cost_usd: Optional[float] = None
    provider: str = ""
    model: str = ""
    candidate_count: int = 0
    physical_request_count: int = 0
    merged_count: int = 0
    reason: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        value: Dict[str, Any] = {
            "kind": self.kind,
            "disposition": self.disposition,
            "batchHash": self.batch_hash,
            "npcHash": self.npc_hash,
            "requestKind": self.request_kind,
            "attempt": self.attempt,
            "latencyMs": self.latency_ms,
            "tokens": {
                "prompt": self.usage.prompt_tokens,
                "completion": self.usage.completion_tokens,
                "total": self.usage.total_tokens,
            },
            "provider": self.provider,
            "model": self.model,
            "candidateCount": self.candidate_count,
            "physicalRequestCount": self.physical_request_count,
            "mergedCount": self.merged_count,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }
        if self.cost_usd is not None:
            value["costUsd"] = self.cost_usd
            value["costDisposition"] = "known"
        else:
            value["costDisposition"] = "unknown"
        return {key: item for key, item in value.items() if item not in ("", None)}


class VoiceTelemetry:
    """Bounded, thread-safe telemetry with no packet, thought, name, or error text."""

    def __init__(
        self,
        max_records: int = 4096,
        path: Optional[os.PathLike[str] | str] = None,
    ) -> None:
        self._records: Deque[VoiceTelemetryRecord] = deque(maxlen=max_records)
        self._lock = threading.Lock()
        configured_path = path or os.environ.get("NPC_VOICE_TELEMETRY_PATH")
        self._path = Path(configured_path) if configured_path else None
        self._write_lock = threading.Lock()

    def record(self, record: VoiceTelemetryRecord) -> None:
        with self._lock:
            self._records.append(record)
        if self._path is None:
            return
        with self._write_lock:
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                with self._path.open("a", encoding="ascii") as handle:
                    handle.write(
                        json.dumps(
                            record.to_dict(),
                            ensure_ascii=True,
                            separators=(",", ":"),
                        )
                        + "\n"
                    )
            except Exception:
                pass

    def snapshot(self) -> Tuple[VoiceTelemetryRecord, ...]:
        with self._lock:
            return tuple(self._records)

    def record_disposition(
        self,
        kind: str,
        disposition: str,
        *,
        batch_id: str = "",
        npc_id: str = "",
        reason: str = "",
    ) -> None:
        try:
            self.record(
                VoiceTelemetryRecord(
                    kind=_safe_identifier(kind),
                    disposition=_safe_identifier(disposition),
                    batch_hash=_identifier_hash(batch_id) if batch_id else "",
                    npc_hash=_identifier_hash(npc_id) if npc_id else "",
                    reason=str(reason),
                )
            )
        except Exception:
            pass


def _safe_identifier(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return "".join(
        character
        for character in value
        if character.isalnum() or character in "._-"
    )[:120]


def _identifier_hash(value: Any) -> str:
    # Telemetry-only log sanitization (batch_hash/npc_hash fields), NEVER
    # identity: nothing compares, gates, or dedups on this value.
    return hashlib.sha256(str(value).encode("utf-8", errors="replace")).hexdigest()[:16]


def _configured_cost(model: str, usage: Usage, provider: str) -> Optional[float]:
    if provider == "lmstudio":
        return 0.0
    try:
        return capture_module._calculate_cost(
            model,
            {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
            },
            capture_module._load_config(),
        )
    except Exception:
        return None


class _RequestCounter:
    """Thread-safe telemetry count for physical provider calls."""

    def __init__(self) -> None:
        self._count = 0
        self._lock = threading.Lock()

    def claim(self) -> bool:
        with self._lock:
            self._count += 1
            return True

    @property
    def count(self) -> int:
        with self._lock:
            return self._count


@dataclass(frozen=True)
class NpcVoiceResult:
    npc_id: str
    npc_name: str
    # Carries the VALUE cache key (canonical-JSON string), not a digest; the
    # field name is kept for sidecar compatibility.
    content_hash: str
    thought: str
    affinity_event: Optional[Dict[str, Any]]
    model: str
    usage: Usage
    latency_seconds: float
    say: Optional[str] = None
    do: Optional[str] = None
    want: Optional[str] = None
    cached: bool = False
    stale: bool = False
    source_turn_id: str = ""
    counterparty_id: str = ""
    relationship_evidence_summary: str = ""
    relationship_evidence_id: str = ""
    packet_hash: str = ""
    module: str = ""
    location_id: str = ""
    current_goal_reference: str = ""
    open_question: str = ""
    mood_tags: Tuple[str, ...] = ()
    expires_after_turn: Optional[int] = None
    scene_id: str = ""
    generation_token: str = ""
    completed_at: float = field(default=0.0, repr=False, compare=False)
    cacheable: bool = field(default=True, repr=False, compare=False)


@dataclass(frozen=True)
class NpcVoiceBatch:
    batch_id: str
    results: Tuple[NpcVoiceResult, ...]
    generation_token: str = ""
    candidate_count: int = 0
    physical_request_count: int = 0
    telemetry: Optional[VoiceTelemetry] = field(default=None, repr=False, compare=False)


class NpcVoiceUnavailable(RuntimeError):
    """All bounded T105 attempts failed."""


class VoiceCache:
    """Thread-safe validated-result LRU."""

    def __init__(self, max_entries: int = 256) -> None:
        self.max_entries = max_entries
        self._values: OrderedDict[str, NpcVoiceResult] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[NpcVoiceResult]:
        with self._lock:
            value = self._values.get(key)
            if value is None:
                return None
            self._values.move_to_end(key)
            return value

    def put(self, key: str, value: NpcVoiceResult) -> None:
        with self._lock:
            self._values[key] = value
            self._values.move_to_end(key)
            while len(self._values) > self.max_entries:
                self._values.popitem(last=False)

    def __len__(self) -> int:
        with self._lock:
            return len(self._values)


def _usage_from_response(response: Any) -> Usage:
    usage = getattr(response, "usage", None)
    return Usage(
        prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
        completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
        total_tokens=int(getattr(usage, "total_tokens", 0) or 0),
    )


def _prompt_text() -> str:
    prompt_path = (
        Path(__file__).resolve().parents[2]
        / "prompts"
        / "npc"
        / "npc_voice_t105.txt"
    )
    return prompt_path.read_text(encoding="ascii").strip()


def _classification_prompt_text() -> str:
    prompt_path = (
        Path(__file__).resolve().parents[2]
        / "prompts"
        / "npc"
        / "npc_affinity_t105.txt"
    )
    return prompt_path.read_text(encoding="ascii").strip()


def build_messages(
    packet: Mapping[str, Any], retry_reason: Optional[str] = None
) -> list[Dict[str, str]]:
    messages = [{"role": "system", "content": _prompt_text()}]
    if retry_reason:
        messages.append(
            {
                "role": "system",
                "content": (
                    "The previous private response failed the strict contract "
                    "(%s). Return a corrected exact JSON object only." % retry_reason
                ),
            }
        )
    messages.append(
        {
            "role": "user",
            "content": json.dumps(
                packet,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ),
        }
    )
    return messages


def build_classification_messages(
    relationship_evidence: Mapping[str, Any],
    retry_reason: Optional[str] = None,
) -> list[Dict[str, str]]:
    """Build an isolated classifier request containing only one accepted pair."""
    messages = [{"role": "system", "content": _classification_prompt_text()}]
    if retry_reason:
        messages.append(
            {
                "role": "system",
                "content": (
                    "The previous private response failed the strict contract "
                    "(%s). Return a corrected exact JSON object only." % retry_reason
                ),
            }
        )
    messages.append(
        {
            "role": "user",
            "content": json.dumps(
                {"relationshipEvidence": dict(relationship_evidence)},
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ),
        }
    )
    return messages


def _config_for_provider(provider: str) -> Dict[str, Any]:
    # OpenAI/legacy use plain JSON mode (json_object) + client-side
    # validate_thought_response + one bounded retry. We deliberately do NOT use
    # OpenAI strict json_schema here: the enriched contract makes say/do/want
    # OPTIONAL (strict mode requires every property), and the same callsite also
    # serves the affinity classifier which returns only thought + affinityEvent.
    # Gemini needs response_schema or it silently drops the enriched fields
    # (T014-class bug). Never attach response_schema on the OpenAI path (400).
    if provider == "openai":
        selected = copy.deepcopy(model_config.NPC_VOICE_T105_OPENAI_LUNA_NONE)
        selected["response_format"] = {"type": "json_object"}
    elif provider == "gemini":
        selected = copy.deepcopy(model_config.NPC_VOICE_T105_GEMINI_FLASHLITE_LOW)
        selected["response_schema"] = gemini_response_schema()
    elif provider == "lmstudio":
        selected = copy.deepcopy(model_config.NPC_VOICE_T105_LMSTUDIO)
        selected["response_format"] = None
    elif provider == "legacy":
        selected = copy.deepcopy(model_config.NPC_VOICE_T105_LEGACY)
        selected["response_format"] = {"type": "json_object"}
    else:
        raise ValueError("unsupported T105 provider: %s" % provider)
    return selected


class NpcVoiceService:
    """Bounded process-long fanout service shared by both packet lenses."""

    def __init__(
        self,
        completion_fn: Callable[..., Any] = api_client.create_completion,
        *,
        capture_fn: Callable[..., Any] = capture_and_fanout,
        cache: Optional[VoiceCache] = None,
        telemetry: Optional[VoiceTelemetry] = None,
        cost_fn: Callable[[str, Usage, str], Optional[float]] = _configured_cost,
    ) -> None:
        self.completion_fn = completion_fn
        self.capture_fn = capture_fn
        self.cache = cache if cache is not None else VoiceCache()
        self.telemetry = telemetry if telemetry is not None else VoiceTelemetry()
        self.cost_fn = cost_fn

    def _record(
        self,
        *,
        kind: str,
        disposition: str,
        batch_id: str = "",
        npc_id: str = "",
        request_kind: str = "",
        attempt: int = 0,
        latency_seconds: float = 0.0,
        usage: Usage = Usage(),
        cost_usd: Optional[float] = None,
        provider: str = "",
        model: str = "",
        candidate_count: int = 0,
        physical_request_count: int = 0,
        merged_count: int = 0,
        reason: str = "",
    ) -> None:
        try:
            self.telemetry.record(
                VoiceTelemetryRecord(
                    kind=kind,
                    disposition=disposition,
                    batch_hash=_identifier_hash(batch_id) if batch_id else "",
                    npc_hash=_identifier_hash(npc_id) if npc_id else "",
                    request_kind=_safe_identifier(request_kind),
                    attempt=max(0, int(attempt)),
                    latency_ms=max(0, int(round(latency_seconds * 1000))),
                    usage=usage,
                    cost_usd=cost_usd,
                    provider=_safe_identifier(provider),
                    model=_safe_identifier(model),
                    candidate_count=max(0, int(candidate_count)),
                    physical_request_count=max(0, int(physical_request_count)),
                    merged_count=max(0, int(merged_count)),
                    reason=str(reason),
                )
            )
        except Exception:
            pass

    def _cost(self, model: str, usage: Usage, provider: str) -> Optional[float]:
        try:
            return self.cost_fn(model, usage, provider)
        except Exception:
            return None

    def _cache_key(self, packet: Mapping[str, Any], provider: str) -> str:
        # Value key (in-memory LRU): the lossless canonical-JSON STRING of the
        # same material the retired digest covered -- equality of this string
        # is equality of the underlying values, never a hash collision.
        return canonical_json(
            {
                "packet": packet,
                "promptVersion": PROMPT_VERSION,
                "responseSchemaVersion": RESPONSE_SCHEMA_VERSION,
                "profileStoreRevision": canonical_json(
                    {
                        "profile": packet.get("npc", {}).get("profile"),
                        "relationship": packet.get("relationship"),
                        "working": packet.get("working"),
                    }
                ),
                "modelConfig": _config_for_provider(provider),
                "provider": provider,
            }
        )

    def think(self, packet: Mapping[str, Any]) -> NpcVoiceResult:
        packet_copy = validate_packet(packet)
        return self._think_with_provider(
            packet_copy,
            model_config.get_provider(),
            counter=_RequestCounter(),
            cache_result=True,
        )

    def _request_validated(
        self,
        *,
        request_packet: Mapping[str, Any],
        validation_packet: Mapping[str, Any],
        provider: str,
        classification: bool,
        counter: _RequestCounter,
        batch_id: str,
        npc_id: str,
        advisory_scope=None,
    ) -> tuple[Dict[str, Any], Any, str]:
        last_error: Optional[BaseException] = None
        retry_reason: Optional[str] = None
        for attempt in range(MAX_ATTEMPTS):
            config = _config_for_provider(provider)
            model = config.pop("model")
            request_kind = "classification" if classification else "thought"
            if not counter.claim():
                self._record(
                    kind="request_omission",
                    disposition="request_cap",
                    batch_id=batch_id,
                    npc_id=npc_id,
                    request_kind=request_kind,
                    attempt=attempt + 1,
                    provider=provider,
                    model=model,
                )
                break
            if classification:
                messages = build_classification_messages(
                    request_packet["beat"]["relationshipEvidence"],
                    retry_reason,
                )
            else:
                messages = build_messages(request_packet, retry_reason)
            started = time.perf_counter()
            response = None
            try:
                response = self.capture_fn(
                    TASK_ID,
                    self.completion_fn,
                    _request_provider=provider,
                    messages=messages,
                    model=model,
                    temperature=TEMPERATURE,
                    # No max_tokens/max_completion_tokens on any call: the gpt-5.x
                    # default (luna) rejects max_tokens with a 400. Output length is
                    # bounded by the client-side contract validation instead.
                    retry_attempt=attempt,
                    _live_selected="advisory" if advisory_scope is not None else False,
                    _detached_scope=advisory_scope,
                    **config,
                )
                raw = response.choices[0].message.content
                validated = validate_thought_response(raw, validation_packet)
                usage = _usage_from_response(response)
                effective_model = getattr(response, "model", None) or model
                disposition = "valid"
                self._record(
                    kind="physical_call",
                    disposition=disposition,
                    batch_id=batch_id,
                    npc_id=npc_id,
                    request_kind=request_kind,
                    attempt=attempt + 1,
                    latency_seconds=time.perf_counter() - started,
                    usage=usage,
                    cost_usd=self._cost(effective_model, usage, provider),
                    provider=provider,
                    model=effective_model,
                )
                return validated, response, model
            except Exception as exc:
                from utils.capture.live_provider_call import LiveProviderSuperseded

                if isinstance(exc, LiveProviderSuperseded):
                    raise
                last_error = exc
                retry_reason = (
                    "invalid_contract"
                    if isinstance(exc, ThoughtContractError)
                    else "provider_failure"
                )
                usage = _usage_from_response(response)
                effective_model = getattr(response, "model", None) or model
                self._record(
                    kind="physical_call",
                    disposition=retry_reason,
                    batch_id=batch_id,
                    npc_id=npc_id,
                    request_kind=request_kind,
                    attempt=attempt + 1,
                    latency_seconds=time.perf_counter() - started,
                    usage=usage,
                    cost_usd=self._cost(effective_model, usage, provider),
                    provider=provider,
                    model=effective_model,
                )
        raise NpcVoiceUnavailable("T105 attempts exhausted") from last_error

    def _think_with_provider(
        self,
        packet: Mapping[str, Any],
        provider: str,
        *,
        counter: _RequestCounter,
        cache_result: bool,
        advisory_scope=None,
    ) -> NpcVoiceResult:
        packet_copy = validate_packet(packet)
        batch_id = packet_copy["beat"]["id"]
        npc_id = packet_copy["npc"]["id"]
        key = self._cache_key(packet_copy, provider)
        cached = self.cache.get(key)
        if cached is not None:
            self._record(
                kind="cache",
                disposition="hit",
                batch_id=batch_id,
                npc_id=npc_id,
                provider=provider,
                model=cached.model,
            )
            return replace(
                cached,
                usage=Usage(),
                latency_seconds=0.0,
                cached=True,
                completed_at=time.perf_counter(),
            )

        started = time.perf_counter()
        thought_packet = copy.deepcopy(packet_copy)
        thought_packet["beat"]["relationshipEvidence"] = None
        validated, thought_response, thought_model = self._request_validated(
            request_packet=thought_packet,
            validation_packet=thought_packet,
            provider=provider,
            classification=False,
            counter=counter,
            batch_id=batch_id,
            npc_id=npc_id,
            advisory_scope=advisory_scope,
        )
        affinity_event = None
        classification_response = None
        classification_complete = (
            packet_copy["beat"]["relationshipEvidence"] is None
        )
        if packet_copy["beat"]["relationshipEvidence"] is not None:
            try:
                classified, classification_response, _classification_model = (
                    self._request_validated(
                        request_packet=packet_copy,
                        validation_packet=packet_copy,
                        provider=provider,
                        classification=True,
                        counter=counter,
                        batch_id=batch_id,
                        npc_id=npc_id,
                        advisory_scope=advisory_scope,
                    )
                )
                affinity_event = classified["affinityEvent"]
                classification_complete = True
            except NpcVoiceUnavailable:
                _LOGGER.debug("T105 isolated classification skipped")

        thought_usage = _usage_from_response(thought_response)
        classification_usage = _usage_from_response(classification_response)
        result = NpcVoiceResult(
            npc_id=packet_copy["npc"]["id"],
            npc_name=packet_copy["npc"]["name"],
            content_hash=key,
            thought=validated["thought"],
            affinity_event=affinity_event,
            say=validated.get("say"),
            do=validated.get("do"),
            want=validated.get("want"),
            model=getattr(thought_response, "model", None) or thought_model,
            usage=Usage(
                prompt_tokens=(
                    thought_usage.prompt_tokens
                    + classification_usage.prompt_tokens
                ),
                completion_tokens=(
                    thought_usage.completion_tokens
                    + classification_usage.completion_tokens
                ),
                total_tokens=(
                    thought_usage.total_tokens
                    + classification_usage.total_tokens
                ),
            ),
            latency_seconds=round(time.perf_counter() - started, 4),
            source_turn_id=packet_copy["beat"]["id"],
            counterparty_id=packet_copy["relationship"]["counterpartyId"],
            relationship_evidence_summary=(
                packet_copy["beat"]["relationshipEvidence"]["summary"]
                if packet_copy["beat"]["relationshipEvidence"] is not None
                else ""
            ),
            # packetHash persistence is retired (digest identity ban); the
            # store writes "" regardless and tolerates legacy hex on load.
            packet_hash="",
            module=packet_copy["scene"]["module"],
            location_id=packet_copy["scene"]["locationId"],
            current_goal_reference=packet_copy["working"]["currentGoal"],
            open_question=packet_copy["working"]["openQuestion"],
            mood_tags=tuple(packet_copy["working"]["moodTags"]),
            expires_after_turn=packet_copy["working"]["expiresAfterTurn"],
            scene_id=(
                "%s|%s"
                % (
                    packet_copy["scene"]["module"],
                    packet_copy["scene"]["locationId"],
                )
            ),
            completed_at=time.perf_counter(),
            cacheable=classification_complete,
        )
        if classification_complete and cache_result:
            self.cache.put(key, result)
        return result

    def dispatch_batch(
        self,
        packets: Iterable[Mapping[str, Any]],
        *,
        parent_scope=None,
        completion_required: bool = False,
    ) -> "VoiceBatchHandle":
        """Dispatch every supplied actor in an independently fenced monitor."""
        from utils.capture.live_provider_call import open_advisory_scopes

        batch_started = time.perf_counter()
        candidates = list(packets)
        provider = ""
        batch_id = ""
        validated_packets = []
        immediate: list = []
        futures: Dict[str, Future] = {}
        scopes: Dict[str, Any] = {}
        counters: Dict[str, _RequestCounter] = {}
        try:
            provider = model_config.get_provider()
            for packet in candidates:
                try:
                    packet_copy = validate_packet(packet)
                    candidate_batch_id = packet_copy["beat"]["id"]
                    if batch_id and candidate_batch_id != batch_id:
                        raise ValueError("mixed batch IDs")
                    batch_id = candidate_batch_id
                    validated_packets.append(packet_copy)
                    self._record(
                        kind="candidate",
                        disposition="selected",
                        batch_id=batch_id,
                        npc_id=packet_copy["npc"]["id"],
                    )
                except Exception as exc:
                    npc_id = ""
                    if isinstance(packet, Mapping):
                        npc = packet.get("npc")
                        if isinstance(npc, Mapping):
                            npc_id = str(npc.get("id") or "")
                    _LOGGER.warning(
                        "T105 packet invalid for %s: %s",
                        npc_id or "unknown NPC",
                        exc,
                    )
                    self._record(
                        kind="candidate",
                        disposition="packet_invalid",
                        batch_id=batch_id,
                        npc_id=npc_id,
                        reason=str(exc),
                    )

            def terminal_completion_handle(npc_ids, terminal_parent):
                return VoiceBatchHandle(
                    service=self,
                    batch_id=batch_id,
                    npc_ids=tuple(npc_ids),
                    futures={},
                    immediate=(),
                    candidate_count=len(validated_packets),
                    counters={},
                    scopes={},
                    parent_scope=terminal_parent,
                    batch_started=batch_started,
                    provider=provider,
                    completion_required=True,
                )

            if completion_required:
                from utils.capture.live_provider_call import get_live_turn_scope

                active_scope = get_live_turn_scope()
                if parent_scope is None:
                    # A3-C6: missing authority is a loud one-beat terminal, not
                    # an engine-exiting supersession and never an unfenced call.
                    for packet_copy in validated_packets:
                        npc_id = packet_copy["npc"]["id"]
                        self._record(
                            kind="candidate",
                            disposition="missing_authority",
                            batch_id=batch_id,
                            npc_id=npc_id,
                        )
                        _LOGGER.warning(
                            "T105 voice call for %s skipped without live authority",
                            npc_id,
                        )
                    self._record(
                        kind="batch",
                        disposition="missing_authority",
                        batch_id=batch_id,
                        latency_seconds=time.perf_counter() - batch_started,
                        provider=provider,
                        candidate_count=len(validated_packets),
                        physical_request_count=0,
                    )
                    return terminal_completion_handle((), None)
                if parent_scope is not active_scope or parent_scope.is_superseded():
                    for packet_copy in validated_packets:
                        self._record(
                            kind="candidate",
                            disposition="stale_rejected",
                            batch_id=batch_id,
                            npc_id=packet_copy["npc"]["id"],
                        )
                    return terminal_completion_handle(
                        (
                            packet_copy["npc"]["id"]
                            for packet_copy in validated_packets
                        ),
                        parent_scope,
                    )

            pending_packets = []
            for packet_copy in validated_packets:
                npc_id = packet_copy["npc"]["id"]
                key = self._cache_key(packet_copy, provider)
                cached = self.cache.get(key)
                if cached is not None:
                    immediate.append(
                        replace(
                            cached,
                            usage=Usage(),
                            latency_seconds=0.0,
                            cached=True,
                            completed_at=time.perf_counter(),
                        )
                    )
                    self._record(
                        kind="cache",
                        disposition="hit",
                        batch_id=batch_id,
                        npc_id=npc_id,
                        provider=provider,
                        model=cached.model,
                    )
                    continue
                pending_packets.append(packet_copy)

            reserved_scopes = open_advisory_scopes(
                parent_scope,
                batch_id,
                len(pending_packets),
                completion_required=completion_required,
            )
            if len(reserved_scopes) != len(pending_packets):
                rejected_disposition = (
                    "stale_rejected" if completion_required else "missing_authority"
                )
                for packet_copy in pending_packets:
                    npc_id = packet_copy["npc"]["id"]
                    self._record(
                        kind="candidate",
                        disposition=rejected_disposition,
                        batch_id=batch_id,
                        npc_id=npc_id,
                    )
                    _LOGGER.warning("T105 voice call for %s skipped without live authority", npc_id)
                pending_packets = []

            for packet_copy, advisory_scope in zip(pending_packets, reserved_scopes):
                npc_id = packet_copy["npc"]["id"]
                future = Future()
                counter = _RequestCounter()
                scopes[npc_id] = advisory_scope
                counters[npc_id] = counter

                def run_worker(
                    selected_packet: Mapping[str, Any] = packet_copy,
                    worker_npc_id: str = npc_id,
                    worker_scope=advisory_scope,
                    worker_future=future,
                    worker_counter=counter,
                ):
                    try:
                        if worker_scope.is_superseded():
                            raise RuntimeError("advisory scope superseded before start")
                        result = self._think_with_provider(
                            selected_packet,
                            provider,
                            counter=worker_counter,
                            cache_result=True,
                            advisory_scope=worker_scope,
                        )
                        worker_future.set_result(result)
                    except Exception as exc:
                        worker_future.set_exception(exc)
                        _LOGGER.warning(
                            "T105 voice call for %s FAILED: %s",
                            worker_npc_id,
                            type(exc).__name__,
                        )
                        self._record(
                            kind="candidate",
                            disposition="degraded_this_beat",
                            batch_id=batch_id,
                            npc_id=worker_npc_id,
                        )
                    finally:
                        worker_scope.finish()

                try:
                    futures[npc_id] = future
                    threading.Thread(
                        target=run_worker,
                        name="npc-voice-%s" % _safe_identifier(npc_id),
                        daemon=True,
                    ).start()
                except Exception as exc:
                    if not future.done():
                        future.set_exception(exc)
                    advisory_scope.seal()
                    advisory_scope.finish()
                    _LOGGER.warning(
                        "T105 voice worker submission failed for %s: %s",
                        npc_id,
                        type(exc).__name__,
                    )
                    self._record(
                        kind="candidate",
                        disposition="submission_failure",
                        batch_id=batch_id,
                        npc_id=npc_id,
                    )
        except Exception:
            self._record(
                kind="batch",
                disposition="batch_failure",
                batch_id=batch_id,
                latency_seconds=time.perf_counter() - batch_started,
                provider=provider,
                candidate_count=len(validated_packets),
                physical_request_count=sum(item.count for item in counters.values()),
            )
        return VoiceBatchHandle(
            service=self,
            batch_id=batch_id,
            npc_ids=tuple(
                packet_copy["npc"]["id"] for packet_copy in validated_packets
            ),
            futures=futures,
            immediate=tuple(immediate),
            candidate_count=len(validated_packets),
            counters=counters,
            scopes=scopes,
            parent_scope=parent_scope,
            batch_started=batch_started,
            provider=provider,
            completion_required=completion_required,
        )

class VoiceBatchHandle:
    """Request-local view of one parallel voice batch.

    collect() remains the non-blocking OOC/legacy poll (run at validator-inject time,
    after the main DM call has overlapped the voice latency). Monotonic and
    idempotent: each call folds newly completed results in and returns the
    union until the consumer seals the exact beat. Pending values are cancelled
    and reaped by their task-owned monitor rather than delivered on another beat.

    collect_to_completion() is typed-combat-only. It completion-collects the
    already-parallel work for the current round; transport liveness remains owned
    by each provider child and destructive controls supersede the parent authority.
    """

    def __init__(
        self,
        *,
        service: NpcVoiceService,
        batch_id: str,
        npc_ids: Tuple[str, ...],
        futures: Mapping[str, Future],
        immediate: Tuple[NpcVoiceResult, ...],
        candidate_count: int,
        counters: Mapping[str, _RequestCounter],
        scopes: Mapping[str, Any],
        parent_scope,
        batch_started: float,
        provider: str,
        completion_required: bool,
    ) -> None:
        self._service = service
        self.batch_id = batch_id
        self._npc_ids = npc_ids
        self._collected = list(immediate)
        self._done_ids = {result.npc_id for result in immediate}
        self._terminal_ids = set(self._done_ids)
        self.candidate_count = candidate_count
        self._futures = dict(futures)
        self._counters = dict(counters)
        self._scopes = dict(scopes)
        self._parent_scope = parent_scope
        self._batch_started = batch_started
        self._provider = provider
        self._completion_required = bool(completion_required)
        self._finalized = False

    def _authority_current(self) -> bool:
        try:
            from utils.capture.live_provider_call import get_live_turn_scope
            return (
                self._parent_scope is not None
                and get_live_turn_scope() is self._parent_scope
                and not self._parent_scope.is_superseded()
                and all(scope.beat_id == self.batch_id for scope in self._scopes.values())
            )
        except Exception:
            return False

    def _absorb(self, npc_id: str) -> bool:
        future = self._futures.get(npc_id)
        if future is None:
            self._terminal_ids.add(npc_id)
            return True
        if not future.done():
            self._service._record(
                kind="candidate",
                disposition="pending_at_boundary",
                batch_id=self.batch_id,
                npc_id=npc_id,
            )
            return False
        try:
            result = future.result()
        except Exception as exc:
            from utils.capture.live_provider_call import LiveProviderSuperseded

            if isinstance(exc, LiveProviderSuperseded):
                raise
            self._terminal_ids.add(npc_id)
            return True
        if not self._authority_current():
            from utils.capture.live_provider_call import LiveProviderSuperseded

            raise LiveProviderSuperseded("combat voice batch authority superseded")
        self._collected.append(result)
        self._done_ids.add(npc_id)
        self._terminal_ids.add(npc_id)
        self._service._record(
            kind="merge",
            disposition="merged",
            batch_id=self.batch_id,
            npc_id=npc_id,
        )
        return True

    def _finalize(self) -> NpcVoiceBatch:
        for result in self._collected:
            if result.affinity_event is not None:
                self._service._record(
                    kind="event",
                    disposition="staged",
                    batch_id=self.batch_id,
                    npc_id=result.npc_id,
                )
        if not self._finalized:
            self._finalized = True
            self._service._record(
                kind="batch",
                disposition="complete",
                batch_id=self.batch_id,
                latency_seconds=time.perf_counter() - self._batch_started,
                provider=self._provider,
                candidate_count=self.candidate_count,
                physical_request_count=sum(item.count for item in self._counters.values()),
                merged_count=len(self._collected),
            )
        return NpcVoiceBatch(
            batch_id=self.batch_id,
            results=tuple(self._collected),
            candidate_count=self.candidate_count,
            physical_request_count=sum(item.count for item in self._counters.values()),
            telemetry=self._service.telemetry,
        )

    def collect(self) -> NpcVoiceBatch:
        for npc_id in self._npc_ids:
            if npc_id not in self._done_ids:
                self._absorb(npc_id)
        return self._finalize()

    def collect_to_completion(
        self,
        status_emit: Optional[Callable[[str], None]] = None,
    ) -> NpcVoiceBatch:
        """Collect every typed-combat call to a terminal result for this round."""
        if not self._completion_required:
            return self.collect()
        selected_count = self.candidate_count
        started = time.monotonic()
        last_elapsed = None
        while len(self._terminal_ids) < len(self._npc_ids):
            if not self._authority_current():
                from utils.capture.live_provider_call import LiveProviderSuperseded

                raise LiveProviderSuperseded("combat voice batch authority superseded")
            for npc_id in self._npc_ids:
                if npc_id not in self._terminal_ids:
                    self._absorb(npc_id)
            if len(self._terminal_ids) >= len(self._npc_ids):
                break
            elapsed = max(0, int(time.monotonic() - started))
            if status_emit is not None and elapsed != last_elapsed:
                try:
                    status_emit(
                        "Listening to companion voices (%d/%d complete, %d seconds elapsed)..."
                        % (len(self._terminal_ids), selected_count, elapsed)
                    )
                except Exception:
                    pass
                last_elapsed = elapsed
            pending = [
                future
                for npc_id, future in self._futures.items()
                if npc_id not in self._terminal_ids
            ]
            if pending:
                wait(pending, timeout=1.0, return_when=FIRST_COMPLETED)
        if status_emit is not None:
            try:
                status_emit(
                    "Companion voices are ready; resolving this combat round..."
                )
            except Exception:
                pass
        return self._finalize()

    def seal_and_cancel_pending(self) -> None:
        for npc_id, scope in self._scopes.items():
            if npc_id not in self._terminal_ids:
                scope.seal()
