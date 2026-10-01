"""Experience points through the rules engine (X1b).

An award is one ``adjust "<cid>" stat "xp" by <n>;`` per character: the engine
changes the declared base of ``xp`` (awards never pile up as effects), derives
``xp:next`` and ``xp:pending``, and the status view brings every total back
onto the sheet through stats.store. A negative amount corrects a mistaken
award; zero is refused by the engine (E_AMOUNT) and never sent.
"""
import copy
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.nql import apply, genesis, stats


@dataclass
class ExperienceOutcome:
    ok: bool
    sheet: Optional[Dict[str, Any]] = None
    before: Optional[int] = None
    after: Optional[int] = None
    reason: Optional[str] = None
    receipt: Optional[Dict[str, Any]] = None
    gaps: List[str] = field(default_factory=list)


def _q(value: str) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def normalize_amount(amount: Any) -> Optional[int]:
    """A signed whole number of XP, or None."""
    if isinstance(amount, bool):
        return None
    if isinstance(amount, int):
        return amount
    if isinstance(amount, float) and amount.is_integer():
        return int(amount)
    if isinstance(amount, str):
        text = amount.strip().replace(",", "")
        if text.startswith("+"):
            text = text[1:]
        try:
            return int(text)
        except ValueError:
            return None
    return None


def award(sheet: Dict[str, Any], amount: Any, *, location: str = "sheet", request_id: Optional[str] = None,
          binary: Optional[str] = None) -> ExperienceOutcome:
    """One character's XP award (or correction) through the engine; the sheet comes back with engine numbers."""
    n = normalize_amount(amount)
    if n is None:
        return ExperienceOutcome(False, reason=f"amount {amount!r} is not a whole number of XP")
    if n == 0:
        return ExperienceOutcome(False, reason="an award of 0 XP changes nothing")
    sheet = copy.deepcopy(sheet)
    world = genesis.build_world([sheet], location)
    cid = genesis.character_id(sheet)
    before = stats._int(sheet.get(stats.XP_FIELD))
    try:
        response = apply.call({"world": world.source, "world_name": "experience-genesis.nql",
                               "actions": f"adjust {_q(cid)} stat \"xp\" by {n};", "actions_name": "experience.nql",
                               "actor": {"kind": "character", "id": cid},
                               "request": request_id or f"experience:{uuid.uuid4().hex}",
                               "status": [cid]}, binary=binary)
    except apply.EngineUnavailable as error:
        return ExperienceOutcome(False, reason=str(error), gaps=world.gaps)
    if not response.get("ok"):
        fault = response.get("fault") or {}
        return ExperienceOutcome(False, reason=f"engine refused at {response.get('phase')}: "
                                 f"{response.get('diagnostics') or fault or response.get('error')}", gaps=world.gaps)
    for status in response.get("status") or []:
        who = status.get("character") if isinstance(status.get("character"), dict) else {}
        if who.get("id") != cid:
            continue
        base = None
        for record in status.get("stats") or []:
            if isinstance(record, dict) and record.get("stat") == "xp" and type(record.get("base")) is int:
                base = record["base"]
        if base is None:
            return ExperienceOutcome(False, reason="engine returned no xp base for the character", gaps=world.gaps)
        sheet[stats.XP_FIELD] = base
        stats.store(sheet, status)
        return ExperienceOutcome(True, sheet=sheet, before=before, after=base, receipt=response.get("receipt"), gaps=world.gaps)
    return ExperienceOutcome(False, reason="engine returned no status for the character", gaps=world.gaps)
