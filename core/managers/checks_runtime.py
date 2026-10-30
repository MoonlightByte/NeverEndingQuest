"""rollCheck staging, the player's answer to an open roll, and the DM Note line (C2a).

A submitted roll is player input: a check the DM asks for waits until the
player's next line answers it, and its result line is in the DM Note of the
turn that line starts. Bare numbers and a blank line call no model; any other
line is read by T126, and code acts on its typed answer (#1118 item 4).
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from core.managers import checks_state, roll_prompt
from core.managers.effects_runtime import _resolve_character
from core.nql import checks
from utils.enhanced_logger import info, warning


def _is_player(role: Optional[str]) -> bool:
    return str(role or "").lower() == "player"


def stage_roll_check(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a rollCheck action and either resolve it now or hold it for the player's answer."""
    name = parameters.get("characterName")
    if not isinstance(name, str) or not name.strip():
        return {"error": "rollCheck requires characterName."}
    stat = checks.stat_id(parameters.get("stat"))
    if stat is None:
        # Fail forward: the turn goes on and the DM reads why next turn.
        line = (f"{name} check {parameters.get('stat')!r}: not resolved (stat must be exactly one of "
                f"{', '.join(checks.STATS)}; issue rollCheck again)")
        checks_state.add_result(line)
        warning(f"CHECK: {line}", category="character_updates")
        return {"resolved": line}
    dc = parameters.get("dc")
    if dc is not None and (type(dc) is not int or dc < 1):
        return {"error": "rollCheck: dc must be a positive whole number or omitted."}
    mode = parameters.get("mode")
    if mode is not None and mode not in ("normal",) + checks.MODES:
        return {"error": "rollCheck: mode must be advantage, disadvantage or omitted."}
    if mode == "normal":
        mode = None
    roller = parameters.get("roller") or "player"
    if roller not in ("player", "engine"):
        return {"error": "rollCheck: roller must be player or engine."}
    resolved, role, _path, sheet = _resolve_character(name)
    reason = str(parameters.get("reason") or "").strip()
    if roller == "engine" or not _is_player(role):
        result = checks.resolve(sheet, stat, dc=dc, mode=mode)
        line = checks.describe(result) + (f" [{reason}]" if reason else "")
        checks_state.add_result(line)
        info(f"CHECK: {line}", category="character_updates")
        return {"resolved": line}
    net = checks.net_mode(sheet, stat, mode)
    if net.reason:
        warning(f"CHECK: {resolved}: roll mode not read ({net.reason}); asking for one die", category="character_updates")
    if net.mode == "fail":
        result = checks.resolve(sheet, stat, dc=dc, mode=mode)
        line = checks.describe(result) + (f" [{reason}]" if reason else "")
        checks_state.add_result(line)
        info(f"CHECK: {line}", category="character_updates")
        return {"resolved": line}
    entry = {"characterName": resolved, "stat": stat, "dc": dc, "mode": mode, "netMode": net.mode,
             "sources": net.sources, "faces": checks.faces_needed(net.mode), "reason": reason}
    if net.dice:
        # #889: an added die (Guidance, Bless) is the game's to roll.
        entry["dice"] = [{"name": d["name"], "count": d["count"], "sides": d["sides"]} for d in net.dice]
    if not checks_state.add_pending(entry):
        # #1118 item 4: a check persists across turns; asking for it again stages nothing new.
        line = f"{resolved} {checks.label(stat)}: not resolved (already waiting for the player's roll; not staged again)"
        checks_state.add_result(line)
        info(f"CHECK: {line}", category="character_updates")
        return {"resolved": line}
    info(f"CHECK: pending for {resolved}: {checks.label(stat)} ({net.mode}, {entry['faces']} dice)", category="character_updates")
    return {"pending": entry}


def fitting_faces(text: Any, count: int, sides: int) -> Any:
    """The fast path for an open roll (#1118; D-KW-1; bare numbers are values per #1118 owner direction):
    [] for a blank line or the exact D-KW-1 line (the game rolls), the faces for bare whole numbers that fit
    ``count`` dice of ``sides``, ("unfitting", values) for bare whole numbers that do not, and None for any
    other line (read by T126)."""
    from core.managers.combat_orchestrator import _FACE_LIST, _lets_the_game_roll

    if text is None or not str(text).strip() or _lets_the_game_roll(text):
        return []
    if not _FACE_LIST.match(str(text)):
        return None
    values = [int(value) for value in re.findall(r"\d+", str(text))]
    if len(values) != count or any(v < 1 or v > sides for v in values):
        return ("unfitting", values)
    return values


