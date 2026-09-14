# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Pure single-character level-up response contract (#323)."""

import json
from dataclasses import dataclass
from typing import Literal, get_args

from utils.character_sheet_contract import extract_json_object
from utils.level_up_workspace import Domain, validate_player_question


@dataclass(frozen=True)
class LevelUpTurn:
    kind: Literal["interview", "complete", "not_applied"]
    narration: str


STAGES = ('ask', 'commit', 'report')
# The specialist domain type is the single source; the deleted public DOMAINS
# constant is not reintroduced (SO-07). An unknown domain would reach constrain().
_DOMAINS = frozenset(get_args(Domain))


def _check_choices(choices):
    """Every recorded choice is a typed {value, source}; anything else is refused."""
    if not isinstance(choices, dict):
        raise ValueError('choices must be an object of {name: {"value": ..., "source": ...}}')
    for name, entry in choices.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError('each recorded choice name must be a nonempty question name')
        if (not isinstance(entry, dict) or not {'value', 'source'} <= set(entry)
                or set(entry) - {'value', 'source', 'domain'}):
            raise ValueError(f'choice {name!r} requires value/source and optional domain')
        if 'domain' in entry and (not isinstance(entry['domain'], str) or entry['domain'] not in _DOMAINS):
            raise ValueError('choice domain must be features, spells or numbers')
        if name == 'final_confirmation':
            raise ValueError('final_confirmation is reserved for consent, not a recorded choice')
        if not isinstance(entry['source'], str) or not entry['source'].strip():
            raise ValueError(f'choice {name!r} source must name the accepted player line or npc-policy')


def parse_level_up_stage(raw) -> dict:
    """Private coordinator turn envelope (D-3.1); never a second character author."""
    data = json.loads(raw)
    json.dumps(data, allow_nan=False)
    if not isinstance(data, dict) or set(data) != {'stage', 'narration', 'asking', 'choices'}:
        raise ValueError('coordinator requires stage, narration, asking and choices only')
    stage = data['stage']
    if stage not in STAGES:
        raise ValueError('unknown coordinator stage')
    if not isinstance(data['narration'], str):
        raise ValueError('narration must be a string')
    asking = data['asking']
    if isinstance(asking, dict):
        if (not {'choice', 'domain', 'prompt'} <= set(asking)
                or set(asking) - {'choice', 'domain', 'prompt', 'options', 'facts'}):
            raise ValueError('new question requires choice/domain/prompt and optional options/facts')
        if not isinstance(asking['domain'], str) or asking['domain'] not in _DOMAINS:
            raise ValueError('question domain must be features, spells or numbers')
        validate_player_question(asking)
        if asking['choice'] == 'final_confirmation':
            raise ValueError('final_confirmation is reserved; use its string form')
    elif not (asking is None or isinstance(asking, str)):
        raise ValueError('asking must be a question object, name, final_confirmation or null')
    _check_choices(data['choices'])
    if stage == 'ask':
        if not data['narration'].strip():
            raise ValueError('ask narration must be nonempty player text')
        if asking is not None and not isinstance(asking, dict) and (not isinstance(asking, str) or not asking.strip()):
            raise ValueError('ask must name one pending question or final_confirmation')
    else:  # commit, report
        if data['asking'] is not None:
            raise ValueError(f'{stage} asks nothing; asking must be null')
        if stage == 'report' and data['choices']:
            raise ValueError(f'{stage} records no choices; code uses the current approved workspace')
        if stage == 'commit' and data['narration'].strip():
            raise ValueError('commit authorizes calculation silently; narration must be empty until the save is verified')
    return data


def parse_level_up_validation_response(raw, *, postcommit=False) -> dict:
    """T048's structured verdict with typed, routable error objects (GL-1 row).

    Four keys unchanged; each error is exactly {'text', 'domain'} with domain a
    specialist domain or null. postcommit=True (the session passes
    self._reporting_state is not None) adds ONE stage-contract check: after the
    write every error's domain must be null, else ValueError like a malformed
    verdict so the existing private T048 re-request corrects it (FF7-F2).
    """
    json_blob = extract_json_object(raw)
    if json_blob is None:
        raise ValueError('no JSON object found')
    result = json.loads(json_blob)
    json.dumps(result, allow_nan=False)
    if not isinstance(result, dict) or set(result) != {'valid', 'errors', 'warnings', 'recommendation'}:
        raise ValueError('verdict requires exactly valid, errors, warnings and recommendation')
    if type(result['valid']) is not bool:
        raise ValueError("'valid' must be a boolean")
    if not isinstance(result['errors'], list):
        raise ValueError("'errors' must be an array of typed error objects")
    for error in result['errors']:
        if not isinstance(error, dict) or set(error) != {'text', 'domain'}:
            raise ValueError("each error must be exactly {'text': <objection>, "
                             "'domain': <specialist domain or null>}")
        if not isinstance(error['text'], str) or not error['text'].strip():
            raise ValueError('each error text must be a nonempty objection string')
        if not (error['domain'] is None or error['domain'] in _DOMAINS):
            raise ValueError('each error domain must name a specialist domain or be null')
        if postcommit and error['domain'] is not None:
            raise ValueError('after the write every error must carry domain null and state what the '
                             'narration must say about the observed saved sheet; restate your verdict')
    if not isinstance(result['warnings'], list) or not all(isinstance(item, str) for item in result['warnings']):
        raise ValueError("'warnings' must be an array of strings")
    if not isinstance(result['recommendation'], str):
        raise ValueError("'recommendation' must be a string")
    return result
