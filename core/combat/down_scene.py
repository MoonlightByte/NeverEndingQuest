# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Down-scene rules text and player-facing down-state texts (#242, D-242-1..6).

House rule: there are no death saves. A party member at 0 HP is unconscious
(or exhausted, as the scene reads), stable, and cannot act; they die only if
the whole party falls. This module renders ONE rules string for every
DM-facing model call while any party member is down, plus the constants the
prompt lines and sink lines use. It never decides anything: every input is a
value read from the encounter or the sheets, and the text is rendered once,
byte-identical on every surface.
"""

import re

from core.managers.combat_state import is_down, sheet_is_down

__all__ = [
    "GO_ON_TOKEN",
    "COMBAT_DOWN_SINK_LINE",
    "MAIN_DOWN_SINK_LINE",
    "COMBAT_DOWN_BANNER",
    "MAIN_DOWN_BANNER",
    "TPK_BANNER_CONTROLS",
    "TPK_BANNER_TERMINAL",
    "TPK_PAUSE_TEXT",
    "TABLE_TALK_PREFIX",
    "DOWN_RULES_MARKER",
    "PRESENT_DOWN_MARKER",
    "present_down_text",
    "present_from_sheets",
    "from_encounter",
    "from_sheets",
    "sheet_is_down",
    "is_go_on",
]

# Exact full-line control command (same class as the existing quit/reset
# words at the travel-recovery menu); compared with strip().lower(), never
# matched inside prose.
GO_ON_TOKEN = "go on"

COMBAT_DOWN_SINK_LINE = (
    "You are down and cannot act. Your companions and the enemies take this "
    "round on their own. Anything you send now is you at the table, speaking "
    "to your companions - not {name} acting or speaking. Send '{token}' to let "
    "the round run. Save and Load work as always."
)
MAIN_DOWN_SINK_LINE = (
    "You are down and cannot act. Anything you send now is you at the table, "
    "speaking to your companions - not {name} acting or speaking. Your "
    "companions will tend to you as they see fit, or as you ask. Save and "
    "Load work as always."
)
# Banner suffixes: appended after the [date][time][HP][XP] prefix the headless
# and web clients parse (the main prompt's [date] is #642's; the combat prompt
# has none); the suffixes never change the prefix bytes.
COMBAT_DOWN_BANNER = "{name} is down - table talk, or '{token}':"
MAIN_DOWN_BANNER = "{name} is down - table talk:"
TPK_BANNER_CONTROLS = "Your party has fallen - Load, Reset, or Quit:"
TPK_BANNER_TERMINAL = (
    "Your party has fallen - press Ctrl+C to close, then Load or Reset from "
    "the launcher:"
)
TPK_PAUSE_TEXT = (
    "Your whole party has fallen. No further turns were taken. This fight "
    "cannot go on from here. Load a save to return to an earlier moment, or "
    "Reset the campaign."
)
TABLE_TALK_PREFIX = (
    "Table talk from the player (the character is unconscious and cannot act; "
    "the tactical model may reflect it in companion intents as their own "
    "judgment, never as the character's words or an order they must obey): "
)
# Marker constant for the dedicated conversation-history system entry
# (consumer 3). It joins the stale-entry removal list in
# conversation_utils.update_character_data, so it is refreshed each turn and
# never accumulates. Must not begin with "Here's the" (the sheet markers).
DOWN_RULES_MARKER = "Down-scene rules:"

_RULES_TEMPLATE = """{marker} the following party member(s) are DOWN this beat: {members}.

House rule (this game has NO death saves): a character at 0 HP is unconscious - or exhausted, as the scene reads - and stable. They cannot act, speak, or answer; allies may speak to or about them. Their HP cannot fall below 0. They cannot die while any party member still stands; death comes only if the whole party falls. A party member whose status is dead or defeated is out of the fight and cannot be restored by ordinary healing.

This is a rescue, not a death. Your goal every window is to keep the downed alive and get them back up. Companions decide how in their own voice - heal, a potion, carry them out of reach, hold the line, a fighting withdrawal - from what the sheets actually hold, including a potion in the downed character's own pack (an ally administers it; the resource stays owned by the sheet that holds it). Enemies turn to the active threats; a downed body is not a target.

Narration: keep narrating the scene in second person as the player's view of what happens to and around their fallen character ("Thane hauls you clear of the mud"), open to muffled sense, a half-heard voice, or plain dark as the scene reads. Never have the character do, say, decide, or notice anything as an act; never ask what they do; never end on the character's move. End the beat on the party's move, the danger that remains, or the moment of rescue.

Table talk: everything the player types while their character is at 0 HP is the human at the table - directing companions, asking what they see, or choosing Load. It is never the character speaking, deciding, or acting. Companions may act on it as their own choice. The character's first act is the moment they wake.

