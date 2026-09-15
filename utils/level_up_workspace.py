# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Private proposal composition for #323; never character mutation authority.

Composition returns a delta, not a replacement sheet. The character writer still
owns projection/persistence. Rule applicability and conflicting values belong to
the coordinator; this module only identifies structural disagreement. Every helper
here is pure data over the workspace: no counts, clocks, sizes or prose reading.
"""

from copy import deepcopy
from dataclasses import dataclass, field
import math
from typing import Literal


Domain = Literal['features', 'spells', 'numbers']
FORWARD_ORDER = ('features', 'spells', 'numbers')
# What each domain actually consumes from another domain's approved output.
# Spells needs the approved subclass and feature grants; numbers needs the
# approved feats and proficiencies (initiative, attacks, skills). Numbers does
# not consume spells (save DC and attack bonus come from the ability score and
# proficiency bonus; slot maxima are spells' own), so spells and numbers are
# authored side by side once features is approved (owner ruling 2026-09-14).
DEPENDS_ON = {'features': (), 'spells': ('features',), 'numbers': ('features',)}


def dependents_of(domain):
    """Every domain that consumes `domain`'s output, transitively (excluding itself)."""
    found = []
    frontier = [domain]
    while frontier:
        current = frontier.pop()
        for other, needs in DEPENDS_ON.items():
            if current in needs and other not in found:
                found.append(other)
                frontier.append(other)
    return tuple(d for d in FORWARD_ORDER if d in found)
QuestionState = Literal['open', 'answered', 'reopened']
Origin = Literal['admission', 'review', 'assembly', 'prepared_sheet',
                 'merge', 'fact_conflict', 'review_format']


@dataclass
class DomainProposal:
    domain: Domain
    draft: int
    input_snapshot: dict
    changes: dict
    calculations: list[dict] = field(default_factory=list)
    rule_refs: list[str] = field(default_factory=list)
    variations: list[dict] = field(default_factory=list)
    rule_facts: dict = field(default_factory=dict)


@dataclass
class DomainReview:
    valid: bool
    errors: list[dict]


@dataclass
class Constraint:
    origin: Origin
    domain: Domain
    draft: int
    errors: list[dict]
    stale_inputs: dict = field(default_factory=dict)


@dataclass
class LevelUpWorkspace:
    choices: dict[str, dict] = field(default_factory=dict)
    questions: dict[str, dict] = field(default_factory=dict)
    proposals: dict[Domain, DomainProposal] = field(default_factory=dict)
    reviews: dict[Domain, DomainReview] = field(default_factory=dict)
    constraints: dict[Domain, dict[Origin, Constraint]] = field(default_factory=dict)
    rule_facts: dict[str, dict] = field(default_factory=dict)
    drafts: dict[Domain, int] = field(default_factory=dict)
    revision: int = 0


def _same_value(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_same_value(value, right[key]) for key, value in left.items())
    if isinstance(left, list):
        return len(left) == len(right) and all(_same_value(a, b) for a, b in zip(left, right))
    return left == right


def _capture_inputs(packet, domain):
    """Keep source evidence in code, never ask an author to regenerate it."""
    upstream = DEPENDS_ON[domain]
    validated = packet.get('validated') or {}
    return deepcopy({
        'stored': packet.get('stored'), 'effective': packet.get('effective'),
        'validated': {
            'choices': validated.get('choices', {}),
            'rules': {name: fact['value'] for name, fact in validated.get('rules', {}).items()
                      if fact.get('origin') is None or fact.get('origin') in upstream},
            'domains': {name: changes for name, changes in validated.get('domains', {}).items()
                        if name in upstream},
        },
    })


def _input_mismatches(proposal, current):
    """Compare captured inputs, not author echoes or changing fact-origin labels."""
    recorded = proposal.input_snapshot
    errors = []
    for root in ('stored', 'effective'):
        if not _same_value(recorded[root], current.get(root)):
            errors.append({'path': [root], 'error': 'source sheet changed; recalculate from current inputs'})
    saved = recorded['validated']
    validated = current.get('validated') or {}
    choices = validated.get('choices', {})
    for name in saved['choices'].keys() | choices.keys():
        if (name not in saved['choices'] or name not in choices
                or not _same_value(saved['choices'][name], choices[name])):
            errors.append({'path': ['validated', 'choices', name], 'error': 'accepted choice changed'})
    for name, changes in saved['domains'].items():
        if not _same_value(changes, validated.get('domains', {}).get(name)):
            errors.append({'path': ['validated', 'domains', name], 'error': 'approved upstream changes changed'})
    # Promotion may reassert the same rule under a different origin. Compare the
    # captured names/values without re-filtering current origins or capturing the
    # author's newly produced facts as its own inputs.
    errors.extend(dependency_mismatches(saved['rules'], validated.get('rules', {}), ('validated', 'rules')))
    return errors


