"""Multi-model capture and fanout wrapper.

Primary call runs synchronously and returns immediately.
All other variants fire in background threads via ThreadPoolExecutor.
"""
import atexit
import copy
import hashlib
import inspect
import email.utils
import json
import logging
import math
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import model_config
from utils.capture.file_writer import CaptureFileWriter
from utils.capture.openai_caller import call_openai_variant
from utils.capture.gemini_caller import call_gemini_variant
from utils.transient_filesystem import raise_if_save_stopped

# Shared thread pool - initialized once
_executor = ThreadPoolExecutor(max_workers=8)

# HIGH-14 (#127): drain in-flight capture variant calls on process exit so they
# cannot be abandoned mid-write (pairs with the atomic writer to prevent corrupt
# capture JSON). wait=True lets background OpenAI/Gemini calls finish.
atexit.register(_executor.shutdown, wait=True)

_writer = None
_config = None
_config_lock = threading.Lock()
_error_logger = None
_init_lock = threading.Lock()
_source_revision = None
_repo_root = Path(__file__).resolve().parents[2]
_SOURCE_FINGERPRINT_VERSION = b"neq-runtime-inputs/v1\0"
_RUNTIME_PYTHON_ROOTS = ("core", "utils", "updates", "web")


def _capture_dir():
    value = os.environ.get("NEQ_MODEL_CAPTURE_DIR", "").strip()
    return os.path.abspath(value) if value else str(_repo_root / "model_captures")


def _capture_config_path():
    value = os.environ.get("NEQ_MODEL_CAPTURE_CONFIG", "").strip()
    return os.path.abspath(value) if value else os.path.join(
        _capture_dir(), "capture_config.json"
    )


def _capture_enabled():
    override = os.environ.get("NEQ_MULTI_MODEL_CAPTURE", "").strip().lower()
    if override:
        return override in {"1", "true", "yes", "on"}
    return bool(getattr(model_config, "MULTI_MODEL_CAPTURE", False))


def _evaluation_primary_override(task_id, provider, attempt):
    """Return an explicit incumbent profile only in opted-in evaluation runs."""
    mode = os.environ.get("NEQ_MODEL_EVAL_PRIMARY", "").strip().lower()
    if mode != "incumbent" or provider != "openai" or not _capture_enabled():
        return None
    entries = (_load_config().get("primary_overrides") or {}).get(task_id)
    if not isinstance(entries, list) or not entries:
        raise RuntimeError("Missing incumbent evaluation profile for %s" % task_id)
    index = min(max(int(attempt), 0), len(entries) - 1)
    entry = entries[index]
    if not isinstance(entry, dict) or not isinstance(entry.get("model"), str):
        raise RuntimeError("Invalid incumbent evaluation profile for %s" % task_id)
    allowed = {"model", "reasoning_effort", "thinking_level"}
    unknown = set(entry) - allowed - {"provider", "use_caller_temp", "label"}
    if unknown:
        raise RuntimeError(
            "Unsupported incumbent evaluation options for %s: %s"
            % (task_id, sorted(unknown))
        )
    return {name: copy.deepcopy(entry[name]) for name in allowed if name in entry}


def _runtime_source_paths():
    """Return the finite, sorted runtime-input set without consulting Git."""
    paths = {
        path
        for path in _repo_root.glob("*.py")
        if path.is_file() and path.name != "config.py"
    }
    for root_name in _RUNTIME_PYTHON_ROOTS:
        root = _repo_root / root_name
        if root.is_dir():
            paths.update(path for path in root.rglob("*.py") if path.is_file())
    for root_name in ("prompts", "schemas"):
        root = _repo_root / root_name
        if root.is_dir():
            paths.update(path for path in root.rglob("*") if path.is_file())
    return tuple(sorted(paths, key=lambda path: path.relative_to(_repo_root).as_posix()))


def _compute_source_revision():
    digest = hashlib.sha256()
    digest.update(_SOURCE_FINGERPRINT_VERSION)
    paths = _runtime_source_paths()
    for path in paths:
        relative = path.relative_to(_repo_root).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return "runtime-v1-%s-%d" % (digest.hexdigest(), len(paths))


