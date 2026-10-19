"""Pure startup wire contracts; #114 / #193 D-114-1.

These validate structure, never approval semantics or successful persistence.
The wizard owns the conversation and validates candidates against the existing
character schema before publication.
"""

import copy
import json

from jsonschema import Draft7Validator

from utils.character_sheet_contract import extract_json_object


def _object_schema(properties):
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


STARTUP_RESPONSE_SCHEMA = _object_schema({
    "version": {"type": "integer", "enum": [1]},
    "decision": {"type": "string", "enum": ["continue_interview", "finalize_character", "pause_setup"]},
    "narration": {"type": "string"},
    "confirmation": _object_schema({
        "player_message_index": {"type": ["integer", "null"], "minimum": 0},
        "whole_build_approved": {"type": "boolean"},
    }),
    "character": {"type": ["object", "null"]},
    # A new character's typed origin and starting-package picks (D-KW-16): null
    # on every response but finalize_character, like character. The class and
    # background enums come from the data at call time (startup_response_schema).
    "origin": dict(_object_schema({
        "class_key": {"type": "string"},
        "background_key": {"type": "string"},
    }), type=["object", "null"]),
    "starting_equipment": dict(_object_schema({
        "background_package": {"type": "string"},
        "class_package": {"type": "string"},
        "slot_picks": {"type": "array", "items": {"oneOf": [
            _object_schema({"slot": {"type": "string"}, "catalog_id": {"type": "string"}}),
            _object_schema({"slot": {"type": "string"}, "display_name": {"type": "string"}}),
        ]}},
        "equipped": {"type": "array", "items": {"type": "string"}},
    }), type=["object", "null"]),
})

STARTUP_REVIEW_SCHEMA = _object_schema({
    "version": {"type": "integer", "enum": [1]},
    "accepted": {"type": "boolean"},
    "feedback": {"type": "string"},
    "needs_player_clarification": {"type": "boolean"},
})

# One section reviewer's typed verdict (D-CREATE-COST-3, T128-T131): demands name the field.
SECTION_REVIEW_SCHEMA = _object_schema({
    "version": {"type": "integer", "enum": [1]},
    "section": {"type": "string", "enum": ["S1", "S2", "S3", "S4"]},
    "accepted": {"type": "boolean"},
    "needs_player_clarification": {"type": "boolean"},
    "demands": {"type": "array", "items": _object_schema({
        "field": {"type": "string"},
        "demand": {"type": "string"},
    })},
})

STARTUP_CHECKPOINT_SCHEMA = _object_schema({
    "startup_checkpoint_version": {"type": "integer", "enum": [1]},
    "startup_id": {"type": "string", "minLength": 1},
    "phase": {"type": "string", "enum": [
        "module_selection", "interview", "approved", "character_saved", "ready",
    ]},
    "module": {"type": ["string", "null"]},
    "latest_user_index": {"type": ["integer", "null"], "minimum": 0},
    "candidate": {"type": ["object", "null"]},
    "location": {"type": ["object", "null"]},
    "character_path": {"type": ["string", "null"]},
})


# The player's typed intent on the scoped path (D-CREATE-COST-4): what the player
# chose or approved so far, the picks keyed by the choice ids the engine scope
# issued, and the options the player is only asking about (considering).
STARTUP_INTENT_SCHEMA = _object_schema({
    "class_key": {"type": ["string", "null"]},
    "species_key": {"type": ["string", "null"]},
    "background_key": {"type": ["string", "null"]},
    "choices": {"type": "object", "additionalProperties": {"type": "array", "items": {"type": "string"}}},
    "considering": _object_schema({
        "class_keys": {"type": "array", "items": {"type": "string"}},
        "species_keys": {"type": "array", "items": {"type": "string"}},
        "background_keys": {"type": "array", "items": {"type": "string"}},
    }),
    # D-CREATE-COST-5 (amendment 1f): the method the player chose and the base score per ability, as typed
    # fields the author sets; null until chosen. A random method's numbers are the engine's roll item.
    "ability_scores": dict(_object_schema({
        "method": {"type": "string", "enum": ["standard_array", "point_buy", "random"]},
        "assignment": dict(_object_schema({ability: {"type": "integer"} for ability in (
            "strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")}),
            type=["object", "null"]),
    }), type=["object", "null"]),
})