def _entry_key(entry, name_field, array_field):
    if not isinstance(entry, dict):
        raise ValueError(f'{array_field} requires named object entries')
    name = entry.get(name_field)
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f'{array_field} requires a nonempty {name_field}')
    # Match the existing writer: equipment identity is exact, other named
    # arrays use lower/strip. This is storage identity, never rule selection.
    return name if array_field == 'equipment' else name.lower().strip()


def _removes_entry(entry, array_field):
    if array_field not in ('equipment', 'ammunition'):
        return False
    quantity = entry.get('quantity', 1)
    empty = isinstance(quantity, (int, float)) and quantity <= 0
    return empty or (array_field == 'equipment' and bool(entry.get('_remove', False)))


def _combine(left, right, named_arrays, errors, path='', segments=()):
    result = deepcopy(left)
    for key, value in right.items():
        location = f'{path}.{key}' if path else key
        seg = segments + (key,)
        if key in named_arrays and isinstance(value, list):
            if key in result and not isinstance(result[key], list):
                errors.append({'field': location, 'path': list(seg),
                               'actual': result[key], 'proposed': value})
                continue
            prior = result.get(key, [])
            # The ordinary writer treats an explicit empty equipment-effects
            # list as a clear, unlike its other named arrays.
            if key == 'equipment_effects' and key in result and bool(prior) != bool(value):
                errors.append({'field': location, 'path': list(seg),
                               'actual': prior, 'proposed': value})
                continue
            name_field = named_arrays[key]
            entries = {}
            for item in prior:
                entries[_entry_key(item, name_field, key)] = deepcopy(item)
            for item in value:
                identity = _entry_key(item, name_field, key)
                if identity in entries:
                    if _removes_entry(entries[identity], key) != _removes_entry(item, key):
                        errors.append({'field': f'{location}[{identity}]',
                                       'path': list(seg + (identity,)),
                                       'error': 'Entry removal conflicts with another proposed update',
                                       'actual': deepcopy(entries[identity]), 'proposed': deepcopy(item)})
                        continue
                    body = {field_name: data for field_name, data in item.items() if field_name != name_field}
                    entries[identity] = _combine(
                        entries[identity], body, named_arrays, errors,
                        f'{location}[{identity}]', seg + (identity,),
                    )
                else:
                    entries[identity] = deepcopy(item)
            result[key] = list(entries.values())
        elif key not in result:
            result[key] = deepcopy(value)
        elif isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _combine(result[key], value, named_arrays, errors, location, seg)
        elif not _same_value(result[key], value):
            errors.append({'field': location, 'path': list(seg), 'actual': deepcopy(result[key]),
                           'proposed': deepcopy(value)})
    return result


def _materialize_named_fields(base, changes, named_arrays, merge_dict):
    result = deepcopy(changes)
    for key, value in result.items():
        if key in named_arrays and isinstance(value, list):
            name_field = named_arrays[key]
            saved = {
                _entry_key(item, name_field, key): item
                for item in base.get(key, [])
            }
            for item in value:
                previous = saved.get(_entry_key(item, name_field, key), {})
                if previous:
                    item[name_field] = previous[name_field]
                # Specialist values are absolute stored quantities; the one
                # ordinary ammunition writer consumes an additive delta.
                if key == 'ammunition':
                    for field_name, supplied in item.items():
                        if field_name not in ('name', 'quantity'):
                            fill_description = field_name == 'description' and field_name not in previous
                            if not fill_description and (field_name not in previous or
                                                         not _same_value(previous[field_name], supplied)):
                                raise ValueError(f'ammunition[{item[name_field]}].{field_name}: '
                                                 'existing writer cannot apply this replacement')
                    if 'quantity' in item:
                        item['quantity'] -= previous.get('quantity', 0)
                for field_name, supplied in list(item.items()):
                    original = previous.get(field_name)
                    if isinstance(original, dict) and isinstance(supplied, dict):
                        item[field_name] = merge_dict(original, supplied)
        elif isinstance(value, dict) and isinstance(base.get(key), dict):
            result[key] = _materialize_named_fields(
                base[key], value, named_arrays, merge_dict,
            )
    return result


def _identity_matches(entry, name_field, array_field, segment):
    """Guarded writer-identity test for one entry against a string segment.

    Returns False (never raises) when the entry is not a dict, its identity field
    is missing, blank or not a string, or the segment is not a non-blank string.
    Only then is the ONE existing `_entry_key` applied to the entry and to a
    `{name_field: segment}` stand-in, so the writer's rule lives once in the module
    and the raising helper never sees malformed input (L6-1 / SP FYI-R6-1).
    """
    if not isinstance(segment, str) or not segment.strip():
        return False
    if not (isinstance(entry, dict) and isinstance(entry.get(name_field), str) and entry[name_field].strip()):
        return False
    return _entry_key(entry, name_field, array_field) == _entry_key({name_field: segment}, name_field, array_field)


