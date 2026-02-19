# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
LLM Usage Tracker - Provider-agnostic usage aggregation with session/week rollups
Tracks tokens and costs with USD->NZD conversion.
Cost strategy: provider-reported first, blended fallback when unavailable.
"""

import json
from datetime import datetime, timedelta
from collections import deque
import threading
from pathlib import Path
import traceback
from typing import Dict, Any, Tuple


class LLMUsageTracker:
    """
    Provider-agnostic usage tracker with session/week rollups and cost estimation.
    Works with OpenAI-compatible usage responses from any provider.
    Cost source: provider-reported when available, fallback estimate when missing.
    """

    def __init__(self, telemetry_log="telemetry_log.jsonl"):
        # Session start time
        self.session_start = datetime.now()

        # Session totals (process lifetime)
        self.session_tokens = 0
        self.session_prompt_tokens = 0
        self.session_completion_tokens = 0
        self.session_requests = 0
        self.session_cost_usd = 0.0
        self.session_cost_nzd = 0.0
        
        # Session cost source tracking (for accurate source determination)
        self.session_provider_reported_count = 0
        self.session_estimated_count = 0
        self.session_unavailable_count = 0

        # Rolling window for TPM/RPM (last 60 seconds)
        self.usage_history = deque()  # (timestamp, prompt_tokens, completion_tokens, total_tokens, context)

        # Week window usage events for rollups
        # Format: (timestamp, total_tokens, cost_usd, cost_source)
        self.week_window_events = deque()

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

        # Telemetry log file
        self.telemetry_log = Path(telemetry_log)

        # Lock for thread safety
        self._lock = threading.Lock()

        # Load config
        self._load_config()

        # Bootstrap week data from telemetry log if available
        self._bootstrap_week_from_log()

    def _load_config(self):
        """Load config constants for conversion and fallback pricing."""
        try:
            from model_config import (
                USD_TO_NZD_RATE,
                USAGE_WEEK_WINDOW_DAYS,
                USD_PER_1M_TOKENS_BLEND
            )
            self.usd_to_nzd_rate = USD_TO_NZD_RATE if isinstance(USD_TO_NZD_RATE, (int, float)) and USD_TO_NZD_RATE > 0 else 1.65
            self.week_window_days = USAGE_WEEK_WINDOW_DAYS if isinstance(USAGE_WEEK_WINDOW_DAYS, int) and USAGE_WEEK_WINDOW_DAYS > 0 else 7
            self.fallback_rate = USD_PER_1M_TOKENS_BLEND if isinstance(USD_PER_1M_TOKENS_BLEND, (int, float)) and USD_PER_1M_TOKENS_BLEND >= 0 else 1.50
        except Exception:
            # Safe defaults on any config error
            self.usd_to_nzd_rate = 1.65
            self.week_window_days = 7
            self.fallback_rate = 1.50

    def _calculate_cost(self, total_tokens: int, provider_cost = None) -> Tuple[float, str, bool]:
        """
        Calculate cost for a usage event.
        Returns (cost_usd, cost_source, is_estimate).

        Priority:
        1. Provider-reported cost if available (>= 0)
        2. Blended fallback estimate if fallback_rate > 0
        3. Zero with unavailable status otherwise
        """
        # Provider-reported cost takes priority
        if provider_cost is not None and isinstance(provider_cost, (int, float)) and provider_cost >= 0.0:
            return (float(provider_cost), "provider_reported", False)

        # Fallback estimate using blended rate
        if self.fallback_rate > 0 and total_tokens > 0:
            estimated_cost = (total_tokens / 1_000_000) * self.fallback_rate
            return (estimated_cost, "estimated", True)

        # Unavailable
        return (0.0, "unavailable", True)

    def _bootstrap_week_from_log(self):
        """Bootstrap week window from telemetry log file with cost backfill for historical entries."""
        try:
            if not self.telemetry_log.exists():
                return

            cutoff = datetime.now() - timedelta(days=self.week_window_days)

            with open(self.telemetry_log, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        entry = json.loads(line)

                        # Skip spike entries and non-usage entries
                        if entry.get('type') == 'spike_detected':
                            continue

                        # Parse timestamp
                        ts_str = entry.get('timestamp', '')
                        if not ts_str:
                            continue

                        try:
                            ts = datetime.fromisoformat(ts_str)
                        except Exception:
                            continue

                        # Only load entries within week window
                        if ts < cutoff:
                            continue

                        total_tokens = entry.get('total_tokens', 0)

                        # Cost backfill: if cost_usd missing, compute fallback estimate
                        if 'cost_usd' in entry and entry['cost_usd'] is not None:
                            cost_usd = float(entry['cost_usd'])
                            cost_source = entry.get('cost_source', 'provider_reported')
                        else:
                            # Backfill using fallback estimate from tokens
                            if self.fallback_rate > 0 and total_tokens > 0:
                                cost_usd = (total_tokens / 1_000_000) * self.fallback_rate
                                cost_source = "estimated"
                            else:
                                cost_usd = 0.0
                                cost_source = "unavailable"

                        self.week_window_events.append((ts, total_tokens, cost_usd, cost_source))

                    except json.JSONDecodeError:
                        # Skip malformed lines
                        continue
                    except Exception:
                        # Skip any other errors in individual lines
                        continue

        except Exception as e:
            # Fail open - week window starts empty
            print(f"DEBUG: [LLM_USAGE] Week bootstrap warning: {e}")

    def track(self, response, context=None):
        """
        Track usage from LLM response with cost estimation.
        Works with OpenAI-compatible usage responses from any provider.
        """
        try:
            # Extract usage data from response
            usage = None
            provider_cost: float = -1.0

            if hasattr(response, 'usage'):
                usage = response.usage
                # Try to get provider-reported cost
                if hasattr(response.usage, 'cost'):
                    cost_val = getattr(response.usage, 'cost', None)
                    if cost_val is not None:
                        provider_cost = float(cost_val)
            elif isinstance(response, dict) and 'usage' in response:
                usage = response['usage']
                # Try to get provider-reported cost from dict
                if isinstance(usage, dict):
                    cost_val = usage.get('cost')
                    if cost_val is not None and isinstance(cost_val, (int, float)):
                        provider_cost = float(cost_val)

            if usage is None:
                return

            # Extract token counts
            if hasattr(usage, 'prompt_tokens'):
                prompt_tokens = getattr(usage, 'prompt_tokens', 0)
                completion_tokens = getattr(usage, 'completion_tokens', 0)
                total_tokens = getattr(usage, 'total_tokens', 0)
            else:
                prompt_tokens = usage.get('prompt_tokens', 0)
                completion_tokens = usage.get('completion_tokens', 0)
                total_tokens = usage.get('total_tokens', 0)

            # Calculate cost
            cost_usd, cost_source, is_estimate = self._calculate_cost(total_tokens, provider_cost)

            with self._lock:
                now = datetime.now()

                # Update session totals
                self.session_tokens += total_tokens
                self.session_prompt_tokens += prompt_tokens
                self.session_completion_tokens += completion_tokens
                self.session_requests += 1
                self.session_cost_usd += cost_usd
                self.session_cost_nzd = self.session_cost_usd * self.usd_to_nzd_rate
                
                # Track cost source for session-level source determination
                if cost_source == "provider_reported":
                    self.session_provider_reported_count += 1
                elif cost_source == "estimated":
                    self.session_estimated_count += 1
                else:
                    self.session_unavailable_count += 1

                # Track spike - individual call
                if total_tokens > self.max_single_call_tokens:
                    self.max_single_call_tokens = total_tokens
                    self.max_single_call_context = {
                        'timestamp': now.isoformat(),
                        'tokens': total_tokens,
                        'context': context or {}
                    }
                    self.max_single_call_timestamp = now
                    self._log_spike(total_tokens, context)

                # Add to rolling window history
                self.usage_history.append((now, prompt_tokens, completion_tokens, total_tokens, context))

                # Add to week window
                self.week_window_events.append((now, total_tokens, cost_usd, cost_source))

                # Clean old entries (older than 60 seconds for TPM/RPM)
                cutoff_60s = now - timedelta(seconds=60)
                while self.usage_history and self.usage_history[0][0] < cutoff_60s:
                    self.usage_history.popleft()

                # Clean old week entries
                cutoff_week = now - timedelta(days=self.week_window_days)
                while self.week_window_events and self.week_window_events[0][0] < cutoff_week:
                    self.week_window_events.popleft()

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
                if context:
                    if isinstance(context, str):
                        endpoint = context
                    elif isinstance(context, dict):
                        endpoint = context.get('endpoint', 'unknown')

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

                # Log telemetry entry
                self._log_telemetry(now, prompt_tokens, completion_tokens, total_tokens, context, cost_usd, cost_source, is_estimate)

        except Exception as e:
            print(f"DEBUG: [LLM_USAGE] Error tracking: {e}")
            traceback.print_exc()

    def _log_telemetry(self, timestamp, prompt_tokens, completion_tokens, total_tokens, context, cost_usd, cost_source, is_estimate):
        """Log telemetry entry to file."""
        try:
            entry = {
                'timestamp': timestamp.isoformat(),
                'prompt_tokens': prompt_tokens,
                'completion_tokens': completion_tokens,
                'total_tokens': total_tokens,
                'context': context or {},
                'session_elapsed': str(timestamp - self.session_start),
                'cost_usd': cost_usd,
                'cost_source': cost_source,
                'cost_estimate': is_estimate
            }
            with open(self.telemetry_log, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry) + '\n')
        except Exception as e:
            print(f"DEBUG: [LLM_USAGE] Error logging: {e}")

    def _log_spike(self, tokens, context):
        """Log spike detection to file."""
        try:
            spike_entry = {
                'type': 'spike_detected',
                'timestamp': datetime.now().isoformat(),
                'tokens': tokens,
                'context': context or {},
                'previous_max': self.max_single_call_tokens
            }
            with open(self.telemetry_log, 'a', encoding='utf-8') as f:
                f.write(json.dumps(spike_entry) + '\n')
        except Exception as e:
            print(f"DEBUG: [LLM_USAGE] Error logging spike: {e}")

    def _compute_week_totals(self) -> Tuple[int, float, float, str]:
        """
        Compute week window totals under lock.
        Returns (tokens, cost_usd, cost_nzd, dominant_cost_source).
        """
        # Clean old entries first
        now = datetime.now()
        cutoff_week = now - timedelta(days=self.week_window_days)
        while self.week_window_events and self.week_window_events[0][0] < cutoff_week:
            self.week_window_events.popleft()

        week_tokens = sum(event[1] for event in self.week_window_events)
        week_cost_usd = sum(event[2] for event in self.week_window_events)
        week_cost_nzd = week_cost_usd * self.usd_to_nzd_rate

        # Determine dominant cost source
        if not self.week_window_events:
            dominant_source = "unavailable"
        else:
            # Count by source
            has_provider = any(e[3] == "provider_reported" for e in self.week_window_events)
            has_estimated = any(e[3] == "estimated" for e in self.week_window_events)

            if has_provider and not has_estimated:
                dominant_source = "provider_reported"
            elif has_estimated:
                dominant_source = "estimated"
            else:
                dominant_source = "unavailable"

        return (week_tokens, week_cost_usd, week_cost_nzd, dominant_source)

    def get_current_stats(self) -> Dict[str, Any]:
        """Get comprehensive usage statistics with session/week rollups and cost data."""
        try:
            with self._lock:
                # Clean old entries for TPM/RPM
                now = datetime.now()
                cutoff_60s = now - timedelta(seconds=60)
                while self.usage_history and self.usage_history[0][0] < cutoff_60s:
                    self.usage_history.popleft()

                # Calculate current TPM/RPM
                tpm = sum(entry[3] for entry in self.usage_history)
                rpm = len(self.usage_history)

                # Calculate week totals (already cleans old entries)
                week_tokens, week_cost_usd, week_cost_nzd, week_cost_source = self._compute_week_totals()

                # Determine session cost source based on tracked event counters
                # Priority: estimated > provider_reported > unavailable
                total_tracked = self.session_provider_reported_count + self.session_estimated_count + self.session_unavailable_count
                if total_tracked == 0:
                    session_cost_source = "unavailable"
                    session_cost_estimate = True
                elif self.session_estimated_count > 0:
                    session_cost_source = "estimated"
                    session_cost_estimate = True
                elif self.session_provider_reported_count > 0:
                    session_cost_source = "provider_reported"
                    session_cost_estimate = False
                else:
                    session_cost_source = "unavailable"
                    session_cost_estimate = True

                # Prepare endpoint summary
                endpoint_summary = {}
                for endpoint, stats in self.endpoint_stats.items():
                    endpoint_summary[endpoint] = {
                        'count': stats['count'],
                        'total_tokens': stats['total_tokens'],
                        'avg_tokens': stats['total_tokens'] // stats['count'] if stats['count'] > 0 else 0,
                        'max_tokens': stats['max_tokens']
                    }

                return {
                    # Current rates (existing keys)
                    'tpm': tpm,
                    'rpm': rpm,

                    # Session totals (existing key + new cost keys)
                    'total_tokens': self.session_tokens,
                    'total_prompt_tokens': self.session_prompt_tokens,
                    'total_completion_tokens': self.session_completion_tokens,
                    'total_requests': self.session_requests,

                    # Session rollups with cost (new)
                    'session_tokens': self.session_tokens,
                    'session_prompt_tokens': self.session_prompt_tokens,
                    'session_completion_tokens': self.session_completion_tokens,
                    'session_requests': self.session_requests,
                    'session_cost_usd': round(self.session_cost_usd, 4),
                    'session_cost_nzd': round(self.session_cost_nzd, 4),
                    'session_cost_source': session_cost_source,
                    'session_cost_estimate': session_cost_estimate,

                    # Week rollups with cost (new)
                    'week_tokens': week_tokens,
                    'week_cost_usd': round(week_cost_usd, 4),
                    'week_cost_nzd': round(week_cost_nzd, 4),
                    'week_cost_source': week_cost_source,

                    # Cost metadata (new)
                    'usd_to_nzd_rate': self.usd_to_nzd_rate,
                    'cost_estimate': session_cost_estimate or week_cost_source in ('estimated', 'unavailable'),

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
                    'avg_tokens_per_request': self.session_tokens // self.session_requests if self.session_requests > 0 else 0,
                    'week_window_days': self.week_window_days
                }
        except Exception as e:
            print(f"DEBUG: [LLM_USAGE] Error getting stats: {e}")
            traceback.print_exc()
            return {
                'tpm': 0,
                'rpm': 0,
                'total_tokens': 0,
                'total_prompt_tokens': 0,
                'total_completion_tokens': 0,
                'total_requests': 0,
                'session_tokens': 0,
                'session_cost_usd': 0.0,
                'session_cost_nzd': 0.0,
                'week_tokens': 0,
                'week_cost_usd': 0.0,
                'week_cost_nzd': 0.0,
                'usd_to_nzd_rate': 1.65,
                'cost_estimate': True,
                'error': str(e)
            }


# Global tracker instance
_global_tracker = None
_global_tracker_lock = threading.Lock()


def get_global_tracker():
    """Get or create the global LLM usage tracker."""
    global _global_tracker
    if _global_tracker is None:
        with _global_tracker_lock:
            if _global_tracker is None:
                _global_tracker = LLMUsageTracker()
    return _global_tracker


def track_response(response, context=None):
    """Track an LLM response (safe - never throws)."""
    try:
        tracker = get_global_tracker()
        tracker.track(response, context)
        return True
    except:
        return False


def get_usage_stats():
    """Get current usage statistics with session/week rollups (safe - always returns valid data)."""
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
            'total_requests': 0,
            'session_tokens': 0,
            'session_cost_usd': 0.0,
            'session_cost_nzd': 0.0,
            'week_tokens': 0,
            'week_cost_usd': 0.0,
            'week_cost_nzd': 0.0,
            'usd_to_nzd_rate': 1.65,
            'cost_estimate': True
        }


def track_image_cost(cost_usd: float, size: str = "1024x1024", quality: str = "standard", model: str = "dall-e-3", context=None):
    """
    Track a cost-only image generation event (no tokens) into session/week rollups.
    Safe fail-open: returns True on success, False on any error without raising.
    
    Args:
        cost_usd: USD cost for the image generation (use 0.0 if unavailable)
        size: Image size (e.g., "1024x1024", "1024x1792", "1792x1024")
        quality: Image quality (e.g., "standard", "hd")
        model: Model identifier (default "dall-e-3")
        context: Optional dict with endpoint/purpose metadata
    
    Returns:
        True if tracked successfully, False otherwise
    """
    try:
        tracker = get_global_tracker()
        with tracker._lock:
            now = datetime.now()
            
            # Determine cost source
            if cost_usd is not None and isinstance(cost_usd, (int, float)) and cost_usd > 0:
                cost_source = "estimated"
                is_estimate = True
                actual_cost = float(cost_usd)
            else:
                cost_source = "unavailable"
                is_estimate = True
                actual_cost = 0.0
            
            # Update session cost totals (tokens remain unchanged)
            tracker.session_cost_usd += actual_cost
            tracker.session_cost_nzd = tracker.session_cost_usd * tracker.usd_to_nzd_rate
            
            # Track cost source for session-level source determination
            if cost_source == "estimated":
                tracker.session_estimated_count += 1
            else:
                tracker.session_unavailable_count += 1
            
            # Add to week window with zero tokens
            tracker.week_window_events.append((now, 0, actual_cost, cost_source))
            
            # Clean old week entries
            cutoff_week = now - timedelta(days=tracker.week_window_days)
            while tracker.week_window_events and tracker.week_window_events[0][0] < cutoff_week:
                tracker.week_window_events.popleft()
            
            # Log telemetry entry (image-specific)
            entry = {
                'timestamp': now.isoformat(),
                'prompt_tokens': 0,
                'completion_tokens': 0,
                'total_tokens': 0,
                'cost_usd': actual_cost,
                'cost_source': cost_source,
                'cost_estimate': is_estimate,
                'context': context or {},
                'image_metadata': {
                    'model': model,
                    'size': size,
                    'quality': quality
                },
                'session_elapsed': str(now - tracker.session_start)
            }
            try:
                with open(tracker.telemetry_log, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(entry) + '\n')
            except Exception:
                pass  # Fail open on log write
            
        return True
    except Exception:
        return False


def get_dalle3_cost_usd(size: str = "1024x1024", quality: str = "standard") -> float:
    """
    Get estimated USD cost for a DALL-E 3 image generation.
    Returns 0.0 if pricing config is unavailable or invalid.
    
    Args:
        size: Image size (e.g., "1024x1024", "1024x1792", "1792x1024")
        quality: Image quality ("standard" or "hd")
    
    Returns:
        Estimated USD cost, or 0.0 if unavailable
    """
    try:
        from model_config import DALLE3_PRICING_USD
        
        # Normalize inputs
        size_key = str(size) if size else "1024x1024"
        quality_key = str(quality) if quality else "standard"
        
        # Look up pricing
        if size_key in DALLE3_PRICING_USD:
            size_pricing = DALLE3_PRICING_USD[size_key]
            if quality_key in size_pricing:
                return float(size_pricing[quality_key])
        
        # Fallback to standard quality if hd not found
        if size_key in DALLE3_PRICING_USD and "standard" in DALLE3_PRICING_USD[size_key]:
            return float(DALLE3_PRICING_USD[size_key]["standard"])
        
        return 0.0
    except Exception:
        return 0.0