def parse_faces(text: str, count: int) -> Optional[List[int]]:
    """Whole numbers 1-20 in the required count, or [] for a blank line; None when it is neither."""
    if text is None or not text.strip():
        return []
    faces = fitting_faces(text, count, 20)
    return faces if isinstance(faces, list) and faces else None


def new_message_id() -> str:
    """A fresh player-output message id (the web cache keys a record by it)."""
    return f"msg-{uuid4().hex}"


def _show_check_receipt(content: str, message_id: Optional[str] = None) -> None:
    """Show the player the scored check at once (#530). The DM narrates it next turn without the numbers.
    A record shown again under its own ``message_id`` (a dice card, #1118) is not shown twice on the web."""
    from web.shared_state import emit_player_output, has_player_output_sink
    has_sink = has_player_output_sink()
    if emit_player_output({"type": "system", "content": content,
                           "message_id": message_id or new_message_id()}) is True:
        return
    if not has_sink:
        print(content)


def read_player_line(read: Callable[[str], str], prompt: str) -> str:
    """The free-command read (#1118 item 4). While a check heads the queue its panel is published for this
    read and cleared once the read returns or raises; the line read is the answer (the settle takes it)."""
    pending = checks_state.pending_checks()
    try:
        if pending:
            roll_prompt.publish({**pending[0], "label": checks.label(pending[0]["stat"])})
        return read(prompt)
    finally:
        if pending:
            roll_prompt.publish(None)


def _last_dm_narration(conversation_history: Any) -> str:
    """The DM's last narration as the player saw it (the ask T126 is shown), or ""."""
    import json

    for message in reversed(conversation_history or []):
        if isinstance(message, dict) and message.get("role") == "assistant":
            content = message.get("content")
            try:
                parsed = json.loads(content) if isinstance(content, str) else None
            except ValueError:
                parsed = None
            if isinstance(parsed, dict) and isinstance(parsed.get("narration"), str):
                return parsed["narration"]
            return content if isinstance(content, str) else ""
    return ""


def settle_pending_rolls(line: str, conversation_history: Any) -> Dict[str, Any]:
    """Settle the open roll with the line the player typed (#1118 items 3 and 4).

    The check at the head of the queue comes first; the short rest held for the
    player's hit dice is offered only when no check waits. The placement, fast
    path and result are ``settle_pending_rest``'s, plus "kind" ("check" or
    "hitDie"): the request this line answered.
    """
    pending = checks_state.pending_checks()
    if pending:
        return _settle_pending_check(pending[0], line, conversation_history)
    result = settle_pending_rest(line, conversation_history)
    result["kind"] = "hitDie"
    return result