def merge_domain_changes(base: dict, proposals: list[DomainProposal]) -> tuple[dict, list[dict]]:
    """Combine proposed leaves, then expand nested named-entry fields once.

No conflicting proposal can produce a usable merged delta. Author drafts remain
in the workspace so reconciliation can correct them without restarting siblings.
The existing writer supplies both named-array metadata and nested merge behavior.
Each error gains 'domains' by the M-merge row: the producer's own domain for an
envelope error, path membership for a `_combine` conflict, and [] for a
materialization failure - never parsed from the display string.
"""
    from updates.update_character_info import CHARACTER_NAMED_ARRAYS, deep_merge_dict

    changes = {}
    errors = []
    for proposal in proposals:
        if not isinstance(proposal.changes, dict):
            errors.append({'field': proposal.domain, 'domain': proposal.domain,
                           'error': 'changes must be an object', 'domains': [proposal.domain]})
            continue
        try:
            changes = _combine(changes, proposal.changes, CHARACTER_NAMED_ARRAYS, errors)
        except ValueError as exc:
            errors.append({'field': proposal.domain, 'domain': proposal.domain,
                           'error': str(exc), 'domains': [proposal.domain]})
    for error in errors:
        if 'domain' not in error:
            error['domains'] = changes_owning_path(proposals, error['path'])
    if errors:
        return {}, errors
    try:
        return _materialize_named_fields(base, changes, CHARACTER_NAMED_ARRAYS, deep_merge_dict), []
    except (TypeError, ValueError) as exc:
        return {}, [{'field': 'changes', 'error': str(exc), 'domains': []}]


def changes_owning_path(proposals, path) -> list[Domain]:
    """The domains whose proposal changes contain that exact leaf or object path.

    Accepts a structured list path (from `_combine` errors and `sheet_diff`) or
    the dotted dict-only `field.nested` string `purge_invalid_fields` reports.
    A named-array list segment is matched by the writer's identity rule, an int
    segment positionally, a dict key exactly. Membership is not validation: a
    malformed entry or segment never matches and never raises. A touched parent
    object does not own an untouched sibling key. Empty list = unintroduced.
    """
    from updates.update_character_info import CHARACTER_NAMED_ARRAYS
    segments = path.split('.') if isinstance(path, str) else list(path)
    owners = []
    for proposal in proposals:
        if isinstance(proposal.changes, dict) and _changes_contains(proposal.changes, segments, CHARACTER_NAMED_ARRAYS):
            owners.append(proposal.domain)
    return owners


def _changes_contains(changes, segments, named_arrays):
    node = changes
    array_field = None
    for segment in segments:
        if isinstance(node, dict):
            if not (isinstance(segment, str) and segment in node):
                return False
            array_field = segment
            node = node[segment]
        elif isinstance(node, list):
            if type(segment) is int and not isinstance(segment, bool):
                if not (0 <= segment < len(node)):
                    return False
                node = node[segment]
            elif array_field in named_arrays:
                name_field = named_arrays[array_field]
                match = None
                for item in node:
                    if _identity_matches(item, name_field, array_field, segment):
                        match = item
                        break
                if match is None:
                    return False
                node = match
            else:
                return False
        else:
            return False
    return True


def sheet_diff(before: dict, after: dict) -> list[dict]:
    """Leaf-level differences between two sheets, keys sorted.

    A named array whose entries ALL carry unique string identities is walked by
    identity (segment = the entry's stored name in ORIGINAL case); any other list
    positionally so a nameless or duplicate entry never raises. An added/removed
    leaf carries 'missing': 'before'|'after' beside a null placeholder because
    null itself is a real value.
    """
    from updates.update_character_info import CHARACTER_NAMED_ARRAYS
    diffs = []
    _sheet_diff(before, after, [], diffs, CHARACTER_NAMED_ARRAYS)
    return diffs


def _named_index(entries, name_field, array_field):
    index = {}
    for item in entries:
        if not (isinstance(item, dict) and isinstance(item.get(name_field), str) and item[name_field].strip()):
            return None
        identity = _entry_key(item, name_field, array_field)
        if identity in index:
            return None
        index[identity] = item
    return index