def _get_source_revision():
    """Return a stable fingerprint of model-affecting runtime inputs.

    Audit prose, ignored captures, and test harness edits must not invalidate a
    production request captured from unchanged runtime code.  Conversely, an
    uncommitted prompt/schema/runtime edit must change the fingerprint even when
    HEAD has not moved.
    """
    global _source_revision
    if _source_revision is None:
        with _init_lock:
            if _source_revision is None:
                try:
                    _source_revision = _compute_source_revision()
                except Exception:
                    _source_revision = "unknown"
    return _source_revision


# Prime provenance synchronously during normal module import, before any
# provider/capture worker can ask for it. A failed scan is diagnostic-only.
_get_source_revision()


def _get_error_logger():
    global _error_logger
    if _error_logger is None:
        with _init_lock:
            if _error_logger is None:
                os.makedirs(_capture_dir(), exist_ok=True)
                _error_logger = logging.getLogger("capture_errors")
                if not _error_logger.handlers:
                    handler = logging.FileHandler(
                        os.path.join(_capture_dir(), "errors.log")
                    )
                    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
                    _error_logger.addHandler(handler)
                    _error_logger.setLevel(logging.ERROR)
    return _error_logger


def _get_writer():
    global _writer
    if _writer is None:
        # Taken before _init_lock, which _get_error_logger takes too (#1621).
        error_logger = _get_error_logger()
        with _init_lock:
            if _writer is None:
                _writer = CaptureFileWriter(_capture_dir(), error_logger=error_logger)
    return _writer


def _load_config():
    global _config
    with _config_lock:
        if _config is not None:
            return _config
        config_path = _capture_config_path()
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                _config = json.load(f)
        else:
            _config = {"capture_enabled": False, "full_tier_variants": [], "mini_tier_variants": []}
        return _config


def reload_config():
    """Invalidate the cached capture config so the next _load_config() re-reads disk.

    MED-14 (#127): _config is cached for the life of the process for hot-path speed
    (capture runs on every API call). The web-UI settings handler (and tests) call
    this to apply a capture on/off change without a restart.
    """
    global _config
    with _config_lock:
        _config = None


def _determine_tier(model_string):
    """Determine if a model string is full or mini tier."""
    mini_models = {
        model_config.DM_MINI_MODEL,
        model_config.DM_SUMMARIZATION_MODEL,
        model_config.NARRATIVE_COMPRESSION_MODEL,
        model_config.COMBAT_DIALOGUE_SUMMARY_MODEL,
        model_config.ADVENTURE_SUMMARY_MODEL,
        model_config.PLOT_UPDATE_MODEL,
        model_config.NPC_INFO_UPDATE_MODEL,
        model_config.ENCOUNTER_UPDATE_MODEL,
        model_config.TRANSITION_VALIDATOR_MODEL,
    }
    if model_string in mini_models or "mini" in model_string.lower():
        return "mini"
    return "full"


def _runtime_uses_temperature(provider, model, kwargs):
    if provider == "gemini":
        return False
    if provider != "openai":
        return True

    model_lower = str(model or "").lower()
    reasoning = str(kwargs.get("reasoning_effort", "")).lower()
    if "5-mini" in model_lower:
        return False
    if "5.4-mini" in model_lower:
        return not reasoning or reasoning == "none"
    return not reasoning or reasoning == "none"


def _variant_matches_primary(variant, provider, model, primary_kwargs):
    """True when a capture variant would duplicate the selected request."""
    if variant.get("provider") != provider or variant.get("model") != model:
        return False
    for key in ("reasoning_effort", "thinking_level"):
        if variant.get(key) != primary_kwargs.get(key):
            return False

    primary_temperature = (
        primary_kwargs.get("temperature")
        if _runtime_uses_temperature(provider, model, primary_kwargs)
        else None
    )
    variant_temperature = (
        primary_kwargs.get("temperature")
        if variant.get("use_caller_temp")
        else None
    )
    if variant_temperature != primary_temperature:
        return False

    if provider == "gemini":
        if variant.get("response_schema") != primary_kwargs.get("response_schema"):
            return False
    return True