def _settle_pending_check(entry: Dict[str, Any], line: str, conversation_history: Any) -> Dict[str, Any]:
    """A fitting answer or a request to roll scores the check, a decline closes it, and any other line
    leaves it waiting: the DM answers the line and asks again (#1118 item 4)."""
    from core.combat.invocation import InvocationSupersededError
    from utils.capture.live_provider_call import (
        LiveProviderCompletedError, LiveProviderSuperseded, get_live_turn_scope)
    from utils.transient_filesystem import ReadOnlySaveStop

    result = {"kind": "check", "pending": True, "settled": False, "unfitting": None, "readerUnavailable": False,
              "providerError": None}
    name, count = entry.get("characterName"), entry.get("faces")
    label = checks.label(entry.get("stat"))
    try:
        answer = fitting_faces(line, count, 20)
        if isinstance(answer, tuple):
            result["unfitting"] = answer[1]
            return result
        if answer is None:
            from core.ai.roll_answer import read_roll_answer, request_payload

            try:
                read = read_roll_answer(request_payload(
                    f"{label} for {name}", "check", [{"count": count, "sides": 20}], True,
                    _last_dm_narration(conversation_history), line))
            except LiveProviderCompletedError as exc:
                result["providerError"] = exc
                return result
            scope = get_live_turn_scope()
            if scope is not None and scope.is_superseded():
                return result
            kind = read.get("kind")
            if read.get("readerUnavailable"):
                result["readerUnavailable"] = True
                return result
            if kind == "decline":
                result["settled"] = checks_state.complete_pending(
                    entry, f"{name} {label}: not resolved (the player chose not to roll)")
                return result
            if kind == "let_game_roll":
                answer = []
            elif kind == "faces":
                values = read.get("values") or []
                faces = values[0] if len(values) == 1 else [v for group in values for v in group]
                if (len(values) != 1 or len(faces) != count
                        or any(type(f) is not int or f < 1 or f > 20 for f in faces)):
                    result["unfitting"] = faces
                    return result
                answer = faces
            else:
                return result
        scope = get_live_turn_scope()
        if scope is not None and scope.is_superseded():
            return result
        try:
            _resolved, _role, _path, sheet = _resolve_character(name)
            scored = checks.resolve(sheet, entry["stat"], dc=entry.get("dc"), mode=entry.get("mode"),
                                    faces=answer or None)
        except (LiveProviderSuperseded, InvocationSupersededError, ReadOnlySaveStop):
            raise
        except Exception as exc:  # the sheet vanished or the engine is down: the DM hears why
            warning(f"CHECK: {name}: not resolved ({exc})", category="character_updates")
            result["settled"] = checks_state.complete_pending(
                entry, f"{name} {label}: not resolved (rules engine unavailable)")
            return result
        result_line = checks.describe(scored) + (f" [{entry['reason']}]" if entry.get("reason") else "")
        if not checks_state.complete_pending(entry, result_line):
            return result
        result["settled"] = True
        if scored.ok:
            _show_check_receipt(checks.describe(scored))
        info(f"CHECK: {result_line}", category="character_updates")
        return result
    except (LiveProviderSuperseded, InvocationSupersededError, ReadOnlySaveStop):
        raise
    except Exception as exc:
        warning(f"CHECK: settle_failed for {name}: {type(exc).__name__}: {exc}", category="character_updates")
        result["readerUnavailable"] = True
        return result


def settle_pending_rest(line: str, conversation_history: Any) -> Dict[str, Any]:
    """Settle the short rest held for the player's hit dice with the line they typed (#1118 item 3).

    Runs inside the turn's live scope, before the DM note is built. The fast path
    (a blank line, the D-KW-1 line, bare numbers) calls no model; any other line
    is read by T126. Returns {"pending", "settled", "unfitting", "readerUnavailable",
    "providerError"}: a completed provider error from T126 is handed back (the
    turn's own policy decides), and the held rest stays.
    """
    from core.combat.invocation import InvocationSupersededError
    from utils.capture.live_provider_call import (
        LiveProviderCompletedError, LiveProviderSuperseded, get_live_turn_scope)
    from utils.transient_filesystem import ReadOnlySaveStop

    result = {"pending": False, "settled": False, "unfitting": None, "readerUnavailable": False,
              "providerError": None}
    entry = checks_state.pending_rest()
    if entry is None:
        return result
    result["pending"] = True
    name, die, count = entry.get("characterName"), entry.get("die"), entry.get("count")
    taken = False
    try:
        answer = fitting_faces(line, count, die)
        if isinstance(answer, tuple):
            result["unfitting"] = answer[1]
            return result
        if answer is None:
            from core.ai.roll_answer import read_roll_answer, request_payload

            try:
                read = read_roll_answer(request_payload(
                    f"Hit die for {name}", "hitDie", [{"count": count, "sides": die}], True,
                    _last_dm_narration(conversation_history), line))
            except LiveProviderCompletedError as exc:
                result["providerError"] = exc
                return result
            scope = get_live_turn_scope()
            if scope is not None and scope.is_superseded():
                return result
            kind = read.get("kind")
            if read.get("readerUnavailable"):
                result["readerUnavailable"] = True
                return result
            if kind == "decline":
                if not checks_state.take_pending_rest(entry):
                    return result
                taken = True
                checks_state.add_result(
                    f"{name}'s hit dice: not spent; the player chose not to roll; the short rest was not applied. "
                    + ("The Hit Die is kept; do not state a rest for it."
                       if entry.get("afterRest") is not None else
                       "The hour has already passed in the story: state the rest again now, without their hitDice "
                       "and with no new updateTime, unless the story has already cut the rest short."))
                result["settled"] = True
                return result
            if kind == "let_game_roll":
                answer = []
            elif kind == "faces":
                values = read.get("values") or []
                faces = values[0] if len(values) == 1 else [v for group in values for v in group]
                if (len(values) != 1 or len(faces) != count
                        or any(type(f) is not int or f < 1 or f > die for f in faces)):
                    result["unfitting"] = faces
                    return result
                answer = faces
            else:
                return result
        scope = get_live_turn_scope()
        if scope is not None and scope.is_superseded():
            return result
        if not checks_state.take_pending_rest(entry):
            return result
        taken = True
        _apply_held_rest(entry, answer or ["engine"] * count, conversation_history)
        result["settled"] = True
        return result
    except (LiveProviderSuperseded, InvocationSupersededError, ReadOnlySaveStop):
        raise
    except Exception as exc:
        warning(f"REST: settle_failed for {name}: {type(exc).__name__}: {exc}", category="character_updates")
        if taken:
            try:
                checks_state.add_result(_REST_SYSTEM_ERROR)
                result["settled"] = True
            except Exception as write_exc:
                warning(f"REST: could not report the settle failure: {type(write_exc).__name__}",
                        category="character_updates")
        else:
            result["readerUnavailable"] = True
        return result