def _sheet_diff(before, after, path, diffs, named_arrays):
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(set(before) | set(after)):
            if key in before and key in after:
                _sheet_diff(before[key], after[key], path + [key], diffs, named_arrays)
            elif key in after:
                diffs.append({'path': path + [key], 'before': None, 'after': after[key], 'missing': 'before'})
            else:
                diffs.append({'path': path + [key], 'before': before[key], 'after': None, 'missing': 'after'})
        return
    if isinstance(before, list) and isinstance(after, list):
        array_field = path[-1] if path and isinstance(path[-1], str) else None
        name_field = named_arrays.get(array_field) if array_field else None
        before_index = _named_index(before, name_field, array_field) if name_field else None
        after_index = _named_index(after, name_field, array_field) if name_field else None
        if before_index is not None and after_index is not None:
            for identity, item in before_index.items():
                segment = item[name_field]
                if identity in after_index:
                    _sheet_diff(item, after_index[identity], path + [segment], diffs, named_arrays)
                else:
                    diffs.append({'path': path + [segment], 'before': item, 'after': None, 'missing': 'after'})
            for identity, item in after_index.items():
                if identity not in before_index:
                    diffs.append({'path': path + [item[name_field]], 'before': None, 'after': item, 'missing': 'before'})
            return
        for index in range(max(len(before), len(after))):
            if index < len(before) and index < len(after):
                _sheet_diff(before[index], after[index], path + [index], diffs, named_arrays)
            elif index < len(after):
                diffs.append({'path': path + [index], 'before': None, 'after': after[index], 'missing': 'before'})
            else:
                diffs.append({'path': path + [index], 'before': before[index], 'after': None, 'missing': 'after'})
        return
    if not _same_value(before, after):
        diffs.append({'path': path, 'before': before, 'after': after})


def _named_entry_dependencies(expected, actual, key):
    """Named-array entries recorded by identity, using the writer's own identity rule.

    Returns None unless the recorded list is a list of objects that all carry the
    array's identity field and the supplied value is a list; otherwise the list is
    compared exactly. Unrecorded entries are not dependencies (#323 A2 lines 14/43).
    """
    from updates.update_character_info import CHARACTER_NAMED_ARRAYS
    name_field = CHARACTER_NAMED_ARRAYS.get(key)
    if name_field is None or not isinstance(expected, list) or not isinstance(actual, list) or not expected:
        return None
    if not any(isinstance(item, dict) and name_field in item for item in expected):
        return None  # Not recorded as named entries at all: exact comparison applies.
    supplied = {}
    ambiguous = set()
    for item in actual:
        if isinstance(item, dict) and isinstance(item.get(name_field), str):
            identity = _entry_key(item, name_field, key)
            if identity in supplied:
                ambiguous.add(identity)  # The writer's own merge would face the same ambiguity.
            supplied[identity] = item
    return name_field, supplied, ambiguous