# The creative fields of an engine-built character (D-CREATE-COST-5, amendment 1a): copied verbatim, never
# read for mechanics. backstory and appearance never reach the sheet (char_schema is frozen); they ride in
# the startup_engine_build item. feature_descriptions: display text per engine-named feature (D1).
STARTUP_CREATIVE_SCHEMA = _object_schema({
    "name": {"type": "string"},
    "alignment": {"type": "string"},
    "personality_traits": {"type": "string"},
    "ideals": {"type": "string"},
    "bonds": {"type": "string"},
    "flaws": {"type": "string"},
    "backstory": {"type": ["string", "null"]},
    "appearance": {"type": ["string", "null"]},
    "feature_descriptions": {"type": ["object", "null"], "additionalProperties": {"type": "string"}},
})


def startup_response_schema(*, scoped=False):
    """STARTUP_RESPONSE_SCHEMA with the origin enums from the data: the 12 class
    keys of choices.json and the background keys of the origins file. Built at
    each call, never at import; when the data cannot be read the schema is
    returned without the enums, and a finalize then reaches the grant, which
    reports the data unavailable. scoped adds the required intent, with the
    class, species and background enums (null until chosen)."""
    from core.nql.startup_rows import package_records
    schema = copy.deepcopy(STARTUP_RESPONSE_SCHEMA)
    records = package_records()
    if records is not None:
        origin = schema["properties"]["origin"]["properties"]
        origin["class_key"]["enum"] = sorted(records.classes)
        origin["background_key"]["enum"] = sorted(records.backgrounds)
    if scoped:
        from core.nql import creation_scope
        intent = copy.deepcopy(STARTUP_INTENT_SCHEMA)
        for field, keys in (("class_key", creation_scope.class_keys()),
                            ("species_key", creation_scope.species_keys()),
                            ("background_key", creation_scope.background_keys())):
            if keys:
                intent["properties"][field]["enum"] = keys + [None]
        schema["properties"]["intent"] = intent
        schema["required"].append("intent")
        creative = dict(copy.deepcopy(STARTUP_CREATIVE_SCHEMA), type=["object", "null"])
        alignment = (_char_schema().get("properties") or {}).get("alignment") or {}
        if alignment.get("enum"):
            creative["properties"]["alignment"]["enum"] = list(alignment["enum"])
        schema["properties"]["creative"] = creative
        schema["required"].append("creative")
    return schema


def _char_schema():
    from utils.encoding_utils import safe_json_load
    return safe_json_load("schemas/char_schema.json") or {}


def _validate(value, schema):
    errors = list(Draft7Validator(schema).iter_errors(value))
    if errors:
        raise ValueError("; ".join(
            f"{'.'.join(map(str, error.absolute_path)) or '$'}: {error.message}"
            for error in errors
        ))
    return value


def _parse_object(text, schema):
    if not isinstance(text, str):
        raise ValueError("Startup response must be JSON text")
    extracted = extract_json_object(text)
    if extracted is None:
        raise ValueError("Startup response must contain one JSON object")
    try:
        value = json.loads(extracted)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid startup JSON: {exc}") from exc
    return _validate(value, schema)