_REST_SYSTEM_ERROR = (
    "Rest System Error: an unexpected error occurred while applying the rest; the pending short rest is closed, "
    "and part or all of it may already be applied. The party stats in this note show the sheets as they are now: "
    "narrate from them, and do not state the rest again.")


def _apply_held_rest(entry: Dict[str, Any], faces: List[Any], conversation_history: Any) -> None:
    """Apply the held rest with the player's faces (or "engine" per die) and report it under CHECK RESULTS."""
    from core.combat.invocation import InvocationSupersededError
    from core.managers.rest_manager import execute_rest, rest_outcome_lines
    from utils.capture.live_provider_call import LiveProviderSuperseded
    from utils.encoding_utils import safe_json_load
    from utils.transient_filesystem import ReadOnlySaveStop

    try:
        result = execute_rest(entry.get("restType"), safe_json_load("party_tracker.json") or {},
                              conversation_history, hit_dice=entry.get("hitDice"),
                              faces={entry.get("characterName"): faces}, after_rest=entry.get("afterRest"),
                              operation=entry.get("operation"))
    except (LiveProviderSuperseded, InvocationSupersededError, ReadOnlySaveStop):
        # #202 C2: a Load, Reset or Quit during a busy-sheet wait ends the turn, as a save stop does.
        raise
    except Exception as exc:
        warning(f"REST: held rest raised {type(exc).__name__}: {exc}", category="character_updates")
        checks_state.add_result(_REST_SYSTEM_ERROR)
        return
    outcome = rest_outcome_lines(result)
    if not result.get("success"):
        if entry.get("afterRest") is not None:
            tail = (". No sheet changed; the hit die offer has closed and the Hit Die is kept. Tell the player in "
                    "the story; do not state a rest for it.")
        else:
            tail = (". No sheet changed; the pending short rest is closed. The hour has already passed in the "
                    "story: state the rest again now, without that character's hitDice and with no new updateTime, "
                    "unless the story has already cut the rest short.")
        checks_state.add_result(outcome["line"] + tail)
        return
    line = outcome["line"]
    if outcome["refused"]:
        # #1239 (D-1239-2 B): the rest is applied without the refused dice. The asking response's other
        # actions were applied on its own turn; nothing from it is waiting.
        line += (" Some hit dice were not spent (this Rest line says whose and why); the rest itself is applied. "
                 "Tell the player in the story which die is kept and why, without the record's field names. Do not "
                 "state the rest again and do not move the clock.")
    checks_state.add_result(line)
    if result.get("effects_note") and isinstance(conversation_history, list):
        conversation_history.append(result["effects_note"])
    if outcome["receipt"]:
        _show_check_receipt(outcome["receipt"])


