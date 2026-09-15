# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Specialist-owned level-up computation and code-coordinated private correction loops."""

from copy import deepcopy
from concurrent.futures import FIRST_COMPLETED, Future, wait
from dataclasses import dataclass
import json
from pathlib import Path
import threading
from typing import Literal
from uuid import uuid4

from utils.level_up_workspace import (
    Constraint, Domain, DomainProposal, DomainReview, FORWARD_ORDER, DEPENDS_ON, dependents_of,
    _capture_inputs, merge_domain_changes, pending_questions, promote,
    retract, sheet_diff, sources_for_admission,
    validate_calculations, validated_view, withdraw, _same_value)


DOMAIN_TASKS = {
    'features': ('T115', 'T116'),
    'spells': ('T117', 'T118'),
    'numbers': ('T119', 'T120'),
}

def _load_response(raw):
    data = json.loads(raw)
    # Reject both nonstandard constants and numeric exponent overflow before
    # these values reach private retained work or a later request serializer.
    json.dumps(data, allow_nan=False)
    return data


# Original inputs stay in a code-owned snapshot, not in the model's output.
# The former specialist questions field is retired by the postapproval owner
# direction; authors now report the lawful default selections they had to make
# in variations (metadata for the DM post-save note, never a player prompt).
ENVELOPE_ORDER = ('calculations', 'rule_facts', 'rule_refs', 'variations', 'changes')
REVIEW_STAGES = ('proposal',)   # one independent review per domain draft; nothing reviews the merged sheet again


def _envelope_feedback(data, fields):
    """Name exactly what is missing, extra or misnested; never move a value (#323 A2 lines 15-52)."""
    missing = [key for key in ENVELOPE_ORDER if key not in data]
    unexpected = [key for key in data if key not in fields]
    parts = ['author JSON must have exactly the top-level keys calculations, rule_facts, rule_refs, '
             'variations and changes; original source data is retained by code, not returned by the author']
    if missing:
        parts.append('missing top-level: ' + ', '.join(missing))
    if unexpected:
        parts.append('unexpected top-level: ' + ', '.join(unexpected))
    return '; '.join(parts)


def _validate_variation(variation):
    """A variation records one lawful default/selection the author had to make.

    Shape only (field path, chosen selection, plain-language reason); it is never a
    character-sheet field and never a player prompt. The independent reviewer checks
    the note against the actual proposed change and explicit choices.
    """
    if not isinstance(variation, dict) or set(variation) != {'field', 'selection', 'reason'}:
        raise ValueError('each variation must be exactly {"field": path, "selection": chosen value, '
                         '"reason": plain-language comment}')
    field = variation['field']
    if not (isinstance(field, str) and field.strip()) and not (
            isinstance(field, list) and field and all(
                (isinstance(part, str) and part.strip()) or (type(part) is int and part >= 0)
                for part in field)):
        raise ValueError('a variation field must be a nonempty path string or array of keys/indexes')
    if not isinstance(variation['reason'], str) or not variation['reason'].strip():
        raise ValueError('a variation reason must be a nonempty plain-language string')


def parse_domain_proposal(domain, raw, packet):
    """Bind five author fields to an independent code-owned input snapshot."""
    if domain not in DOMAIN_TASKS:
        raise ValueError('unknown specialist domain')
    data = _load_response(raw)
    fields = set(ENVELOPE_ORDER)
    if not isinstance(data, dict) or set(data) != fields:
        raise ValueError(_envelope_feedback(data if isinstance(data, dict) else {}, fields))
    for key in ('changes', 'rule_facts'):
        if not isinstance(data[key], dict):
            raise ValueError(f'{key} must be an object')
    for key in ('calculations', 'variations'):
        if not isinstance(data[key], list) or any(not isinstance(item, dict) for item in data[key]):
            raise ValueError(f'{key} must be an array of objects')
    if not isinstance(data['rule_refs'], list) or any(not isinstance(item, str) or not item.strip()
                                                    for item in data['rule_refs']):
        raise ValueError('rule_refs must be an array of nonempty source references '
                         '(strings only, not name/source objects). Put structured facts in rule_facts '
                         'and default-selection notes in variations; do not change the other fields.')
    for name, fact in data['rule_facts'].items():
        if not isinstance(fact, dict) or 'value' not in fact:
            raise ValueError(f'rule_fact {name!r} requires value, source and a supplied flag')
        if not isinstance(fact.get('source'), str) or not fact['source'].strip():
            raise ValueError(f'rule_fact {name!r} requires a nonempty source')
        if type(fact.get('supplied')) is not bool:
            raise ValueError(f'rule_fact {name!r} requires a boolean supplied flag')
    for variation in data['variations']:
        _validate_variation(variation)
    return DomainProposal(domain, packet['draft'], _capture_inputs(packet, domain), data['changes'],
                          data['calculations'], data['rule_refs'], data['variations'], data['rule_facts'])