def dependency_mismatches(expected, actual, path=()) -> list[dict]:
    """Exact paths where recorded dependency facts are absent from or differ in the supplied data.

    A recorded object is matched key by key; a recorded list of named-array
    entries is matched entry by entry through the writer's identity rule; any
    other recorded value must equal the supplied value exactly. Missing facts are
    mismatches, never implicit approval. Two explicit typed namespaces unwrap the
    entry contract: ('validated','rules',name) against {value,source,supplied[,origin]}
    and ('validated','choices',name) against {value,source,state}; every other
    path (including ('validated','domains',...)) compares exactly.
    """
    if (len(path) == 3 and path[:2] == ('validated', 'rules') and isinstance(actual, dict)
            and 'value' in actual and set(actual) <= {'value', 'source', 'supplied', 'origin'}):
        # A reviewed rule fact is recorded as exactly its mechanical value, of any JSON
        # type, compared whole (no key-subset matching, no unwrapping). Provenance
        # stays in the supplied context; a {value,source} wrapper only matches when it
        # literally is the fact's value (#323 A3: verbatim source copies failed 6/6).
        if _same_value(expected, actual['value']):
            return []
        error = ('captured rule value differs from the current supplied fact; '
                 'recalculate from current inputs')
        if (isinstance(expected, dict) and 'source' in expected
                and not (isinstance(actual['value'], dict) and 'source' in actual['value'])):
            error += '; a provenance wrapper was recorded'
        return [{'path': list(path), 'expected': deepcopy(expected), 'actual': deepcopy(actual['value']),
                 'error': error}]
    if (len(path) == 3 and path[:2] == ('validated', 'choices') and isinstance(actual, dict)
            and 'value' in actual and set(actual) <= {'value', 'source', 'state'}):
        # A typed choice is a dependency fact recorded as exactly its selected value;
        # provenance and question state stay in the supplied context.
        if _same_value(expected, actual['value']):
            return []
        return [{'path': list(path), 'expected': deepcopy(expected), 'actual': deepcopy(actual['value']),
                 'error': (f'recorded value differs from the supplied choice value; record exactly '
                           f'context.validated.choices.{path[2]}.value')}]
    if path and isinstance(expected, list):
        named = _named_entry_dependencies(expected, actual, path[-1])
        if named is not None:
            name_field, supplied, ambiguous = named
            mismatches = []
            seen = set()
            for index, item in enumerate(expected):
                if not (isinstance(item, dict) and isinstance(item.get(name_field), str)
                        and item[name_field].strip()):
                    mismatches.append({'path': list(path) + [index], 'error': f'entry lacks {name_field}'})
                    continue
                identity = _entry_key(item, name_field, path[-1])
                entry_path = path + (item[name_field],)
                if identity in seen:
                    mismatches.append({'path': list(entry_path), 'error': 'recorded more than once'})
                    continue
                seen.add(identity)
                if identity in ambiguous:
                    mismatches.append({'path': list(entry_path),
                                       'error': 'ambiguous identity in supplied data: more than one '
                                                'supplied entry has this name; do not record this entry; '
                                                'depend on the effective total you consumed '
                                                '(effective.<field>) or on a validated rule fact instead'})
                    continue
                if identity not in supplied:
                    mismatches.append({'path': list(entry_path), 'expected': deepcopy(item),
                                       'error': 'named entry missing in supplied data'})
                    continue
                leaves = {field_name: value for field_name, value in item.items() if field_name != name_field}
                mismatches.extend(dependency_mismatches(leaves, supplied[identity], entry_path))
            return mismatches
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [{'path': list(path), 'expected': deepcopy(expected), 'actual': deepcopy(actual),
                     'error': 'recorded an object where the supplied data is not an object'}]
        mismatches = []
        for key, value in expected.items():
            if key not in actual:
                mismatches.append({'path': list(path) + [key], 'expected': deepcopy(value),
                                   'error': 'missing in supplied data'})
            else:
                mismatches.extend(dependency_mismatches(value, actual[key], path + (key,)))
        return mismatches
    if _same_value(expected, actual):
        return []
    return [{'path': list(path), 'expected': deepcopy(expected), 'actual': deepcopy(actual),
             'error': 'recorded value differs from supplied data'}]


def _dependencies_match(expected, actual):
    return not dependency_mismatches(expected, actual)


def consumed_operand_mismatches(proposal: DomainProposal, validated) -> list[dict]:
    """Validated operands a calculation actually consumed whose supplied value changed.

    Arithmetic evidence also covers the author's same-response rule facts, which
    are proposed outputs rather than captured inputs.
    """
    mismatches = []

    def walk(expression):
        if not isinstance(expression, dict):
            return
        if expression.get('source') == 'validated':
            path = expression.get('path')
            try:
                actual = _path_value(validated, path, 'validated')
            except (TypeError, ValueError):
                mismatches.append({'path': ['validated'] + (path if isinstance(path, list) else []),
                                   'expected': deepcopy(expression.get('value')),
                                   'error': 'missing in supplied data'})
                return
            if not _same_value(actual, expression.get('value')):
                mismatches.append({'path': ['validated'] + list(path), 'expected': deepcopy(expression.get('value')),
                                   'actual': deepcopy(actual), 'error': 'recorded value differs from supplied data'})
        elif 'source' not in expression:
            for operand in expression.get('operands') or []:
                walk(operand)

    for calculation in proposal.calculations:
        if isinstance(calculation, dict):
            walk(calculation.get('expression'))
    return mismatches


def validated_view(ws: LevelUpWorkspace) -> dict:
    """The approved dependency context: reviewed facts, recorded choices, approved changes.

    A choice's state is its question entry's state when present, else 'answered' (a
    retained choice whose reopened question was dropped by `retract`: the LAST
    ACCEPTED ANSWER, never a claim of current legal applicability; Custodian FYI-R6-3).
    """
    choices = {}
    for name, entry in ws.choices.items():
        question = ws.questions.get(name)
        state = question['state'] if (question is not None and 'state' in question) else 'answered'
        choices[name] = {'value': entry.get('value'), 'source': entry.get('source'), 'state': state}
    domains = {}
    for domain, review in ws.reviews.items():
        if review.valid:
            proposal = ws.proposals.get(domain)
            if isinstance(proposal, DomainProposal):
                domains[domain] = deepcopy(proposal.changes)
    return {'rules': deepcopy(ws.rule_facts), 'choices': choices, 'domains': domains}