def _calculate_cost(model_name, token_usage, cfg):
    """Calculate USD cost based on model pricing and token usage.

    Args:
        model_name: The model identifier (e.g., "gpt-5.2", "gemini-3-flash-preview")
        token_usage: dict with prompt_tokens and completion_tokens
        cfg: loaded config with model_pricing section

    Returns:
        float: cost in USD, or None if pricing not available
    """
    pricing = cfg.get("model_pricing", {}).get(model_name)
    if not pricing or not token_usage:
        return None

    prompt_tokens = token_usage.get("prompt_tokens", 0)
    cached_tokens = min(prompt_tokens, token_usage.get("cached_tokens", 0) or 0)
    input_cost = ((prompt_tokens - cached_tokens) / 1_000_000) * pricing.get("input", 0)
    input_cost += (cached_tokens / 1_000_000) * pricing.get(
        "cached_input", pricing.get("input", 0)
    )
    output_cost = (token_usage.get("completion_tokens", 0) / 1_000_000) * pricing.get("output", 0)
    return round(input_cost + output_cost, 6)


def _track_module_primary(response, task_id, provider, requested_model):
    """Account for a selected module-build response independently of capture."""
    try:
        from utils.openai_usage_tracker import track_module_build_response

        track_module_build_response(
            response,
            task_id=task_id,
            provider=provider,
            model=getattr(response, "model", None) or requested_model,
        )
    except Exception:
        # Usage telemetry must never break gameplay or provider routing.
        pass


def _variant_provider_configured(variant):
    """True when the variant's provider can be called: OpenAI (the primary provider's own credentials), or
    Gemini with a key available to its client (#1308). Any other provider is never fired."""
    provider = variant.get("provider")
    if provider == "openai":
        return True
    if provider == "gemini":
        from utils.capture.gemini_caller import gemini_configured
        return gemini_configured()
    return False


def _fire_background_variant(variant, task_id, messages, invocation_id,
                              caller_temperature, caller_kwargs):
    """Execute one variant call and write result. Runs in thread pool."""
    label = variant["label"]
    model_name = variant.get("model", "unknown")
    writer = _get_writer()
    cfg = _load_config()
    try:
        if variant["provider"] == "openai":
            content, latency_s, token_usage = call_openai_variant(
                variant, messages, caller_temperature, caller_kwargs
            )
        else:
            content, latency_s, token_usage = call_gemini_variant(
                variant, messages, caller_temperature, caller_kwargs
            )
        cost_usd = _calculate_cost(model_name, token_usage, cfg)
        writer.merge_background_output(
            task_id, invocation_id, label, content, latency_s,
            token_usage=token_usage, cost_usd=cost_usd
        )
    except Exception as e:
        error_str = f"{type(e).__name__}: {e}"
        writer.merge_background_error(task_id, invocation_id, label, error_str)
        try:
            _get_error_logger().error(f"[{task_id}][{label}] {error_str}")
        except Exception:
            pass


def _resolve_effective_callsite_kwargs(task_id, provider, kwargs, attempt=0):
    """Return detached runtime kwargs with only the model profile replaced.

    Prompts are a separate argument to ``capture_and_fanout``.  Response schemas,
    formats, temperatures, and other callsite-owned request policy remain exactly
    as the production caller assembled them.
    """
    effective = copy.deepcopy(kwargs)
    from model_registry import CALLSITE_BINDINGS

    if task_id not in CALLSITE_BINDINGS:
        return effective
    selected = _evaluation_primary_override(task_id, provider, attempt)
    if selected is None:
        selected = model_config.resolve_callsite_config(task_id, provider, attempt)
    effective["model"] = selected["model"]
    for option in ("reasoning_effort", "thinking_level"):
        effective.pop(option, None)
        if option in selected:
            effective[option] = copy.deepcopy(selected[option])
    for option in ("max_tokens", "max_completion_tokens"):
        if option in selected:
            effective[option] = copy.deepcopy(selected[option])
    # Per-callsite output ceiling, OpenAI only: a streamed answer past it is
    # abandoned and the identical request reissued (core/ai/api_client).
    effective.pop("_output_ceiling_chars", None)
    if provider == "openai":
        from model_registry import openai_output_ceiling

        ceiling = openai_output_ceiling(task_id)
        if ceiling:
            effective["_output_ceiling_chars"] = ceiling
    return effective