def parse_startup_response(text, *, latest_user_index, scoped=False):
    """Check wire shape/reference; the caller supplies its actual user index.
    scoped: the response carries intent, and a finalize's origin must equal it."""
    value = _parse_object(text, startup_response_schema(scoped=scoped))
    confirmation = value["confirmation"]
    index = confirmation["player_message_index"]
    if value["decision"] == "finalize_character":
        if (confirmation["whole_build_approved"] is not True
                or value["character"] is None
                or type(index) is not int
                or type(latest_user_index) is not int
                or index != latest_user_index):
            raise ValueError("Finalization requires whole-build approval of the latest actual player input and a character")
        if value["origin"] is None or value["starting_equipment"] is None:
            raise ValueError("Finalization requires origin (class_key, background_key) and starting_equipment "
                             "(the chosen package keys, slot_picks and equipped)")
        if scoped and (value["origin"]["class_key"], value["origin"]["background_key"]) != (
                value["intent"]["class_key"], value["intent"]["background_key"]):
            raise ValueError("Finalization requires origin class_key and background_key equal to intent's")
    elif value["character"] is not None or confirmation["whole_build_approved"]:
        raise ValueError("An interview response cannot approve or contain a character")
    elif scoped and value.get("creative") is not None:
        raise ValueError("An interview response has creative null; it is set at finalization")
    elif value["origin"] is not None or value["starting_equipment"] is not None:
        raise ValueError("An interview response has origin and starting_equipment null; they are set at finalization")
    elif value["decision"] == "pause_setup" and (
            type(index) is not int or type(latest_user_index) is not int
            or index != latest_user_index):
        raise ValueError("A pause must cite the latest actual player input, which asked to stop")
    elif index is not None and (type(index) is not int or index != latest_user_index):
        raise ValueError("Confirmation reference must be null or the latest actual player input")
    return value


def parse_startup_review(text, *, decision=None):
    """Validate the independent review, without treating prose as a verdict.

    An accepted continue_interview may also need the player: publishing it asks
    them (#887). For any other decision, or none given, that pair stays invalid,
    so an accepted finalize_character is never saved without the player's answer."""
    value = _parse_object(text, STARTUP_REVIEW_SCHEMA)
    if (value["accepted"] and value["needs_player_clarification"]
            and decision != "continue_interview"):
        raise ValueError("An accepted proposal cannot still need player clarification")
    if not value["accepted"] and not value["feedback"].strip():
        raise ValueError("A rejected proposal requires corrective feedback")
    return value


def parse_startup_checkpoint(messages):
    """Read the latest valid code-authored record without changing history.

    Old unstructured histories return None. Invalid-only records raise a
    diagnostic for the wizard to reconcile using real history and files.
    Assistant or user JSON cannot become a code-authored progress record.
    """
    if not isinstance(messages, list):
        raise ValueError("Startup history must be a message list")
    latest = None
    invalid = None
    for message in messages:
        if not isinstance(message, dict) or message.get("role") != "system":
            continue
        try:
            record = json.loads(message.get("content", ""))
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(record, dict) or "startup_checkpoint_version" not in record:
            continue
        try:
            _validate(record, STARTUP_CHECKPOINT_SCHEMA)
        except ValueError as exc:
            invalid = exc
        else:
            latest = record
    if latest is None and invalid is not None:
        raise invalid
    return latest


def parse_section_review(text, *, section):
    """One section's verdict: its own section, a rejection with at least one demand, an accept
    without clarification."""
    value = _parse_object(text, SECTION_REVIEW_SCHEMA)
    if value["section"] != section:
        raise ValueError(f"This review is section {section}, not {value['section']}")
    if not value["accepted"] and not [d for d in value["demands"] if d["demand"].strip()]:
        raise ValueError("A rejected section requires at least one demand")
    if value["accepted"] and value["needs_player_clarification"]:
        raise ValueError("An accepted section cannot still need player clarification")
    return value


def merge_section_reviews(verdicts):
    """The four section verdicts as one review in today's shape (STARTUP_REVIEW_SCHEMA): any reject is a
    reject, clarification if any section asks, the demands tagged by section in the feedback."""
    rejected = [v for v in verdicts if not v["accepted"]]
    feedback = "\n".join(f"[{v['section']}] {d['field']}: {d['demand']}"
                         for v in rejected for d in v["demands"] if d["demand"].strip())
    return {"version": 1, "accepted": not rejected, "feedback": feedback,
            "needs_player_clarification": any(v["needs_player_clarification"] for v in rejected)}
