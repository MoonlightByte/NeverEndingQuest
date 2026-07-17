#!/usr/bin/env python3
"""
OpenAI Usage Tracker - Uses built-in usage data from OpenAI API responses
Enhanced with telemetry logging and spike detection for migration analysis
"""

import json
import hashlib
import re
from datetime import datetime, timedelta
from collections import OrderedDict, deque
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
import threading
from pathlib import Path
import weakref
from uuid import uuid4


_MODULE_CONTEXT_FIELDS = frozenset(
    {
        "endpoint",
        "purpose",
        "build_id",
        "callsite_id",
        "provider",
        "model",
        "attempt",
        "outcome",
    }
)

_IDENTITY_CACHE_LIMIT = 4096
_IDENTITY_TEXT_LIMIT = 512
_PROVIDER_METADATA_LIMIT = 64
_MODEL_METADATA_LIMIT = 128
_CALLSITE_METADATA_LIMIT = 64
_GENERAL_METADATA_LIMIT = 128
_SENSITIVE_VALUE = re.compile(
    r"(?i)(?:sk-[a-z0-9_-]{4,}|aiza[a-z0-9_-]{8,}|api[ _-]?key|"
    r"bearer\s+|password|secret)"
)
_URL_OR_QUERY_VALUE = re.compile(
    r"(?i)(?:[a-z][a-z0-9+.-]*://|[?&#=])"
)
_SAFE_IDENTIFIER_VALUE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.@+:-]*$")
_SAFE_MODEL_VALUE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.@+:/-]*$")
MODULE_BUILD_OUTCOMES = frozenset(
    {
        "provider_response",
        "generated",
        "published",
        "failed",
        "not_published",
        "indeterminate",
        "contract_rejected",
        "lock_unavailable",
        "builder_recovery_required",
        "lifecycle_recovery_required",
        "not_generated",
        "ready_candidate_missing",
        "cleanup_recovery_required",
        "publication_indeterminate",
        "published_recovered",
        "published_replay",
        "delivery_pending",
        "cancelled",
        "canceled",
        "success",
        "error",
        "unknown",
    }
)
_KNOWN_PROVIDERS = frozenset({"legacy", "openai", "gemini", "lmstudio"})
_KNOWN_INTERFACES = frozenset({"web", "terminal", "toolkit"})
_TELEMETRY_CONTEXT_LIMITS = {
    "endpoint": _GENERAL_METADATA_LIMIT,
    "purpose": _GENERAL_METADATA_LIMIT,
    "build_id": _GENERAL_METADATA_LIMIT,
    "callsite_id": _CALLSITE_METADATA_LIMIT,
    "provider": _PROVIDER_METADATA_LIMIT,
    "model": _MODEL_METADATA_LIMIT,
    "outcome": _GENERAL_METADATA_LIMIT,
    "interface": _GENERAL_METADATA_LIMIT,
}


def _normalized_metadata_text(value):
    if not isinstance(value, str):
        return None
    if "\n" in value or "\r" in value:
        return None
    normalized = " ".join(value.split()).strip()
    if (
        not normalized
        or _SENSITIVE_VALUE.search(normalized)
        or _URL_OR_QUERY_VALUE.search(normalized)
    ):
        return None
    return normalized


def _sanitize_identifier(value, limit, default="unknown", lowercase=False):
    normalized = _normalized_metadata_text(value)
    if normalized is None or not _SAFE_IDENTIFIER_VALUE.fullmatch(normalized):
        return default
    if lowercase:
        normalized = normalized.lower()
    return normalized[:limit]


def _sanitize_model(value, default="unknown"):
    normalized = _normalized_metadata_text(value)
    if normalized is None or not _SAFE_MODEL_VALUE.fullmatch(normalized):
        return default
    return normalized[:_MODEL_METADATA_LIMIT]