def sources_for_admission(packet: dict, proposal: DomainProposal) -> dict:
    """Packet views plus validated.rules merged with the proposal's own pending facts.

    An author's own supplied rule facts are legal operands before review; the
    reviewer still judges their applicability at the next cycle.
    """
    validated = deepcopy(packet.get('validated') or {})
    rules = dict(validated.get('rules') or {})
    for name, fact in (proposal.rule_facts or {}).items():
        rules[name] = deepcopy(fact)
    validated['rules'] = rules
    return {'stored': packet.get('stored'), 'effective': packet.get('effective'), 'validated': validated}


def validate_player_question(question):
    """Shared typed question shape; option legality belongs to model validation."""
    if not isinstance(question, dict):
        raise ValueError('a player question must be an object')
    if not isinstance(question.get('choice'), str) or not question['choice'].strip():
        raise ValueError('a player question requires a nonempty string "choice" key naming the stable '
                         'player-owned choice; the wire key is "choice", not "name" (a "name" key belongs '
                         'only to an option object or a reference question)')
    if not isinstance(question.get('prompt'), str) or not question['prompt'].strip():
        raise ValueError('a player question requires a nonempty string "prompt" key')
    # Structural player-question contract: options is null or a list of option
    # objects, each with a nonempty name/summary/source; facts is an object.
    # Code never chooses the legal options - it only enforces their shape.
    if 'options' in question:
        options = question['options']
        if options is not None:
            if not isinstance(options, list):
                raise ValueError('a player question "options" field must be null or a JSON array of option objects')
            for option in options:
                if not isinstance(option, dict):
                    raise ValueError('each player question "options" entry must be a JSON object with "name", "summary" and "source"')
                for attribute in ('name', 'summary', 'source'):
                    if not isinstance(option.get(attribute), str) or not option[attribute].strip():
                        raise ValueError('each player question option requires a nonempty string "name", "summary" and "source"')
    if 'facts' in question and not isinstance(question['facts'], dict):
        raise ValueError('a player question "facts" field must be a JSON object, not an array or other type')


def record_choices(ws: LevelUpWorkspace, choices: dict) -> set[str]:
    """Merge typed choices; return names whose value changed; mark answered when asked.

    A retained choice whose question entry was dropped is left as is (no KeyError);
    reviews are never touched here.
    """
    changed = set()
    for name, entry in choices.items():
        new_entry = {key: deepcopy(entry[key]) for key in ('value', 'source')}
        old = ws.choices.get(name)
        if old is not None and not _same_value(old.get('value'), new_entry.get('value')):
            changed.add(name)
        ws.choices[name] = new_entry
        question = ws.questions.get(name)
        if question is not None:
            question['state'] = 'answered'
    return changed


def answered_questions(ws: LevelUpWorkspace) -> list[str]:
    """Names in ws.choices whose question entry is absent or in state 'answered'."""
    result = []
    for name in ws.choices:
        question = ws.questions.get(name)
        if question is None or question.get('state') == 'answered':
            result.append(name)
    return result


def pending_questions(ws: LevelUpWorkspace) -> list[dict]:
    """Question dicts (with their stable name) in state 'open' or 'reopened'."""
    return [{'name': name, **question} for name, question in ws.questions.items()
            if question.get('state') in ('open', 'reopened')]


def retract(ws: LevelUpWorkspace, domain: Domain) -> None:
    """The ONE transition that makes a repaired domain dispatchable again.

    Pops the review and drops rule_facts with origin == domain. Interview questions,
    recorded choices, the latest draft and every live per-origin constraint stay.
    """
    ws.reviews.pop(domain, None)
    for name in [name for name, fact in ws.rule_facts.items() if fact.get('origin') == domain]:
        ws.rule_facts.pop(name, None)


def rule_fact_conflicts(approved: dict, incoming: dict, origin: Domain) -> list[dict]:
    """Incoming facts that disagree with an approved fact of a DIFFERENT origin.

    A same-origin replacement is not a conflict. Each conflicting fact yields an
    error for the approved origin and one for the incoming origin, so both
    re-author (CU3-1).
    """
    errors = []
    for name, entry in incoming.items():
        approved_entry = approved.get(name)
        if approved_entry is None or approved_entry.get('origin') == origin:
            continue
        if not _same_value(approved_entry.get('value'), entry.get('value')):
            errors.append({'name': name, 'origin': approved_entry.get('origin'),
                           'value': approved_entry.get('value'),
                           'error': 'rule fact conflicts with an approved fact of another origin'})
            errors.append({'name': name, 'origin': origin, 'value': entry.get('value'),
                           'error': 'rule fact conflicts with an approved fact of another origin'})
    return errors


