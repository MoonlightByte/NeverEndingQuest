# SPDX-FileCopyrightText: 2026 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""What this play session has cost the player, as typed counters (#1388).

One module-level counter, filled where every live provider call returns
(utils/capture/live_provider_call.py) and where the portrait and voice
handlers get their answer. It keeps numbers only: no key, prompt, message,
task id, path or provider error text ever reaches it, so the snapshot it
hands the web UI is safe to send as it is.

Dollars are an estimate at the owner's list prices in
model_registry.MODEL_CATALOG, priced by the model the REQUEST named (the
catalog id). The response's model can be a dated snapshot name that the
catalog does not hold, so it is never used for pricing.
"""

import threading

_LOCK = threading.Lock()

_SESSION_FIELDS = (
    "calls", "prompt", "cached", "completion", "usd",
    "unpriced", "possibly_billed", "portraits", "voice",
)
_TURN_FIELDS = ("turn_calls", "turn_usd")

_state = {}
_turn_key = None
_priced_at = ""
_failed = False


def _zero():
    values = {name: 0 for name in _SESSION_FIELDS + _TURN_FIELDS}
    values["usd"] = 0.0
    values["turn_usd"] = 0.0
    return values


def reset_session():
    """Start the counters over: a new game, a load or a reset."""
    global _state, _turn_key, _priced_at, _failed
    with _LOCK:
        _state = _zero()
        _turn_key = None
        _priced_at = ""
        _failed = False


reset_session()


def _price(model_id, prompt, cached, completion):
    """(usd, priced_at) at the catalog's list prices, or (None, "") when the
    catalog has no entry for this id."""
    from model_registry import MODEL_CATALOG

    entry = MODEL_CATALOG.get(model_id) if isinstance(model_id, str) else None
    if entry is None:
        return None, ""
    cached = min(cached, prompt)
    usd = (
        (prompt - cached) * entry.input_usd_per_million
        + cached * entry.cached_input_usd_per_million
        + completion * entry.output_usd_per_million
    ) / 1_000_000
    return usd, entry.pricing_source_date


def _count(value):
    return value if type(value) is int and value > 0 else 0


def _enter_turn(turn_key):
    global _turn_key
    if turn_key != _turn_key:
        _turn_key = turn_key
        _state["turn_calls"] = 0
        _state["turn_usd"] = 0.0


def record_generation(request_model, usage, *, provider="openai", turn_key=None):
    """Count one successful provider generation.

    ``request_model`` is the model id the request named; ``usage`` is the
    envelope's typed usage dict; ``turn_key`` is the live turn's operation id
    (advisory calls share their turn's id). Never raises.
    """
    global _priced_at, _failed
    try:
        usage = usage if isinstance(usage, dict) else {}
        prompt = _count(usage.get("prompt_tokens"))
        cached = _count(usage.get("cached_tokens"))
        completion = _count(usage.get("completion_tokens"))
        usd, priced_at = (None, "")
        if provider == "openai":
            usd, priced_at = _price(request_model, prompt, cached, completion)
        with _LOCK:
            _enter_turn(turn_key)
            _state["calls"] += 1
            _state["turn_calls"] += 1
            _state["prompt"] += prompt
            _state["cached"] += cached
            _state["completion"] += completion
            if usd is None:
                if provider == "openai":
                    _state["unpriced"] += 1
            else:
                _state["usd"] += usd
                _state["turn_usd"] += usd
                _priced_at = max(_priced_at, priced_at)
    except Exception:
        _failed = True


def record_possibly_billed(*, turn_key=None):
    """Count one failed generation that may have been billed (#1342's billed
    phases). Its usage is unknown, so it adds no dollars. Never raises."""
    global _failed
    try:
        with _LOCK:
            _enter_turn(turn_key)
            _state["possibly_billed"] += 1
    except Exception:
        _failed = True


def record_other(kind):
    """Count one portrait or voice clip. They bill per item, not per token,
    and are not priced. Never raises."""
    global _failed
    try:
        field = {"portrait": "portraits", "voice": "voice"}[kind]
        with _LOCK:
            _state[field] += 1
    except Exception:
        _failed = True


def _catalog_date():
    """The newest list-price date in the catalog, for the disclaimer before
    the first priced call."""
    try:
        from model_registry import MODEL_CATALOG

        return max(entry.pricing_source_date for entry in MODEL_CATALOG.values())
    except Exception:
        return ""


def snapshot(provider_kind="openai"):
    """The typed ``spend`` object for the token_update event: numbers and two
    short strings, nothing else."""
    with _LOCK:
        values = dict(_state)
        priced_at = _priced_at
        failed = _failed
    return {
        "calls": values["calls"],
        "usd": round(values["usd"], 4),
        "prompt": values["prompt"],
        "cached": values["cached"],
        "completion": values["completion"],
        "turn_calls": values["turn_calls"],
        "turn_usd": round(values["turn_usd"], 4),
        "unpriced": values["unpriced"],
        "possibly_billed": values["possibly_billed"],
        "portraits": values["portraits"],
        "voice": values["voice"],
        "priced_at": priced_at or _catalog_date(),
        "provider_kind": provider_kind if provider_kind in ("openai", "gemini", "local") else "local",
        "available": not failed,
    }
