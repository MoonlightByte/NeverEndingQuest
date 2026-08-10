# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Sanitized, fail-open development metrics for agentic combat calls."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_LEDGER_PATH = Path("debug/combat/agentic_attempts.jsonl")
DEFAULT_SUMMARY_PATH = Path("debug/combat/agentic_attempts_summary.json")
_PROCESS_RUN_ID = os.environ.get("NEQ_COMBAT_VALIDATION_RUN_ID") or uuid.uuid4().hex
_WRITE_LOCK = threading.Lock()
_ALLOWED_RECORD_TYPES = frozenset(("call_attempt", "window_outcome"))
_ALLOWED_CALLSITES = frozenset(("T096", "T097", "POST_COMBAT"))


def _path_from_env(name, default):
    value = os.environ.get(name)
    return Path(value) if isinstance(value, str) and value.strip() else Path(default)


def diagnostic_run_id():
    return _PROCESS_RUN_ID


def hash_identifier(value):
    if value is None:
        return None
    return hashlib.sha256(str(value).encode("utf-8", errors="replace")).hexdigest()[:16]


def _bounded_identifier(value, limit=120):
    if not isinstance(value, str):
        return None
    clean = "".join(character for character in value if character.isalnum() or character in "._-")
    return clean[:limit] or None


def record_combat_diagnostic(
    *,
    record_type,
    callsite,
    outcome,
    provider=None,
    model=None,
    encounter_id=None,
    turn_id=None,
    revision=None,
    round_number=None,
    window_kind=None,
    actor_count=None,
    attempt=None,
    correction=False,
    elapsed_ms=None,
    failure_class=None,
    error_code=None,
    capability_candidates=None,
    rule_references=None,
    intents=None,
    committed_events=None,
    deterministic_fallback=False,
    recovered=False,
    violation_codes=None,
    warning_codes=None,
    rules_contract_key=None,
    rules_contract_version=None,
    dropped_actions=None,
):
    """Append one bounded metadata record; never raise into gameplay."""
    try:
        if record_type not in _ALLOWED_RECORD_TYPES or callsite not in _ALLOWED_CALLSITES:
            return False
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runId": diagnostic_run_id(),
            "recordType": record_type,
            "callsite": callsite,
            "outcome": _bounded_identifier(str(outcome or "unknown")),
            "provider": _bounded_identifier(provider),
            "model": _bounded_identifier(model),
            "encounterHash": hash_identifier(encounter_id),
            "turnHash": hash_identifier(turn_id),
            "revision": revision if type(revision) is int else None,
            "round": round_number if type(round_number) is int else None,
            "windowKind": (
                window_kind
                if window_kind in ("player", "npc", "clock", "unknown")
                else "unknown"
            ),
            "actorCount": max(0, actor_count) if type(actor_count) is int else None,
            "attempt": max(1, attempt) if type(attempt) is int else None,
            "correction": bool(correction),
            "elapsedMs": (
                max(0, int(elapsed_ms))
                if isinstance(elapsed_ms, (int, float))
                else None
            ),
            "failureClass": _bounded_identifier(failure_class),
            "errorCode": _bounded_identifier(error_code),
            "capabilityCandidateCount": (
                max(0, capability_candidates)
                if type(capability_candidates) is int
                else None
            ),
            "ruleReferenceCount": (
                max(0, rule_references)
                if type(rule_references) is int
                else None
            ),
            "intentCount": max(0, intents) if type(intents) is int else None,
            "committedEventCount": (
                max(0, committed_events)
                if type(committed_events) is int
                else None
            ),
            "deterministicFallback": bool(deterministic_fallback),
            "recovered": bool(recovered),
            "violationCodeCounts": {
                code: count
                for code, count in Counter(
                    _bounded_identifier(value)
                    for value in (violation_codes or [])
                    if _bounded_identifier(value)
                ).items()
            },
            "warningCodeCounts": {
                code: count
                for code, count in Counter(
                    _bounded_identifier(value)
                    for value in (warning_codes or [])
                    if _bounded_identifier(value)
                ).items()
            },
            "rulesContractKey": _bounded_identifier(rules_contract_key),
            "rulesContractVersion": _bounded_identifier(rules_contract_version),
            "droppedActionCount": (
                max(0, dropped_actions)
                if type(dropped_actions) is int
                else None
            ),
        }
        entry = {
            key: value
            for key, value in entry.items()
            if value is not None and value != {}
        }
        path = _path_from_env("NEQ_COMBAT_DIAGNOSTICS_PATH", DEFAULT_LEDGER_PATH)
        line = json.dumps(entry, ensure_ascii=True, separators=(",", ":")) + "\n"
        if not _WRITE_LOCK.acquire(blocking=False):
            return False
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line)
        finally:
            _WRITE_LOCK.release()
        return True
    except Exception:
        return False


