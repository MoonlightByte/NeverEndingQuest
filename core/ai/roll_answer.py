# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""T126: what a player's line says about the roll the game is waiting for (#1118).

Where code holds an open roll and acts on the player's reply before any model
call (a code-issued attack or damage phase; later a pending check or hit die),
the kept fast path runs first: a blank line, the D-KW-1 control line, the dice
tray sentence and bare numbers never call a model. Any other line is read by
T126 (D-KW-16/D-KW-17): the model reads the words and returns one typed answer,
and code acts on it.

- ``let_game_roll``: the player asks the game to roll the requested dice.
- ``faces``: the numbers the player says they rolled, one list per dice term,
  exactly as given. Whether they fit the dice is the site's compare.
- ``decline``: the player gives this roll up (takes the action back, or wants
  to do something else instead).
- ``other``: anything else (a question, a remark, doing something first while
  still meaning to roll); the roll stays open.

Code never reads the player's line or the open ask: both go to the model whole.
A completed provider refusal and a supersession re-raise; a reply that breaks
the contract, or any other failure, is ``other`` with ``readerUnavailable``
(D-1118-7 A), so the site keeps the roll open or hands it back."""
import json
from typing import Any, Dict, List, Optional

from core.ai import api_client
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
from utils.enhanced_logger import warning

TASK_ID = "T126"
register_callsite(TASK_ID, "core/ai/roll_answer.py", 122)

KINDS = ("let_game_roll", "faces", "decline", "other")

# No count, range or length bounds and no oneOf: the fit is the site's compare,
# and the Gemini converter keeps such bounds and takes only a first oneOf branch.
SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": list(KINDS)},
        "values": {"type": "array", "items": {"type": "array", "items": {"type": "integer"}}},
    },
    "required": ["kind", "values"],
    "additionalProperties": False,
}

_SYSTEM = """You read one line a player typed while the game is waiting for a dice roll in a tabletop roleplaying game. You are shown the roll the game asked for, the ask the player saw, and the player's whole line. Read the line as a person at the table would, and say what it means for this roll.

Return exactly one JSON object {"kind": ..., "values": [...]} where kind is one of:
- "let_game_roll": the player asks the game to roll it. The player asks the game to roll when they ask the DM or the game to make this roll for them.
- "faces": the player says what they rolled for this roll. Put the numbers in values, one list per dice term in the order the request lists its dice, exactly as the player gave them, even a number the die cannot show or fewer numbers than dice. When eachDie is false and the phase is not "attack", the roll takes one total: when the player states that total, values is [[total]], not the dice that made it.
- "decline": the player gives this roll up: they take the action back, change their mind, say they would rather do something else, or name a different action to take instead of this one, even before they say what it is.
- "other": anything else: a question, a remark, an unclear line, or something the player does before rolling while still meaning to make this roll.

Numbers meant for a later die or for something else are not this roll's faces. A line that mentions dice but does not ask the game to roll is not "let_game_roll". values is [] unless kind is "faces"."""


class RollAnswerError(ValueError):
    """A T126 reply that breaks the contract (invalid JSON, a kind outside the
    four, values that are not lists of integers)."""


def check_answer(raw: Any) -> Dict[str, Any]:
    """The typed answer from a T126 reply, or RollAnswerError. It checks the
    contract only; whether faces fit the dice is decided at the site."""
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else None
    except ValueError as exc:
        raise RollAnswerError("T126: invalid JSON: %s" % exc) from exc
    if not isinstance(parsed, dict):
        raise RollAnswerError("T126: the answer must be one JSON object")
    kind = parsed.get("kind")
    if kind not in KINDS:
        raise RollAnswerError("T126: kind must be one of %s, not %r" % (", ".join(KINDS), kind))
    if kind != "faces":
        return {"kind": kind}
    values = parsed.get("values")
    if not (isinstance(values, list)
            and all(isinstance(group, list) and all(type(face) is int for face in group) for group in values)):
        raise RollAnswerError("T126: values must be an array of arrays of integers")
    return {"kind": "faces", "values": values}


def request_payload(label: str, phase: str, dice: List[Dict[str, int]], each_die: bool,
                    asked: Optional[str], line: str) -> Dict[str, Any]:
    """The T126 request: the typed roll, the ask as the player saw it and the
    player's whole line (nothing sliced, NEQ-LEDGER-08)."""
    return {"request": {"label": label, "phase": phase, "dice": dice, "eachDie": bool(each_die)},
            "asked": asked or "", "playerLine": line}


def _response_format(provider, config):
    """The provider's transport form of the one schema (transport only)."""
    if provider in ("openai", "legacy"):
        config["response_format"] = {"type": "json_schema", "json_schema": {
            "name": "roll_answer", "strict": True, "schema": SCHEMA}}
    elif provider == "gemini":
        from model_config import convert_to_gemini_schema

        config["response_schema"] = convert_to_gemini_schema(SCHEMA, preserve_required=True, preserve_constraints=True)
        config["response_format"] = {"type": "json_object"}
    else:
        config["response_format"] = {"type": "json_object"}
    return config


def read_roll_answer(request: Dict[str, Any]) -> Dict[str, Any]:
    """One T126 read of ``request`` (``request_payload``). Inside a live turn
    scope T126 is a required call: a transport failure is reissued by the scope
    until it recovers or is superseded. Returns the typed answer, or
    {"kind": "other", "readerUnavailable": <diagnostic outcome>} on a contract
    defect or any other failure."""
    import model_config
    from core.combat.invocation import InvocationSupersededError
    from utils.capture.live_provider_call import LiveProviderCompletedError, LiveProviderSuperseded
    from utils.transient_filesystem import ReadOnlySaveStop

    try:
        provider = model_config.get_provider()
        config = _response_format(provider, model_config.resolve_callsite_config(TASK_ID, provider))
        response = capture_and_fanout(
            TASK_ID, api_client.create_completion,
            _request_provider=provider,
            messages=[{"role": "system", "content": _SYSTEM},
                      {"role": "user", "content": json.dumps(request, ensure_ascii=False)}],
            model=config.pop("model"),
            temperature=0.1,
            **config,
        )
        return check_answer(response.choices[0].message.content)
    except (LiveProviderSuperseded, InvocationSupersededError, ReadOnlySaveStop, LiveProviderCompletedError):
        raise
    except RollAnswerError as exc:
        warning("[Roll answer] T126 reply broke the contract; the roll stays open: %s" % exc, category="combat_events")
        return {"kind": "other", "readerUnavailable": "roll_answer_invalid"}
    except Exception as exc:
        warning("[Roll answer] T126 unavailable (%s); the roll stays open" % type(exc).__name__,
                category="combat_events")
        return {"kind": "other", "readerUnavailable": "roll_answer_unavailable"}