def pending_roll_note(settle_result: Optional[Dict[str, Any]] = None) -> str:
    """The PENDING ROLL line for every DM turn while a roll waits (#1118 items 3 and 4): the check at the head
    of the queue, or else the held rest, never both; DM-only, never sliced."""
    settle_result = settle_result or {}
    pending = checks_state.pending_checks()
    if pending:
        check = pending[0]
        name, faces = check.get("characterName"), check.get("faces")
        note = (f"\nPENDING ROLL: {name}'s {checks.label(check.get('stat'))} waits for the player's d20 answer. You "
                "cannot roll it or state a result. If the player's words are not that answer, answer them and ask for "
                "the roll again in your own words.")
        if settle_result.get("kind") == "check":
            note += _last_answer_tail(settle_result, f"{faces}d20")
        return note + "\n"
    entry = checks_state.pending_rest()
    if entry is None:
        return ""
    name, die, count = entry.get("characterName"), entry.get("die"), entry.get("count")
    note = (f"\nPENDING ROLL: {name}'s {count}d{die} hit dice for the short rest wait for the player's answer. You "
            "cannot roll them or state a result. If the player's words are not that answer, answer them and ask for "
            "the roll again in your own words. If the roll is no longer needed (the character is now at full hit "
            "points) or the player has moved on, do not ask: say so, and state the rest again without their hitDice "
            "and with no new updateTime; that closes this pending roll. If you call for a check this turn, ask for "
            "that check only.")
    if settle_result.get("kind", "hitDie") == "hitDie":
        note += _last_answer_tail(settle_result, f"{count}d{die}")
    return note + "\n"


def _last_answer_tail(settle_result: Dict[str, Any], dice: str) -> str:
    """What the DM hears about the player's last line when it did not settle the roll."""
    if settle_result.get("unfitting") is not None:
        values = ", ".join(str(v) for v in settle_result["unfitting"])
        return f" Their last answer, {values}, does not fit {dice}."
    if settle_result.get("readerUnavailable") or settle_result.get("providerError") is not None:
        return " The game could not read their last line as an answer to this roll."
    return ""


LAST_NOTE = ""  # the CHECK RESULTS delivered with the current turn's DM note (the validator reviews against it)

# A read of a person or a scene: the character's own silent observation.
_READ = re.compile(r"^(?P<who>.+?) (?P<skill>Insight|Perception) check\b(?!: not resolved)")


def read_note(line: str) -> str:
    """The narration rule for a scored read, beside its result. Replays of a
    successful Insight read on an NPC whose record says she admits a secret
    had her confess it in every draft while this rule lived only in the system
    prompt; next to the result, no draft did, and pressing her still did."""
    match = _READ.match(line)
    if not match:
        return ""
    who, skill = match.group("who"), match.group("skill")
    return (f"READ ({who}'s {skill}): a silent observation; no one in the scene knows a check was made. Narrate only what "
            f"{who} notices (tells, tension, a mismatch between words and body, a detail out of place) and what it suggests; "
            "on a failure the surface stays consistent or the signs are ambiguous. In this response no NPC confesses, explains "
            "or names what they are hiding, even if their record says they admit it: that disclosure waits until the player "
            "presses, asks or persuades them. Then stop and leave the next move to the player.\n")


def check_results_note(turn_marker=None) -> str:
    """turn_marker: the count of DM replies in the history (the turn this note is for); see checks_state.consume_results."""
    global LAST_NOTE
    lines = checks_state.consume_results(turn_marker)
    if not lines:
        LAST_NOTE = ""
        return ""
    LAST_NOTE = ("\nCHECK RESULTS (the rules engine settled the rolls and actions you left open last turn; open this response by "
                 "narrating each outcome in story terms, then answer the new input; never re-roll or re-add; the player already "
                 "sees these numbers on the dice receipt, so do not restate dice, bonus, total, DC or margin; a not-resolved, "
                 "declined or Rest line has no success or failure: tell the player what happened): "
                 + " | ".join(lines) + "\n" + "".join(read_note(line) for line in lines))
    return LAST_NOTE


LAST_REST_OFFERS: List[Dict[str, Any]] = []  # the open Hit Die offers in the current turn's DM note (#1472)


