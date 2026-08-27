#!/usr/bin/env python3
"""
Centralized API Call Logger
Logs all OpenAI API calls (request + response) to a master JSONL log

Usage:
    from utils.api_logger import log_api_call

    response = client.chat.completions.create(...)
    log_api_call("main_dm", messages, response)
"""

import json
import os
import threading
from datetime import datetime
from pathlib import Path

# Master log file - JSONL format (one JSON object per line)
MASTER_LOG_FILE = "debug/api_captures/api_calls_master.jsonl"

# Process-level per-file lock registry for JSONL appends (issue #214). One
# Python write() on independently opened buffered streams is not a portable
# native-Windows atomicity guarantee; concurrent welcome/player threads could
# interleave a large record. Telemetry stays observational: a logging failure
# is swallowed and counted, never surfaced to gameplay.
_APPEND_LOCKS_GUARD = threading.Lock()
_APPEND_LOCKS = {}
_APPEND_FAILURES = {"count": 0}


def _lock_for_path(path):
    key = os.path.abspath(path)
    with _APPEND_LOCKS_GUARD:
        lock = _APPEND_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _APPEND_LOCKS[key] = lock
        return lock


def append_jsonl_record(path, record):
    """Append one JSON record to ``path`` as a single locked line.

    The complete line is serialized BEFORE the lock is acquired; the
    open-append/write/close happens entirely under the per-file lock, so
    concurrent in-process writers can never interleave partial records.
    Returns True on success; failures are swallowed and counted (diagnostics
    must never affect gameplay).
    """
    try:
        line = json.dumps(record, ensure_ascii=False) + "\n"
    except (TypeError, ValueError):
        _APPEND_FAILURES["count"] += 1
        return False
    lock = _lock_for_path(path)
    try:
        with lock:
            with open(path, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
        return True
    except Exception:
        _APPEND_FAILURES["count"] += 1
        return False

def log_api_call(endpoint_name, messages, response, metadata=None):
    """
    Log an API call with request and response.

    Args:
        endpoint_name: Identifier (e.g., "main_dm", "combat", "validation", "initiative")
        messages: The messages array sent to the API
        response: The OpenAI response object
        metadata: Optional dict with additional context
    """

    # Ensure debug/api_captures directory exists
    Path("debug/api_captures").mkdir(parents=True, exist_ok=True)

    # Extract response data
    try:
        response_content = response.choices[0].message.content
        model_used = response.model
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens
    except Exception as e:
        # If response parsing fails, log what we can
        response_content = str(response)
        model_used = "unknown"
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0

    # Build log entry
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "endpoint": endpoint_name,
        "model": model_used,
        "tokens": {
            "prompt": prompt_tokens,
            "completion": completion_tokens,
            "total": total_tokens
        },
        "request": {
            "messages": messages,
            "message_count": len(messages)
        },
        "response": {
            "content": response_content
        }
    }

    # Add metadata if provided
    if metadata:
        log_entry["metadata"] = metadata

    # Append to master log (JSONL format - one locked single-line write)
    if append_jsonl_record(MASTER_LOG_FILE, log_entry):
        print(f"[API_LOG] Logged {endpoint_name} call: {total_tokens} tokens to {MASTER_LOG_FILE}")
    else:
        print("[API_LOG] ERROR: Failed to log API call (append_jsonl_record)")

def get_recent_api_calls(endpoint=None, limit=10):
    """
    Retrieve recent API calls from the master log.

    Args:
        endpoint: Filter by endpoint name (None = all)
        limit: Max number of calls to return

    Returns:
        List of log entries (newest first)
    """

    if not os.path.exists(MASTER_LOG_FILE):
        return []

    calls = []

    try:
        with open(MASTER_LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    if endpoint is None or entry.get("endpoint") == endpoint:
                        calls.append(entry)

        # Return newest first
        calls.reverse()
        return calls[:limit]

    except Exception as e:
        print(f"[API_LOG] ERROR: Failed to read API log: {e}")
        return []

def analyze_api_usage(since_date=None):
    """
    Analyze API usage from the master log.

    Args:
        since_date: ISO date string (e.g., "2025-10-01") or None for all time

    Returns:
        Dict with usage statistics
    """

    if not os.path.exists(MASTER_LOG_FILE):
        return {"error": "No log file found"}

    stats = {
        "total_calls": 0,
        "total_tokens": 0,
        "by_endpoint": {},
        "by_model": {}
    }

    try:
        with open(MASTER_LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue

                entry = json.loads(line)

                # Filter by date if specified
                if since_date:
                    entry_date = entry.get("timestamp", "")[:10]
                    if entry_date < since_date:
                        continue

                stats["total_calls"] += 1
                tokens = entry.get("tokens", {}).get("total", 0)
                stats["total_tokens"] += tokens

                # Track by endpoint
                endpoint = entry.get("endpoint", "unknown")
                if endpoint not in stats["by_endpoint"]:
                    stats["by_endpoint"][endpoint] = {"calls": 0, "tokens": 0}
                stats["by_endpoint"][endpoint]["calls"] += 1
                stats["by_endpoint"][endpoint]["tokens"] += tokens

                # Track by model
                model = entry.get("model", "unknown")
                if model not in stats["by_model"]:
                    stats["by_model"][model] = {"calls": 0, "tokens": 0}
                stats["by_model"][model]["calls"] += 1
                stats["by_model"][model]["tokens"] += tokens

        return stats

    except Exception as e:
        return {"error": str(e)}

# Example usage and test
if __name__ == "__main__":
    print("API Logger Utility")
    print("=" * 80)
    print()

    # Check if log exists
    if os.path.exists(MASTER_LOG_FILE):
        # Analyze usage
        stats = analyze_api_usage()
        print(f"Total API calls logged: {stats.get('total_calls', 0)}")
        print(f"Total tokens: {stats.get('total_tokens', 0):,}")
        print()

        print("By Endpoint:")
        for endpoint, data in stats.get('by_endpoint', {}).items():
            print(f"  {endpoint}: {data['calls']} calls, {data['tokens']:,} tokens")
        print()

        # Show recent calls
        recent = get_recent_api_calls(limit=5)
        print(f"Recent {len(recent)} calls:")
        for call in recent:
            print(f"  - {call['timestamp'][:19]} | {call['endpoint']} | {call['tokens']['total']} tokens")

    else:
        print(f"No log file found at: {MASTER_LOG_FILE}")
        print("Log will be created when first API call is made")