def parse_domain_review(raw, packet=None, *, domain=None):
    data = _load_response(raw)
    if not isinstance(data, dict) or set(data) != {'valid', 'errors'} or type(data['valid']) is not bool:
        raise ValueError('review requires boolean valid and errors array')
    if not isinstance(data['errors'], list) or any(not isinstance(error, dict) or not error
                                                 for error in data['errors']):
        raise ValueError('review errors must be nonempty objects')
    for error in data['errors']:
        if not error.get('field') or not isinstance(error.get('correction'), str) or not error['correction'].strip():
            raise ValueError('each review error requires a nonempty "field" and a nonempty string "correction" key '
                             'stating the actionable repair; supplying "required" evidence does not replace '
                             'the literal "correction" key')
        if 'domain' in error and error['domain'] not in DOMAIN_TASKS:
            raise ValueError('a review error domain must name a specialist domain')
        if (packet is not None and packet.get('review_stage') == 'proposal' and domain is not None
                and error.get('domain', domain) != domain
                and error['domain'] not in packet.get('validated', {}).get('domains', {})):
            raise ValueError('proposal review cannot require unfinished downstream work: judge '
                             'this author and the supplied upstream facts now')
    if data['valid'] == bool(data['errors']):
        raise ValueError('approval requires no errors; rejection requires corrections')
    return DomainReview(data['valid'], data['errors'])


def request_config(task_id, provider):
    """Use the same canonical registry/adapter for every supported provider."""
    from model_config import resolve_callsite_config
    config = resolve_callsite_config(task_id, provider)
    config['response_format'] = None if provider == 'lmstudio' else {'type': 'json_object'}
    return config


def build_messages(domain, packet, proposal=None):
    """Keep complete supplied facts/references and private feedback together."""
    if domain not in DOMAIN_TASKS:
        raise ValueError('unknown specialist domain')
    role = 'review' if proposal is not None else 'author'
    prompt_root = Path('prompts/leveling')
    contract = (prompt_root / 'specialist_contract.txt').read_text(encoding='utf-8')
    prompt = (prompt_root / f'{domain}_{role}.txt').read_text(encoding='utf-8')
    payload = {'context': deepcopy(packet)}
    if proposal is not None:
        payload['proposal'] = {'domain': proposal.domain, 'draft': proposal.draft, **_project_proposal(proposal)}
    return [{'role': 'system', 'content': contract}, {'role': 'system', 'content': prompt},
            {'role': 'user', 'content': json.dumps(payload, ensure_ascii=True, allow_nan=False)}]


class DomainResponseError(ValueError):
    """Retain the actual rejected answer for the coordinator's private repair."""

    def __init__(self, raw, cause):
        super().__init__(str(cause))
        self.raw = raw


def _request(domain, packet, scope, proposal=None, status_emit=None):
    from utils.capture.live_provider_call import LiveProviderSuperseded
    if scope is None:
        raise ValueError('specialist request requires captured lifecycle authority')
    if scope.is_superseded():
        raise LiveProviderSuperseded('level-up specialist superseded before request')
    from core.ai import api_client
    from utils.capture.multi_model_capture import capture_and_fanout, register_callsite

    task_id = DOMAIN_TASKS[domain][1 if proposal is not None else 0]
    provider = packet['provider']
    register_callsite(task_id, 'core/ai/level_up_specialists.py', 0)
    response = capture_and_fanout(
        task_id, api_client.create_completion,
        _request_provider=provider, _live_selected='required',
        _detached_scope=scope, _detached_status=status_emit,
        messages=build_messages(domain, packet, proposal),
        **request_config(task_id, provider),
    )
    if scope.is_superseded():
        raise LiveProviderSuperseded('level-up specialist superseded after request')
    raw = response.choices[0].message.content
    try:
        return parse_domain_review(raw, packet, domain=domain) if proposal is not None else parse_domain_proposal(domain, raw, packet)
    except (TypeError, ValueError) as exc:
        raise DomainResponseError(raw, exc) from exc


