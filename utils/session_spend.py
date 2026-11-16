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
# #2033: what an in-game module build (and its follow-up announcement) cost,
# also counted in the session fields above. Never in the turn fields.
_BUILD_FIELDS = ("build_calls", "build_usd")

_state = {}
_turn_key = None
_priced_at = ""
_failed = False


def _zero():
    values = {name: 0 for name in _SESSION_FIELDS + _TURN_FIELDS + _BUILD_FIELDS}
    values["usd"] = 0.0
    values["turn_usd"] = 0.0
    values["build_usd"] = 0.0
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


def record_generation(request_model, usage, *, provider="openai", turn_key=None, build=False):
    """Count one successful provider generation.

    ``request_model`` is the model id the request named; ``usage`` is the
    envelope's typed usage dict; ``turn_key`` is the live turn's operation id
    (advisory calls share their turn's id). ``build`` marks a module build's
    generation (#2033): it counts in the session and build fields and never
    in, or resets, the turn's. Never raises.
    """
    global _priced_at, _failed
    try:
        usage_known = isinstance(usage, dict)
        usage = usage if usage_known else {}
        prompt = _count(usage.get("prompt_tokens"))
        cached = _count(usage.get("cached_tokens"))
        completion = _count(usage.get("completion_tokens"))
        usd, priced_at = (None, "")
        # #2033: usage the response did not carry (None, not a dict) is
        # unpriced, never $0. Route L always passes a dict.
        if provider == "openai" and usage_known:
            usd, priced_at = _price(request_model, prompt, cached, completion)
        with _LOCK:
            if build:
                _state["build_calls"] += 1
            else:
                _enter_turn(turn_key)
                _state["turn_calls"] += 1
            _state["calls"] += 1
            _state["prompt"] += prompt
            _state["cached"] += cached
            _state["completion"] += completion
            if usd is None:
                if provider == "openai":
                    _state["unpriced"] += 1
            else:
                _state["usd"] += usd
                if build:
                    _state["build_usd"] += usd
                else:
                    _state["turn_usd"] += usd
                _priced_at = max(_priced_at, priced_at)
    except Exception:
        _failed = True


def record_possibly_billed(*, turn_key=None, build=False):
    """Count one failed generation that may have been billed (#1342's billed
    phases). Its usage is unknown, so it adds no dollars. A build's (#2033)
    does not enter or reset the turn. Never raises."""
    global _failed
    try:
        with _LOCK:
            if not build:
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
        "build_calls": values["build_calls"],
        "build_usd": round(values["build_usd"], 4),
        "priced_at": priced_at or _catalog_date(),
        "provider_kind": provider_kind if provider_kind in ("openai", "gemini", "local") else "local",
        "available": not failed,
    }


# --- #2036: a fight's helper processes report their spend to the game -------
# The encounter builder (and the NPC builder inside it) and its monster
# builders call the provider in their own processes, where no live scope is
# open, so their calls never reached this counter. Each such process is given
# a sink: the result directory its game-side waiter already made. Route P then
# appends one line per attempt to <dir>/spend-<pid>-<run>.jsonl, and the game
# reads every line once, before it removes the directory, under the scope that
# was open when the fight started. A line holds numbers and the catalog id
# only: no key, URL, prompt or reply text. It is never printed or logged.

_CHILD_PHASES = ("sent", "done", "possibly_billed", "failed")
_CHILD_PROVIDERS = ("openai", "gemini", "local")
_CHILD_USAGE_KEYS = (
    "prompt_tokens", "completion_tokens", "total_tokens", "cached_tokens", "reasoning_tokens",
)
_CHILD_TOKEN_CAP = 10_000_000
_CHILD_MAX_BYTES = 1_000_000
_CHILD_MAX_LINES = 10_000
_CHILD_MODEL_MAX = 200
_child_lock = threading.Lock()
_child_sink = None  # (directory, run id) in a helper process; None elsewhere
_child_seq = 0


def set_child_sink(directory):
    """Point this helper process's Route P spend lines at ``directory`` (a run
    id is made here, once), or clear the sink with None."""
    global _child_sink, _child_seq
    import uuid

    with _child_lock:
        _child_sink = (str(directory), uuid.uuid4().hex) if directory else None
        _child_seq = 0


def child_sink_set():
    return _child_sink is not None


def _child_write(entry):
    import json
    import os

    with _child_lock:
        sink = _child_sink
        if sink is None:
            return None
        directory, run = sink
        if not os.path.isdir(directory):
            return None  # stopped: the waiter already removed the directory
        line = dict(entry, run=run)
        path = os.path.join(directory, "spend-%d-%s.jsonl" % (os.getpid(), run))
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(line, separators=(",", ":")) + "\n")
        return line