def summarize_combat_diagnostics(path=None, run_id=None, output_path=None):
    """Build an ignored aggregate report from sanitized ledger records."""
    source = Path(path) if path else _path_from_env(
        "NEQ_COMBAT_DIAGNOSTICS_PATH", DEFAULT_LEDGER_PATH
    )
    selected_run = run_id or diagnostic_run_id()
    records = []
    try:
        with source.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    value = json.loads(line)
                except (TypeError, ValueError):
                    continue
                if isinstance(value, dict) and value.get("runId") == selected_run:
                    records.append(value)
    except OSError:
        records = []

    attempts = [record for record in records if record.get("recordType") == "call_attempt"]
    t096 = [record for record in attempts if record.get("callsite") == "T096"]
    t097 = [record for record in attempts if record.get("callsite") == "T097"]
    outcomes = Counter(record.get("outcome", "unknown") for record in records)
    failures = Counter(
        record.get("failureClass")
        for record in attempts
        if record.get("failureClass")
    )
    windows = defaultdict(list)
    for record in t096:
        marker = record.get("turnHash")
        if marker:
            windows[marker].append(record)
    calls_per_window = [len(values) for values in windows.values()]
    elapsed = [
        record.get("elapsedMs")
        for record in attempts
        if type(record.get("elapsedMs")) is int
    ]
    accepted_outcomes = frozenset(
        ("success_first_attempt", "success_after_correction", "player_input_required")
    )
    first_attempt_successes = sum(
        1
        for values in windows.values()
        if (
            values
            and values[0].get("attempt") == 1
            and values[0].get("outcome") in accepted_outcomes
        )
    )
    corrected_successes = sum(
        1
        for record in t096
        if (
            record.get("correction") is True
            and record.get("outcome") in accepted_outcomes
        )
    )
    corrected_by_failure = Counter()
    for values in windows.values():
        previous_failure = None
        for record in sorted(values, key=lambda item: item.get("attempt", 0)):
            if record.get("failureClass"):
                previous_failure = record["failureClass"]
            if (
                record.get("correction") is True
                and record.get("outcome") in accepted_outcomes
                and previous_failure
            ):
                corrected_by_failure[previous_failure] += 1
                previous_failure = None
    rejected_calls = sum(
        1
        for record in t096
        if record.get("outcome")
        in {
            "provider_error",
            "response_parse_error",
            "response_contract_error",
            "stale_state_or_actor_order",
            "intent_validation_error",
            "mechanical_resolution_error",
            "rules_drift_reject",
            "unexpected_internal_error",
        }
    )
    summary = {
        "runId": selected_run,
        "totalT096Calls": len(t096),
        "totalT097Calls": len(t097),
        "firstAttemptT096Successes": first_attempt_successes,
        "firstAttemptT096SuccessRate": (
            first_attempt_successes / len(windows) if windows else None
        ),
        "correctedT096Successes": corrected_successes,
        "correctionSuccessesByFailureClass": [
            {"name": name, "count": count}
            for name, count in corrected_by_failure.most_common()
        ],
        "rejectedT096Calls": rejected_calls,
        "playerActionsExhausted": outcomes.get("player_action_exhausted", 0),
        "playerRollRejections": outcomes.get("player_roll_rejected", 0),
        "rulesDriftRejects": outcomes.get("rules_drift_reject", 0),
        "rulesDriftCorrections": outcomes.get("rules_drift_corrected", 0),
        "rulesDriftUncheckedAmbiguous": outcomes.get(
            "rules_drift_unchecked_ambiguous", 0
        ),
        "rulesDriftUncheckedNoProfile": outcomes.get(
            "rules_drift_unchecked_no_profile", 0
        ),
        "rulesContractsUnavailable": outcomes.get(
            "rules_contract_unavailable", 0
        ),
        "npcDefendFallbacks": outcomes.get("npc_defend_fallback", 0),
        "postCombatUpdateDropPasses": outcomes.get(
            "post_combat_update_dropped", 0
        ),
        "postCombatDroppedActions": sum(
            record.get("droppedActionCount", 0)
            for record in records
            if (
                record.get("outcome") == "post_combat_update_dropped"
                and type(record.get("droppedActionCount")) is int
            )
        ),
        "t097Fallbacks": sum(
            1 for record in t097 if record.get("outcome") == "narration_fallback"
        ),
        "t097FallbackRate": (
            sum(
                1
                for record in t097
                if record.get("outcome") == "narration_fallback"
            )
            / len(t097)
            if t097
            else None
        ),
        "meanCallsPerWindow": (
            sum(calls_per_window) / len(calls_per_window) if calls_per_window else None
        ),
        "maxCallsPerWindow": max(calls_per_window) if calls_per_window else 0,
        "meanElapsedMs": sum(elapsed) / len(elapsed) if elapsed else None,
        "maxElapsedMs": max(elapsed) if elapsed else 0,
        "failureClasses": [
            {"name": name, "count": count}
            for name, count in failures.most_common()
        ],
        "narrationViolationCodes": [
            {"name": name, "count": count}
            for name, count in Counter(
                code
                for record in t097
                for code, count in (record.get("violationCodeCounts") or {}).items()
                for _ in range(count if type(count) is int and count > 0 else 0)
            ).most_common()
        ],
        "narrationWarningCodes": [
            {"name": name, "count": count}
            for name, count in Counter(
                code
                for record in t097
                for code, count in (record.get("warningCodeCounts") or {}).items()
                for _ in range(count if type(count) is int and count > 0 else 0)
            ).most_common()
        ],
    }
    destination = Path(output_path) if output_path else _path_from_env(
        "NEQ_COMBAT_DIAGNOSTICS_SUMMARY_PATH", DEFAULT_SUMMARY_PATH
    )
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(summary, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass
    return summary
