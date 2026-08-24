"""One-time, fail-open T107 structured NPC profile seeding."""

from __future__ import annotations

import copy
import json
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional

from jsonschema import Draft202012Validator

import model_config
from core.ai import api_client
from core.npc.relationship_store import RelationshipStore
from core.npc.voice_contracts import (
    STRUCTURED_PROFILE_SCHEMA,
    canonical_json,
    profile_gemini_response_schema,
)
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite


TASK_ID = "T107"
PROFILE_VERSION = 1
PROMPT_VERSION = "npc-profile-seed-prompt/v1"
SCHEMA_VERSION = "npc-profile-seed-response/v1"
TEMPERATURE = 0.4
MAX_OUTPUT_TOKENS = 500
MAX_ATTEMPTS = 2
MAX_SOURCE_CHARS = 9000

register_callsite("T107", "core/npc/profile_service.py", 292)


class ProfileContractError(ValueError):
    """A T107 source or response violated its strict private contract."""


class NpcProfileUnavailable(RuntimeError):
    """Both bounded T107 attempts failed."""


@dataclass(frozen=True)
class ProfileSeedResult:
    profile: Dict[str, Any]
    source_canonical: str
    model: str = ""
    cached: bool = False


class ProfileCache:
    """Process-local LRU containing validated T107 results only."""

    def __init__(self, max_entries: int = 64) -> None:
        self.max_entries = max_entries
        self._values: OrderedDict[str, ProfileSeedResult] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[ProfileSeedResult]:
        with self._lock:
            value = self._values.get(key)
            if value is None:
                return None
            self._values.move_to_end(key)
            return copy.deepcopy(value)

    def put(self, key: str, value: ProfileSeedResult) -> None:
        with self._lock:
            self._values[key] = copy.deepcopy(value)
            self._values.move_to_end(key)
            while len(self._values) > self.max_entries:
                self._values.popitem(last=False)


def _strip_json_fence(value: str) -> str:
    return re.sub(
        r"^```(?:json)?\s*|\s*```$", "", value.strip(), flags=re.IGNORECASE
    )


def validate_profile(raw: Any) -> Dict[str, Any]:
    try:
        candidate = json.loads(_strip_json_fence(raw)) if isinstance(raw, str) else raw
    except json.JSONDecodeError as exc:
        raise ProfileContractError("profile response is not JSON") from exc
    error = next(Draft202012Validator(STRUCTURED_PROFILE_SCHEMA).iter_errors(candidate), None)
    if error is not None:
        path = ".".join(str(part) for part in error.path) or "response"
        raise ProfileContractError(
            "invalid profile response at %s: %s" % (path, error.message)
        )
    result = copy.deepcopy(candidate)
    result["voice"]["cadence"] = result["voice"]["cadence"].strip()
    result["voice"]["diction"] = result["voice"]["diction"].strip()
    result["conflictStyle"] = result["conflictStyle"].strip()
    for key in (
        "taboos", "goals", "fears", "values", "preferences", "boundaries",
        "protectionPriorities", "retreatRules", "arcSeeds",
    ):
        container = result["voice"] if key == "taboos" else result
        stripped = [item.strip() for item in container[key]]
        if any(not item for item in stripped) or len(set(stripped)) != len(stripped):
            raise ProfileContractError("profile strings must be nonempty and unique")
        container[key] = stripped
    return result


def _text(value: Any, limit: int) -> str:
    return value.strip()[:limit] if isinstance(value, str) else ""


def _unique(values: Any, count: int, limit: int) -> list[str]:
    if not isinstance(values, (list, tuple)):
        values = [values]
    result = []
    for value in values:
        item = _text(value, limit)
        if item and item not in result:
            result.append(item)
        if len(result) >= count:
            break
    return result


def profile_source_canonical(source: Mapping[str, Any]) -> str:
    """Lossless value fingerprint of the profile source (no digest).

    The canonical-JSON string of exactly the same {profileVersion, source}
    material the retired sourceHash digest covered -- string equality of this
    value is equivalent to value equality of those fields, so WHEN a profile
    regenerates is unchanged.
    """
    return canonical_json({"profileVersion": PROFILE_VERSION, "source": source})