def child_sent(model, provider):
    """One Route P attempt is about to be sent from a helper process: write its
    ``sent`` line and return its seq, or None without a sink. Never raises."""
    global _child_seq
    try:
        with _child_lock:
            if _child_sink is None:
                return None
            _child_seq += 1
            seq = _child_seq
        written = _child_write({
            "seq": seq, "phase": "sent", "model": str(model or "")[:_CHILD_MODEL_MAX],
            "provider": provider, "usage": None,
        })
        return seq if written is not None else None
    except Exception:
        return None


def child_end(seq, phase, model, provider, usage=None):
    """The end of attempt ``seq``: done (with usage or None), possibly_billed or
    failed. Never raises."""
    try:
        if seq is None or phase not in _CHILD_PHASES[1:]:
            return
        _child_write({
            "seq": seq, "phase": phase, "model": str(model or "")[:_CHILD_MODEL_MAX],
            "provider": provider,
            "usage": {key: int(usage.get(key) or 0) for key in _CHILD_USAGE_KEYS}
            if isinstance(usage, dict) else None,
        })
    except Exception:
        pass


def _child_usage(value):
    if value is None:
        return True, None
    if not isinstance(value, dict) or set(value) != set(_CHILD_USAGE_KEYS):
        return False, None
    for key in _CHILD_USAGE_KEYS:
        count = value[key]
        if type(count) is not int or count < 0 or count > _CHILD_TOKEN_CAP:
            return False, None
    return True, dict(value)


def _child_line(raw):
    import json

    try:
        line = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(line, dict):
        return None
    run, seq, phase = line.get("run"), line.get("seq"), line.get("phase")
    model, provider = line.get("model"), line.get("provider")
    if not (isinstance(run, str) and len(run) == 32 and all(c in "0123456789abcdef" for c in run)):
        return None
    if type(seq) is not int or seq < 0 or phase not in _CHILD_PHASES:
        return None
    if not isinstance(model, str) or len(model) > _CHILD_MODEL_MAX or provider not in _CHILD_PROVIDERS:
        return None
    ok, usage = _child_usage(line.get("usage"))
    if not ok:
        return None
    return {"run": run, "seq": seq, "phase": phase, "model": model, "provider": provider, "usage": usage}


def _child_file_lines(path):
    """The accepted lines of one file, inside the bounds; a last line with no
    newline is a partial write and is skipped."""
    with open(path, "rb") as handle:
        data = handle.read(_CHILD_MAX_BYTES + 1)
    data = data[:_CHILD_MAX_BYTES]
    rows = data.split(b"\n")
    complete = rows[:-1]  # the piece after the last newline is partial (or empty)
    out = []
    for raw in complete[:_CHILD_MAX_LINES]:
        try:
            line = _child_line(raw.decode("utf-8"))
        except UnicodeDecodeError:
            line = None
        if line is not None:
            out.append(line)
    return out


def record_child_spend(directory, scope):
    """Game side, before the helper's result directory is removed: count every
    attempt its helpers wrote, under ``scope`` (the live scope read when the
    fight started; None records nothing, as Route P). Paired by (run, seq):
    done is a call, possibly_billed is possibly billed, failed is nothing, and
    a sent with no end (the helper died or was stopped mid-attempt) is possibly
    billed. Returns the number of attempts counted. Never raises."""
    if scope is None or not directory:
        return 0
    try:
        import glob
        import os

        from utils.capture.live_provider_call import _spend_is_build

        attempts = {}
        for path in sorted(glob.glob(os.path.join(directory, "spend-*.jsonl"))):
            try:
                if os.path.islink(path) or not os.path.isfile(path):
                    continue
                lines = _child_file_lines(path)
            except OSError:
                continue
            for line in lines:
                slot = attempts.setdefault((line["run"], line["seq"]), {})
                slot.setdefault(line["phase"], line)
        build = _spend_is_build(scope)
        turn_key = getattr(scope, "operation_id", None)
        counted = 0
        for key in sorted(attempts):
            slot = attempts[key]
            if "done" in slot:
                line = slot["done"]
                record_generation(line["model"], line["usage"], provider=line["provider"],
                                  turn_key=turn_key, build=build)
            elif "possibly_billed" in slot:
                record_possibly_billed(turn_key=turn_key, build=build)
            elif "failed" in slot:
                continue
            elif "sent" in slot:
                record_possibly_billed(turn_key=turn_key, build=build)
            else:
                continue
            counted += 1
        return counted
    except Exception:
        return 0