# #1963: an in-process call on an OpenAI-SDK provider turns the library's own
# hidden resends off and the game makes them, counted, logged and stoppable.
# Only the failures the library itself resends are eligible, in its order
# (openai _base_client._should_retry). A Retry-After above the cap means no
# resend at all; #1981 lowered the cap to 60 s and shares it with the live
# child (live_provider_call.RETRY_AFTER_CAP).
_ROUTE_P_REISSUE_PROVIDERS = frozenset({"openai", "legacy", "lmstudio"})
_ROUTE_P_POLL_SECONDS = 0.25


def _route_p_retry_after(headers):
    """Retry-After in seconds as the openai SDK parses it, or None."""
    from utils.capture.live_provider_call import RETRY_AFTER_CAP

    if headers is None:
        return None
    for header, divisor in (("retry-after-ms", 1000.0), ("retry-after", 1.0)):
        value = headers.get(header)
        if value is None:
            continue
        try:
            delay = float(value)
        except ValueError:
            continue
        if delay == math.inf and value.strip().lower() not in (
            "inf", "+inf", "infinity", "+infinity",
        ):
            return RETRY_AFTER_CAP + 1
        return delay / divisor
    try:
        parsed = email.utils.parsedate_tz(headers.get("retry-after"))
        if parsed is None:
            return None
        return float(email.utils.mktime_tz(parsed) - time.time())
    except (TypeError, ValueError, OverflowError):
        return None


def _route_p_reissue_delay(exc, reissue):
    """Seconds to wait before reissue number ``reissue``, or None when the
    library would not have resent this failure. Typed fields only."""
    import openai

    from utils.capture.live_provider_call import (
        RETRY_AFTER_CAP,
        _delay_for_error,
        _primitive_error,
    )
    from utils.provider_errors import QUOTA_ERROR_CODES

    original = getattr(exc, "original_error", None)
    retry_after = None
    if isinstance(original, openai.APIStatusError):
        headers = getattr(getattr(original, "response", None), "headers", None)
        retry_after = _route_p_retry_after(headers)
        if (retry_after is not None and math.isfinite(retry_after)
                and retry_after > RETRY_AFTER_CAP):
            return None
        envelope = _primitive_error(exc, {})
        code = envelope.get("error_code")
        if isinstance(code, str) and code.lower() in QUOTA_ERROR_CODES:
            # Not resent even when the server says x-should-retry: true (the
            # library would): no resend pays the bill (#1963, R18c).
            return None
        should_retry = headers.get("x-should-retry") if headers is not None else None
        if should_retry == "false":
            return None
        if should_retry != "true" and envelope.get("disposition") != "retryable_http":
            return None
    elif not isinstance(original, openai.APIConnectionError):
        return None
    if (retry_after is not None and math.isfinite(retry_after)
            and 0 < retry_after <= RETRY_AFTER_CAP):
        return retry_after
    return _delay_for_error({"retry_after": None}, reissue)


def _route_p_wait(seconds):
    """Wait before a reissue, ending at once on Load, Reset or a save stop."""
    from utils.capture.live_provider_call import (
        _check_live_authority,
        get_live_provider_scope,
    )

    deadline = time.monotonic() + max(0.0, float(seconds))
    while True:
        raise_if_save_stopped()
        _check_live_authority(get_live_provider_scope())
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(_ROUTE_P_POLL_SECONDS, remaining))


