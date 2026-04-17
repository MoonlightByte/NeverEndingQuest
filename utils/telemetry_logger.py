#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""
Enhanced Telemetry Logger for OpenAI API Usage
Tracks TPM/RPM with spike detection and detailed logging for migration analysis
"""

import json
import time
from datetime import datetime, timedelta
from collections import deque
import threading
from pathlib import Path
import traceback

class TelemetryLogger:
    """Enhanced telemetry tracking with spike detection and detailed logging"""
    
    def __init__(self, log_file="telemetry_log.jsonl"):
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
        
        # Lock for thread safety
        self.lock = threading.Lock()
        
        # Log file
        self.log_file = Path(log_file)
        
        # Session start time
        self.session_start = datetime.now()
    
    def track(self, response, context=None):
        """
        Track usage from OpenAI response with context
        context should include: endpoint, model, purpose (e.g., 'combat', 'validation', 'main')
        """
        try:
            # Only proceed if response has usage data
            if not hasattr(response, 'usage'):
                return
            
            with self.lock:
                now = datetime.now()
                
                # Extract OpenAI's provided usage data
                usage = response.usage
                prompt_tokens = getattr(usage, 'prompt_tokens', 0)
                completion_tokens = getattr(usage, 'completion_tokens', 0)
                total_tokens = getattr(usage, 'total_tokens', 0)
                
                # Extract model from response if available
                model = "unknown"
                if hasattr(response, 'model'):
                    model = response.model
                elif context and 'model' in context:
                    model = context['model']
                
                # Create telemetry entry
                entry = {
                    'timestamp': now.isoformat(),
                    'prompt_tokens': prompt_tokens,
                    'completion_tokens': completion_tokens,
                    'total_tokens': total_tokens,
                    'model': model,
                    'context': context or {},
                    'session_elapsed': str(now - self.session_start)
                }
                
                # Update totals
                self.total_prompt_tokens += prompt_tokens
                self.total_completion_tokens += completion_tokens
                self.total_tokens += total_tokens
                self.total_requests += 1
                
                # Track spike - individual call
                if total_tokens > self.max_single_call_tokens:
                    self.max_single_call_tokens = total_tokens
                    self.max_single_call_context = entry
                    self.max_single_call_timestamp = now
                    
                    # Log spike immediately
                    spike_entry = {
                        'type': 'spike_detected',
                        'timestamp': now.isoformat(),
                        'tokens': total_tokens,
                        'model': model,
                        'context': context or {},
                        'previous_max': self.max_single_call_tokens
                    }
                    self._log_to_file(spike_entry)
                
                # Add to history
                self.usage_history.append((now, prompt_tokens, completion_tokens, total_tokens, context))
                
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
                endpoint = context.get('endpoint', 'unknown') if context else 'unknown'
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
                
                # Log regular entry
                self._log_to_file(entry)
                
        except Exception as e:
            print(f"DEBUG: [TELEMETRY] Error tracking usage: {e}")
            traceback.print_exc()
    
    def _log_to_file(self, entry):
        """Append entry to log file"""
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry) + '\n')
        except Exception as e:
            print(f"DEBUG: [TELEMETRY] Error writing to log: {e}")
    
    def get_current_stats(self):
        """Get current usage statistics with spike information"""
        try:
            with self.lock:
                # Clean old entries first
                now = datetime.now()
                cutoff = now - timedelta(seconds=60)
                while self.usage_history and self.usage_history[0][0] < cutoff:
                    self.usage_history.popleft()
                
                # Calculate current metrics
                tpm = sum(entry[3] for entry in self.usage_history)
                rpm = len(self.usage_history)
                
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
        except Exception as e:
            print(f"DEBUG: [TELEMETRY] Error getting stats: {e}")
            return {
                'tpm': 0,
                'rpm': 0,
                'total_tokens': 0,
                'total_prompt_tokens': 0,
                'total_completion_tokens': 0,
                'total_requests': 0,
                'error': str(e)
            }
    
    def export_summary(self, filename="telemetry_summary.json"):
        """Export a comprehensive summary for migration analysis"""
        try:
            stats = self.get_current_stats()
            
            # Add recommendations for migration
            stats['migration_analysis'] = {
                'spike_concern': self.max_single_call_tokens > 50000,
                'high_tpm_concern': self.max_tpm_observed > 100000,
                'recommendations': []
            }
            
            if self.max_single_call_tokens > 50000:
                stats['migration_analysis']['recommendations'].append(
                    f"Large single calls detected ({self.max_single_call_tokens} tokens). "
                    "Consider chunking or streaming for open-source models."
                )
            
            if self.max_tpm_observed > 100000:
                stats['migration_analysis']['recommendations'].append(
                    f"High TPM observed ({self.max_tpm_observed}). "
                    "Ensure open-source model can handle this throughput."
                )
            
            # Identify heavy endpoints
            heavy_endpoints = []
            for endpoint, data in stats['endpoints'].items():
                if data['avg_tokens'] > 10000:
                    heavy_endpoints.append(f"{endpoint} (avg: {data['avg_tokens']} tokens)")
            
            if heavy_endpoints:
                stats['migration_analysis']['recommendations'].append(
                    f"Heavy endpoints: {', '.join(heavy_endpoints)}. "
                    "These may need optimization for open-source models."
                )
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=2, default=str)
            
            print(f"DEBUG: [TELEMETRY] Summary exported to {filename}")
            return stats
            
        except Exception as e:
            print(f"DEBUG: [TELEMETRY] Error exporting summary: {e}")
            return None
    
    def print_debug_display(self):
        """Print formatted telemetry for debug screen"""
        stats = self.get_current_stats()
        
        print("\n" + "="*60)
        print("TELEMETRY DASHBOARD")
        print("="*60)
        
        # Current rates
        print(f"\nCURRENT RATES (last 60s):")
        print(f"  TPM: {stats['tpm']:,}")
        print(f"  RPM: {stats['rpm']}")
        
        # Session totals
        print(f"\nSESSION TOTALS:")
        print(f"  Total Requests: {stats['total_requests']:,}")
        print(f"  Total Tokens: {stats['total_tokens']:,}")
        print(f"    - Prompt: {stats['total_prompt_tokens']:,}")
        print(f"    - Completion: {stats['total_completion_tokens']:,}")
        print(f"  Avg per Request: {stats['avg_tokens_per_request']:,}")
        print(f"  Session Duration: {stats['session_duration']}")
        
        # Spikes
        print(f"\nSPIKE TRACKING:")
        print(f"  Max Single Call: {stats['max_single_call']['tokens']:,} tokens")
        if stats['max_single_call']['timestamp']:
            print(f"    - Time: {stats['max_single_call']['timestamp']}")
            if stats['max_single_call']['context']:
                ctx = stats['max_single_call']['context']
                if ctx and 'context' in ctx:
                    print(f"    - Context: {ctx['context'].get('endpoint', 'unknown')}")
        
        print(f"  Max TPM: {stats['max_tpm']['value']:,}")
        if stats['max_tpm']['timestamp']:
            print(f"    - Time: {stats['max_tpm']['timestamp']}")
        
        print(f"  Max RPM: {stats['max_rpm']['value']}")
        if stats['max_rpm']['timestamp']:
            print(f"    - Time: {stats['max_rpm']['timestamp']}")
        
        # Top endpoints
        if stats['endpoints']:
            print(f"\nTOP ENDPOINTS BY USAGE:")
            sorted_endpoints = sorted(
                stats['endpoints'].items(), 
                key=lambda x: x[1]['total_tokens'], 
                reverse=True
            )[:5]
            
            for endpoint, data in sorted_endpoints:
                print(f"  {endpoint}:")
                print(f"    - Calls: {data['count']}")
                print(f"    - Total: {data['total_tokens']:,} tokens")
                print(f"    - Avg: {data['avg_tokens']:,} tokens")
                print(f"    - Max: {data['max_tokens']:,} tokens")
        
        print("="*60)


# Global telemetry instance
_global_telemetry = None

def get_global_telemetry():
    """Get or create the global telemetry logger"""
    global _global_telemetry
    if _global_telemetry is None:
        _global_telemetry = TelemetryLogger()
    return _global_telemetry

def track_response(response, context=None):
    """Convenience function to track a response"""
    telemetry = get_global_telemetry()
    telemetry.track(response, context)

def print_telemetry_dashboard():
    """Print the telemetry dashboard"""
    telemetry = get_global_telemetry()
    telemetry.print_debug_display()

def export_telemetry_summary():
    """Export telemetry summary for migration analysis"""
    telemetry = get_global_telemetry()
    return telemetry.export_summary()