def request_domain(domain, packet, scope, status_emit=None):
    """One completed semantic author request; no autonomous correction loop.

    status_emit is the coordinator-owned truthful phase sink for provider
    heartbeats; None keeps the generic transport status.
    """
    return _request(domain, packet, scope, status_emit=status_emit)


def review_domain(proposal, packet, scope, status_emit=None):
    """One independent review of the exact supplied private proposal."""
    return _request(proposal.domain, packet, scope, proposal, status_emit=status_emit)


def collect_domain_work(work, parent, *, on_result=None):
    """Completion-own all requested work, preserving each result or failure.

    The coordinator supplies domain author/review calls bound to immutable
    packets. Each receives its exact registered child scope. No semantic retries,
    detached work, time budget or provider-dependent domain omission lives here.
    """
    from utils.capture.live_provider_call import open_advisory_scopes, LiveProviderSuperseded
    if not work:
        return {}
    scopes = open_advisory_scopes(parent, f'level-up-{uuid4()}', len(work), completion_required=True)
    if len(scopes) != len(work):
        if parent is not None and parent.is_superseded():
            raise LiveProviderSuperseded('level-up work superseded before admission')
        raise ValueError('level-up work has no current captured parent authority')
    submitted = set()
    results = {}
    futures = {}
    threads = []

    def run(call, scope, future):
        try:
            if scope.is_superseded():
                raise LiveProviderSuperseded('level-up work superseded before start')
            future.set_result(call(scope))
        except BaseException as exc:
            future.set_exception(exc)
        finally:
            scope.finish()

    try:
        # Explicit thread admission, as used by existing voice workers: unlike
        # executor.submit, a failed start leaves no queued job for another worker.
        for index, ((domain, call), scope) in enumerate(zip(work.items(), scopes)):
            future = Future()
            futures[domain] = future
            try:
                thread = threading.Thread(target=run, args=(call, scope, future),
                                          name=f'level-up-{domain}', daemon=False)
                thread.start()
                threads.append(thread)
                submitted.add(index)
            except Exception as exc:
                scope.finish()
                future.set_exception(exc)
        domain_of = {future: domain for domain, future in futures.items()}
        pending = set(futures.values())
        while pending:
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                domain = domain_of[future]
                try:
                    results[domain] = future.result()
                except Exception as exc:
                    results[domain] = exc
                if on_result is not None:
                    on_result(domain, results[domain])
    finally:
        for thread in threads:
            thread.join()
        # Constructor/admission failure must not strand reserved child scopes.
        for index, scope in enumerate(scopes):
            if index not in submitted:
                scope.finish()
    if parent.is_superseded():
        raise LiveProviderSuperseded('level-up work superseded during collection')
    for result in results.values():
        if isinstance(result, LiveProviderSuperseded):
            raise result
    return results


_H6_TOP_PATHS = ('hitPoints', 'experience_points')


def _preserved_h6(before, after):
    """Report equal H6 resource values, using the writer's named-entry identity.

    These dotted paths are display labels only, never parsed as mutation paths.
    Missing/null resource objects are changes, not preserved current counts.
    """
    from updates.update_character_info import CHARACTER_NAMED_ARRAYS
    from utils.level_up_workspace import _named_index

    preserved = []
    if not isinstance(before, dict) or not isinstance(after, dict):
        return preserved
    for key in _H6_TOP_PATHS:
        if key in before and key in after and _same_value(before[key], after[key]):
            preserved.append(key)

    def current(left, right, path):
        if (isinstance(left, dict) and isinstance(right, dict)
                and 'current' in left and 'current' in right
                and _same_value(left['current'], right['current'])):
            preserved.append('.'.join(str(segment) for segment in path + ('current',)))

    def walk(left, right, path=(), array_field=None):
        if isinstance(left, dict) and isinstance(right, dict):
            for key, value in left.items():
                if key not in right:
                    continue
                child_path = path + (key,)
                if key == 'usage':
                    current(value, right[key], child_path)
                elif key == 'spellSlots' and isinstance(value, dict) and isinstance(right[key], dict):
                    for level, slot in value.items():
                        if level in right[key]:
                            current(slot, right[key][level], child_path + (level,))
                walk(value, right[key], child_path, key)
        elif isinstance(left, list) and isinstance(right, list):
            name_field = CHARACTER_NAMED_ARRAYS.get(array_field)
            left_index = _named_index(left, name_field, array_field) if name_field else None
            right_index = _named_index(right, name_field, array_field) if name_field else None
            if left_index is not None and right_index is not None:
                for identity, item in left_index.items():
                    if identity in right_index:
                        walk(item, right_index[identity], path + (item[name_field],))
            else:
                for index, (old, new) in enumerate(zip(left, right)):
                    walk(old, new, path + (index,))

    walk(before, after)
    return preserved