def rest_offers_note() -> str:
    """The open Hit Die offers after a short rest (#1472), rebuilt for every DM turn while they are open.

    Building the note ends the previous turn: an offer still unstamped takes the
    clock now (after all of its rest turn's actions), and one whose clock moved
    on closes. DM-only text; the DM decides whether and when to raise it."""
    global LAST_REST_OFFERS
    from core.nql import game_clock

    LAST_REST_OFFERS = checks_state.settle_rest_offers(game_clock.clock_tick())
    return "".join(
        f"\nREST (open offer): {o['name']} (id {o['characterId']}) ended a short rest at HP {o['hp']}/{o['maxHp']} "
        f"with {o['left']} Hit Dice (d{o['die']}) unspent; at most {o['offer']} can heal. The player decides whether "
        "to spend them; you decide whether and when to raise it, in story terms, without these field names. If the "
        f'player chooses to spend, record rest {{"restType": "short", "afterRest": "{o["restId"]}", "hitDice": '
        f'{{"{o["characterId"]}": n}}}} with no updateTime. The offer ends when time moves on.'
        for o in LAST_REST_OFFERS)


LAST_QUEST_NOTES: List[str] = []  # the travel quest refusals in the current turn's DM note (#1122)


def quest_notes_note(turn_marker=None) -> str:
    """#1122: each updatePlot the engine refused during the last travel, once (handed again
    if that turn never landed). DM-only text; the DM decides whether to record it later."""
    global LAST_QUEST_NOTES
    LAST_QUEST_NOTES = checks_state.consume_quest_notes(turn_marker)
    return "".join("\n" + text for text in LAST_QUEST_NOTES)


def _quest_notes_validation() -> str:
    if not LAST_QUEST_NOTES:
        return ""
    return ("\nThe DM Note carried engine notices of quest updates refused during the last travel: "
            + " | ".join(LAST_QUEST_NOTES)
            + " The DM may record them now if the story supports it, or not; neither is invalid on that account.")


def _rest_offers_validation() -> str:
    if not LAST_REST_OFFERS:
        return ""
    return ("\nOpen REST offers this turn (engine-issued; the DM may raise them or not, and is never required to): "
            + "; ".join(f"{o['restId']} for {o['name']} ({o['characterId']}), at most {o['offer']} hit dice"
                        for o in LAST_REST_OFFERS)
            + ". A rest with afterRest naming one of these, restType short and hitDice for that character only, "
              "with no updateTime, is the spend at the end of that rest: valid, not a new rest, and needs no "
              "updateTime. An afterRest naming any other id is invalid.")


def _pending_validation() -> str:
    """#1118 items 3 and 4: the validator's part while a roll waits for the player's answer. The restated-rest
    close applies only when the held rest is the roll being asked for (no check waits)."""
    check = bool(checks_state.pending_checks())
    if not check and checks_state.pending_rest() is None:
        return ""
    return ("\nA roll is pending. A candidate that answers the player and asks for that roll again, with no result "
            "narrated and no rest action, is valid."
            + ("" if check else " For a pending short rest, a candidate that closes it by restating the rest without "
               "the player's hitDice, with no new updateTime, is valid.")
            + " A candidate that narrates a result for it is invalid.")


def validation_context() -> str:
    """What the validator must know: the engine already scored these checks and the DM was told to narrate them."""
    if not LAST_NOTE:
        return (_rest_offers_validation() + _pending_validation() + _quest_notes_validation()).lstrip("\n")
    return ("The Dungeon Master Note for this turn carried the rules engine's scored check results below. The candidate "
            "is REQUIRED to narrate each outcome (success or failure and what it means in the scene) as a settled fact; "
            "a candidate that calls such a check pending or unresolved, contradicts its success or failure, or asks for "
            "the dice of a scored check line again, is invalid. The dice, bonus, total, DC and margin are the engine's and the player already "
            "sees them on the dice receipt: do NOT require the narration to state any of these numbers, and do not reject "
            "a candidate for leaving them out. The DM never scores a number the player typed; only these lines are results. A READ "
            "line governs how its read is narrated: a candidate in which an NPC confesses, explains or names what they are "
            "hiding in answer to that read is invalid." + LAST_NOTE + _rest_offers_validation() + _pending_validation()
            + _quest_notes_validation())