def _sanitize_provider(value, default="unknown"):
    normalized = _sanitize_identifier(
        value,
        _PROVIDER_METADATA_LIMIT,
        default=default,
        lowercase=True,
    )
    return normalized if normalized in _KNOWN_PROVIDERS else default


def _sanitize_outcome(value, default="unknown"):
    normalized = _normalized_metadata_text(value)
    if normalized is None:
        return default
    normalized = normalized.lower()
    return normalized if normalized in MODULE_BUILD_OUTCOMES else default


def _sanitize_interface(value, default="unknown"):
    normalized = _sanitize_identifier(
        value,
        _GENERAL_METADATA_LIMIT,
        default=default,
        lowercase=True,
    )
    return normalized if normalized in _KNOWN_INTERFACES else default


def _sanitize_context_field(key, value, limit):
    if key == "model":
        return _sanitize_model(value)
    if key == "outcome":
        return _sanitize_outcome(value)
    if key == "provider":
        return _sanitize_provider(value)
    if key == "interface":
        return _sanitize_interface(value)
    return _sanitize_identifier(
        value,
        limit,
        lowercase=False,
    )


def _sanitize_telemetry_context(context):
    if isinstance(context, str):
        return {
            "endpoint": _sanitize_identifier(
                context, _GENERAL_METADATA_LIMIT
            )
        }
    if not isinstance(context, dict):
        return {}

    sanitized = {}
    for key, limit in _TELEMETRY_CONTEXT_LIMITS.items():
        if key not in context:
            continue
        value = context[key]
        if key == "attempt":
            continue
        sanitized[key] = _sanitize_context_field(key, value, limit)
    attempt = context.get("attempt")
    if isinstance(attempt, int) and not isinstance(attempt, bool):
        sanitized["attempt"] = max(0, min(attempt, 1_000_000))
    return sanitized


def _valid_token_count(value):
    if type(value) is not int or value < 0:
        return None
    return value


def _live_object_identity(value):
    """Return a process-local identity used only beside an owning weakref."""
    return id(value)


class _UsageTrackerToken:
    """Opaque identity owned by a response but never serialized."""

    __slots__ = ()


@dataclass
class ModuleBuildUsageContext:
    """Request-local accounting state for one module generation lifecycle."""

    build_id: str
    attempts: dict = field(default_factory=dict)
    terminal_outcome: str = None
    terminal_recorded: bool = False
    lock: threading.Lock = field(
        default_factory=threading.Lock, repr=False, compare=False
    )


_module_build_context = ContextVar("module_build_usage_context", default=None)