@dataclass
class LayerResult:
    revision: int
    layer: Literal['assembled', 'interviewing']
    prepared: dict | None

    def report(self, ws, *, prior_commit_proposed, observed_write):
        """D-3.6: pending questions and recorded choices read the workspace AT CALL TIME."""
        validated = validated_view(ws)
        pending = [{'choice': question['name'], 'domain': question.get('domain'),
                    'prompt': question.get('prompt'), 'options': question.get('options'),
                    'facts': question.get('facts', {}), 'state': question['state']}
                   for question in pending_questions(ws)]
        domains = {}
        for domain in DOMAIN_TASKS:
            if domain in ws.reviews:
                state = 'approved'
            else:
                state = 'not_started' if self.layer == 'interviewing' else 'working'
            domains[domain] = {'state': state}
        assembled = None
        if self.layer == 'assembled' and self.prepared is not None:
            checks = self.prepared.get('checks') or {}
            before = self.prepared['before']
            after = self.prepared['after']
            assembled = {'diff': sheet_diff(before, after),
                         'preserved': _preserved_h6(before, after),
                         'code_owned': {'removed_fields': checks.get('removed_fields', []),
                                        'armor_repair': checks.get('armor_repair', [])}}
        return {'revision': self.revision, 'layer': self.layer,
                'pending_player_questions': pending, 'recorded_choices': validated['choices'],
                'domains': domains, 'validated_rule_facts': validated['rules'],
                'assembled': assembled, 'prior_commit_proposed': prior_commit_proposed,
                'observed_write': observed_write}


class AssemblyConflict(ValueError):
    """Every conflict entry lands in a bucket; an empty carrier is a programming error (CU4-1)."""

    domain_errors: dict[Domain, list[dict]]
    unattributed: list[dict]

    def __init__(self, domain_errors: dict[Domain, list[dict]], unattributed: list[dict]):
        if not domain_errors and not unattributed:
            raise ValueError('assembly conflict carrier must hold at least one entry')
        self.domain_errors = domain_errors
        self.unattributed = unattributed
        super().__init__('assembly conflict')


def _project_proposal(proposal):
    """Only author fields return to models; private source snapshots stay in code."""
    return {key: deepcopy(getattr(proposal, key)) for key in ENVELOPE_ORDER}


