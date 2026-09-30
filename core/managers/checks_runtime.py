"""rollCheck staging, the roll prompt, and the DM Note line (C2a).

One DM call per player input, never an extra one: a check the DM asks for in
turn N is scored before the DM's turn N+1 begins, and its result line is in
that turn's DM Note. The player's dice are typed at a numbers-only roll
prompt (blank = the game rolls); the DM never converts words into dice.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional

from core.managers import checks_state
from core.managers.effects_runtime import _resolve_character
from core.nql import checks
from utils.enhanced_logger import info, warning

ROLL_TAG = "[ROLL]"
_NUMBERS = re.compile(r"^\s*(\d{1,2})(?:[\s,]+(\d{1,2}))?\s*$")


def _is_player(role: Optional[str]) -> bool:
    return str(role or "").lower() == "player"


def stage_roll_check(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a rollCheck action and either resolve it now or hold it for the roll prompt."""
    name = parameters.get("characterName")
    if not isinstance(name, str) or not name.strip():
        return {"error": "rollCheck requires characterName."}
    stat = checks.stat_id(parameters.get("check"))
    if stat is None:
        # Fail forward: the turn goes on and the DM reads why next turn.
        line = (f"{name} check {parameters.get('check')!r}: not resolved (name a skill, an ability save, an ability check "
                f"or initiative and issue rollCheck again)")
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
    checks_state.add_pending(entry)
    info(f"CHECK: pending for {resolved}: {checks.label(stat)} ({net.mode}, {entry['faces']} dice)", category="character_updates")
    return {"pending": entry}


def roll_prompt_text(entry: Dict[str, Any]) -> str:
    what = checks.label(entry["stat"])
    count = entry["faces"]
    why = f" ({entry['netMode']}" + (f" from {', '.join(entry['sources'])}" if entry.get("sources") else "") + ")" if count == 2 else ""
    dc = f" vs DC {entry['dc']}" if entry.get("dc") is not None else ""
    dice = f"roll {count}d20{why} and type " + ("both results (e.g. 15 3)" if count == 2 else "the result (e.g. 15)")
    return f"{ROLL_TAG} {what} for {entry['characterName']}{dc}: {dice}, or press Enter and the game rolls: "


def parse_faces(text: str, count: int) -> Optional[List[int]]:
    """Whole numbers 1-20 in the required count, or [] for a blank line; None when it is neither."""
    if text is None or not text.strip():
        return []
    match = _NUMBERS.match(text)
    if not match:
        return None
    faces = [int(g) for g in match.groups() if g is not None]
    if len(faces) != count or any(f < 1 or f > 20 for f in faces):
        return None
    return faces


def take_player_rolls(read: Callable[[str], str]) -> None:
    """Settle every pending player check at the roll prompt, then return to the free command."""
    while True:
        entry = checks_state.pop_pending()
        if entry is None:
            return
        faces: Optional[List[int]] = None
        for _attempt in range(5):
            faces = parse_faces(read(roll_prompt_text(entry)), entry["faces"])
            if faces is not None:
                break
            print(f"Type {entry['faces']} whole number{'s' if entry['faces'] == 2 else ''} between 1 and 20, or press Enter to let the game roll.")
        try:
            _resolved, _role, _path, sheet = _resolve_character(entry["characterName"])
            result = checks.resolve(sheet, entry["stat"], dc=entry.get("dc"), mode=entry.get("mode"), faces=faces or None)
        except Exception as exc:  # the sheet vanished or the engine is down: the DM hears why
            warning(f"CHECK: {entry['characterName']}: not resolved ({exc})", category="character_updates")
            checks_state.add_result(f"{entry['characterName']} {checks.label(entry['stat'])}: not resolved ({exc})")
            continue
        line = checks.describe(result) + (f" [{entry['reason']}]" if entry.get("reason") else "")
        checks_state.add_result(line)
        info(f"CHECK: {line}", category="character_updates")
        print(line)


def check_results_note() -> str:
    lines = checks_state.consume_results()
    if not lines:
        return ""
    return ("\nCHECK RESULTS (the rules engine scored the attempts you left unresolved last turn; open this response by narrating "
            "each outcome, then answer the new input; never re-roll or re-add): " + " | ".join(lines) + "\n")