Aftermath: if this is the aftermath after the last enemy falls and the character is still down, narrate the party turning to them, but the character stays unconscious in this beat; waking happens only through a real action on the next turn.

Recovery must be a real committed action, never a narrated claim: a heal, a potion administered by an ally, or a feature in combat; out of combat, an ally tending a party member at exactly 0 HP up to 1 HP with no check (an updateCharacterInfo change, never above 1 HP this way), a potion, or rest, and rest only when the scene allows it. A withdrawal is legitimate, but the fight closes only when the enemies are resolved; never narrate an escape that did not close the encounter. Surrender is not offered. Level-up waits until the character is conscious."""


def is_go_on(text):
    """Return whether an input line is the exact 'go on' control command."""
    return isinstance(text, str) and text.strip().lower() == GO_ON_TOKEN


def _members_text(down_members, round_number):
    parts = []
    for name, hp, status in down_members:
        item = "%s (HP %s, %s)" % (name, hp, status)
        parts.append(item)
    text = "; ".join(parts)
    if round_number is not None:
        text += " - combat round %s now" % round_number
    return text


# #1469: people present at the party's place, outside the party, who are at
# 0 HP. A DM-note element for the DM (and the T065 validator), never shown
# to the player; the party's rescue rules above are not theirs.
PRESENT_DOWN_MARKER = "Present persons at 0 HP:"
_PRESENT_TEMPLATE = (
    "{marker} {members}. They are unconscious and stable and cannot act, speak, "
    "or answer. Waking one is a real action on their own sheet (an "
    "updateCharacterInfo heal with hpDelta, a potion administered, or rest when "
    "the scene allows), never a narrated claim. They are not party members: the "
    "party's down-scene rules do not apply to them."
)


def present_from_sheets(sheets):
    """The present-persons element for the down sheets among these (a dead
    one is not down: nobody can wake them), or None."""
    down = [
        (str(sheet.get("name") or "Unknown"), sheet.get("hitPoints"), _status_text(sheet.get("status")))
        for sheet in sheets or [] if isinstance(sheet, dict) and sheet_is_down(sheet)
        and _status_text(sheet.get("status")) != "dead"
    ]
    if not down:
        return None
    return _PRESENT_TEMPLATE.format(marker=PRESENT_DOWN_MARKER, members=_members_text(down, None))


def present_down_text(party_tracker_data, path_manager):
    """The element for the person occupants present now at the party's place
    who are outside the party and have a sheet at 0 HP, or None. A person
    with no sheet is skipped; no sheet is ever created here."""
    import json
    import os

    from core.nql.occupants import id_stem, present_people
    from utils.npc_name_normalizer import normalize_npc_name_for_action

    sheets = []
    for person in present_people(party_tracker_data or {}):
        name = person.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        if normalize_npc_name_for_action(name, party_tracker_data)[0] is not None:
            continue
        # The id stem is the typed link to the sheet (#1450); the display
        # name finds a file only for an occupant without one.
        path = path_manager.get_character_path(id_stem(person) or name)
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as handle:
                    sheet = json.load(handle)
            except (OSError, ValueError):
                sheet = None
            if isinstance(sheet, dict):
                sheets.append(sheet)
    return present_from_sheets(sheets)


def _render(down_members, round_number=None):
    """Render the one rules string, or None when nobody is down."""
    if not down_members:
        return None
    return _RULES_TEMPLATE.format(
        marker=DOWN_RULES_MARKER,
        members=_members_text(down_members, round_number),
    )


def _status_text(value):
    return re.sub(r"\s+", " ", str(value or "alive")).strip().lower()


def from_encounter(encounter):
    """Rules text for the encounter's down party members, or None."""
    if not isinstance(encounter, dict):
        return None
    from core.managers.combat_state import is_party_member

    down = []
    for creature in encounter.get("creatures", []) or []:
        if is_party_member(creature) and is_down(creature):
            down.append(
                (
                    str(creature.get("name") or "Unknown"),
                    creature.get("currentHitPoints"),
                    _status_text(creature.get("status")),
                )
            )
    state = encounter.get("combatState") or {}
    return _render(down, state.get("round"))


def from_sheets(sheets):
    """Rules text for the down members among the given sheets, or None.

    ``sheets`` is an iterable of character sheet dicts (player and party NPCs).
    """
    down = []
    for sheet in sheets or []:
        if sheet_is_down(sheet):
            down.append(
                (
                    str(sheet.get("name") or "Unknown"),
                    sheet.get("hitPoints"),
                    _status_text(sheet.get("status")),
                )
            )
    return _render(down)