def _spell_list_errors(proposal, stored):
    """Count the spells author's own lists against the facts it declared (code owns the counting).

    The author declares prepared_capacity, cantrip_count and always_prepared_grants
    (name + spell level). The lists must agree with them: every grant present in
    preparedSpells and in the level list of its own spell level, exactly
    capacity-many non-grant preparations, the class cantrip count, no duplicate
    names, and every prepared spell present in some level list. On Luna the author
    got the arithmetic wrong in four of five drafts and a reviewer approved a wrong
    count once (replay, 2026-09-14); the reviewer judges merit, code judges counts.
    """
    facts = proposal.rule_facts if isinstance(proposal.rule_facts, dict) else {}
    changes = proposal.changes if isinstance(proposal.changes, dict) else {}
    spellcasting = changes.get('spellcasting')
    if not isinstance(spellcasting, dict):
        return []
    errors = []

    def fact(name):
        entry = facts.get(name)
        return entry.get('value') if isinstance(entry, dict) else None

    capacity, cantrip_count, grants = fact('prepared_capacity'), fact('cantrip_count'), fact('always_prepared_grants')
    if not isinstance(capacity, int) or not isinstance(cantrip_count, int) or not isinstance(grants, list) or any(
            not isinstance(g, dict) or not isinstance(g.get('name'), str) or not isinstance(g.get('level'), int) for g in grants):
        return [{'field': ['rule_facts'],
                 'error': 'declare rule_facts named exactly prepared_capacity (integer), cantrip_count (integer) and '
                          'always_prepared_grants (array of {"name": spell, "level": spell level integer}); code checks '
                          'your lists against them'}]
    grant_names = [g['name'] for g in grants]
    stored_spells = ((stored or {}).get('spellcasting') or {}).get('spells') or {}
    proposed_spells = spellcasting.get('spells') if isinstance(spellcasting.get('spells'), dict) else {}

    def level_list(level):
        key = 'level%d' % level
        value = proposed_spells.get(key, stored_spells.get(key))
        return value if isinstance(value, list) else []

    prepared = spellcasting.get('preparedSpells')
    if isinstance(prepared, list):
        seen = set()
        for name in prepared:
            if name in seen:
                errors.append({'field': ['spellcasting', 'preparedSpells'], 'error': 'remove the duplicate entry %r' % name})
            seen.add(name)
        for name in grant_names:
            if name not in prepared:
                errors.append({'field': ['spellcasting', 'preparedSpells'], 'error': 'add the always-prepared grant %r' % name})
        ordinary = [name for name in prepared if name not in grant_names]
        if len(ordinary) != capacity:
            errors.append({'field': ['spellcasting', 'preparedSpells'],
                           'error': 'preparedSpells holds %d ordinary (non-grant) spells but prepared_capacity is %d: the list '
                                    'must be exactly %d ordinary spells plus the %d grants = %d names'
                                    % (len(ordinary), capacity, capacity, len(grant_names), capacity + len(grant_names))})
        all_levels = [n for level in range(1, 10) for n in level_list(level)]
        for name in prepared:
            if name not in all_levels:
                errors.append({'field': ['spellcasting', 'spells'],
                               'error': '%r is in preparedSpells but in no spells.levelN list: add it to the list of its spell level' % name})
    for g in grants:
        if g['name'] not in level_list(g['level']):
            errors.append({'field': ['spellcasting', 'spells', 'level%d' % g['level']],
                           'error': 'add the grant %r to spells.level%d (keep the existing entries)' % (g['name'], g['level'])})
    cantrips = proposed_spells.get('cantrips')
    if isinstance(cantrips, list):
        if len(cantrips) != cantrip_count:
            errors.append({'field': ['spellcasting', 'spells', 'cantrips'],
                           'error': 'cantrips holds %d names but cantrip_count is %d: list exactly %d distinct cantrips'
                                    % (len(cantrips), cantrip_count, cantrip_count)})
        if len(set(cantrips)) != len(cantrips):
            errors.append({'field': ['spellcasting', 'spells', 'cantrips'], 'error': 'remove the duplicate cantrip'})
    # Every listed spell sits at its own level: the SRD reference index (a name
    # lookup in data/spell_repository.json) supplies the level; unresolved
    # names are left to the reviewer, never guessed.
    try:
        from core.ai.srd_reference import load_srd_reference_index
        index = load_srd_reference_index()
    except Exception:
        index = None
    if index is not None:
        listed = {}
        for level in range(1, 10):
            for name in level_list(level):
                listed.setdefault(name, []).append(level)
        for name, levels in sorted(listed.items()):
            reference = index.reference(name)
            actual = (reference or {}).get('entry', {}).get('level') if isinstance(reference, dict) else None
            if isinstance(actual, int) and actual >= 1 and levels != [actual]:
                errors.append({'field': ['spellcasting', 'spells'],
                               'error': '%r is a level %d spell: list it in spells.level%d only (it is in %s)'
                                        % (name, actual, actual, ', '.join('level%d' % l for l in levels))})
    return errors


def spells_merged_preview(proposal, stored):
    """The exact spellcasting block the writer would save for this proposal (omitted lists keep stored entries)."""
    from updates.update_character_info import deep_merge_dict
    changes = proposal.changes if isinstance(proposal.changes, dict) else {}
    if not isinstance(changes.get('spellcasting'), dict) or not isinstance((stored or {}).get('spellcasting'), dict):
        return None
    return deep_merge_dict(deepcopy(stored['spellcasting']), deepcopy(changes['spellcasting']))