def _fire_primary_with_retry(primary_fn, messages, kwargs, task_id,
                             max_attempts=3, base_delay=0.6):
    """Fire the primary provider call, retrying transient empty responses and,
    on an OpenAI-SDK provider, the failures the SDK itself would resend.

    A provider occasionally returns a response with no text content
    (finish_reason=stop, empty/whitespace content) -- a transient glitch that
    succeeds on retry. Retrying HERE (the shared production boundary) keeps
    create_completion() a thin router (wrapper-scope rule) while making every
    registered callsite resilient. An exhausted empty budget re-raises the
    original ProviderEmptyResponse unchanged.

    #1963: for openai, legacy and lmstudio, with no caller-owned timeout, the
    SDK's hidden resends are off and the game makes at most two of its own,
    counted, logged, waiting as the live child does, and checking Load, Reset
    and a save stop before each. Any other error propagates immediately.
    """
    from core.ai import api_client
    from core.ai.api_client import ProviderCallError, ProviderEmptyResponse
    from utils.capture import live_provider_call as live
    from utils.openai_usage_tracker import build_connection_state
    from utils.provider_errors import BuildConnectionStopped

    provider = kwargs.get("_request_provider")
    # #1981 PR C: in a build that already gave up on a connection class, no
    # call is made at all, whatever the caller's fallback does next.
    build_state = build_connection_state()
    if build_state is not None and build_state.stopped_class is not None:
        raise BuildConnectionStopped(build_state.stopped_class, build_state.provider)
    try:
        return _fire_primary_attempts(
            primary_fn, messages, kwargs, task_id, max_attempts, base_delay,
            provider, build_state,
        )
    except BaseException as exc:
        if build_state is not None:
            from utils.provider_errors import connection_class

            # The first give-up of a connection class stops the build.
            build_state.stop(connection_class(exc), provider)
        raise


def _build_retry_notice(build_state, exc, provider, attempt, max_attempts):
    """#1981 PR C: a Route P retry inside a build: a progress event at the
    same stage and percentage with the retry sentence and a typed notice,
    and the same sentence once per class per build as a system card."""
    from utils.provider_errors import connection_class, connection_retry_line

    cls = connection_class(exc)
    line = connection_retry_line(cls, provider) if cls else None
    if line is None:
        return
    hook = build_state.progress_notice
    if hook is not None:
        try:
            hook(line, {"class": cls, "attempt": attempt, "max": max_attempts})
        except Exception:
            pass
    with build_state.lock:
        first = cls not in build_state.notices_shown
        build_state.notices_shown.add(cls)
    if first:
        try:
            from utils.player_notice import show_player_notice

            show_player_notice(line)
        except Exception:
            pass


def _fire_primary_attempts(primary_fn, messages, kwargs, task_id, max_attempts,
                           base_delay, provider, build_state):
    """_fire_primary_with_retry's attempts (#1963), unchanged."""
    from core.ai import api_client
    from core.ai.api_client import ProviderCallError, ProviderEmptyResponse
    from utils.capture import live_provider_call as live

    reissue_on = (
        primary_fn is api_client.create_completion
        and provider in _ROUTE_P_REISSUE_PROVIDERS
        and kwargs.get("timeout") is None
    )
    if reissue_on:
        kwargs = dict(kwargs, _sdk_max_retries=0)
    # #1981: with no caller-owned timeout, the call gets its connection
    # class's deadline as a CLIENT option, never the request's ``timeout``
    # (that would mean the caller owns its retries and turn the reissue off).
    chars = live.prompt_chars(messages)
    base_url = live.local_base_url(kwargs) if provider == "lmstudio" else None
    if (
        primary_fn is api_client.create_completion
        and kwargs.get("timeout") is None
        and provider is not None
    ):
        deadline = live.class_deadline(
            provider, chars, base_url, kwargs.get("reasoning_effort")
        )
        if provider == "gemini":
            kwargs = dict(kwargs, _sdk_timeout=deadline)
        else:
            import httpx

            kwargs = dict(
                kwargs,
                _sdk_timeout=httpx.Timeout(deadline, connect=live._CONNECT_SECONDS),
            )
    attempt = 1
    reissues = 0
    while True:
        try:
            started = time.monotonic()
            response = primary_fn(messages=messages, **kwargs)
            if base_url is not None and kwargs.get("timeout") is None:
                # No phase stream in process: the whole call's time is an upper
                # bound of the time to the first chunk, so the deadline errs long.
                live.record_local_answer(base_url, time.monotonic() - started, chars)
            return response
        except ProviderEmptyResponse as exc:
            if attempt >= max_attempts:
                raise
            _get_error_logger().warning(
                "Transient empty provider response for %s (attempt %d/%d, "
                "finish_reason=%s); retrying.",
                task_id, attempt, max_attempts,
                getattr(exc, "finish_reason", "unknown"),
            )
            time.sleep(base_delay * attempt)
            attempt += 1
        except ProviderCallError as exc:
            if not reissue_on or reissues >= live._BILLED_REISSUE_LIMIT:
                raise
            delay = _route_p_reissue_delay(exc, reissues + 1)
            if delay is None:
                raise
            reissues += 1
            original = getattr(exc, "original_error", None)
            # The game's log files only: the capture error log keeps ERROR and
            # above, and a console record reaches a terminal player (#1981).
            from utils.enhanced_logger import file_only

            file_only(
                "PROVIDER_REISSUE: %s failed (%s, HTTP %s); reissue %d/%d "
                "in %.1f s." % (
                    task_id, type(original).__name__,
                    getattr(original, "status_code", None),
                    reissues, live._BILLED_REISSUE_LIMIT, delay,
                ),
                category="provider_retry",
            )
            if build_state is not None:
                _build_retry_notice(
                    build_state, exc, provider, reissues + 1,
                    1 + live._BILLED_REISSUE_LIMIT,
                )
            _route_p_wait(delay)


