"""The awardExperience action (X1b): the DM names the character and the amount; the engine adds it."""
from typing import Any, Dict

from core.managers.effects_runtime import _resolve_character
from core.nql import experience
from utils.enhanced_logger import info, warning
from utils.file_operations import safe_write_json


def award_experience(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Apply one award; return {"awarded": line} or {"error": reason}. Never raises for a bad parameter."""
    name = str(parameters.get("characterName") or "").strip()
    if not name:
        return {"error": "awardExperience: characterName is required."}
    amount = experience.normalize_amount(parameters.get("amount"))
    if amount is None:
        return {"error": f"awardExperience: amount {parameters.get('amount')!r} is not a whole number of XP."}
    if amount == 0:
        return {"error": "awardExperience: an award of 0 XP changes nothing."}
    reason = str(parameters.get("reason") or "").strip()
    resolved, _role, path, sheet = _resolve_character(name)
    outcome = experience.award(sheet, amount)
    if not outcome.ok:
        return {"error": f"awardExperience: {resolved}: {outcome.reason}"}
    if not safe_write_json(path, outcome.sheet):
        return {"error": f"awardExperience: {resolved}: the sheet could not be saved."}
    pending = outcome.sheet.get("levelUpsPending")
    line = (f"{resolved}: {amount:+d} XP -> {outcome.after}/{outcome.sheet.get('exp_required_for_next_level')}"
            + (f", level-up earned ({pending})" if type(pending) is int and pending > 0 else "")
            + (f" [{reason}]" if reason else ""))
    info(f"XP: {line}", category="character_updates")
    for gap in outcome.gaps:
        warning(f"XP: {resolved}: {gap}", category="character_updates")
    return {"awarded": line}
