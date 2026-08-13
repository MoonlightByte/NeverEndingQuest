# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Sanitized, fail-open diagnostics for resource transaction failures."""

from __future__ import annotations

import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_LEDGER_PATH = Path("debug/resource_transactions.jsonl")
_PROCESS_RUN_ID = uuid.uuid4().hex
_WRITE_LOCK = threading.Lock()
_SAFE_IDENTIFIER = re.compile(r"[^A-Za-z0-9_.:-]+")
_SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_ -]?key\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\bAIza[A-Za-z0-9_-]{8,}\b"),
)


def new_resource_correlation_id():
    """Return an opaque per-response identifier containing no game data."""
    return uuid.uuid4().hex


def _identifier(value, default="unknown", limit=120):
    clean = _SAFE_IDENTIFIER.sub("_", str(value or default)).strip("_.:-")
    return (clean or default)[:limit]


def _sanitize_diagnostic(value, limit=600):
    """Bound one exception message and redact credential-shaped fragments."""
    if not isinstance(value, str):
        value = str(value or "unknown failure")
    clean = " ".join(value.replace("\x00", " ").split())
    for pattern in _SECRET_PATTERNS:
        if pattern.groups:
            clean = pattern.sub(lambda match: match.group(1) + "[REDACTED]", clean)
        else:
            clean = pattern.sub("[REDACTED]", clean)
    return clean[:limit] or "unknown failure"


def _path():
    configured = os.environ.get("NEQ_RESOURCE_DIAGNOSTICS_PATH")
    return Path(configured) if configured and configured.strip() else DEFAULT_LEDGER_PATH


def record_resource_failure(
    *,
    correlation_id,
    failure_code,
    stage,
    action_indices=(),
    exception_class=None,
    diagnostic=None,
):
    """Append bounded failure metadata without ever affecting game behavior."""
    try:
        indices = sorted(
            {
                value
                for value in action_indices
                if type(value) is int and 0 <= value <= 4096
            }
        )[:64]
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runId": _PROCESS_RUN_ID,
            "correlationId": _identifier(correlation_id, limit=64),
            "recordType": "resource_transaction_failure",
            "failureCode": _identifier(failure_code),
            "stage": _identifier(stage),
            "actionIndices": indices,
            "exceptionClass": _identifier(exception_class),
            "diagnostic": _sanitize_diagnostic(diagnostic),
        }
        line = json.dumps(entry, ensure_ascii=True, separators=(",", ":")) + "\n"
        if not _WRITE_LOCK.acquire(blocking=False):
            return False
        try:
            path = _path()
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line)
        finally:
            _WRITE_LOCK.release()
        return True
    except Exception:
        return False


def record_resource_routing(
    *,
    provider,
    model_family,
    route,
    score,
    threshold,
    participant_count,
    asset_family_count,
    fact_count,
    planner_calls,
    outcome,
    elapsed_ms,
):
    """Append non-game-data routing facts for T105 threshold tuning."""
    try:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runId": _PROCESS_RUN_ID,
            "recordType": "resource_transaction_routing",
            "provider": _identifier(provider),
            "modelFamily": _identifier(model_family),
            "route": _identifier(route),
            "score": max(0, min(int(score), 100)),
            "threshold": max(0, min(int(threshold), 100)),
            "participantCount": max(0, min(int(participant_count), 64)),
            "assetFamilyCount": max(0, min(int(asset_family_count), 16)),
            "factCount": max(0, min(int(fact_count), 256)),
            "plannerCalls": max(0, min(int(planner_calls), 2)),
            "outcome": _identifier(outcome),
            "elapsedMs": max(0, min(int(elapsed_ms), 3600000)),
            "usageSource": "shared_callsite_telemetry",
        }
        line = json.dumps(entry, ensure_ascii=True, separators=(",", ":")) + "\n"
        if not _WRITE_LOCK.acquire(blocking=False):
            return False
        try:
            path = _path()
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line)
        finally:
            _WRITE_LOCK.release()
        return True
    except Exception:
        return False


def record_turn_receipt(
    receipt,
    *,
    failure_code=None,
    stage=None,
    exception_class=None,
    diagnostic=None,
):
    """Append a bounded receipt projection; never expose game data or secrets."""
    try:
        if not isinstance(receipt, dict):
            return False
        intended = receipt.get("intendedActionIndices") or []
        committed = receipt.get("committedActionIndices") or []
        transaction_ids = receipt.get("transactionIds") or []
        participants = receipt.get("participants") or []
        deltas = receipt.get("resourceDeltas") or []
        advisories = receipt.get("advisories") or []
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runId": _PROCESS_RUN_ID,
            "recordType": "turn_receipt",
            "correlationId": _identifier(
                receipt.get("correlationId"), limit=64
            ),
            "success": receipt.get("success") is True,
            "intendedActionIndices": sorted(
                value
                for value in intended
                if type(value) is int and 0 <= value <= 4096
            )[:64],
            "committedActionIndices": sorted(
                value
                for value in committed
                if type(value) is int and 0 <= value <= 4096
            )[:64],
            "transactionIds": [
                _identifier(value, limit=160)
                for value in transaction_ids[:16]
                if value
            ],
            "participantCount": min(len(participants), 64),
            "resourceDeltaCount": min(len(deltas), 256),
            "advisoryCount": min(len(advisories), 256),
        }
        if receipt.get("success") is not True:
            entry.update(
                {
                    "failureCode": _identifier(failure_code),
                    "stage": _identifier(stage),
                    "exceptionClass": _identifier(exception_class),
                    "diagnostic": _sanitize_diagnostic(diagnostic),
                }
            )
        line = json.dumps(entry, ensure_ascii=True, separators=(",", ":")) + "\n"
        if not _WRITE_LOCK.acquire(blocking=False):
            return False
        try:
            path = _path()
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line)
        finally:
            _WRITE_LOCK.release()
        return True
    except Exception:
        return False
