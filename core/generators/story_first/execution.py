# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

"""Provider-neutral, publication-free execution for one story-first stage."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Callable, Dict, Mapping, Optional, Protocol

import jsonschema

from .compilers import normalize_ascii_typography
from .contracts import StageEvidence, freeze_value, mutable_copy
from utils.capture.multi_model_capture import register_callsite


register_callsite("T098", "core/generators/story_first/execution.py", 183)
register_callsite("T099", "core/generators/story_first/execution.py", 183)
register_callsite("T100", "core/generators/story_first/execution.py", 183)
register_callsite("T101", "core/generators/story_first/execution.py", 183)
register_callsite("T102", "core/generators/story_first/execution.py", 183)
register_callsite("T103", "core/generators/story_first/execution.py", 183)


_ALLOWED_MODEL_OPTIONS = frozenset(
    {"reasoning_effort", "thinking_level", "max_tokens", "max_completion_tokens"}
)
_ALLOWED_FAILURE_CLASSES = frozenset(
    {
        "interrupted",
        "timeout",
        "empty_response",
        "duplicate_json_key",
        "malformed_json",
        "schema",
        "semantic",
        "provider",
        "capacity",
        "authentication",
    }
)


class EmptyResponseError(ValueError):
    pass


class DuplicateJsonKeyError(ValueError):
    pass


class ResponseEnvelopeError(ValueError):
    pass


class GatewayFailure(RuntimeError):
    """Safe provider failure classification supplied by an execution gateway."""

    def __init__(self, failure_class: str):
        if failure_class not in _ALLOWED_FAILURE_CLASSES:
            failure_class = "provider"
        self.failure_class = failure_class
        super().__init__(f"completion gateway failed ({failure_class})")


class SemanticCorrectionError(ValueError):
    """Deterministic validator issues safe to return in a focused retry."""

    _FIELDS = frozenset({"invariant", "offending", "expectation"})

    def __init__(self, issues):
        safe = []
        for issue in list(issues)[:24]:
            if not isinstance(issue, Mapping) or set(issue) != self._FIELDS:
                raise ValueError("invalid semantic correction issue")
            item = {key: str(issue[key]).strip() for key in sorted(self._FIELDS)}
            if any(not value or len(value) > 240 for value in item.values()):
                raise ValueError("invalid semantic correction issue text")
            try:
                json.dumps(item, ensure_ascii=False).encode("ascii")
            except UnicodeEncodeError as exc:
                raise ValueError("semantic correction issue must be ASCII") from exc
            lowered = json.dumps(item).casefold()
            if "bearer " in lowered or "sk-" in lowered or "aiza" in lowered:
                raise ValueError("credential-shaped semantic correction issue")
            safe.append(item)
        if not safe:
            raise ValueError("semantic correction requires at least one issue")
        self.issues = tuple(safe)
        message = "; ".join(
            f"{item['invariant']}: {item['offending']}; {item['expectation']}"
            for item in self.issues
        )
        super().__init__(message)

    def prompt_fragment(self) -> str:
        return json.dumps(list(self.issues), ensure_ascii=True, separators=(",", ":"))


class NonRetryableStageError(RuntimeError):
    """A deterministic stage failure that another model response cannot repair."""


@dataclass(frozen=True)
class StructuredRequest:
    """Safe request description consumed by a production or test gateway."""

    stage: str
    task_id: str
    schema_name: str
    provider: str
    model: str
    model_options: Mapping[str, Any]
    temperature: float
    schema: Mapping[str, Any]
    system_prompt: str
    user_prompt: str

    def __post_init__(self) -> None:
        unknown = set(self.model_options) - _ALLOWED_MODEL_OPTIONS
        if unknown:
            raise ValueError("structured request contains unsupported model options")
        for key, value in self.model_options.items():
            if key in {"max_tokens", "max_completion_tokens"}:
                if type(value) is not int or value < 1:
                    raise ValueError("structured request has an invalid token limit")
            elif not isinstance(value, str) or value not in {
                "none",
                "minimal",
                "low",
                "medium",
                "high",
            }:
                raise ValueError("structured request has an invalid reasoning option")
        object.__setattr__(self, "model_options", freeze_value(self.model_options))
        object.__setattr__(self, "schema", freeze_value(self.schema))

    def schema_copy(self) -> Dict[str, Any]:
        return mutable_copy(self.schema)


@dataclass(frozen=True)
class CompletionPayload:
    raw: str
    finish_reason: Optional[str] = None


class CompletionGateway(Protocol):
    def __call__(self, request: StructuredRequest) -> CompletionPayload:
        raise NotImplementedError


@dataclass(frozen=True)
class StageExecutionResult:
    value: Mapping[str, Any]
    metrics: Mapping[str, Any]
    evidence: StageEvidence

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", freeze_value(self.value))
        object.__setattr__(self, "metrics", freeze_value(self.metrics))


class StageExecutionError(RuntimeError):
    """Bounded failure carrying safe evidence but no raw/provider response text."""

    def __init__(self, evidence: StageEvidence, semantic_issues=()):
        self.evidence = evidence
        self.semantic_issues = (
            tuple(
                dict(issue) for issue in SemanticCorrectionError(semantic_issues).issues
            )
            if semantic_issues
            else ()
        )
        super().__init__(
            f"{evidence.stage} failed after {evidence.attempts} bounded attempts"
        )


def _provider_failure_class(exc: BaseException) -> str:
    """Classify a provider exception without retaining its message or traceback."""
    if isinstance(exc, (KeyboardInterrupt, SystemExit, InterruptedError)):
        return "interrupted"
    if isinstance(exc, TimeoutError) or "timeout" in type(exc).__name__.casefold():
        return "timeout"
    status = getattr(exc, "status_code", None)
    if status in {401, 403}:
        return "authentication"
    if status == 429:
        return "capacity"
    name = type(exc).__name__.casefold()
    if "authentication" in name or "permission" in name:
        return "authentication"
    if "ratelimit" in name or "capacity" in name:
        return "capacity"
    return "provider"


def production_completion_gateway(request: StructuredRequest) -> CompletionPayload:
    """Execute one snapshotted production request through the normal capture path."""
    from core.ai import api_client
    from utils.capture.multi_model_capture import capture_and_fanout

    call_options = mutable_copy(request.model_options)
    if request.provider == "openai":
        call_options["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": request.schema_name,
                "strict": True,
                "schema": request.schema_copy(),
            },
        }
    elif request.provider == "gemini":
        from model_config import convert_to_gemini_schema

        call_options["response_format"] = {"type": "json_object"}
        call_options["response_schema"] = convert_to_gemini_schema(
            request.schema_copy(),
            preserve_required=True,
            preserve_constraints=True,
        )
    else:
        raise GatewayFailure("provider")
    try:
        response = capture_and_fanout(
            request.task_id,
            api_client.create_completion,
            _request_provider=request.provider,
            messages=[
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            model=request.model,
            temperature=request.temperature,
            **call_options,
        )
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException as exc:
        raise GatewayFailure(_provider_failure_class(exc)) from None
    try:
        choice = response.choices[0]
        raw = choice.message.content or ""
        finish_reason = getattr(choice, "finish_reason", None)
    except (AttributeError, IndexError, TypeError):
        raise GatewayFailure("provider") from None
    return CompletionPayload(raw=raw, finish_reason=finish_reason)


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKeyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def extract_response_object(content: str) -> Dict[str, Any]:
    """Accept a bare object or one complete JSON fence; reject all surrounding prose."""
    if not isinstance(content, str):
        raise ResponseEnvelopeError("response content is not text")
    text = (content or "").strip()
    if not text:
        raise EmptyResponseError("response contained no usable text")
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) < 3 or lines[0].strip().casefold() not in {"```", "```json"}:
            raise ResponseEnvelopeError("invalid JSON fence")
        if lines[-1].strip() != "```":
            raise ResponseEnvelopeError("unterminated JSON fence")
        text = "\n".join(lines[1:-1]).strip()
    if text.startswith("<think") or text.startswith("<analysis"):
        raise ResponseEnvelopeError("reasoning appeared in the content channel")
    try:
        value = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except DuplicateJsonKeyError:
        raise
    except json.JSONDecodeError:
        raise
    if not isinstance(value, dict):
        raise ResponseEnvelopeError("response root is not an object")
    return value


def _failure_class(exc: BaseException, phase: str) -> str:
    if isinstance(exc, (KeyboardInterrupt, InterruptedError)):
        return "interrupted"
    if isinstance(exc, TimeoutError):
        return "timeout"
    if isinstance(exc, GatewayFailure):
        return exc.failure_class
    if isinstance(exc, EmptyResponseError):
        return "empty_response"
    if isinstance(exc, DuplicateJsonKeyError):
        return "duplicate_json_key"
    if isinstance(exc, (json.JSONDecodeError, ResponseEnvelopeError)):
        return "malformed_json"
    if isinstance(exc, jsonschema.ValidationError):
        return "schema"
    if phase == "semantic":
        return "semantic"
    return "provider"


def execute_structured_stage(
    *,
    stage: str,
    task_id: str,
    schema_name: str,
    provider: str,
    model: str,
    model_options: Mapping[str, Any],
    temperature: float,
    schema: Mapping[str, Any],
    system_prompt: str,
    user_prompt: str,
    max_attempts: int,
    semantic_gate: Callable[[Dict[str, Any]], Mapping[str, Any]],
    gateway: CompletionGateway,
    correction_guidance: str = "",
) -> StageExecutionResult:
    """Retry one stage without publishing any attempted response."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")
    failures = []
    focused_issues = []
    typed_issues = []
    for attempt in range(1, max_attempts + 1):
        phase = "provider"
        correction = ""
        if failures:
            correction = (
                "\n\nFOCUSED CORRECTION: The previous response failed the "
                f"{failures[-1]} gate. Return the complete object again and preserve "
                "all trusted input IDs and facts."
            )
            if correction_guidance:
                correction += " " + correction_guidance.strip()
            if focused_issues[-1]:
                correction += (
                    " Deterministic validator issues (fix every listed invariant): "
                    + focused_issues[-1]
                )
        request = StructuredRequest(
            stage=stage,
            task_id=task_id,
            schema_name=schema_name,
            provider=provider,
            model=model,
            model_options=model_options,
            temperature=temperature,
            schema=schema,
            system_prompt=system_prompt,
            user_prompt=user_prompt + correction,
        )
        try:
            payload = gateway(request)
            if str(payload.finish_reason or "").casefold() in {
                "length",
                "max_tokens",
                "max_output_tokens",
            }:
                raise GatewayFailure("capacity")
            phase = "parse"
            value = extract_response_object(payload.raw)
            value, typography_replacements = normalize_ascii_typography(value)
            phase = "schema"
            jsonschema.validate(value, request.schema_copy())
            phase = "semantic"
            metrics = {
                **mutable_copy(semantic_gate(value)),
                "deterministicAsciiTypographyReplacements": (typography_replacements),
            }
            return StageExecutionResult(
                value=value,
                metrics=metrics,
                evidence=StageEvidence(
                    stage=stage,
                    attempts=attempt,
                    result="accepted",
                    failure_classes=tuple(failures),
                ),
            )
        except (KeyboardInterrupt, SystemExit, NonRetryableStageError):
            raise
        except BaseException as exc:
            failures.append(_failure_class(exc, phase))
            focused_issues.append(
                exc.prompt_fragment()
                if isinstance(exc, SemanticCorrectionError)
                else ""
            )
            typed_issues.append(
                tuple(dict(issue) for issue in exc.issues)
                if isinstance(exc, SemanticCorrectionError)
                else ()
            )
    raise StageExecutionError(
        StageEvidence(
            stage=stage,
            attempts=max_attempts,
            result="rejected",
            failure_class=failures[-1],
            failure_classes=tuple(failures),
        ),
        semantic_issues=typed_issues[-1],
    ) from None