def promote(ws: LevelUpWorkspace, domain: Domain, proposal: DomainProposal) -> list[dict]:
    """Approve a domain's draft, promoting its facts, or report a conflict.

    Always retracts the promoting domain first. On a fact conflict nothing is
    promoted and the approved origin of every conflicting fact is retracted so both
    re-author (CU3-1). Otherwise the review is valid, the facts are stored with this
    origin for subsequent fixed-order consumers.
    """
    retract(ws, domain)
    conflicts = rule_fact_conflicts(ws.rule_facts, proposal.rule_facts, domain)
    if conflicts:
        for other in {conflict['origin'] for conflict in conflicts
                      if conflict['origin'] is not None and conflict['origin'] != domain}:
            retract(ws, other)
        return conflicts
    ws.proposals[domain] = proposal
    ws.reviews[domain] = DomainReview(True, [])
    for name, fact in (proposal.rule_facts or {}).items():
        entry = dict(fact)
        entry['origin'] = domain
        ws.rule_facts[name] = entry
    return []


def withdraw(ws: LevelUpWorkspace, values: dict, changed_names) -> dict[Domain, list[dict]]:
    """Retract every approved consumer of a changed choice or a retracted fact.

    For each changed name, retract its KNOWN asking domain (from the question
    entry) even when it holds no approval and is awaiting another obsolete
    question - the approved-only filter guards downstream consumer comparison, not
    this asking-domain step. Then run the ONE fixed-point dependency withdrawal
    (`changed_dependencies`) over approved domains, which recomputes the validated
    view as retractions occur so consumers of removed facts also retract. Every
    retraction is a `retract` call; each retracted domain's constraints are marked
    stale with the changed choice names and the retracted fact names its mismatches
    identify (obligations stand; stated figures must be re-derived).
    """
    withdrawn = {}
    changed_names = set(changed_names)

    def mark_stale(domain, mismatches):
        constraints = ws.constraints.get(domain)
        if not constraints:
            return
        facts = []
        choices = []
        for mismatch in mismatches:
            path = mismatch.get('path') or []
            if len(path) >= 3 and path[0] == 'validated' and path[1] == 'rules' and path[2] not in facts:
                facts.append(path[2])
            elif len(path) >= 3 and path[0] == 'validated' and path[1] == 'choices' and path[2] not in choices:
                choices.append(path[2])
        for name in sorted(changed_names):
            if name not in choices:
                choices.append(name)
        for key, names in (('facts', facts), ('choices', choices)):
            if not names:
                continue
            for constraint in constraints.values():
                recorded = constraint.stale_inputs.setdefault(key, [])
                for name in names:
                    if name not in recorded:
                        recorded.append(name)

    for name in changed_names:
        question = ws.questions.get(name)
        if question is not None:
            asking = question.get('domain')
            retract(ws, asking)
            mismatches = withdrawn.setdefault(asking, [])
            mismatches.append({'path': ['validated', 'choices', name],
                               'error': 'asking domain of a changed choice'})
            mark_stale(asking, mismatches)

    for domain, mismatches in changed_dependencies(ws, values).items():
        withdrawn[domain] = mismatches
        mark_stale(domain, mismatches)
    return withdrawn


def changed_dependencies(workspace: LevelUpWorkspace, values: dict) -> dict[Domain, list[dict]]:
    """The single fixed-point dependency withdrawal over APPROVED domains only.

Each round recomputes the validated view from the workspace so a retracted
domain's changes and a removed rule fact both vanish from the supplied context and
their transitive consumers are withdrawn too. Code-owned input snapshots and the
validated operands each calculation consumed are both checked. Every withdrawal is
a retract() call; drafts, choices and live constraints are retained for correction.
"""
    invalidated = {}
    while True:
        current = {'stored': values.get('stored'), 'effective': values.get('effective'),
                   'validated': validated_view(workspace)}
        validated = current['validated']
        progressed = False
        for domain, proposal in list(workspace.proposals.items()):
            if domain not in workspace.reviews:
                continue
            mismatches = (_input_mismatches(proposal, current)
                          + consumed_operand_mismatches(proposal, validated))
            if mismatches:
                retract(workspace, domain)
                invalidated[domain] = mismatches
                progressed = True
        if not progressed:
            return invalidated


def supplied_operand_paths(validated: dict) -> list[list]:
    """Every validated operand path code can resolve; authors never guess names.

    Reviewed rule facts resolve under ["rules", name, "value"] (including numeric
    leaves of a nested value); a recorded choice under ["choices", name, "value"];
    an approved sibling domain's absolute changes at ["domains", domain, ...leaf
    path]. Only finite numbers are listed: text, booleans and lists are dependency
    facts, not arithmetic operands. The list is code-generated from the packet, so
    an absent path is missing evidence to ask for, never a constant to invent.
    """
    paths = []

    def leaves(value, prefix):
        if isinstance(value, dict):
            for key, item in value.items():
                leaves(item, prefix + [key])
        elif isinstance(value, list):
            for index, item in enumerate(value):
                leaves(item, prefix + [index])
        elif type(value) is int or (type(value) is float and math.isfinite(value)):
            paths.append(prefix)

    rules = validated.get('rules') or {}
    for name in sorted(rules):
        if isinstance(rules[name], dict) and 'value' in rules[name]:
            leaves(rules[name]['value'], ['rules', name, 'value'])
    choices = validated.get('choices') or {}
    for name in sorted(choices):
        if isinstance(choices[name], dict) and 'value' in choices[name]:
            leaves(choices[name]['value'], ['choices', name, 'value'])
    for domain in sorted(validated.get('domains') or {}):
        leaves(validated['domains'][domain], ['domains', domain])
    return paths