def deterministic_fallback_profile(
    sheet: Mapping[str, Any],
    lifecycle: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Derive a schema-valid profile without inventing campaign facts."""
    context = lifecycle if isinstance(lifecycle, Mapping) else {}
    personality = _text(
        sheet.get("personality_traits") or sheet.get("personality"), 120
    )
    bonds = _text(sheet.get("bonds"), 180)
    ideals = _text(sheet.get("ideals"), 120)
    role = _text(sheet.get("role") or sheet.get("class"), 120)
    objective = _text(context.get("personalObjective"), 180)
    goals = _unique([objective, bonds, role, ideals, "unknown"], 3, 180)
    values = _unique([ideals, _text(sheet.get("alignment"), 120), "unknown"], 5, 120)
    red_lines = _unique(context.get("redLines", []), 5, 160)
    return {
        "voice": {"cadence": personality, "diction": "", "taboos": []},
        "goals": goals,
        "fears": [],
        "values": values,
        "preferences": [],
        "boundaries": red_lines,
        "conflictStyle": "",
        "initiativeTendency": "balanced",
        "riskTolerance": "measured",
        "protectionPriorities": [],
        "retreatRules": [],
        "arcSeeds": [],
    }


_SOURCE_SHEET_FIELDS = (
    "name", "race", "class", "subclass", "role", "alignment", "background",
    "personality_traits", "personality", "ideals", "bonds", "flaws",
    "skills", "proficiencies", "features", "classFeatures",
)


def build_profile_source(
    *,
    npc_id: str,
    npc_name: str,
    sheet: Mapping[str, Any],
    lifecycle: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    if not isinstance(sheet, Mapping):
        raise ProfileContractError("profile source sheet must be an object")
    lifecycle_value = dict(lifecycle) if isinstance(lifecycle, Mapping) else {}
    compact_sheet = {
        key: copy.deepcopy(sheet[key])
        for key in _SOURCE_SHEET_FIELDS
        if key in sheet
    }
    source = {
        "npcId": _text(npc_id, 240),
        "npcName": _text(npc_name, 100),
        "sheet": compact_sheet,
        "lifecycle": lifecycle_value,
    }
    if not source["npcId"] or not source["npcName"]:
        raise ProfileContractError("profile source identity is required")
    encoded = json.dumps(source, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    if len(encoded) > MAX_SOURCE_CHARS:
        for key in ("classFeatures", "features", "proficiencies", "skills"):
            source["sheet"].pop(key, None)
            encoded = json.dumps(
                source, ensure_ascii=True, sort_keys=True, separators=(",", ":")
            )
            if len(encoded) <= MAX_SOURCE_CHARS:
                break
    if len(encoded) > MAX_SOURCE_CHARS:
        raise ProfileContractError("profile source exceeds T107 input budget")
    return source


def _prompt_text() -> str:
    path = Path(__file__).resolve().parents[2] / "prompts" / "npc" / "npc_profile_seed_t107.txt"
    return path.read_text(encoding="ascii").strip()


def build_messages(source: Mapping[str, Any], retry_reason: str = "") -> list[Dict[str, str]]:
    messages = [{"role": "system", "content": _prompt_text()}]
    if retry_reason:
        messages.append(
            {
                "role": "system",
                "content": (
                    "The previous private response failed the strict contract (%s). "
                    "Return one corrected exact JSON object only." % retry_reason
                ),
            }
        )
    messages.append(
        {
            "role": "user",
            "content": json.dumps(
                source, ensure_ascii=True, sort_keys=True, separators=(",", ":")
            ),
        }
    )
    return messages


def _config_for_provider(provider: str) -> Dict[str, Any]:
    # Structured 12-key profile output. OpenAI/legacy use JSON mode + client-side
    # validation; Gemini needs response_schema or it emits the wrong shape.
    # Never attach response_schema on the OpenAI path (would 400).
    if provider == "openai":
        selected = copy.deepcopy(model_config.NPC_PROFILE_T107_OPENAI_LUNA_NONE)
        selected["response_format"] = {"type": "json_object"}
    elif provider == "gemini":
        selected = copy.deepcopy(model_config.NPC_PROFILE_T107_GEMINI_FLASHLITE_LOW)
        selected["response_schema"] = profile_gemini_response_schema()
    elif provider == "legacy":
        selected = copy.deepcopy(model_config.NPC_PROFILE_T107_LEGACY)
        selected["response_format"] = {"type": "json_object"}
    elif provider == "lmstudio":
        selected = copy.deepcopy(model_config.NPC_PROFILE_T107_LMSTUDIO)
        selected["response_format"] = None
    else:
        raise ValueError("unsupported T107 provider: %s" % provider)
    return selected


class NpcProfileService:
    def __init__(
        self,
        completion_fn: Callable[..., Any] = api_client.create_completion,
        *,
        capture_fn: Callable[..., Any] = capture_and_fanout,
        cache: Optional[ProfileCache] = None,
    ) -> None:
        self.completion_fn = completion_fn
        self.capture_fn = capture_fn
        self.cache = cache if cache is not None else ProfileCache()

    def seed(
        self,
        source: Mapping[str, Any],
        *,
        source_canonical_override: str = "",
        max_attempts: int = MAX_ATTEMPTS,
    ) -> ProfileSeedResult:
        if not isinstance(source, Mapping):
            raise ProfileContractError("profile source must be an object")
        required = {"npcId", "npcName", "sheet", "lifecycle"}
        if set(source) != required:
            raise ProfileContractError("profile source keys are invalid")
        source_copy = copy.deepcopy(dict(source))
        # In-memory cache key = the lossless canonical value string itself.
        source_fingerprint = (
            source_canonical_override
            if isinstance(source_canonical_override, str) and source_canonical_override
            else profile_source_canonical(source_copy)
        )
        cached = self.cache.get(source_fingerprint)
        if cached is not None:
            return ProfileSeedResult(
                profile=cached.profile,
                source_canonical=cached.source_canonical,
                model=cached.model,
                cached=True,
            )
        provider = model_config.get_provider()
        last_error: Optional[BaseException] = None
        retry_reason = ""
        for attempt in range(max_attempts):
            config = _config_for_provider(provider)
            model = config.pop("model")
            response = None
            try:
                response = self.capture_fn(
                    TASK_ID,
                    self.completion_fn,
                    _request_provider=provider,
                    messages=build_messages(source_copy, retry_reason),
                    model=model,
                    temperature=TEMPERATURE,
                    # No max_tokens/max_completion_tokens on any call: gpt-5.x (luna)
                    # rejects max_tokens with a 400. Structured output is bounded by
                    # the client-side profile contract validation instead.
                    retry_attempt=attempt,
                    **config,
                )
                profile = validate_profile(response.choices[0].message.content)
                result = ProfileSeedResult(
                    profile=profile,
                    source_canonical=source_fingerprint,
                    model=getattr(response, "model", None) or model,
                )
                self.cache.put(source_fingerprint, result)
                return result
            except ProfileContractError as exc:
                last_error = exc
                retry_reason = "invalid_contract"
            except Exception as exc:
                last_error = exc
                retry_reason = "provider_failure"
        raise NpcProfileUnavailable("T107 attempts exhausted") from last_error


_DEFAULT_SERVICE: Optional[NpcProfileService] = None
_DEFAULT_SERVICE_LOCK = threading.Lock()


def _default_service() -> NpcProfileService:
    global _DEFAULT_SERVICE
    with _DEFAULT_SERVICE_LOCK:
        if _DEFAULT_SERVICE is None:
            _DEFAULT_SERVICE = NpcProfileService()
        return _DEFAULT_SERVICE


def seed_profile_best_effort(
    *,
    store: RelationshipStore,
    npc_id: str,
    npc_name: str,
    sheet: Mapping[str, Any],
    lifecycle: Optional[Mapping[str, Any]] = None,
    service: Optional[NpcProfileService] = None,
) -> Dict[str, Any]:
    """Persist fallback first; T107 failure can never undo recruitment."""
    lifecycle_value = dict(lifecycle) if isinstance(lifecycle, Mapping) else {}
    full_hash_source = {
        "npcId": npc_id,
        "npcName": npc_name,
        "sheet": dict(sheet),
        "lifecycle": lifecycle_value,
    }
    source_fingerprint = profile_source_canonical(full_hash_source)
    existing = store.get_profile(npc_id)
    # Value-fingerprint gate: string equality of sourceCanonical <=> value
    # equality of the same {profileVersion, source} material the retired
    # sourceHash digest covered. A legacy profile that only carries sourceHash
    # is tolerated on load but treated as non-matching here, so it regenerates
    # ONCE; the write below persists sourceCanonical and the value gate then
    # holds from that point on.
    if (
        isinstance(existing, dict)
        and existing.get("profileVersion") == PROFILE_VERSION
        and existing.get("sourceCanonical") == source_fingerprint
    ):
        return existing
    fallback = deterministic_fallback_profile(sheet, lifecycle_value)
    persisted_fallback = {
        "profileVersion": PROFILE_VERSION,
        "sourceCanonical": source_fingerprint,
        **fallback,
    }
    store.store_profile(npc_id, persisted_fallback)
    try:
        source = build_profile_source(
            npc_id=npc_id,
            npc_name=npc_name,
            sheet=sheet,
            lifecycle=lifecycle_value,
        )
        # Bind the compact request to the full authoritative source fingerprint
        # so mechanical sheet changes still invalidate a prior seed.
        result = (service or _default_service()).seed(
            source,
            source_canonical_override=source_fingerprint,
            max_attempts=1,
        )
        seeded = {
            "profileVersion": PROFILE_VERSION,
            "sourceCanonical": source_fingerprint,
            **result.profile,
        }
        store.store_profile(npc_id, seeded)
        return store.get_profile(npc_id) or persisted_fallback
    except Exception:
        return store.get_profile(npc_id) or persisted_fallback
