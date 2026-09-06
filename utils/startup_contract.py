"""Pure startup wire contracts; #114 / #193 D-114-1.

These validate structure, never approval semantics or successful persistence.
The wizard owns the conversation and validates candidates against the existing
character schema before publication.
"""

import json

from jsonschema import Draft7Validator

from utils.character_sheet_contract import extract_json_object


def _object_schema(properties):
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


STARTUP_RESPONSE_SCHEMA = _object_schema({
    "version": {"type": "integer", "enum": [1]},
    "decision": {"type": "string", "enum": ["continue_interview", "finalize_character"]},
    "narration": {"type": "string"},
    "confirmation": _object_schema({
        "player_message_index": {"type": ["integer", "null"], "minimum": 0},
        "whole_build_approved": {"type": "boolean"},
    }),
    "character": {"type": ["object", "null"]},
})

STARTUP_REVIEW_SCHEMA = _object_schema({
    "version": {"type": "integer", "enum": [1]},
    "accepted": {"type": "boolean"},
    "feedback": {"type": "string"},
    "needs_player_clarification": {"type": "boolean"},
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


def parse_startup_response(text, *, latest_user_index):
    """Check wire shape/reference; the caller supplies its actual user index."""
    value = _parse_object(text, STARTUP_RESPONSE_SCHEMA)
    confirmation = value["confirmation"]
    index = confirmation["player_message_index"]
    if value["decision"] == "finalize_character":
        if (confirmation["whole_build_approved"] is not True
                or value["character"] is None
                or type(index) is not int
                or type(latest_user_index) is not int
                or index != latest_user_index):
            raise ValueError("Finalization requires whole-build approval of the latest actual player input and a character")
    elif value["character"] is not None or confirmation["whole_build_approved"]:
        raise ValueError("An interview response cannot approve or contain a character")
    elif index is not None and (type(index) is not int or index != latest_user_index):
        raise ValueError("Confirmation reference must be null or the latest actual player input")
    return value


def parse_startup_review(text):
    """Validate the independent review, without treating prose as a verdict."""
    value = _parse_object(text, STARTUP_REVIEW_SCHEMA)
    if value["accepted"] and value["needs_player_clarification"]:
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