def _path_value(data, path, source='supplied'):
    if not isinstance(path, list):
        raise ValueError('path must be an array of object keys or array indexes')
    for key in path:
        if isinstance(data, dict) and isinstance(key, str) and key in data:
            data = data[key]
        elif isinstance(data, list) and type(key) is int and 0 <= key < len(data):
            data = data[key]
        else:
            raise ValueError(f'path {path!r} does not identify a value in the {source} data')
    return data


def _validated_operand(validated, path):
    try:
        return _path_value(validated, path, 'validated')
    except ValueError:
        raise ValueError(f'validated operand path {path!r} is not among the supplied validated facts. '
                         'Use the actual supplied fact or declare the needed current-rule fact '
                         'with honest provenance for independent review; never invent an operand path.')


def _number(value):
    if type(value) is int or (type(value) is float and math.isfinite(value)):
        return value
    raise ValueError('operand/result must be a finite number, not a boolean or text')


def _calculate(expression, sources):
    if not isinstance(expression, dict):
        raise ValueError('calculation must be structured data, never expression text')
    if 'source' in expression:
        if set(expression) != {'source', 'path', 'value'}:
            raise ValueError('operand requires only source, path and observed value')
        source = expression['source']
        if source not in ('stored', 'effective', 'validated'):
            raise ValueError('operand source must identify a supplied storage view or validated fact')
        if source == 'validated':
            actual = _number(_validated_operand(sources[source], expression['path']))
        else:
            actual = _number(_path_value(sources[source], expression['path'], source))
        claimed = _number(expression['value'])
        if not _same_value(actual, claimed):
            raise ValueError(f'operand differs from supplied source: actual={actual}, proposed={claimed}')
        return actual
    if set(expression) != {'operation', 'operands'} or not isinstance(expression['operands'], list):
        raise ValueError('formula requires operation and operand array')
    values = [_calculate(operand, sources) for operand in expression['operands']]
    operation = expression['operation']
    if operation == 'add' and values:
        result = sum(values)
    elif operation == 'subtract' and len(values) == 2:
        result = values[0] - values[1]
    elif operation == 'multiply' and values:
        result = math.prod(values)
    elif operation == 'divide' and len(values) == 2:
        result = values[0] / values[1]
    elif operation == 'floor' and len(values) == 1:
        result = math.floor(values[0])
    elif operation == 'ceil' and len(values) == 1:
        result = math.ceil(values[0])
    elif operation == 'min' and values:
        result = min(values)
    elif operation == 'max' and values:
        result = max(values)
    else:
        raise ValueError('unsupported arithmetic operation or operand shape')
    return _number(result)


def validate_calculations(proposal: DomainProposal, sources: dict) -> list[dict]:
    """Check supplied arithmetic without choosing rules or changing proposals.

    Sources are caller-owned stored/effective snapshots and approved rule/domain
    facts, never the author's unvalidated literal constants. Agentic review still
    judges applicability and completeness: an empty calculation list is not
    mechanical approval. Target paths address the author's absolute changes,
    before the writer-native delta adapter.
    """
    errors = []
    for calculation in proposal.calculations:
        field_path = calculation.get('field') if isinstance(calculation, dict) else None
        try:
            if not isinstance(calculation, dict) or set(calculation) != {'field', 'expression'}:
                raise ValueError('each calculation must be exactly {"field": [path in changes], '
                                 '"expression": operand or formula}')
            try:
                actual = _number(_path_value(proposal.changes, field_path, 'changes'))
            except ValueError as exc:
                raise ValueError(f'calculation field {field_path!r} does not locate a numerical value '
                                 f"in this proposal's changes ({exc})")
            expected = _calculate(calculation['expression'], sources)
            if actual != expected:
                errors.append({'field': field_path, 'actual': actual, 'expected': expected,
                               'error': 'proposed value disagrees with grounded arithmetic'})
        except (KeyError, IndexError, TypeError, ValueError, ArithmeticError) as exc:
            errors.append({'field': field_path, 'error': str(exc)})
    return errors