def _admission_errors(domain, proposal, packet, ws):
    """Check calculations against original inputs and independently reviewed rule proposals."""
    sources = sources_for_admission(packet, proposal)
    errors = validate_calculations(proposal, sources)
    if domain == 'spells':
        errors = errors + _spell_list_errors(proposal, packet.get('stored'))
    return errors


def _replace_review(ws, domain, own_errors, draft):
    """An own reviewer verdict REPLACES this domain's review set: approval clears, rejection writes."""
    if own_errors:
        stamped = [{**error, 'raised_by': domain, 'raised_against': draft} for error in own_errors]
        ws.constraints[domain]['review'] = Constraint('review', domain, draft, stamped)
    else:
        ws.constraints[domain].pop('review', None)


def _clear_satisfied_assembly_constraints(domain, proposal, packet, ws):
    """Drop a merge or threshold objection that this admitted draft already satisfies.

    Those objections come from deterministic checks in code, so code can verify
    them again against the new draft before the reviewer sees the packet. Left in
    place, a reviewer re-asserted a stale "nameless attack entry" objection twelve
    times against a draft that named every entry (run 6, 2026-09-14). The reviewer
    still judges the draft on merit; it just no longer sees a check it passed.
    """
    constraints = ws.constraints.get(domain, {})
    if 'merge' in constraints:
        siblings = [ws.proposals[d] for d in FORWARD_ORDER if d != domain and d in ws.reviews and d in ws.proposals]
        _, merge_errors = merge_domain_changes(deepcopy(packet['stored']), siblings + [proposal])
        if not any(domain in (error.get('domains') or []) for error in merge_errors):
            constraints.pop('merge')
    if 'assembly' in constraints:
        remaining = []
        for error in constraints['assembly'].errors:
            if error.get('check') == 'exp_required_for_next_level':
                proposed = (proposal.changes or {}).get('exp_required_for_next_level')
                if proposed is not None and proposed != packet['stored'].get('exp_required_for_next_level'):
                    continue
            remaining.append(error)
        if not remaining:
            constraints.pop('assembly')
        elif len(remaining) != len(constraints['assembly'].errors):
            constraints['assembly'] = Constraint('assembly', domain, constraints['assembly'].draft, remaining)


def run_domain_cycle(domain, packet_for, ws, scope, status_emit, running):
    """One own-domain worker: author -> grounded admission -> independent review.

    Corrects privately until the author's proposal is admitted and its own
    independent reviewer approves it, then returns that approved DomainProposal.
    The fixed forward dispatcher owns promotion and downstream rebuild. There are
    no player, sibling or reference questions, no parks and no cooperative yields;
    a later author consumes the already-validated earlier outputs through its packet.
    """
    latest = ws.proposals.get(domain)
    while True:
        running[domain] = 'authoring'
        # RC5-6: bind this request's code-owned draft BEFORE the author call so the
        # admitted proposal and its review share one provenance (never a default 0).
        draft = ws.drafts.get(domain, 0) + 1
        ws.drafts[domain] = draft
        request_packet = dict(packet_for(domain))
        request_packet['draft'] = draft
        if latest is not None:
            request_packet['latest_proposal'] = _project_proposal(latest)
        try:
            proposal = request_domain(domain, request_packet, scope, status_emit)
        except DomainResponseError as exc:
            ws.constraints[domain]['admission'] = Constraint(
                'admission', domain, draft,
                [{'field': ['envelope'], 'error': 'author response invalid',
                  'correction': str(exc), 'rejected_response': exc.raw}])
            continue
        latest = proposal
        errors = _admission_errors(domain, proposal, request_packet, ws)
        if errors:
            ws.constraints[domain]['admission'] = Constraint('admission', domain, draft, errors)
            continue
        ws.constraints[domain].pop('admission', None)
        _clear_satisfied_assembly_constraints(domain, proposal, request_packet, ws)
        running[domain] = 'reviewing'
        review_packet = dict(packet_for(domain))
        review_packet['latest_proposal'] = _project_proposal(proposal)
        review_packet['review_stage'] = 'proposal'
        if domain == 'spells':
            # The reviewer judges the merged lists it would save, not the delta's
            # omissions: a Luna reviewer rejected five correct drafts for "missing"
            # stored entries the delta rightly left untouched (replay, 2026-09-14).
            preview = spells_merged_preview(proposal, review_packet.get('stored'))
            if preview is not None:
                review_packet['merged_preview'] = {'spellcasting': preview}
        previous_format = ws.constraints[domain].get('review_format')
        format_state = deepcopy(previous_format.errors[0]) if previous_format else {}
        try:
            review = _review_until_parsed(proposal, review_packet, scope, status_emit,
                                          format_state=format_state)
        finally:
            if format_state:
                ws.constraints[domain]['review_format'] = Constraint(
                    'review_format', domain, draft, [format_state])
            else:
                ws.constraints[domain].pop('review_format', None)
        if review.valid:
            ws.constraints[domain].pop('review', None)
            return proposal
        upstream = {}
        for error in review.errors:
            target = error.get('domain', domain)
            if target != domain:
                upstream.setdefault(target, []).append(error)
        if upstream:
            ws.proposals[domain] = proposal
            own_errors = [error for error in review.errors if error.get('domain', domain) == domain]
            if own_errors:
                upstream[domain] = own_errors
            raise AssemblyConflict(upstream, [])
        # The independent reviewer rejected this author's own work on merit.
        _replace_review(ws, domain, review.errors, draft)