class OpenAIUsageTracker:
    """Tracks OpenAI's built-in usage statistics with enhanced telemetry"""
    
    def __init__(self, telemetry_log="telemetry_log.jsonl"):
        # Cumulative totals
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0
        self.total_requests = 0
        
        # Sliding window for TPM/RPM (last 60 seconds)
        self.usage_history = deque()  # (timestamp, prompt_tokens, completion_tokens, total_tokens, context)
        
        # Spike tracking
        self.max_single_call_tokens = 0
        self.max_single_call_context = None
        self.max_single_call_timestamp = None
        
        self.max_tpm_observed = 0
        self.max_tpm_timestamp = None
        
        self.max_rpm_observed = 0
        self.max_rpm_timestamp = None
        
        # Per-endpoint tracking
        self.endpoint_stats = {}  # endpoint -> {'count': N, 'total_tokens': N, 'max_tokens': N}
        
        # Session start time
        self.session_start = datetime.now()
        
        # Telemetry log file
        self.telemetry_log = Path(telemetry_log)

        # A response may be observed both at the central call boundary and at a
        # legacy manual callsite. Stable, invocation, and attached-token keys
        # share one bounded LRU. Weak fallback records own a live weakref, never
        # a bare object id or a strong reference to the response.
        self._identity_cache_limit = _IDENTITY_CACHE_LIMIT
        self._identity_key_cache = OrderedDict()
        self._weak_identity_records = OrderedDict()
        self.health_stats = {
            "identity_unavailable": 0,
            "usage_read_error": 0,
            "usage_validation_error": 0,
            "telemetry_write_error": 0,
        }

        self.lock = threading.Lock()

    @staticmethod
    def _safe_attribute(value, name, default=None):
        try:
            return getattr(value, name, default)
        except Exception:
            return default

    @staticmethod
    def _canonical_provider(response, context=None):
        provider = OpenAIUsageTracker._safe_attribute(response, "provider")
        if not provider and isinstance(context, dict):
            provider = context.get("provider")
        if not provider:
            provider = OpenAIUsageTracker._safe_attribute(
                response, "_usage_tracker_provider"
            )
        return _sanitize_provider(provider)

    @staticmethod
    def _trimmed_identity(value):
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if len(normalized) > _IDENTITY_TEXT_LIMIT:
            digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            return f"sha256:{digest}"
        return normalized

    def _remember_identity_key_locked(self, key):
        if key in self._identity_key_cache:
            self._identity_key_cache.move_to_end(key)
            return False
        self._identity_key_cache[key] = None
        while len(self._identity_key_cache) > self._identity_cache_limit:
            self._identity_key_cache.popitem(last=False)
        return True

    def _remember_weak_identity_locked(self, response):
        object_id = _live_object_identity(response)
        if not isinstance(object_id, int):
            self.health_stats["identity_unavailable"] += 1
            return True
        existing = self._weak_identity_records.get(object_id)
        if (
            isinstance(existing, weakref.ReferenceType)
            and existing() is response
        ):
            self._weak_identity_records.move_to_end(object_id)
            return False
        if existing is not None:
            self._weak_identity_records.pop(object_id, None)

        tracker_reference = weakref.ref(self)

        def remove_dead_response(dead_reference):
            tracker = tracker_reference()
            if tracker is None:
                return
            with tracker.lock:
                current = tracker._weak_identity_records.get(object_id)
                if current is dead_reference:
                    tracker._weak_identity_records.pop(object_id, None)

        try:
            response_reference = weakref.ref(response, remove_dead_response)
        except TypeError:
            self.health_stats["identity_unavailable"] += 1
            return True

        self._weak_identity_records[object_id] = response_reference
        while len(self._weak_identity_records) > self._identity_cache_limit:
            self._weak_identity_records.popitem(last=False)
        return True

    def _reserve_response_identity_locked(self, response, context=None):
        response_id = self._trimmed_identity(
            self._safe_attribute(response, "id")
        )
        if response_id is not None:
            canonical_provider = self._canonical_provider(response, context)
            if canonical_provider != "unknown":
                if (
                    not self._safe_attribute(response, "provider")
                    and not self._safe_attribute(
                        response, "_usage_tracker_provider"
                    )
                ):
                    try:
                        setattr(
                            response,
                            "_usage_tracker_provider",
                            canonical_provider,
                        )
                    except Exception:
                        pass
                return self._remember_identity_key_locked(
                    ("stable", canonical_provider, response_id)
                )

        invocation_id = self._trimmed_identity(
            self._safe_attribute(response, "_usage_invocation_id")
        )
        if invocation_id is not None:
            return self._remember_identity_key_locked(
                ("invocation", invocation_id)
            )

        token = self._safe_attribute(response, "_usage_tracker_token")
        if not isinstance(token, _UsageTrackerToken):
            candidate = _UsageTrackerToken()
            try:
                setattr(response, "_usage_tracker_token", candidate)
                token = getattr(response, "_usage_tracker_token")
            except Exception:
                token = None
        if isinstance(token, _UsageTrackerToken):
            return self._remember_identity_key_locked(("token", token))

        return self._remember_weak_identity_locked(response)

    def _read_usage(self, response):
        try:
            usage = getattr(response, "usage")
        except AttributeError:
            return None
        except Exception:
            with self.lock:
                self.health_stats["usage_read_error"] += 1
            return None
        if usage is None:
            return None
        try:
            counts = tuple(
                _valid_token_count(getattr(usage, field, None))
                for field in (
                    "prompt_tokens",
                    "completion_tokens",
                    "total_tokens",
                )
            )
        except Exception:
            with self.lock:
                self.health_stats["usage_read_error"] += 1
            return None
        if any(count is None for count in counts):
            with self.lock:
                self.health_stats["usage_validation_error"] += 1
            return None
        return counts
    
    def track(self, response, context=None):
        """Track usage from OpenAI response with enhanced telemetry"""
        usage_counts = self._read_usage(response)
        if usage_counts is None:
            return False
        safe_context = _sanitize_telemetry_context(context)
        try:
            with self.lock:
                if not self._reserve_response_identity_locked(
                    response, safe_context
                ):
                    return False
                now = datetime.now()

                # Extract OpenAI's provided usage data
                prompt_tokens, completion_tokens, total_tokens = usage_counts
                
                # Extract model from response if available
                reported_model = self._safe_attribute(response, "model")
                if not isinstance(reported_model, str) and "model" in safe_context:
                    reported_model = safe_context["model"]
                model = _sanitize_model(reported_model)
                
                # Update totals
                self.total_prompt_tokens += prompt_tokens
                self.total_completion_tokens += completion_tokens
                self.total_tokens += total_tokens
                self.total_requests += 1
                
                # Track spike - individual call
                if total_tokens > self.max_single_call_tokens:
                    self.max_single_call_tokens = total_tokens
                    self.max_single_call_context = {
                        'timestamp': now.isoformat(),
                        'tokens': total_tokens,
                        'model': model,
                        'context': safe_context,
                    }
                    self.max_single_call_timestamp = now
                    
                    # Log spike to file
                    self._log_spike(total_tokens, model, safe_context)
                
                # Add to history with context
                self.usage_history.append(
                    (
                        now,
                        prompt_tokens,
                        completion_tokens,
                        total_tokens,
                        safe_context,
                    )
                )
                
                # Clean old entries (older than 60 seconds)
                cutoff = now - timedelta(seconds=60)
                while self.usage_history and self.usage_history[0][0] < cutoff:
                    self.usage_history.popleft()
                
                # Calculate current TPM/RPM
                tpm = sum(entry[3] for entry in self.usage_history)
                rpm = len(self.usage_history)
                
                # Track TPM/RPM spikes
                if tpm > self.max_tpm_observed:
                    self.max_tpm_observed = tpm
                    self.max_tpm_timestamp = now
                    
                if rpm > self.max_rpm_observed:
                    self.max_rpm_observed = rpm
                    self.max_rpm_timestamp = now
                
                # Track per-endpoint stats
                endpoint = 'unknown'
                if safe_context:
                    endpoint = safe_context.get('endpoint', 'unknown')
                
                if endpoint not in self.endpoint_stats:
                    self.endpoint_stats[endpoint] = {
                        'count': 0,
                        'total_tokens': 0,
                        'max_tokens': 0,
                        'models_used': set()
                    }
                
                self.endpoint_stats[endpoint]['count'] += 1
                self.endpoint_stats[endpoint]['total_tokens'] += total_tokens
                self.endpoint_stats[endpoint]['max_tokens'] = max(
                    self.endpoint_stats[endpoint]['max_tokens'], 
                    total_tokens
                )
                self.endpoint_stats[endpoint]['models_used'].add(model)
                
                # Log telemetry entry
                self._log_telemetry(
                    now,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    model,
                    safe_context,
                )
                return True

        except Exception:
            with self.lock:
                self.health_stats["telemetry_write_error"] += 1
            return False

    def record_event(self, event_type, context=None):
        """Write a zero-token lifecycle event without affecting usage totals."""
        safe_event_type = _sanitize_identifier(
            event_type, _GENERAL_METADATA_LIMIT, default="health_event"
        )
        safe_context = _sanitize_telemetry_context(context)
        try:
            entry = {
                "type": safe_event_type,
                "timestamp": datetime.now().isoformat(),
                "context": safe_context,
            }
            with self.lock:
                with open(self.telemetry_log, "a", encoding="utf-8") as handle:
                    handle.write(json.dumps(entry) + "\n")
            return True
        except Exception:
            with self.lock:
                self.health_stats["telemetry_write_error"] += 1
            return False
    
    def _log_telemetry(self, timestamp, prompt_tokens, completion_tokens, total_tokens, model, context):
        """Log telemetry entry to file"""
        try:
            entry = {
                'timestamp': timestamp.isoformat(),
                'prompt_tokens': prompt_tokens,
                'completion_tokens': completion_tokens,
                'total_tokens': total_tokens,
                'model': model,
                'context': context or {},
                'session_elapsed': str(timestamp - self.session_start)
            }
            with open(self.telemetry_log, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry) + '\n')
        except Exception:
            self.health_stats["telemetry_write_error"] += 1
    
    def _log_spike(self, tokens, model, context):
        """Log spike detection to file"""
        try:
            spike_entry = {
                'type': 'spike_detected',
                'timestamp': datetime.now().isoformat(),
                'tokens': tokens,
                'model': model,
                'context': context or {},
                'previous_max': self.max_single_call_tokens
            }
            with open(self.telemetry_log, 'a', encoding='utf-8') as f:
                f.write(json.dumps(spike_entry) + '\n')
        except Exception:
            self.health_stats["telemetry_write_error"] += 1
    
    def get_current_stats(self):
        """Get enhanced usage statistics with telemetry data"""
        try:
            with self.lock:
                # Clean old entries first (older than 60 seconds)
                now = datetime.now()
                cutoff = now - timedelta(seconds=60)
                while self.usage_history and self.usage_history[0][0] < cutoff:
                    self.usage_history.popleft()
                
                # Calculate tokens/requests in the last minute
                tpm = sum(entry[3] for entry in self.usage_history)  # Sum of total_tokens
                rpm = len(self.usage_history)  # Number of requests
                
                # Prepare endpoint summary
                endpoint_summary = {}
                for endpoint, stats in self.endpoint_stats.items():
                    endpoint_summary[endpoint] = {
                        'count': stats['count'],
                        'total_tokens': stats['total_tokens'],
                        'avg_tokens': stats['total_tokens'] // stats['count'] if stats['count'] > 0 else 0,
                        'max_tokens': stats['max_tokens'],
                        'models': list(stats['models_used'])
                    }
                
                return {
                    # Current rates
                    'tpm': tpm,
                    'rpm': rpm,
                    
                    # Session totals
                    'total_tokens': self.total_tokens,
                    'total_prompt_tokens': self.total_prompt_tokens,
                    'total_completion_tokens': self.total_completion_tokens,
                    'total_requests': self.total_requests,
                    
                    # Spike tracking
                    'max_single_call': {
                        'tokens': self.max_single_call_tokens,
                        'timestamp': self.max_single_call_timestamp.isoformat() if self.max_single_call_timestamp else None,
                        'context': self.max_single_call_context
                    },
                    'max_tpm': {
                        'value': self.max_tpm_observed,
                        'timestamp': self.max_tpm_timestamp.isoformat() if self.max_tpm_timestamp else None
                    },
                    'max_rpm': {
                        'value': self.max_rpm_observed,
                        'timestamp': self.max_rpm_timestamp.isoformat() if self.max_rpm_timestamp else None
                    },
                    
                    # Per-endpoint breakdown
                    'endpoints': endpoint_summary,
                    
                    # Session info
                    'session_duration': str(datetime.now() - self.session_start),
                    'avg_tokens_per_request': self.total_tokens // self.total_requests if self.total_requests > 0 else 0
                }
        except Exception:
            with self.lock:
                self.health_stats["telemetry_write_error"] += 1
            return {
                'tpm': 0,
                'rpm': 0,
                'total_tokens': 0,
                'total_prompt_tokens': 0,
                'total_completion_tokens': 0,
                'total_requests': 0,
                'error': 'unavailable'
            }

