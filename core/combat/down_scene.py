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
    "to your companions - not {name} acting or speaking. Send '{token}' (or an "
    "empty line) to let the round run. Save and Load work as always."
)
MAIN_DOWN_SINK_LINE = (
    "You are down and cannot act. Anything you send now is you at the table, "
    "speaking to your companions - not {name} acting or speaking. Your "
    "companions will tend to you as they see fit, or as you ask. Save and "
    "Load work as always."
)
# Banner suffixes: appended after the [time][HP][XP] prefix the headless and
# web clients parse; the prefix bytes are never changed.
COMBAT_DOWN_BANNER = "{name} is down - table talk, or '{token}':"
MAIN_DOWN_BANNER = "{name} is down - table talk:"
TPK_BANNER_CONTROLS = "Your party has fallen - Load, Reset, or Quit:"
TPK_BANNER_TERMINAL = (
    "Your party has fallen - press Ctrl+C to close, then Load or Reset from "
    "the launcher:"
)
TPK_PAUSE_TEXT = (
    "Your whole party has fallen. No further turns were taken and nothing was "
    "saved after your party fell. This fight cannot go on from here. Load a "
    "save to return to an earlier moment, or Reset the campaign."
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

This is a rescue, not a death. Your goal every window is to keep the downed alive and get them back up. Companions decide how in their own voice - heal, a potion, carry them out of reach, hold the line, a fighting withdrawal - from what the sheets actually hold. Enemies turn to the active threats; a downed body is not a target.

Narration: keep narrating the scene in second person as the player's view of what happens to and around their fallen character ("Thane hauls you clear of the mud"), open to muffled sense, a half-heard voice, or plain dark as the scene reads. Never have the character do, say, decide, or notice anything as an act; never ask what they do; never end on the character's move. End the beat on the party's move, the danger that remains, or the moment of rescue.

Table talk: everything the player types while their character is at 0 HP is the human at the table - directing companions, asking what they see, or choosing Load. It is never the character speaking, deciding, or acting. Companions may act on it as their own choice. The character's first act is the moment they wake.

Aftermath: if this is the aftermath after the last enemy falls and the character is still down, narrate the party turning to them, but the character stays unconscious in this beat; waking happens only through a real action on the next turn.

Recovery must be a real committed action, never a narrated claim: a heal, a potion administered by an ally, or a feature in combat; Medicine to stabilize, a potion, or rest out of combat, and rest only when the scene allows it. A withdrawal is legitimate, but the fight closes only when the enemies are resolved; never narrate an escape that did not close the encounter. Surrender is not offered. Level-up waits until the character is conscious."""


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
