"""Request-local DM delivery guidance, after compression and review context."""
from functools import lru_cache
from pathlib import Path

_STORY_ROLES = ("user", "assistant")


@lru_cache(maxsize=1)
def narration_delivery_prompt():
    return (Path(__file__).resolve().parents[1] / "prompts" /
            "narration_delivery.txt").read_text(encoding="utf-8").strip()


@lru_cache(maxsize=1)
def opening_scene_prompt():
    return (Path(__file__).resolve().parents[1] / "prompts" /
            "opening_scene.txt").read_text(encoding="utf-8").strip()


def _location_text(party_tracker):
    conditions = (party_tracker or {}).get("worldConditions") or {}
    name = conditions.get("currentLocation")
    if not name:
        return "the starting location"
    text = str(name)
    if conditions.get("currentLocationId"):
        text += " (%s)" % conditions["currentLocationId"]
    if conditions.get("currentArea"):
        text += " in %s" % conditions["currentArea"]
    return text


def with_opening_scene(messages, party_tracker=None):
    """A fresh adventure (no player or narrator turn yet) asks for an opening
    scene. Request-local like the delivery overlay: never persisted, so the
    history stays empty until the opening is accepted and a fresh start is
    never mistaken for a game in progress."""
    result = list(messages)
    if any(isinstance(m, dict) and m.get("role") in _STORY_ROLES for m in result):
        return result
    try:
        note = opening_scene_prompt().replace("{location}", _location_text(party_tracker))
    except OSError:
        return result
    result.append({"role": "user", "content": note})
    return result


def with_narration_delivery(messages):
    """Keep the complete conversation intact; never persist this request overlay."""
    prompt = narration_delivery_prompt()
    result = list(messages)
    if not result or result[-1] != {"role": "system", "content": prompt}:
        result.append({"role": "system", "content": prompt})
    return result