def capture_and_fanout(task_id, primary_fn, messages, **kwargs):
    """Drop-in wrapper around client.chat.completions.create.

    Fires the primary gpt-4.1 call synchronously, returns immediately.
    Submits all other variants to background thread pool.

    Usage:
        # Before:
        response = client.chat.completions.create(model=..., messages=messages, temperature=0.7)

        # After:
        response = capture_and_fanout("T013", client.chat.completions.create,
                                      messages=messages, model=..., temperature=0.7)
    """
    # Issue #654: after a read-only save stop, no model call is made, whatever
    # a caller's except clauses do. A no-op while no stop is recorded.
    raise_if_save_stopped()
    live_selected = kwargs.pop("_live_selected", None)
    # Detached execution context (issue #214): an off-thread caller (the
    # startup welcome) passes its own cancellable scope + status sink so its
    # provider work never binds the global player-turn scope or the global
    # input-locking status channel. Absent = byte-identical legacy behavior.
    detached_scope = kwargs.pop("_detached_scope", None)
    detached_status = kwargs.pop("_detached_status", None)
    # Parent-only lifecycle observation: never a model option or capture field.
    authority_check = kwargs.pop("_live_authority_check", None)
    # What the player waits for, when the task id alone cannot say (#1422 F2):
    # parent-only, never a model option or capture field.
    wait_purpose = kwargs.pop("_wait_purpose", None)
    if live_selected is None:
        from utils.capture.live_provider_call import live_provider_policy

        live_selected = live_provider_policy(task_id)
    if live_selected is True:
        live_policy = "required"
    elif live_selected in {"required", "advisory"}:
        live_policy = live_selected
    elif live_selected is False or live_selected is None:
        live_policy = None
    else:
        raise ValueError("_live_selected must be required, advisory, or false")
    if authority_check is not None and (not callable(authority_check) or not live_policy):
        raise ValueError("_live_authority_check requires callable live transport authority")

    # Keep the provider used for config selection attached to this request. A UI
    # provider switch while the request is in flight must not redirect it.
    request_provider = (
        kwargs.get("_request_provider") or model_config.get_provider()
    )

    # The capture boundary is also the one production boundary shared by every
    # registered T-ID. Resolve the canonical binding here so older callers that
    # still assemble compatibility constants cannot drift from evaluation or
    # capture selection. Only model-profile options are replaced; the callsite's
    # prompt, response_format/schema, temperature, and other overlays remain
    # exactly as assembled by its production caller.
    callsite_attempt = kwargs.pop("_callsite_attempt", 0)
    kwargs = _resolve_effective_callsite_kwargs(
        task_id, request_provider, kwargs, callsite_attempt
    )

    # Freeze the effective production inputs before the primary callable or its
    # caller can mutate shared message/config objects.
    capture_messages = copy.deepcopy(messages)

    capture_kwargs = copy.deepcopy(kwargs)
    capture_kwargs.pop("_usage_invocation_id", None)
    current_frame = inspect.currentframe()
    caller_frame = current_frame.f_back if current_frame is not None else None
    runtime_line = caller_frame.f_lineno if caller_frame is not None else 0
    runtime_file = caller_frame.f_code.co_filename if caller_frame is not None else ""
    del caller_frame
    del current_frame

    # Gated task_id injection: only inject when callable is create_completion
    # (unmigrated callsites using raw client.chat.completions.create would
    # reject unknown 'task_id' kwarg)
    from core.ai import api_client as _api_client
    usage_invocation_id = str(uuid4())
    if primary_fn is _api_client.create_completion:
        kwargs["_request_provider"] = request_provider
        kwargs["task_id"] = task_id
        kwargs["_usage_invocation_id"] = usage_invocation_id
    else:
        # Private router metadata must never leak into a raw SDK-compatible call.
        kwargs.pop("_request_provider", None)
        kwargs.pop("_usage_invocation_id", None)

    requested_model = capture_kwargs.get("model", "unknown")

    if live_policy:
        if primary_fn is not _api_client.create_completion:
            raise ValueError("live-selected calls require api_client.create_completion")
        from utils.capture.live_provider_call import call_live_provider

        start = time.time()
        response = call_live_provider(
            task_id,
            messages,
            kwargs,
            policy=live_policy,
            scope=detached_scope,
            status_emit=detached_status,
            authority_check=authority_check,
            purpose=wait_purpose,
        )
        primary_latency = round(time.time() - start, 3)
        _track_module_primary(
            response, task_id, request_provider, requested_model
        )

    # Local/Custom is a production runtime, not a capture-test source. Usage is
    # still player-visible production accounting and must happen before this
    # capture-specific early return.
    elif request_provider == "lmstudio":
        response = _fire_primary_with_retry(primary_fn, messages, kwargs, task_id)
        _track_module_primary(
            response, task_id, request_provider, requested_model
        )
        return response

    else:
        # Always fire the legacy primary call synchronously.
        start = time.time()
        response = _fire_primary_with_retry(primary_fn, messages, kwargs, task_id)
        primary_latency = round(time.time() - start, 3)

        # Account before either capture-disabled return below. Diagnostic capture
        # settings must not control production usage totals.
        _track_module_primary(response, task_id, request_provider, requested_model)

    # Capture/fanout must describe the request that produced the response.
    # When the adapter reshaped it for a strict local template (#389) the
    # response carries the array actually sent.
    sent_messages = getattr(response, "sent_messages", None)
    if isinstance(sent_messages, list):
        capture_messages = copy.deepcopy(sent_messages)

    # If capture disabled, return immediately - zero overhead
    if not _capture_enabled():
        return response

    # All capture logic is wrapped - errors never surface to the game
    try:
        cfg = _load_config()
        if not cfg.get("capture_enabled", False):
            return response

        # Gather call metadata
        timestamp = datetime.now(timezone.utc).isoformat()
        invocation_id = str(uuid4())
        model = requested_model
        tier = _determine_tier(model)
        caller_temperature = capture_kwargs.get("temperature")
        caller_kwargs = {k: v for k, v in capture_kwargs.items()
                         if k not in (
                             "model", "messages", "task_id", "retry_attempt",
                             "_request_provider", "_usage_invocation_id",
                         )}

        # Build input record
        input_data = {
            "messages": capture_messages,
            "provider": request_provider,
            "source_revision": _get_source_revision(),
            # Preserve the request assembled by the real callsite. Replay tools
            # replace only provider/model/effort and route it back through the
            # production adapter, so schemas and token ceilings cannot drift.
            "request_kwargs": caller_kwargs,
        }
        if caller_temperature is not None:
            input_data["temperature"] = caller_temperature
        if "reasoning_effort" in capture_kwargs:
            input_data["reasoning_effort"] = capture_kwargs["reasoning_effort"]
        if "thinking_level" in capture_kwargs:
            input_data["thinking_level"] = capture_kwargs["thinking_level"]
        if "response_format" in capture_kwargs:
            input_data["response_format"] = capture_kwargs["response_format"]
        if "response_schema" in capture_kwargs:
            input_data["response_schema"] = capture_kwargs["response_schema"]

        primary_content = response.choices[0].message.content
        primary_label = "selected|%s|%s" % (
            model,
            capture_kwargs.get("reasoning_effort", "n/a"),
        )

        # Extract token usage from primary response
        usage = getattr(response, 'usage', None)
        primary_token_usage = {
            "prompt_tokens": usage.prompt_tokens if usage else 0,
            "completion_tokens": usage.completion_tokens if usage else 0,
            "total_tokens": usage.total_tokens if usage else 0,
            "cached_tokens": getattr(
                getattr(usage, "prompt_tokens_details", None),
                "cached_tokens",
                0,
            ) or 0,
            "reasoning_tokens": getattr(
                getattr(usage, "completion_tokens_details", None),
                "reasoning_tokens",
                0,
            ) or 0,
        }
        primary_cost = _calculate_cost(model, primary_token_usage, cfg)

        # Get variants (check task_overrides first, then per-callsite configs)
        variants = [] if live_policy else cfg.get("task_overrides", {}).get(task_id)

        # An empty tier-variant list means shadows are off for that tier: no
        # per-callsite config re-enables them (#1308). task_overrides above
        # stays an explicit per-task opt-in.
        tier_variants = cfg.get(f"{tier}_tier_variants", [])
        if variants is None and not tier_variants:
            variants = []

        # Then try per-callsite config dicts from model_config.py
        if variants is None:
            from model_config import get_capture_variants_for_task
            variants = get_capture_variants_for_task(task_id)

        # Fall back to tier-based variants (backwards compatibility)
        if variants is None:
            variants = tier_variants

        # Get source location from registered metadata
        meta = _callsite_meta_for(task_id, runtime_file)
        writer = _get_writer()
        writer.write_primary(
            task_id=task_id,
            file_path=meta.get("file", "unknown"),
            line=runtime_line or meta.get("line", 0),
            tier=tier,
            input_data=input_data,
            label=primary_label,
            content=primary_content,
            latency_s=primary_latency,
            timestamp=timestamp,
            invocation_id=invocation_id,
            token_usage=primary_token_usage,
            cost_usd=primary_cost,
        )

        # Fire all non-baseline variants in background
        for variant in variants:
            # Skip disabled variants (enabled defaults to True if not specified)
            if not variant.get("enabled", True):
                continue
            # Never call a provider that is not configured (#1308).
            if not _variant_provider_configured(variant):
                continue
            # Skip an exact effective duplicate of the selected primary call.
            if _variant_matches_primary(
                variant, request_provider, model, capture_kwargs
            ):
                continue
            _executor.submit(
                _fire_background_variant,
                copy.deepcopy(variant),
                task_id,
                copy.deepcopy(capture_messages),
                invocation_id,
                caller_temperature,
                copy.deepcopy(caller_kwargs),
            )

    except Exception as e:
        try:
            _get_error_logger().error(f"[{task_id}] capture_and_fanout error: {type(e).__name__}: {e}")
        except Exception:
            pass

    return response


# Callsite metadata registry
_CALLSITE_META = {}
# Every registration per task_id, keyed by file: one task_id may have more than
# one live callsite (T078, issue #816), and the last import must not relabel the
# other's records.
_CALLSITE_FILES = {}
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _path_key(path):
    return os.path.normcase(path).replace("\\", "/")


def register_callsite(task_id, file_path, line):
    """Register file/line metadata for a task_id. Called at module import."""
    _CALLSITE_META[task_id] = {"file": file_path, "line": line}
    _CALLSITE_FILES.setdefault(task_id, {})[_path_key(file_path)] = _CALLSITE_META[task_id]


def _callsite_meta_for(task_id, runtime_file):
    """The registration of the file that made the call, else the last one."""
    if runtime_file:
        try:
            relative = os.path.relpath(runtime_file, _REPO_ROOT)
        except ValueError:  # another drive on Windows
            relative = None
        if relative is not None:
            meta = _CALLSITE_FILES.get(task_id, {}).get(_path_key(relative))
            if meta is not None:
                return meta
    return _CALLSITE_META.get(task_id, {})