PLAYER_PHASE = {
    # What the player reads in the input box while a domain is in flight. These
    # are game words, never the internal author/review/specialist vocabulary.
    ('features', 'authoring'): 'working out the new class features',
    ('features', 'reviewing'): 'double-checking the class features',
    ('spells', 'authoring'): 'choosing the spells',
    ('spells', 'reviewing'): 'double-checking the spells',
    ('numbers', 'authoring'): 'recalculating the numbers',
    ('numbers', 'reviewing'): 'double-checking the numbers',
}


def player_phase(domains_verbs):
    """One player-facing line for the set of (domain, verb) pairs in flight."""
    parts = [PLAYER_PHASE.get((d, v), f'{v} {d}') for d, v in sorted(domains_verbs)]
    if not parts:
        return 'gathering the results'
    if len(parts) == 1:
        return parts[0]
    return ', '.join(parts[:-1]) + ' and ' + parts[-1]


def _running_status(status, running):
    """The manager's _running_emit, moved (LGC2-3): one heartbeat sink whose label is computed
    per call from the shared {domain: verb} map; workers never rewrite the phase themselves."""
    def emit(message):
        status(message, player_phase(list(running.items())))
    return emit


def _running_worker(running, domain, verb, call):
    """The manager's _running_worker, moved: membership follows the thread's real lifetime, so a
    thread that never started never appears in a sibling's heartbeat label."""
    def run(scope):
        running[domain] = verb
        try:
            return call(scope)
        finally:
            running.pop(domain, None)
    return run


def _review_until_parsed(proposal, packet, scope, status_emit, *, format_state=None):
    """Local reviewer format correction: the reviewer's OWN malformed verdict
    (DomainResponseError, including an index outside the supplied checks) re-requests the
    SAME reviewer with its ACTUAL raw reply and the objection - never a rejection on merit,
    never a synthetic verdict, no count; supersession and every other exception propagate."""
    correction = format_state if format_state is not None else {}
    while True:
        request = packet if not correction else {**packet, 'format_correction': deepcopy(correction)}
        try:
            review = review_domain(proposal, request, scope, status_emit)
        except DomainResponseError as exc:
            correction.clear()
            correction.update({'rejected_response': exc.raw, 'error': str(exc)})
            continue
        correction.clear()
        return review


def _result(ws, layer, prepared):
    ws.revision += 1                          # the ONE per-session counter (RC5-5)
    return LayerResult(ws.revision, layer, prepared)   # no question snapshot: report() reads pending_questions(ws) at call time


