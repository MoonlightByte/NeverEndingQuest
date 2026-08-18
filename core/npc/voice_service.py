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
from concurrent.futures import ThreadPoolExecutor, wait
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
    canonical_hash,
    validate_packet,
    validate_thought_response,
)
from utils.capture import multi_model_capture as capture_module
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite


register_callsite("T105", "core/npc/voice_service.py", 552)

TEMPERATURE = 0.6
MAX_OUTPUT_TOKENS = 180
MAX_ATTEMPTS = 2
DEFAULT_DEADLINE_SECONDS = 4.0
MAX_LOGICAL_NPCS = 4
MAX_PHYSICAL_REQUESTS = 8

_LOGGER = logging.getLogger(__name__)
_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="npc-voice")
_WORKER_SLOTS = threading.BoundedSemaphore(4)


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
    ) -> None:
        try:
            self.record(
                VoiceTelemetryRecord(
                    kind=_safe_identifier(kind),
                    disposition=_safe_identifier(disposition),
                    batch_hash=_identifier_hash(batch_id) if batch_id else "",
                    npc_hash=_identifier_hash(npc_id) if npc_id else "",
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


class _RequestBudget:
    def __init__(self, deadline_seconds: float) -> None:
        self.deadline = time.perf_counter() + max(0.0, deadline_seconds)
        self._count = 0
        self._lock = threading.Lock()

    def claim(self) -> bool:
        with self._lock:
            if self._count >= MAX_PHYSICAL_REQUESTS:
                return False
            if time.perf_counter() >= self.deadline:
                return False
            self._count += 1
            return True

    @property
    def count(self) -> int:
        with self._lock:
            return self._count

    def remaining(self) -> float:
        return max(0.0, self.deadline - time.perf_counter())


class _GenerationRegistry:
    def __init__(self) -> None:
        self._next = 0
        self._active = set()
        self._lock = threading.Lock()

    def issue(self) -> str:
        with self._lock:
            self._next += 1
            token = "voice-generation-%d" % self._next
            self._active.add(token)
            return token

    def expire(self, token: str) -> None:
        with self._lock:
            self._active.discard(token)

    def active(self, token: str) -> bool:
        with self._lock:
            return token in self._active


_GENERATIONS = _GenerationRegistry()


@dataclass(frozen=True)
class NpcVoiceResult:
    npc_id: str
    npc_name: str
    content_hash: str
    thought: str
    affinity_event: Optional[Dict[str, Any]]
    model: str
    usage: Usage
    latency_seconds: float
    cached: bool = False
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
    if provider == "openai":
        selected = model_config.NPC_VOICE_T105_OPENAI_LUNA_NONE
    elif provider == "gemini":
        selected = model_config.NPC_VOICE_T105_GEMINI_FLASHLITE_LOW
    elif provider == "lmstudio":
        selected = model_config.NPC_VOICE_T105_LMSTUDIO
    elif provider == "legacy":
        selected = model_config.NPC_VOICE_T105_LEGACY
    else:
        raise ValueError("unsupported T105 provider: %s" % provider)
    return copy.deepcopy(selected)


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
        return canonical_hash(
            {
                "packet": packet,
                "promptVersion": PROMPT_VERSION,
                "responseSchemaVersion": RESPONSE_SCHEMA_VERSION,
                "profileStoreRevision": canonical_hash(
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
        token = _GENERATIONS.issue()
        budget = _RequestBudget(DEFAULT_DEADLINE_SECONDS)
        try:
            return self._think_with_provider(
                packet_copy,
                model_config.get_provider(),
                budget=budget,
                generation_token=token,
                cache_result=True,
            )
        finally:
            _GENERATIONS.expire(token)

    def _request_validated(
        self,
        *,
        request_packet: Mapping[str, Any],
        validation_packet: Mapping[str, Any],
        provider: str,
        classification: bool,
        budget: _RequestBudget,
        generation_token: str,
        batch_id: str,
        npc_id: str,
    ) -> tuple[Dict[str, Any], Any, str]:
        last_error: Optional[BaseException] = None
        retry_reason: Optional[str] = None
        for attempt in range(MAX_ATTEMPTS):
            config = _config_for_provider(provider)
            model = config.pop("model")
            request_kind = "classification" if classification else "thought"
            if not budget.claim():
                self._record(
                    kind="request_omission",
                    disposition="budget_or_deadline",
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
                    max_tokens=MAX_OUTPUT_TOKENS,
                    retry_attempt=attempt,
                    **config,
                )
                raw = response.choices[0].message.content
                validated = validate_thought_response(raw, validation_packet)
                usage = _usage_from_response(response)
                effective_model = getattr(response, "model", None) or model
                disposition = (
                    "valid"
                    if _GENERATIONS.active(generation_token)
                    else "late_result_rejected"
                )
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
            except ThoughtContractError as exc:
                last_error = exc
                retry_reason = "invalid_contract"
                usage = _usage_from_response(response)
                effective_model = getattr(response, "model", None) or model
                self._record(
                    kind="physical_call",
                    disposition="invalid_contract",
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
            except Exception as exc:
                last_error = exc
                retry_reason = "provider_failure"
                self._record(
                    kind="physical_call",
                    disposition="provider_failure",
                    batch_id=batch_id,
                    npc_id=npc_id,
                    request_kind=request_kind,
                    attempt=attempt + 1,
                    latency_seconds=time.perf_counter() - started,
                    provider=provider,
                    model=model,
                )
        raise NpcVoiceUnavailable("T105 attempts exhausted") from last_error

    def _think_with_provider(
        self,
        packet: Mapping[str, Any],
        provider: str,
        *,
        budget: _RequestBudget,
        generation_token: str,
        cache_result: bool,
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
                generation_token=generation_token,
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
            budget=budget,
            generation_token=generation_token,
            batch_id=batch_id,
            npc_id=npc_id,
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
                        budget=budget,
                        generation_token=generation_token,
                        batch_id=batch_id,
                        npc_id=npc_id,
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
            packet_hash=canonical_hash(packet_copy),
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
            generation_token=generation_token,
            completed_at=time.perf_counter(),
            cacheable=classification_complete,
        )
        if (
            classification_complete
            and cache_result
            and _GENERATIONS.active(generation_token)
        ):
            self.cache.put(key, result)
        return result

    def think_best_effort(
        self,
        packet: Mapping[str, Any],
        *,
        deadline_seconds: float = DEFAULT_DEADLINE_SECONDS,
    ) -> NpcVoiceBatch:
        return self.think_batch_best_effort(
            (packet,), deadline_seconds=deadline_seconds
        )

    def think_batch_best_effort(
        self,
        packets: Iterable[Mapping[str, Any]],
        *,
        deadline_seconds: float = DEFAULT_DEADLINE_SECONDS,
    ) -> NpcVoiceBatch:
        """Run up to four logical NPC calls without waiting past the merge cap."""
        batch_started = time.perf_counter()
        candidates = list(packets)[:MAX_LOGICAL_NPCS]
        token = _GENERATIONS.issue()
        budget = _RequestBudget(deadline_seconds)
        provider = ""
        batch_id = ""
        validated_packets = []
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
                except Exception:
                    self._record(
                        kind="candidate",
                        disposition="invalid_packet",
                        batch_id=batch_id,
                    )

            indexed_results: Dict[int, NpcVoiceResult] = {}
            futures = {}
            for index, packet_copy in enumerate(validated_packets):
                npc_id = packet_copy["npc"]["id"]
                key = self._cache_key(packet_copy, provider)
                cached = self.cache.get(key)
                if cached is not None:
                    result = replace(
                        cached,
                        usage=Usage(),
                        latency_seconds=0.0,
                        cached=True,
                        generation_token=token,
                        completed_at=time.perf_counter(),
                    )
                    indexed_results[index] = result
                    self._record(
                        kind="cache",
                        disposition="hit",
                        batch_id=batch_id,
                        npc_id=npc_id,
                        provider=provider,
                        model=result.model,
                    )
                    continue

                if not _WORKER_SLOTS.acquire(blocking=False):
                    self._record(
                        kind="candidate",
                        disposition="worker_unavailable",
                        batch_id=batch_id,
                        npc_id=npc_id,
                    )
                    continue

                def run_and_release(
                    selected_packet: Mapping[str, Any] = packet_copy,
                ) -> NpcVoiceResult:
                    try:
                        return self._think_with_provider(
                            selected_packet,
                            provider,
                            budget=budget,
                            generation_token=token,
                            cache_result=False,
                        )
                    finally:
                        _WORKER_SLOTS.release()

                try:
                    future = _EXECUTOR.submit(run_and_release)
                    futures[future] = index
                except Exception:
                    _WORKER_SLOTS.release()
                    self._record(
                        kind="candidate",
                        disposition="submission_failure",
                        batch_id=batch_id,
                        npc_id=npc_id,
                    )

            done, pending = wait(tuple(futures), timeout=budget.remaining())
            for future in done:
                index = futures[future]
                npc_id = validated_packets[index]["npc"]["id"]
                try:
                    result = future.result()
                except Exception:
                    self._record(
                        kind="candidate",
                        disposition="future_failure",
                        batch_id=batch_id,
                        npc_id=npc_id,
                    )
                    continue
                if (
                    result.generation_token != token
                    or result.completed_at > budget.deadline
                    or not _GENERATIONS.active(token)
                ):
                    self._record(
                        kind="candidate",
                        disposition="late_result_rejected",
                        batch_id=batch_id,
                        npc_id=npc_id,
                    )
                    continue
                indexed_results[index] = result

            for future in pending:
                index = futures[future]
                self._record(
                    kind="candidate",
                    disposition="deadline_omission",
                    batch_id=batch_id,
                    npc_id=validated_packets[index]["npc"]["id"],
                )

            _GENERATIONS.expire(token)
            ordered = tuple(
                indexed_results[index]
                for index in sorted(indexed_results)
            )
            for result in ordered:
                if not result.cached and result.cacheable:
                    self.cache.put(result.content_hash, result)
                if result.affinity_event is not None:
                    self._record(
                        kind="event",
                        disposition="staged",
                        batch_id=batch_id,
                        npc_id=result.npc_id,
                    )
                self._record(
                    kind="merge",
                    disposition="merged",
                    batch_id=batch_id,
                    npc_id=result.npc_id,
                )
            self._record(
                kind="batch",
                disposition="complete",
                batch_id=batch_id,
                latency_seconds=time.perf_counter() - batch_started,
                provider=provider,
                candidate_count=len(validated_packets),
                physical_request_count=budget.count,
                merged_count=len(ordered),
            )
            return NpcVoiceBatch(
                batch_id=batch_id,
                results=ordered,
                generation_token=token,
                candidate_count=len(validated_packets),
                physical_request_count=budget.count,
                telemetry=self.telemetry,
            )
        except Exception:
            _GENERATIONS.expire(token)
            self._record(
                kind="batch",
                disposition="batch_failure",
                batch_id=batch_id,
                latency_seconds=time.perf_counter() - batch_started,
                provider=provider,
                candidate_count=len(validated_packets),
                physical_request_count=budget.count,
            )
            return NpcVoiceBatch(
                batch_id=batch_id,
                results=(),
                generation_token=token,
                candidate_count=len(validated_packets),
                physical_request_count=budget.count,
                telemetry=self.telemetry,
            )
        finally:
            _GENERATIONS.expire(token)
