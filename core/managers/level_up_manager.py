# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Core Engine - Level Up Manager
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

#!/usr/bin/env python3
# ============================================================================
# LEVEL_UP_MANAGER.PY - AI-DRIVEN CHARACTER PROGRESSION
# ============================================================================
#
# ARCHITECTURE ROLE: Game Systems Layer - Character Progression Management
#
# This module owns a process-local, model-guided level-up conversation. Provider
# calls use the existing live transport; canonical writes are per-file atomic.
#
# KEY RESPONSIBILITIES:
# - Interactive AI-driven level-up interview process for players
# - Automated optimized advancement choices for NPCs
# - 5th edition of the world's most popular roleplaying game rule compliance validation and verification
# - Private correction context separate from accepted conversation
# - Character advancement through the existing canonical writer
# - Integration with main game loop through summary reports
# - Captured cancellation authority; no whole-level-up rollback
#

"""
Level Up Manager Module for NeverEndingQuest

Handles character level up process as a separate, focused conversation.
This module is fully agentic, conducting an interactive interview with the player,
and is designed to be driven by an external UI loop.

Features:
- Manages accepted level-up conversation and its observational audit file.
- AI-driven interview process for players.
- Automatic, optimized choices for NPCs.
- 5e rules compliance with validation.
- Returns a final summary to the main game upon completion.
"""

import json
import copy
import os
import time
from contextlib import contextmanager
from dataclasses import asdict
from core.ai import api_client
from core.ai.srd_reference import load_srd_reference_index
import config
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T047", "core/managers/level_up_manager.py", 287)
register_callsite("T048", "core/managers/level_up_manager.py", 329)
from utils.file_operations import safe_read_json
from updates.update_character_info import normalize_character_name, load_schema
from utils.encoding_utils import safe_json_dump
from utils.level_up_contract import (LevelUpTurn, parse_level_up_stage,
                                     parse_level_up_validation_response)
from utils.level_up_workspace import (LevelUpWorkspace, merge_domain_changes, sheet_diff,
                                     changes_owning_path, record_choices, withdraw,
                                     pending_questions, answered_questions, validated_view, retract,
                                     supplied_operand_paths, _same_value)
from core.ai.level_up_specialists import run_layer, collect_domain_work, AssemblyConflict, LayerResult
from utils.capture.live_provider_call import (get_live_turn_scope, LiveProviderSuperseded,
                                             LiveProviderCompletedError, LiveProviderUnavailable)
from utils.module_path_manager import ModulePathManager

# Token tracking import
try:
    from utils.openai_usage_tracker import track_response
    USAGE_TRACKING_AVAILABLE = True
except ImportError:
    USAGE_TRACKING_AVAILABLE = False

# --- Class-based Level Up Manager ---

@contextmanager
def _level_up_commit_guard(scope):
    if scope is None:
        yield
        return
    with scope.lock:
        if scope.supersession is not None:
            raise LiveProviderSuperseded("level-up operation superseded")
        yield