def run_layer(ws, views, packet_for, assemble, scope, status):
    """Dependency-ordered domain execution: features first, then spells and numbers side by side (#323).

    Each author is corrected privately to an admitted, independently approved
    and promoted proposal; a dependent author consumes the already-validated
    upstream output through its packet's validated view (DEPENDS_ON). Every
    round authors all domains whose dependencies are approved, in parallel. An
    upstream correction or a fact conflict retracts the domain and its
    dependents, which are rebuilt next round. Once all three are approved the complete sheet is prepared by
    the provider-free assembler and returned for the single guarded commit. No
    model reviews the merged sheet again: each domain was already authored and
    independently reviewed, and a further review only restarted the chain (owner
    ruling 2026-09-14, #407). A failed assembly check is handed back to its owning
    domain, or to every approved domain when no owner is known, without a model
    call. No player/sibling/reference questions, no parks, no stall, no scheduler.
    """
    domains = FORWARD_ORDER

    def values():   # CC FYI-R4-CC-5: session views + the validated view AS OF NOW
        return {'stored': views['stored'], 'effective': views['effective'], 'validated': validated_view(ws)}

    def constrain(domain, origin, errors):
        # The ONE repair transition: replace this origin's set, then retract the
        # domain and every domain that consumes its output (CU4-3). Recorded
        # choices, drafts and other origins stay.
        ws.constraints.setdefault(domain, {})[origin] = Constraint(origin, domain, ws.drafts.get(domain, 0), errors)
        retract(ws, domain)
        for dependent in dependents_of(domain):
            retract(ws, dependent)

    withdraw(ws, values(), set())
    while True:
        pending = [domain for domain in domains if domain not in ws.reviews]
        if pending:
            # Author every unapproved domain whose dependencies are all approved,
            # side by side (spells and numbers both only need features). A
            # corrected upstream domain retracts its dependents, so they are
            # rebuilt from the validated upstream output on the next round.
            ready = [domain for domain in pending if all(dep in ws.reviews for dep in DEPENDS_ON[domain])]
            running = {}
            heartbeat = _running_status(status, running)
            work = {}
            for domain in ready:
                ws.constraints.setdefault(domain, {})
                ws.drafts.setdefault(domain, 0)
                work[domain] = _running_worker(
                    running, domain, 'authoring',
                    lambda child_scope, d=domain: run_domain_cycle(d, packet_for, ws, child_scope, heartbeat, running))
            status(None, player_phase([(d, 'authoring') for d in ready]))   # PX FYI-1: truthful pre-dispatch label
            outcomes = collect_domain_work(work, scope)
            failure = next((o for o in outcomes.values() if isinstance(o, Exception) and not isinstance(o, AssemblyConflict)), None)
            if failure is not None:
                raise failure
            for domain in ready:
                outcome = outcomes[domain]
                if isinstance(outcome, AssemblyConflict):
                    for target, errors in outcome.domain_errors.items():
                        constrain(target, 'review', errors)
                    continue
                proposal = outcome
                ws.proposals[domain] = proposal                   # record for correction continuity even on a conflict
                conflicts = promote(ws, domain, proposal)         # store approved facts or report a cross-origin conflict
                if conflicts:
                    constrain(domain, 'fact_conflict', conflicts)             # incoming origin must also see the disagreement
                    for origin in {conflict['origin'] for conflict in conflicts}:
                        constrain(origin, 'fact_conflict', [c for c in conflicts if c['origin'] == origin])
                else:                                                         # successful promotion clears the prior fact_conflict
                    ws.constraints.get(domain, {}).pop('fact_conflict', None)
            withdraw(ws, values(), set())                                     # against the CURRENT views (rebuilds dependents)
            continue
        approved = tuple(domain for domain in domains if domain in ws.reviews)
        try:
            prepared = assemble()
        except AssemblyConflict as conflict:
            # The merge/check attempt completed. Replace its origin sets for the
            # whole approved round before installing the new objections. A check
            # with no known owner is never silently dropped: every approved domain
            # that authored changes receives it and re-authors against it.
            for domain in approved:
                ws.constraints.get(domain, {}).pop('merge', None)
                ws.constraints.get(domain, {}).pop('assembly', None)
            for domain, errors in conflict.domain_errors.items():
                constrain(domain, 'merge', errors)
            if conflict.unattributed:
                broadcast = [domain for domain in approved if ws.proposals[domain].changes] or list(approved)
                for domain in broadcast:
                    constrain(domain, 'assembly', list(conflict.unattributed))
            withdraw(ws, values(), set())
            continue                      # >= 1 domain was retracted above: the fixed-order pending list is non-empty
        # assemble() passed for the complete approved round: the merge and assembly
        # checks that reran are cleared. Never a check that did not run (an earlier
        # raise skips this) and never before attribution above.
        for cleared_domain in approved:
            origins = ws.constraints.get(cleared_domain)
            if origins:
                origins.pop('merge', None)
                origins.pop('assembly', None)
        return _result(ws, 'assembled', prepared)
