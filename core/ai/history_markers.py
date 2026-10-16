# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""The game's own marker messages in conversation history (prose sweep family 3).

A marker is a history message the game writes to record an event: a location
or module transition, a location summary, a chronicle, a rolling summary. The
player's typed text is stored verbatim in user messages, so finding markers by
searching for their words also finds a player who types them. Markers
therefore carry a field naming their kind, and readers test that field.

Histories saved before the field existed are read as they always were: a
message without the field is a marker only when its role matches and its
content STARTS with the marker's exact opening words. Every player turn starts
with "Dungeon Master Note:", so a player's text can never match. Nothing on
disk is rewritten. New player turns and code-written notes never carry the
field either, so the same start rule keeps protecting them.

The field stays inside the game: providers receive role and content only (the
Responses and Gemini paths), or the message without it (Chat Completions).

The player's own turn carries the player's typed words in a second field
(#449). Player speech is read from that field only; every other user message
(an engine note, a marker, a summary) is not player speech. A turn saved before
the field existed is read from the engine's turn envelope as it always was.
"""

MARKER_FIELD = "nql_marker"
PLAYER_INPUT_FIELD = "nql_player_input"
# The combat round a combat history message belongs to, written by the game.
ROUND_FIELD = "nql_round"
# True on the turn whose DM note carries the module creation prompt, written by the game.
MODULE_CREATION_FIELD = "nql_module_creation_prompt"
# The game's own fields on a history message; providers never receive them.
GAME_FIELDS = (MARKER_FIELD, PLAYER_INPUT_FIELD, ROUND_FIELD, MODULE_CREATION_FIELD)

LOCATION_TRANSITION = "location_transition"
MODULE_TRANSITION = "module_transition"
# A module transition the campaign archive neutralized ("[Archived] Module
# transition: ..."). Returning to a module loads its archive back into
# history, where these still bound segments and are dropped like markers.
ARCHIVED_MODULE_TRANSITION = "archived_module_transition"
LOCATION_SUMMARY = "location_summary"
CHRONICLE = "chronicle"
ROLLING_SUMMARY = "rolling_summary"
VALIDATION_ERROR = "validation_error"
# The note the game adds at load when the player returns to a saved game.
RETURN_NOTE = "return_note"
# A legacy combat turn message for an automatic initiative window (the
# game resolves non-player turns; no player action was submitted).
COMBAT_CONTINUATION = "combat_continuation"
# The summary the game writes in place of an old combat round.
COMBAT_ROUND_SUMMARY = "combat_round_summary"
# The turn after a dice submission: the engine asks the DM to narrate the
# settled check; the player typed nothing.
CHECK_CONTINUATION = "check_continuation"

SUMMARY_KINDS = (LOCATION_SUMMARY, CHRONICLE)
MODULE_KINDS = (MODULE_TRANSITION, ARCHIVED_MODULE_TRANSITION)

_CHRONICLE_TAG = "[AI-Generated Chronicle Summary]"
_ARCHIVED_PREFIX = "[Archived] "
# (role, opening words) of markers written before the field existed
_LEGACY_OPENINGS = (
    ("user", "Location transition:", LOCATION_TRANSITION),
    ("user", "Module transition:", MODULE_TRANSITION),
    # Every "Error Note:" the game wrote asked the DM to correct its last
    # reply (failed validation, a refused transition, an unavailable reply);
    # a player's turn opens with the engine's envelope, never with this.
    ("user", "Error Note:", VALIDATION_ERROR),
    ("assistant", "=== LOCATION SUMMARY ===", LOCATION_SUMMARY),
    ("assistant", "[SUMMARY OF EVENTS AT THIS LOCATION]", ROLLING_SUMMARY),
    ("user", "Dungeon Master Note: Resume the game, the player has returned", RETURN_NOTE),
)


def marker(role, content, kind, **extra):
    """A history message the game writes as a marker of ``kind``."""
    message = {"role": role, "content": content}
    message.update(extra)
    message[MARKER_FIELD] = kind
    return message


def marker_kind(message):
    """The marker kind of a history message, or None for any other message."""
    if not isinstance(message, dict):
        return None
    if MARKER_FIELD in message:
        return message[MARKER_FIELD]
    content = message.get("content")
    if not isinstance(content, str):
        return None
    role = message.get("role")
    if role == "user" and content.startswith(_ARCHIVED_PREFIX):
        while content.startswith(_ARCHIVED_PREFIX):
            content = content[len(_ARCHIVED_PREFIX):]
        if content.startswith("Module transition:"):
            return ARCHIVED_MODULE_TRANSITION
        return None
    for legacy_role, opening, kind in _LEGACY_OPENINGS:
        if role == legacy_role and content.startswith(opening):
            if kind == LOCATION_SUMMARY and _CHRONICLE_TAG in content:
                return CHRONICLE
            return kind
    return None


_ENVELOPE = "Dungeon Master Note:"
_ENVELOPE_PLAYER = " Player: "
_ENVELOPE_BLOCKS = ("\n[Inventory Context:", "\n[SRD CONTEXT")


def player_turn(content, player_input):
    """The player's turn message: the engine's envelope as content and the
    player's own words beside it (#449)."""
    return {"role": "user", "content": content, PLAYER_INPUT_FIELD: player_input}


def player_input(message):
    """The player's own words on a history message, or None when it is not a
    player turn.

    A turn saved before the field existed (#449, owner D-449-1 A) has no game
    field; it is read as it always was, only when it is the engine's own turn
    envelope: it starts with "Dungeon Master Note:" and holds " Player: ".
    """
    if not isinstance(message, dict) or message.get("role") != "user":
        return None
    if PLAYER_INPUT_FIELD in message:
        value = message[PLAYER_INPUT_FIELD]
        return value.strip() if isinstance(value, str) else None
    if MARKER_FIELD in message:
        return None
    content = message.get("content")
    if not isinstance(content, str) or not content.startswith(_ENVELOPE) or _ENVELOPE_PLAYER not in content:
        return None
    value = content.rsplit(_ENVELOPE_PLAYER, 1)[1]
    cutoffs = [index for index in (value.find(block) for block in _ENVELOPE_BLOCKS) if index >= 0]
    if cutoffs:
        value = value[: min(cutoffs)]
    return value.strip()


def message_round(message):
    """The combat round the game wrote on a history message, or None."""
    value = message.get(ROUND_FIELD) if isinstance(message, dict) else None
    return value if type(value) is int else None


def is_marker(message, *kinds):
    """Whether ``message`` is a game marker of one of ``kinds``."""
    return marker_kind(message) in kinds


def same_message(a, b):
    """Whether two history messages are equal apart from the marker field.

    Recovery code checks whether a marker it is about to write is already in
    history; one saved before the field existed must still count as present.
    """
    if not (isinstance(a, dict) and isinstance(b, dict)):
        return a == b
    strip = lambda m: {k: v for k, v in m.items() if k != MARKER_FIELD}
    return strip(a) == strip(b) and marker_kind(a) == marker_kind(b)