class LevelUpSession:
    """Manages the state of a single level-up session."""

    def __init__(self, character_name, current_level, new_level, *, accepted_history=None, player_input=None):
        self.character_name = character_name
        self.current_level = current_level
        self.new_level = new_level
        self._entry_history = copy.deepcopy(accepted_history or [])
        self._entry_input = player_input
        self.conversation = []
        self._interview_start = 0
        self.is_player = True
        self.character_data = None
        self.is_complete = False
        self.summary = ""
        self.success = False
        self._started = False
        self._scope = None
        self._last_turn = None
        self._reporting_state = None
        self._workspace = LevelUpWorkspace()
        self._layer = LayerResult(0, 'interviewing', None)
        self._constraints = {'envelope': [], 'full_review': []}
        self._latest_candidate = None
        self._last_verdict = None
        self._prior_commit_proposed = False
        self._advancement_authorized = False
        self._operation_started = None
        self._phase = 'working'
        self._since_label = 'your request'
        self.conversation_file = "modules/conversation_history/level_up_conversation.json"

    def commit_guard(self):
        """Authority captured for this session, never a replacement turn (#323)."""
        return _level_up_commit_guard(self._scope)

    # --- Truthful progress through the existing status channel (task 6) -------
    # Only is_processing=True is ever emitted here: input reopens solely at the
    # existing input boundary, never because a phase or child finished.

    def _begin_operation(self, phase, since_label='your answer'):
        """A player input or the interview start opens one operation clock."""
        self._operation_started = time.monotonic()
        self._since_label = since_label
        self._report_phase(phase)

    def _publish_status(self, message):
        """Advisory publication owned by this operation's captured scope.

        Ownership is checked by StatusManager INSIDE the status lock (status->scope
        order, the direction ready admission already uses; the lifecycle never takes
        the status lock under a scope lock, see
        live_provider_call.request_lifecycle_turn_supersession). A lifecycle owner
        seals the scope first and publishes through the same lock afterwards, so a
        superseded level-up line can only precede the lifecycle message, never
        follow it; seal-before-check publishes nothing. No new lock is held here.
        A failing presentational callback is swallowed exactly as the transport's
        _safe_emit does; real supersession is raised by the provider/write guards,
        never by status.
        """
        from core.managers.status_manager import status_manager
        try:
            status_manager.update_status(message, True, owner_scope=self._scope)
        except Exception:
            pass

    def _report_phase(self, phase):
        self._phase = phase
        self._publish_status(f'Level up: {phase}...')

    def _status_emit(self, _message, phase=None):
        """Provider heartbeats show the real phase and the operation clock, not one call's."""
        started = self._operation_started if self._operation_started is not None else time.monotonic()
        elapsed = max(1, int(time.monotonic() - started))
        self._publish_status(
            f'Level up: {phase or self._phase} ({elapsed} s since {self._since_label}). '
            'Waiting for the AI provider. Your turn is safe.')

    def start(self):
        """Initialize the interview and return only an accepted presentation."""
        if self._started:
            with self.commit_guard():
                return self._last_turn or LevelUpTurn(
                    "interview", "Your level-up interview has already begun."
                )

        self._scope = get_live_turn_scope()
        with self.commit_guard():
            self._started = True
        self._begin_operation('preparing your level-up interview', 'your request')
        print(f"[Level Up Session] Starting for {self.character_name}")
        party_tracker = safe_read_json("party_tracker.json") or {}
        module_name = party_tracker.get("module", "").replace(" ", "_")
        self._path_manager = ModulePathManager(module_name)
        self._character_path = self._path_manager.get_character_path(
            normalize_character_name(self.character_name)
        )
        self.character_data = safe_read_json(self._character_path)
        if not self.character_data:
            self.is_complete = True
            return self._record_update_failure(
                f"The character sheet for {self.character_name} could not be loaded."
            )

        self.is_player = self.character_data.get("character_type", "player").lower() == "player"
        self._initialize_conversation()
        return self._handle_assistant_response()

    def handle_input(self, user_input):
        """Append the raw player answer to the accepted conversation only (no clearing)."""
        with self.commit_guard():
            if self.is_complete:
                return self._last_turn
            self.conversation.append({"role": "user", "content": user_input})
        self._begin_operation('reading your answer', 'your answer')
        return self._handle_assistant_response()

    def _handle_assistant_response(self):
        """THE protected boundary around _cycle(); only accepted narration reaches history."""
        try:
            return self._cycle()
        except LiveProviderSuperseded:
            raise
        except LiveProviderCompletedError:
            return self._hand_back(self._phase)
        except LiveProviderUnavailable as exc:
            envelope = getattr(exc, 'envelope', None)
            if isinstance(envelope, dict) and envelope.get('disposition') == 'deterministic':
                return self._hand_back(self._phase)
            print(f"[WARNING] Level-up step '{self._phase}' could not complete: {type(exc).__name__}")
            return self._hand_back(self._phase)
        except Exception as exc:
            print(f"[WARNING] Level-up step '{self._phase}' could not complete: {type(exc).__name__}")
            return self._hand_back(self._phase)

    def _cycle(self):
        """Interview -> validated authorization -> calculate/save -> observed report."""
        while True:
            with self.commit_guard():
                pass
            if self._reporting_state is not None:
                if self._reporting_state['observed_character'] is None:
                    self._report_phase('confirming the saved result')
                    observed = safe_read_json(self._character_path)
                    if observed is None:
                        return self._hand_back('confirming the saved result')
                    self._reporting_state.update(
                        observed_character=observed,
                        matches_prepared=_same_value(observed, self._layer.prepared['after']))
            proposed_commit = False
            messages = self._coordinator_request()
            self._report_phase('the DM is working on your advancement')
            candidate = self._get_ai_response(messages)
            try:
                parsed = parse_level_up_stage(candidate)
                stage = parsed['stage']
                if self._reporting_state is not None and stage != 'report':
                    raise ValueError('The write committed. Only report the observed result; never apply again.')
                if stage == 'report' and self._reporting_state is None:
                    raise ValueError('No write has committed; report stage is unavailable.')
                objections = self._deterministic_checks(parsed)
                if objections:
                    raise ValueError('; '.join(objections))
            except (TypeError, ValueError) as exc:
                self._constraints['envelope'] = [str(exc)]
                self._latest_candidate = candidate
                continue
            proposed_commit = (stage == 'commit')
            try:
                verdict = self._validate_level_up_response(candidate)
            finally:
                if proposed_commit:
                    self._prior_commit_proposed = True
            if not verdict['valid']:
                self._latest_candidate = candidate
                # Consent/interview and saved narration are T048's boundaries.
                # A rejected reply cannot dispatch pre-consent or post-save work.
                self._constraints['full_review'] = verdict['errors']
                continue
            self._constraints = {'envelope': [], 'full_review': []}
            self._last_verdict = None
            self._latest_candidate = None
            if stage == 'report':
                if self._reporting_state['matches_prepared']:
                    public = json.dumps({'narration': parsed['narration'], 'actions': []})
                    return self._accept_turn(public, parsed['narration'], 'complete', terminal=True)
                return self._hand_back('confirming the saved result')
            self._register_interview_decisions(parsed)
            if self._record_choices(parsed['choices']):
                self._layer = LayerResult(self._workspace.revision, 'interviewing', None)
            if stage == 'ask':
                if isinstance(parsed['asking'], dict):
                    self._layer = LayerResult(self._workspace.revision, 'interviewing', None)
                public = json.dumps({'narration': parsed['narration'], 'actions': []})
                return self._accept_turn(public, parsed['narration'], 'interview')
            if stage == 'commit':
                self._advancement_authorized = True
                if self._layer is None or self._layer.layer != 'assembled':
                    self._run_layer()
                while self._reporting_state is None:
                    self._commit_complete_proposal()
                continue

    def _coordinator_request(self):
        """Frame + accepted interview + constraints + latest candidate + ONE layer report (H5)."""
        messages = copy.deepcopy([message for message in self.conversation])
        if self._constraints['envelope']:
            messages.append({'role': 'user', 'content':
                'PRIVATE ENVELOPE CORRECTION (not player history):\n'
                + json.dumps(self._constraints['envelope'], ensure_ascii=True)})
        if self._constraints['full_review']:
            messages.append({'role': 'user', 'content':
                'PRIVATE FULL-REVIEW CORRECTION (not player history):\n'
                + json.dumps(self._constraints['full_review'], ensure_ascii=True)})
        if self._latest_candidate is not None:
            messages.append({'role': 'user', 'content':
                'YOUR LATEST REJECTED CANDIDATE (correct it; not player history):\n'
                + self._latest_candidate})
        report = self._layer_report()
        messages.append({'role': 'user', 'content':
            'LAYER STATUS (built now; approved preferences and execution/save evidence):\n'
            + json.dumps(report, ensure_ascii=True, allow_nan=False)})
        if self._reporting_state is not None and self._reporting_state['matches_prepared']:
            messages.append({'role': 'system', 'content':
                '[DM NOTE: All specialists have completed and the character sheet is updated. '
                'Narrate the verified changes and automatic selections naturally, never '
                'technically. Explain variations without mentioning agents, JSON or validation. '
                'The saved selection wins if a reviewed selection was adjusted; an absent '
                'selection was not applied. Do not ask approval or apply advancement again. '
                'Later player changes use the normal character-update process.]\n' + json.dumps(
                    self._saved_result_note(), ensure_ascii=True, allow_nan=False)})
        return messages

    def _saved_result_note(self):
        """One verified receipt shared by the narrator and its independent validator."""
        if self._reporting_state is None or not self._reporting_state['matches_prepared']:
            raise ValueError('Saved-result evidence requires a matching canonical readback.')
        observed = self._reporting_state['observed_character']
        return {'saved_changes': sheet_diff(self._layer.prepared['before'], observed),
                'variations': self._saved_variations(observed),
                'preparation_adjustments': self._layer.prepared.get('adjustments', [])}

    def _saved_variations(self, observed):
        """Reconcile approved author notes against canonical named-array identities."""
        from updates.update_character_info import CHARACTER_NAMED_ARRAYS
        from utils.level_up_workspace import _identity_matches
        notes = []
        for proposal in self._workspace.proposals.values():
            for variation in proposal.variations:
                path = variation['field']
                path = path.split('.') if isinstance(path, str) else path
                value, array_field, present = observed, None, True
                try:
                    for part in path:
                        if isinstance(value, list) and isinstance(part, str):
                            name_field = CHARACTER_NAMED_ARRAYS[array_field]
                            value = next(item for item in value if _identity_matches(
                                item, name_field, array_field, part))
                        else:
                            value = value[part]
                            array_field = part
                except (KeyError, IndexError, TypeError, StopIteration):
                    value, present = None, False
                notes.append({**copy.deepcopy(variation),
                              'reviewed_selection': copy.deepcopy(variation['selection']),
                              'selection': copy.deepcopy(value), 'saved_selection_present': present})
        return notes

    def _validator_request(self, candidate):
        """Frame + transition + accepted + ONE report (+ prepared) + envelope + own last verdict."""
        _, validation_prompt, leveling_info = self._load_system_prompts()
        report = self._layer_report()
        messages = [
            {"role": "system", "content": validation_prompt},
            {"role": "system", "content": f"CURRENT CHARACTER DATA:\n{json.dumps(self.character_data, indent=2)}"},
            {"role": "system", "content": f"LEVELING INFORMATION (Reference):\n{leveling_info}"},
            {"role": "system", "content": self._schema_context},
            {"role": "system", "content": self._spell_context},
            {"role": "system", "content": "REQUESTED TRANSITION:\n" + json.dumps({
                "character_name": self.character_name,
                "current_level": self.current_level,
                "new_level": self.new_level,
                "prior_commit_proposed": self._prior_commit_proposed,
                "advancement_authorized": self._advancement_authorized,
            })},
            {"role": "user", "content": "ACCEPTED INTERVIEW (only established inputs/accepted replies):\n"
                + json.dumps([message for message in self.conversation
                              if message["role"] in ("user", "assistant")], indent=2)},
            {"role": "user", "content": "LAYER STATUS (built now):\n"
                + json.dumps(report, ensure_ascii=True, allow_nan=False)},
        ]
        if self._layer is not None and self._layer.layer == 'assembled' and self._layer.prepared is not None:
            messages.append({"role": "user", "content": "EXACT PREPARED SHEET (before/after the write):\n"
                + json.dumps({'before': self._layer.prepared['before'],
                              'after': self._layer.prepared['after']}, indent=2)})
        if self._reporting_state is not None and self._reporting_state['matches_prepared']:
            messages.append({'role': 'system', 'content': 'VERIFIED SAVED RESULT AND VARIATIONS:\n'
                + json.dumps(self._saved_result_note(), ensure_ascii=True, allow_nan=False)})
        if self._constraints['envelope']:
            messages.append({"role": "user", "content": "PRIVATE ENVELOPE CORRECTION (not player consent):\n"
                + json.dumps(self._constraints['envelope'], ensure_ascii=True)})
        if self._last_verdict is not None:
            messages.append({"role": "user", "content":
                "YOUR OWN PREVIOUS VERDICT FOR THIS CANDIDATE LINE (private):\n"
                + json.dumps(self._last_verdict, ensure_ascii=True)})
        messages.append({"role": "user", "content":
            "CURRENT CANDIDATE: Review its conversational stage, agency, mechanics and truthful "
            f"narration. The candidate is not evidence of consent.\n\n{candidate}"})
        return messages

    def _layer_report(self):
        layer = self._layer or LayerResult(self._workspace.revision, 'interviewing', None)
        report = layer.report(self._workspace, prior_commit_proposed=self._prior_commit_proposed,
                              observed_write=self._reporting_state)
        report['advancement_authorized'] = self._advancement_authorized
        report['selected_spell_references'] = self._selected_spell_references()
        return report

    def _selected_spell_references(self):
        """Resolve exact structured choice values as advisory catalogue references."""
        def names(value):
            if isinstance(value, str):
                yield value
            elif isinstance(value, list):
                for item in value:
                    yield from names(item)
            elif isinstance(value, dict):
                for item in value.values():
                    yield from names(item)
        references = {}
        try:
            index = load_srd_reference_index()
            for choice in self._workspace.choices.values():
                for name in names(choice['value']):
                    reference = index.reference(name)
                    if reference is not None:
                        references[reference['id']] = reference
        except (OSError, ValueError) as exc:
            print(f"[WARNING] Selected spell evidence unavailable: {type(exc).__name__}")
        return list(references.values())

    def _deterministic_checks(self, parsed):
        """Private envelope corrections read the PROSPECTIVE choice state (RC2-4); no mutation."""
        ws = self._workspace
        stage = parsed['stage']
        choices = parsed['choices']
        recorded = set(choices)
        pending = pending_questions(ws)
        prospective_pending = [question for question in pending if question['name'] not in recorded]
        errors = []
        unknown = sorted(name for name in recorded if name not in ws.questions and not choices[name].get('domain'))
        if unknown:
            errors.append('new choices require a typed domain and accepted source: ' + ', '.join(unknown))
        for name, entry in choices.items():
            owner = ws.questions.get(name, {}).get('domain')
            if owner is not None and entry.get('domain', owner) != owner:
                errors.append('a recorded choice cannot change its owning domain: ' + name)
        if stage == 'ask':
            asking = parsed['asking']
            if self._advancement_authorized:
                if asking is not None or choices:
                    errors.append('advancement is already authorized: do not reopen questions or '
                                  'request another confirmation; explain the operational status '
                                  'without asking, or commit only when the player requests retry')
            elif asking == 'final_confirmation':
                if prospective_pending:
                    errors.append('record outstanding interview answers before asking permission; '
                                  'no specialist calculations are needed to request approval')
            elif isinstance(asking, dict):
                name = asking['choice']
                existing = ws.questions.get(name)
                if name in recorded:
                    errors.append('do not ask a question answered in this same turn')
                if existing and existing.get('domain') != asking['domain']:
                    errors.append('a question cannot change its owning domain: ' + name)
                if name in ws.choices and not asking.get('facts', {}).get('reopens'):
                    errors.append('reopening an answered question requires facts.reopens with its reason')
            elif asking not in {question['name'] for question in prospective_pending}:
                errors.append('ask must name one still-pending question; pending now: '
                              + ', '.join(sorted(question['name'] for question in prospective_pending)))
        elif stage == 'commit':
            if prospective_pending:
                errors.append('record the accepted answers or expressly delegated preferences '
                              'before execution; still pending: '
                              + ', '.join(question['name'] for question in prospective_pending))
        return errors

    def _register_interview_decisions(self, parsed):
        """Apply only the structurally and semantically approved question metadata."""
        ws = self._workspace
        for name, entry in parsed['choices'].items():
            if name not in ws.questions:
                ws.questions[name] = {'domain': entry['domain'], 'origin': 'coordinator',
                                      'state': 'answered', 'prompt': '', 'options': None, 'facts': {}}
        asking = parsed['asking']
        if isinstance(asking, dict):
            name = asking['choice']
            ws.questions[name] = {
                'domain': asking['domain'], 'origin': 'coordinator',
                'prompt': asking['prompt'], 'options': copy.deepcopy(asking.get('options')),
                'facts': copy.deepcopy(asking.get('facts', {})),
                'state': 'reopened' if name in ws.choices else 'open',
            }
            retract(ws, asking['domain'])
            withdraw(ws, self._views(), set())

    def _views(self):
        from core.effects.effective import effective_sheet
        sheet = copy.deepcopy(self.character_data)
        return {'stored': sheet, 'effective': effective_sheet(copy.deepcopy(sheet))}

    def _record_choices(self, choices):
        """Deterministic name membership already held; record, then withdraw changed consumers."""
        # A first answer to an open question completes collection; it does not
        # invalidate the other questions in that same reviewed interview batch.
        # New unprompted decisions after calculation still invalidate their owner.
        pending_names = {question['name'] for question in pending_questions(self._workspace)}
        new_names = set(choices) - set(self._workspace.choices) - pending_names
        changed = record_choices(self._workspace, choices)
        if self._workspace.proposals:
            changed.update(new_names)
        if changed:
            withdraw(self._workspace, self._views(), changed)
        return changed

    def _packet_for(self, domain):
        """Immutable per-domain packet; a Constraint is projected to plain JSON before serialization."""
        from core.effects.effective import effective_sheet
        from model_config import get_provider
        from core.ai.level_up_specialists import _project_proposal
        validated = validated_view(self._workspace)
        constraints = self._workspace.constraints.get(domain, {})
        proposal = self._workspace.proposals.get(domain)
        # Both sheet views stay complete dicts: the workspace snapshots them from
        # this packet and compares them value-for-value with the live views after
        # every approval, so any substitute here reads as a changed source sheet
        # and retracts the approved domain on every round.
        return {
            'provider': get_provider(),
            'stored': copy.deepcopy(self.character_data),
            'effective': effective_sheet(copy.deepcopy(self.character_data)),
            'validated': validated,
            'supplied_operands': supplied_operand_paths(validated),
            'latest_proposal': _project_proposal(proposal) if proposal is not None else None,
            'constraints': {origin: asdict(constraint) for origin, constraint in constraints.items()},
            'answered_questions': answered_questions(self._workspace),
            # The level-up interview only: entry request, DM questions, player
            # answers, approval. Pre-level-up campaign history is not evidence
            # for advancement mechanics and was the largest item in every packet.
            'interview': copy.deepcopy([message for message in self.conversation[self._interview_start:]
                                       if message['role'] in ('user', 'assistant')]),
            'references': self._leveling_reference,
            'saved_spell_references': self._spell_context,
            'selected_spell_references': self._selected_spell_references(),
            'schema': self._schema_context,
            'current_level': self.current_level,
            'new_level': self.new_level,
        }

    def _run_layer(self):
        if not self._advancement_authorized or self._reporting_state is not None:
            raise ValueError('Calculation requires accepted authorization and an uncommitted advancement.')
        self._layer = None                                    # FF5-1: cleared first; a failed run leaves None for the _cycle guard
        from core.effects.effective import effective_sheet   # the lazy import _packet_for already uses
        sheet = copy.deepcopy(self.character_data)
        views = {'stored': sheet, 'effective': effective_sheet(copy.deepcopy(sheet))}
        self._layer = run_layer(self._workspace, views, self._packet_for, self._assemble,
                                self._scope, self._status_emit)
        return self._layer

    def _assemble(self):
        """LGC3-1 step 0 armor offer, then merge/prepare; every data-check raise is AssemblyConflict."""
        from updates.update_character_info import (prepare_character_delta, repair_character_data,
                                                   validate_critical_fields_preserved)
        from core.validation.character_validator import AICharacterValidator, armor_contract_errors

        schema = load_schema()
        base = copy.deepcopy(self.character_data)
        proposals = list(self._workspace.proposals.values())
        armor_repair = []
        armor_probe = AICharacterValidator(
            commit_guard=self.commit_guard, provider_scope=self._scope,
            provider_status=self._status_emit, persist_cache=False)
        armor_errors = armor_contract_errors(
            armor_probe.extract_ac_relevant_data(base)['equipment'],
            schema['properties']['equipment']['items'])
        if armor_errors:
            self._report_phase('repairing stored armor data')
            def repair_armor(scope):
                validator = AICharacterValidator(
                    commit_guard=self.commit_guard, provider_scope=scope,
                    provider_status=self._status_emit, persist_cache=False)
                return validator.ai_validate_armor_class_with_result(base)
            result = collect_domain_work({'armor': repair_armor}, self._scope)['armor']
            if isinstance(result, Exception):
                raise result                     # actual class S/P/X; no invented validator result
            base = result.data                   # strict owner loop completes or raises; never FAILED
            armor_repair = sheet_diff(self.character_data, base)

        changes, merge_errors = merge_domain_changes(base, proposals)
        if merge_errors:
            owned, unowned = {}, []
            for error in merge_errors:
                for domain in error['domains']:
                    owned.setdefault(domain, []).append(error)
                if not error['domains']:
                    unowned.append(error)
            raise AssemblyConflict(owned, [{'index': i, 'check': 'merge', **entry}
                                           for i, entry in enumerate(unowned)])
        changes.pop('experience_points', None)
        role = 'player' if self.is_player else 'npc'

        _, proposed, checks = prepare_character_delta(
            repair_character_data(copy.deepcopy(base)), changes, role, schema, self.character_name)
        domain_errors, unattributed, unowned_removed = {}, [], []
        for field in checks.get('removed_fields', []):
            owners = changes_owning_path(proposals, field)
            entry = {'check': 'removed_fields', 'field': field,
                     'path': field.split('.') if isinstance(field, str) else list(field),
                     'domains': owners}
            if owners:
                for owner in owners:
                    domain_errors.setdefault(owner, []).append(entry)
            else:
                unowned_removed.append(field)
        if checks['critical_warnings']:
            unattributed.append({'check': 'critical_warnings', 'warnings': checks['critical_warnings']})
        if not checks['schema_valid']:
            unattributed.append({'check': 'schema_valid', 'error': checks.get('error_message')})
        if domain_errors or unattributed:
            raise AssemblyConflict(domain_errors, [{'index': i, **entry}
                                                   for i, entry in enumerate(unattributed)])

        # The prepared sheet is exactly the merged domain proposals over the
        # stored base. The ordinary character-update path's post-write
        # normalizers (T051 armor class, T052 inventory categories, T054
        # currency and the effects validator) do not run inside a level-up:
        # they rewrite possessions no domain authored, and the final
        # preservation review then correctly rejects edits it cannot attribute
        # to any author (#407). Those normalizers keep their place on the
        # ordinary update path; a later ordinary update still applies them.
        self._report_phase('checking the prepared sheet')
        prepared_after = proposed
        post_unattributed = []
        critical_warnings = validate_critical_fields_preserved(
            self.character_data, prepared_after, self.character_name)
        if critical_warnings:
            post_unattributed.append({'check': 'critical_warnings', 'warnings': critical_warnings})
        if prepared_after.get('experience_points') != self.character_data.get('experience_points'):
            post_unattributed.append({'check': 'experience_points',
                                      'error': 'prepared proposal changed the earned XP total'})
        if prepared_after.get('level') != self.new_level:
            post_unattributed.append({'check': 'level',
                                      'error': 'prepared proposal does not contain the requested new level'})
        if post_unattributed:
            raise AssemblyConflict({}, [{'index': i, **entry}
                                        for i, entry in enumerate(post_unattributed)])

        checks['removed_fields'] = unowned_removed
        checks['armor_repair'] = [entry for entry in armor_repair
                                  if entry in sheet_diff(self.character_data, prepared_after)
                                  and not changes_owning_path(proposals, entry['path'])]
        return {'before': copy.deepcopy(self.character_data), 'after': prepared_after,
                'changes': changes, 'checks': checks,
                'adjustments': list(checks['armor_repair'])}

    def _commit_complete_proposal(self):
        from updates.update_character_info import (commit_character_sheet, CharacterSnapshotChanged,
            _get_character_update_lock, get_character_path, create_character_backup, cleanup_old_backups)
        from utils.path_transaction_lock import path_transaction_lock
        if (not self._advancement_authorized or self._reporting_state is not None
                or self._layer is None or self._layer.layer != 'assembled'):
            raise ValueError('Only an authorized prepared advancement can reach the writer once.')
        role = 'player' if self.is_player else 'npc'
        self._report_phase('confirming the same character still owns this sheet')
        resolved_path = get_character_path(self.character_name, role)
        if os.path.normcase(os.path.abspath(resolved_path)) != os.path.normcase(os.path.abspath(self._character_path)):
            raise ValueError('Character identity/path changed; reconcile the current canonical owner.')
        prepared = self._layer.prepared
        self._report_phase('saving your character')
        try:
            with _get_character_update_lock(self.character_name, role):
                with self.commit_guard():
                    pass
                with path_transaction_lock(self._character_path, suffix='.effects.lock', timeout_seconds=None):
                    with self.commit_guard():
                        pass
                    # Existing archival backup policy; primary atomic writer also
                    # preserves its own .bak inside the final file ownership.
                    if create_character_backup(self._character_path, 'update') is not None:
                        cleanup_old_backups(self._character_path)
                    applied = commit_character_sheet(self._character_path, prepared['after'],
                        commit_guard=self.commit_guard, expected_before=prepared['before'])
        except CharacterSnapshotChanged as exc:
            if isinstance(exc.current, dict):
                if exc.current.get('level') != self.current_level:
                    self._report_phase('confirming the character still has the starting level')
                    raise ValueError('The starting level changed; this advancement no longer matches.')
                self.character_data = exc.current
                for domain in list(self._workspace.proposals):
                    retract(self._workspace, domain)
                self._layer = None
                self._run_layer()
                return
            raise
        if not applied:
            raise ValueError('The atomic character update did not commit; correct/retry without claiming success.')
        # From this point forward the cycle is report-only, even on read failure.
        self._reporting_state = {'write_committed': True, 'observed_character': None,
                                 'matches_prepared': False}
        with self.commit_guard():
            pass
        self._report_phase('confirming the saved result')
        observed = safe_read_json(self._character_path)
        self._reporting_state.update(observed_character=observed,
            matches_prepared=_same_value(observed, prepared['after']))

    def _accept_turn(self, candidate, narration, kind, *, terminal=False):
        with self.commit_guard():
            self.conversation.append({"role": "assistant", "content": candidate})
            self.is_complete = terminal
            self.success = kind == "complete"
            self.summary = f"Level Up: {narration}" if self.success else narration
            self._last_turn = LevelUpTurn(kind, narration)
        self._save_conversation()
        return self._last_turn

    def _record_update_failure(self, reason):
        """The sheet-cannot-load terminal only (LGC6-F3); no interview ever began."""
        narration = (
            f"Your level-up has not been applied. {reason} "
            "The interview has ended; you can ask to level up again, or load a saved game."
        )
        return self._accept_turn(
            json.dumps({"narration": narration, "actions": []}),
            narration, "not_applied", terminal=self.is_complete,
        )

    def _hand_back(self, reason):
        """LevelUpTurn kind 'interview' both precommit and postcommit; _accept_turn clears nothing."""
        if self._reporting_state is not None:
            if self.is_player:
                narration = (
                    "Your sheet is already updated, but I could not finish confirming the result "
                    f"while {reason}. Say 'retry' to finish the report, or Save to keep the "
                    "advancement - Load would restore the older save and discard it."
                )
            else:
                narration = (
                    f"{self.character_name}'s sheet is already updated, but I could not finish "
                    f"confirming the result while {reason}. Say 'retry' to continue "
                    f"{self.character_name}'s advancement, or load a save."
                )
            public = json.dumps({"narration": narration, "actions": []})
            return self._accept_turn(public, narration, "interview")
        retained = ("Your choices so far are kept" if self._workspace.choices
                    else "No choices have been recorded yet")
        next_move = ("Your approval is kept. Say 'retry' to resume the calculation, or Load/Quit."
                     if self._advancement_authorized else
                     "You can continue the interview, or load a saved game.")
        narration = (
            f"Your level-up has not been applied; the {reason} step could not complete. "
            f"{retained}. {next_move}"
        )
        public = json.dumps({"narration": narration, "actions": []})
        return self._accept_turn(public, narration, "interview")

    def _initialize_conversation(self):
        level_up_prompt, _, leveling_info = self._load_system_prompts()
        self._leveling_reference = leveling_info
        try:
            schema_text = json.dumps(load_schema(), ensure_ascii=True, separators=(",", ":"))
        except (OSError, UnicodeError, ValueError) as exc:
            print(f"[WARNING] Level-up schema evidence unavailable: {type(exc).__name__}")
            schema_text = "Schema evidence unavailable; do not infer new writable fields from its absence."
        self._schema_context = (
            "STORED CHARACTER SCHEMA (writer contract, not a complete-delta requirement):\n"
            "Required fields describe the complete saved sheet, not every advancement proposal. "
            "The existing writer remains responsible for schema validation and persistence.\n"
            + schema_text
        )
        # #323: saved attack text alone omitted applicable spell upgrades.
        spellcasting = self.character_data.get("spellcasting") or {}
        names = []
        for values in (spellcasting.get("spells") or {}).values():
            if isinstance(values, list):
                names.extend(name for name in values if isinstance(name, str))
        names.extend(spellcasting.get("preparedSpells") or [])
        references = {}
        unresolved = []
        try:
            index = load_srd_reference_index()
            for name in dict.fromkeys(names):
                reference = index.reference(name)
                if reference is None:
                    unresolved.append(name)
                else:
                    references[reference["id"]] = reference
            evidence = json.dumps({
                "references": list(references.values()),
                "unresolved_names": unresolved,
            }, ensure_ascii=True)
        except (OSError, ValueError) as exc:
            print(f"[WARNING] Level-up spell reference unavailable: {type(exc).__name__}")
            evidence = "Spell reference unavailable; do not infer that a saved spell is illegal."
        self._spell_context = (
            "SAVED SPELL REFERENCES (SRD guidance, not availability or mutation authority):\n"
            "Apply scaling using the requested total/class level and the actual rule. "
            "Unresolved names are missing evidence, not invalid spells.\n" + evidence
        )
        self.conversation = [
            {"role": "system", "content": level_up_prompt},
            {"role": "system", "content": f"LEVELING INFORMATION (Reference):\n{leveling_info}"},
            {"role": "system", "content": self._schema_context},
            {"role": "system", "content": self._spell_context},
            {"role": "system", "content": f"Current Character Data:\n{json.dumps(self.character_data, indent=2)}"},
            {"role": "user", "content": f"Begin the interactive level-up interview for {self.character_name}, who is advancing from level {self.current_level} to level {self.new_level}."}
        ]
        # Accepted pre-entry context is evidence, never system instructions or the
        # candidate levelUp action. The DM needs where the party is and what was
        # just said, not the campaign: only the last accepted exchange (the most
        # recent assistant turn and the player turn before it) is carried in.
        # The full history stays in main; the location summaries it holds were
        # the largest single item in every interview and specialist packet.
        accepted = [copy.deepcopy(message) for message in self._entry_history
                    if message.get('role') in ('user', 'assistant')]
        accepted = accepted[-2:]
        self.conversation.extend(accepted)
        # Specialists receive the interview from the entry request onward.
        self._interview_start = len(self.conversation)
        if self._entry_input is not None and not (
                accepted and accepted[-1].get('role') == 'user'
                and accepted[-1].get('content') == self._entry_input):
            self.conversation.append({'role': 'user', 'content': self._entry_input})
        else:
            self._interview_start = max(0, len(self.conversation) - 1)

    def _save_conversation(self):
        """Accepted audit only; capture failure is not gameplay failure."""
        try:
            safe_json_dump(self.conversation, self.conversation_file, commit_guard=self.commit_guard)
        except LiveProviderSuperseded:
            raise
        except Exception as exc:
            print(f"[WARNING] Saving accepted level-up audit: {exc}")

    def _get_ai_response(self, messages):
        """ONE completed T047 request; the required transport owns transient reissue (FF3-1)."""
        with self.commit_guard():
            pass
        from model_config import MODEL_PROVIDER
        if MODEL_PROVIDER == "openai":
            conv_config = config.LEVELUP_CONV_GPT52_NONE
        elif MODEL_PROVIDER == "gemini":
            conv_config = config.LEVELUP_CONV_GEMINI_FLASH_LOW
        elif MODEL_PROVIDER == "lmstudio":
            conv_config = config.LEVELUP_CONV_LMSTUDIO
        else:  # legacy
            conv_config = config.LEVELUP_CONV_LEGACY
        response = capture_and_fanout("T047", api_client.create_completion,
            _live_selected='required', _detached_scope=self._scope,
            _detached_status=self._status_emit,
            _request_provider=MODEL_PROVIDER,
            messages=messages,
            model=conv_config["model"],
            temperature=0.7,
            **{k: v for k, v in conv_config.items() if k != "model"})
        self._track_usage(response)
        return response.choices[0].message.content

    def _validate_level_up_response(self, candidate):
        """Return T048's parsed typed verdict; the request sits OUTSIDE every handler (FF-9).

        ONLY the parse call is guarded: T048's own response-format or postcommit
        stage-contract error re-requests T048 with its last raw verdict and the
        objection (private; no attempt count; supersession interrupts). Every
        exception from the request itself - including a pre-call allowlist/config
        ValueError (class X) - propagates untouched to the boundary.
        """
        from model_config import MODEL_PROVIDER
        if MODEL_PROVIDER == "openai":
            val_config = config.LEVELUP_VAL_GPT52_NONE
        elif MODEL_PROVIDER == "gemini":
            val_config = config.LEVELUP_VAL_GEMINI_PRO_LOW
        elif MODEL_PROVIDER == "lmstudio":
            val_config = config.LEVELUP_VAL_LMSTUDIO
        else:  # legacy
            val_config = config.LEVELUP_VAL_LEGACY
        correction = None
        while True:
            messages = self._validator_request(candidate)
            if correction is not None:
                messages.append({"role": "user", "content":
                    "PRIVATE STRUCTURAL OBJECTION TO YOUR LAST VERDICT (restate it in the exact "
                    "contract; not player history):\n" + json.dumps(correction, ensure_ascii=True)})
            self._report_phase('checking the proposal against the rules')
            response = capture_and_fanout("T048", api_client.create_completion,
                _live_selected='required', _detached_scope=self._scope,
                _detached_status=self._status_emit,
                _request_provider=MODEL_PROVIDER,
                messages=messages,
                model=val_config["model"],
                temperature=0.2,
                **{k: v for k, v in val_config.items() if k != "model"})
            self._track_usage(response)
            raw = response.choices[0].message.content
            try:
                verdict = parse_level_up_validation_response(
                    raw, postcommit=self._reporting_state is not None)
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                correction = {'rejected_verdict': raw, 'objection': str(exc)}
                continue
            self._last_verdict = verdict
            return verdict

    def _track_usage(self, response):
        """Existing token-usage telemetry, kept outside the parse-only handler (shared helper)."""
        if USAGE_TRACKING_AVAILABLE:
            try:
                from utils.openai_usage_tracker import get_global_tracker
                get_global_tracker().track(response, context={'endpoint': 'level_up',
                    'purpose': 'level_up_processing', 'character': self.character_name})
            except Exception:
                pass

    @staticmethod
    def _load_system_prompts():
        # Get project root from the current manager location
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.join(script_dir, '..', '..')
        
        with open(os.path.join(project_root, "prompts/leveling/level_up_system_prompt.txt"), "r", encoding="utf-8") as f:
            level_up_prompt = f.read()
        with open(os.path.join(project_root, "prompts/leveling/leveling_validation_prompt.txt"), "r", encoding="utf-8") as f:
            validation_prompt = f.read()
        with open(os.path.join(project_root, "prompts/leveling/leveling_info.txt"), "r", encoding="utf-8") as f:
            leveling_info = f.read()
        return level_up_prompt, validation_prompt, leveling_info