# Global tracker instance
_global_tracker = None
_global_tracker_lock = threading.Lock()

def get_global_tracker():
    """Get or create the global usage tracker"""
    global _global_tracker
    if _global_tracker is None:
        with _global_tracker_lock:
            if _global_tracker is None:
                _global_tracker = OpenAIUsageTracker()
    return _global_tracker


def get_module_build_usage_context():
    """Return the active module-build context, if this request owns one."""
    return _module_build_context.get()


@contextmanager
def module_build_usage_scope(build_id=None):
    """Create a nested-safe usage scope for builder and publication calls."""
    active = get_module_build_usage_context()
    if active is not None:
        yield active
        return

    context = ModuleBuildUsageContext(build_id=build_id or str(uuid4()))
    token = _module_build_context.set(context)
    try:
        yield context
    except Exception:
        mark_module_build_outcome("failed")
        raise
    finally:
        _module_build_context.reset(token)


def _module_usage_context(
    context, *, task_id, provider, model, attempt, outcome
):
    candidate = {
        "endpoint": "module_generation",
        "purpose": "module_generation_response",
        "build_id": _sanitize_identifier(
            context.build_id, _GENERAL_METADATA_LIMIT, default="unknown"
        ),
        "callsite_id": _sanitize_identifier(
            task_id, _CALLSITE_METADATA_LIMIT, default="unknown"
        ),
        "provider": _sanitize_provider(provider),
        "model": _sanitize_model(model),
        "attempt": int(attempt),
        "outcome": _sanitize_outcome(outcome, default="provider_response"),
    }
    return {key: candidate[key] for key in _MODULE_CONTEXT_FIELDS}


