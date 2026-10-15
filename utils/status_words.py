"""Status words in character names (#1119).

A status word ("Wounded Ranger Gareth") describes a state, not a person. A
new character never takes a name that carries one: the NPC builder, the party
add, combat creation, the startup wizard and module generation all refuse it,
and the refusal names the proper name to use. Only structured name fields are
checked, never prose. This module has no imports beyond re, so generators can
use it without loading the character-update module.
"""

import re

NPC_STATUS_WORDS = ("corrupted", "wounded", "elite", "enhanced")
_STATUS_WORD_PATTERN = re.compile(r"\b(?:" + "|".join(NPC_STATUS_WORDS) + r")\b", re.IGNORECASE)


def name_without_status_words(character_name):
    """The name with its status words removed ("Wounded Ranger Gareth" ->
    "Ranger Gareth"), or "" when nothing else is left."""
    cleaned = _STATUS_WORD_PATTERN.sub(" ", str(character_name or ""))
    return " ".join(cleaned.split()).strip(" _-")


def status_word_refusal(character_name):
    """Why a new character cannot take this name because it carries a status
    word, or None. A state such as "wounded" belongs in the character's
    description, not its name."""
    name = str(character_name or "")
    found = _STATUS_WORD_PATTERN.search(name)
    if not found:
        return None
    proper = name_without_status_words(name)
    example = f", such as {proper!r}" if proper else ""
    return (f"the name {name!r} carries the status word {found.group(0).lower()!r}; "
            f"a character takes its proper name without it{example}")
