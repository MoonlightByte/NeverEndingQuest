"""Multi-model capture and fanout wrapper.

Primary call runs synchronously and returns immediately.
All other variants fire in background threads via ThreadPoolExecutor.
"""
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import model_config
from utils.capture.file_writer import CaptureFileWriter
from utils.capture.openai_caller import call_openai_variant
from utils.capture.gemini_caller import call_gemini_variant

# Shared thread pool - initialized once
_executor = ThreadPoolExecutor(max_workers=8)
_writer = None
_config = None
_config_lock = threading.Lock()
_error_logger = None


def _get_error_logger():
    global _error_logger
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


def _fire_background_variant(variant, task_id, messages, timestamp,
                              caller_temperature, caller_kwargs):
    """Execute one variant call and write result. Runs in thread pool."""
    label = variant["label"]
    writer = _get_writer()
    try:
        if variant["provider"] == "openai":
            content, latency_s = call_openai_variant(
                variant, messages, caller_temperature, caller_kwargs
            )
        else:
            content, latency_s = call_gemini_variant(
                variant, messages, caller_temperature, caller_kwargs
            )
        writer.merge_background_output(task_id, timestamp, label, content, latency_s)
    except Exception as e:
        error_str = f"{type(e).__name__}: {e}"
        writer.merge_background_error(task_id, timestamp, label, error_str)
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
    # Always fire primary call synchronously
    start = time.time()
    response = primary_fn(messages=messages, **kwargs)
    primary_latency = round(time.time() - start, 3)

    # If capture disabled, return immediately
    if not getattr(model_config, "MULTI_MODEL_CAPTURE", False):
        return response

    cfg = _load_config()
    if not cfg.get("capture_enabled", False):
        return response

    # Gather call metadata
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    model = kwargs.get("model", "unknown")
    tier = _determine_tier(model)
    caller_temperature = kwargs.get("temperature")
    caller_kwargs = {k: v for k, v in kwargs.items() if k not in ("model", "messages")}

    # Build input record
    input_data = {"messages": messages}
    if caller_temperature is not None:
        input_data["temperature"] = caller_temperature
    if "reasoning_effort" in kwargs:
        input_data["reasoning_effort"] = kwargs["reasoning_effort"]

    primary_content = response.choices[0].message.content
    primary_label = f"{model}|baseline"

    # Get variants (check task_overrides first)
    variants = cfg.get("task_overrides", {}).get(task_id)
    if variants is None:
        variants = cfg.get(f"{tier}_tier_variants", [])

    # Get source location from registered metadata
    meta = _CALLSITE_META.get(task_id, {})
    writer = _get_writer()
    writer.write_primary(
        task_id=task_id,
        file_path=meta.get("file", "unknown"),
        line=meta.get("line", 0),
        tier=tier,
        input_data=input_data,
        label=primary_label,
        content=primary_content,
        latency_s=primary_latency,
        timestamp=timestamp,
    )

    # Fire all non-baseline variants in background
    for variant in variants:
        # Skip re-firing the exact same model as the primary baseline
        if (variant.get("model") == model
                and variant.get("reasoning_effort") is None
                and not variant.get("thinking_level")):
            continue
        _executor.submit(
            _fire_background_variant,
            variant, task_id, messages, timestamp, caller_temperature, caller_kwargs
        )

    return response


# Callsite metadata registry
_CALLSITE_META = {}


def register_callsite(task_id, file_path, line):
    """Register file/line metadata for a task_id. Called at module import."""
    _CALLSITE_META[task_id] = {"file": file_path, "line": line}
