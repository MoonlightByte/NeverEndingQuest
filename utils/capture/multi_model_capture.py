"""Multi-model capture and fanout wrapper.

Primary call runs synchronously and returns immediately.
All other variants fire in background threads via ThreadPoolExecutor.
"""
import atexit
import copy
import inspect
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from uuid import uuid4

import model_config
from utils.capture.file_writer import CaptureFileWriter
from utils.capture.openai_caller import call_openai_variant
from utils.capture.gemini_caller import call_gemini_variant

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


def _get_error_logger():
    global _error_logger
    if _error_logger is None:
        with _init_lock:
            if _error_logger is None:
                os.makedirs("model_captures", exist_ok=True)
                _error_logger = logging.getLogger("capture_errors")
                if not _error_logger.handlers:
                    handler = logging.FileHandler("model_captures/errors.log")
                    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
                    _error_logger.addHandler(handler)
                    _error_logger.setLevel(logging.ERROR)
    return _error_logger


def _get_writer():
    global _writer
    if _writer is None:
        with _init_lock:
            if _writer is None:
                _writer = CaptureFileWriter("model_captures")
    return _writer


def _load_config():
    global _config
    with _config_lock:
        if _config is not None:
            return _config
        config_path = "model_captures/capture_config.json"
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

    input_cost = (token_usage.get("prompt_tokens", 0) / 1_000_000) * pricing.get("input", 0)
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
    # Freeze capture inputs before the primary callable or its caller can mutate
    # shared message/config objects. The primary still receives the originals.
    capture_messages = copy.deepcopy(messages)
    capture_kwargs = copy.deepcopy(kwargs)
    capture_kwargs.pop("_usage_invocation_id", None)
    current_frame = inspect.currentframe()
    caller_frame = current_frame.f_back if current_frame is not None else None
    runtime_line = caller_frame.f_lineno if caller_frame is not None else 0
    del caller_frame
    del current_frame

    # Keep the provider used for config selection attached to this request. A UI
    # provider switch while the request is in flight must not redirect it.
    request_provider = (
        capture_kwargs.get("_request_provider") or model_config.get_provider()
    )

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

    # Local/Custom is a production runtime, not a capture-test source. Usage is
    # still player-visible production accounting and must happen before this
    # capture-specific early return.
    if request_provider == "lmstudio":
        response = primary_fn(messages=messages, **kwargs)
        _track_module_primary(
            response, task_id, request_provider, requested_model
        )
        return response

    # Always fire primary call synchronously
    start = time.time()
    response = primary_fn(messages=messages, **kwargs)
    primary_latency = round(time.time() - start, 3)

    # Account before either capture-disabled return below. Diagnostic capture
    # settings must not control production usage totals.
    _track_module_primary(response, task_id, request_provider, requested_model)

    # If capture disabled, return immediately - zero overhead
    if not getattr(model_config, "MULTI_MODEL_CAPTURE", False):
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
        primary_label = f"{model}|baseline"

        # Extract token usage from primary response
        usage = getattr(response, 'usage', None)
        primary_token_usage = {
            "prompt_tokens": usage.prompt_tokens if usage else 0,
            "completion_tokens": usage.completion_tokens if usage else 0,
            "total_tokens": usage.total_tokens if usage else 0,
        }
        primary_cost = _calculate_cost(model, primary_token_usage, cfg)

        # Get variants (check task_overrides first, then per-callsite configs)
        variants = cfg.get("task_overrides", {}).get(task_id)

        # Then try per-callsite config dicts from model_config.py
        if variants is None:
            from model_config import get_capture_variants_for_task
            variants = get_capture_variants_for_task(task_id)

        # Fall back to tier-based variants (backwards compatibility)
        if variants is None:
            variants = cfg.get(f"{tier}_tier_variants", [])

        # Get source location from registered metadata
        meta = _CALLSITE_META.get(task_id, {})
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


def register_callsite(task_id, file_path, line):
    """Register file/line metadata for a task_id. Called at module import."""
    _CALLSITE_META[task_id] = {"file": file_path, "line": line}