def track_module_build_response(
    response, *, task_id, provider=None, model=None, outcome="provider_response"
):
    """Count one selected primary response when a module build is active."""
    context = get_module_build_usage_context()
    if context is None:
        return False

    callsite_key = _sanitize_identifier(
        task_id, _CALLSITE_METADATA_LIMIT, default="unknown"
    )
    # Lock order is always context -> tracker. The terminal check and attempt
    # allocation are one transaction with the tracker update.
    with context.lock:
        if context.terminal_outcome is not None:
            return False
        next_attempt = context.attempts.get(callsite_key, 0) + 1
        tracked = get_global_tracker().track(
            response,
            context=_module_usage_context(
                context,
                task_id=callsite_key,
                provider=provider,
                model=model,
                attempt=next_attempt,
                outcome=outcome,
            ),
        )
        if tracked:
            context.attempts[callsite_key] = next_attempt
        return tracked


def mark_module_build_outcome(outcome):
    """Record one sanitized terminal event for the active module build."""
    context = get_module_build_usage_context()
    if context is None:
        return False
    normalized = _sanitize_outcome(outcome)
    # Match track_module_build_response's context -> tracker lock order.
    with context.lock:
        if context.terminal_outcome is not None:
            return False
        context.terminal_outcome = normalized
        context.terminal_recorded = get_global_tracker().record_event(
            "module_build_terminal",
            {
                "endpoint": "module_generation",
                "build_id": context.build_id,
                "outcome": normalized,
            },
        )
        return context.terminal_recorded

def track_response(response):
    """Track an OpenAI response (safe - never throws)"""
    try:
        tracker = get_global_tracker()
        return tracker.track(response)
    except:
        return False

def get_usage_stats():
    """Get current usage statistics (safe - always returns valid data)"""
    try:
        tracker = get_global_tracker()
        return tracker.get_current_stats()
    except:
        return {
            'tpm': 0,
            'rpm': 0,
            'total_tokens': 0,
            'total_prompt_tokens': 0,
            'total_completion_tokens': 0,
            'total_requests': 0
        }
