# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""T127: which numbered startup menu option a player's sentence picks (D-STARTUP-MENU-1, #1260).

The startup adventure and character menus resolve a bare in-range number, the
whole listed name (D-KW-6) and "new" in code, with no call. Any other line is
read by T127 (D-KW-16): the model reads the player's words against the numbered
options exactly as printed and returns one typed answer, and code acts on it.

- ``choice``: the number of the one option the line picks; code checks that it
  is one of the listed numbers and takes the same path as that typed number.
- ``question``: when the line names no option, names more than one, or is
  unclear, choice is 0 and the model's short question is shown as the DM's
  line; the menu waits for the next answer.

Code never reads the player's line: it goes to the model whole. A reply that
breaks the contract, an out-of-range number or any provider failure is
``unavailable``, and the menu prints its own "I didn't understand" line. The
call is one bounded attempt outside the live turn path, so a provider that is
down never stalls the menu."""
import json
from typing import Any, Dict, List

from core.ai import api_client
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
from utils.enhanced_logger import warning

TASK_ID = "T127"
register_callsite(TASK_ID, "core/ai/menu_answer.py", 113)

# One bounded attempt: the menu falls back to its own line rather than wait.
REQUEST_TIMEOUT_SECONDS = 30

SCHEMA = {
    "type": "object",
    "properties": {
        "choice": {"type": "integer"},
        "question": {"type": "string"},
    },
    "required": ["choice", "question"],
    "additionalProperties": False,
}

_SYSTEM = """You read one line a player typed at a numbered menu while starting a tabletop roleplaying adventure game. You are shown which menu it is, every option with its number exactly as the player saw it, and the player's whole line. Read the line as a person would and say which option it picks.

Return exactly one JSON object {"choice": <number>, "question": <text>}:
- When the line picks exactly one listed option, by its name, a clear part of its name, its description or its number in words, choice is that option's number and question is "".
- Otherwise (the line names no option, names more than one, asks something, or is unclear), choice is 0 and question is one short, friendly sentence in plain ASCII asking which listed option the player wants; you may name the options with their numbers.
Never pick an option the line does not name or clearly describe, and never pick one for the player."""


class MenuAnswerError(ValueError):
    """A T127 reply that breaks the contract (invalid JSON, a choice that is
    not an integer, a question that is not text, or choice 0 with no question)."""


def check_answer(raw: Any, numbers: List[int]) -> Dict[str, Any]:
    """The typed answer from a T127 reply, or MenuAnswerError. ``numbers`` are
    the option numbers the player saw; a choice outside them breaks the contract."""
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else None
    except ValueError as exc:
        raise MenuAnswerError("T127: invalid JSON: %s" % exc) from exc
    if not isinstance(parsed, dict):
        raise MenuAnswerError("T127: the answer must be one JSON object")
    choice, question = parsed.get("choice"), parsed.get("question")
    if type(choice) is not int:
        raise MenuAnswerError("T127: choice must be an integer, not %r" % (choice,))
    if not isinstance(question, str):
        raise MenuAnswerError("T127: question must be text")
    if choice == 0:
        if not question.strip():
            raise MenuAnswerError("T127: choice 0 needs a question")
        return {"question": question.strip()}
    if choice not in numbers:
        raise MenuAnswerError("T127: choice %d is not a listed option" % choice)
    return {"choice": choice}


def request_payload(menu: str, options: List[Dict[str, Any]], line: str) -> Dict[str, Any]:
    """The T127 request: the menu, its numbered options as printed and the
    player's whole line (nothing sliced, NEQ-LEDGER-08)."""
    return {"menu": menu, "options": options, "playerLine": line}


def _response_format(provider, config):
    """The provider's transport form of the one schema (transport only)."""
    if provider in ("openai", "legacy"):
        config["response_format"] = {"type": "json_schema", "json_schema": {
            "name": "menu_answer", "strict": True, "schema": SCHEMA}}
    elif provider == "gemini":
        from model_config import convert_to_gemini_schema

        config["response_schema"] = convert_to_gemini_schema(SCHEMA, preserve_required=True, preserve_constraints=True)
        config["response_format"] = {"type": "json_object"}
    else:
        config["response_format"] = {"type": "json_object"}
    return config


def read_menu_answer(request: Dict[str, Any]) -> Dict[str, Any]:
    """One T127 read of ``request`` (``request_payload``). Returns {"choice": n},
    {"question": text}, or {"unavailable": <diagnostic outcome>} on a contract
    defect or any provider failure. A read-only save stop re-raises."""
    import model_config
    from utils.transient_filesystem import ReadOnlySaveStop

    numbers = [option["number"] for option in request["options"]]
    try:
        provider = model_config.get_provider()
        config = _response_format(provider, model_config.resolve_callsite_config(TASK_ID, provider))
        response = capture_and_fanout(
            TASK_ID, api_client.create_completion,
            _request_provider=provider,
            _live_selected=False,
            messages=[{"role": "system", "content": _SYSTEM},
                      {"role": "user", "content": json.dumps(request, ensure_ascii=False)}],
            model=config.pop("model"),
            temperature=0.1,
            timeout=REQUEST_TIMEOUT_SECONDS,
            **config,
        )
        return check_answer(response.choices[0].message.content, numbers)
    except ReadOnlySaveStop:
        raise
    except MenuAnswerError as exc:
        warning("[Menu answer] T127 reply broke the contract; the menu asks again: %s" % exc, category="startup")
        return {"unavailable": "menu_answer_invalid"}
    except Exception as exc:
        warning("[Menu answer] T127 unavailable (%s); the menu asks again" % type(exc).__name__, category="startup")
        return {"unavailable": "menu_answer_unavailable"}
