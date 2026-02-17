# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Web Extension - Missing Media Auto-Generation Worker
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Provides async queue-based worker for automatic portrait generation on media misses.
Supports key dedupe, cooldown, and allied-only policy enforcement.

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional, Set, Any, List
from datetime import datetime

from utils.enhanced_logger import info, warning, error, debug


@dataclass
class MissingMediaTask:
    """Task for generating missing media portrait."""
    missing_key: str          # Unique key for dedupe (e.g., "npcs/grimjaw_thumb.jpg")
    media_type: str         # Type: 'monsters', 'npcs', 'environment'
    filename: str           # Original filename
    character_data: Optional[Dict[str, Any]] = None  # Optional character context
    metadata: Dict[str, Any] = field(default_factory=dict)
    enqueued_at: float = field(default_factory=time.time)


# Worker state (module-level, thread-safe)
_task_queue: queue.Queue = queue.Queue()
_worker_thread: Optional[threading.Thread] = None
_stop_event: threading.Event = threading.Event()
_state_lock: threading.Lock = threading.Lock()

# Dedupe tracking
_queued_keys: Set[str] = set()      # Keys currently in queue
_active_keys: Set[str] = set()      # Keys currently being processed

# Cooldown tracking
_last_enqueue_timestamps: Dict[str, float] = {}

# Default settings (can be overridden via start call)
_COOLDOWN_SECONDS: float = 60.0     # 1 minute cooldown between enqueues for same key

# Stats
_worker_stats: Dict[str, Any] = {
    "tasks_enqueued": 0,
    "tasks_completed": 0,
    "tasks_failed": 0,
    "suppressed_dedupe": 0,
    "suppressed_cooldown": 0,
    "start_time": None,
    "last_task_time": None,
}


def _generate_portrait_callback(task: MissingMediaTask) -> bool:
    """
    Default generation callback using portrait service.
    
    Can be overridden via start call for custom behavior/policy hooks.
    
    Args:
        task: The missing media task to process
        
    Returns:
        True if generation succeeded, False otherwise
    """
    try:
        from core.toolkit.portrait_service import generate_and_save_portrait
        
        info(
            f"MISSING_MEDIA_AUTOGEN: Generating portrait for {task.missing_key}",
            category="missing_media_autogen"
        )
        
        # Build minimal character data if not provided
        character_data = task.character_data or {
            "name": task.filename.replace("_thumb", "").replace(".jpg", "").replace(".png", ""),
            "race": "Unknown",
            "class": "NPC"
        }
        
        result = generate_and_save_portrait(
            character_data=character_data,
            model="dall-e-3",
            size="1024x1024",
            quality="standard"
        )
        
        if result.get("success"):
            info(
                f"MISSING_MEDIA_AUTOGEN: Successfully generated {task.missing_key}",
                category="missing_media_autogen"
            )
            return True
        else:
            warning(
                f"MISSING_MEDIA_AUTOGEN: Failed to generate {task.missing_key}: {result.get('error')}",
                category="missing_media_autogen"
            )
            return False
            
    except Exception as e:
        error(
            f"MISSING_MEDIA_AUTOGEN: Error generating {task.missing_key}",
            exception=e,
            category="missing_media_autogen"
        )
        return False


def _worker_loop(
    generation_callback: Callable[[MissingMediaTask], bool],
    policy_check: Optional[Callable[[MissingMediaTask], bool]] = None
) -> None:
    """
    Main worker thread loop.
    
    Consumes tasks from queue and executes generation callbacks.
    Fail-open: logs errors but does not crash.
    
    Args:
        generation_callback: Function to call for generation
        policy_check: Optional policy function (returns True if generation allowed)
    """
    global _worker_stats
    
    info(
        "MISSING_MEDIA_AUTOGEN: Worker loop started",
        category="missing_media_autogen"
    )
    
    while not _stop_event.is_set():
        try:
            # Block with timeout for responsive shutdown
            task: MissingMediaTask = _task_queue.get(timeout=1.0)
        except queue.Empty:
            continue
        
        # Mark as active and clear from queued (dedupe lifecycle)
        with _state_lock:
            _queued_keys.discard(task.missing_key)
            _active_keys.add(task.missing_key)
        
        try:
            # Policy check if provided
            if policy_check and not policy_check(task):
                debug(
                    f"MISSING_MEDIA_AUTOGEN: Policy blocked {task.missing_key}",
                    category="missing_media_autogen"
                )
                continue
            
            # Execute generation
            success = generation_callback(task)
            
            with _state_lock:
                if success:
                    _worker_stats["tasks_completed"] += 1
                else:
                    _worker_stats["tasks_failed"] += 1
                _worker_stats["last_task_time"] = datetime.now().isoformat()
                
        except Exception as e:
            error(
                f"MISSING_MEDIA_AUTOGEN: Unexpected error processing {task.missing_key}",
                exception=e,
                category="missing_media_autogen"
            )
            with _state_lock:
                _worker_stats["tasks_failed"] += 1
        finally:
            # Always clear from active
            with _state_lock:
                _active_keys.discard(task.missing_key)
            _task_queue.task_done()
    
    info(
        "MISSING_MEDIA_AUTOGEN: Worker loop stopped",
        category="missing_media_autogen"
    )


def start_missing_media_autogen_worker(
    generation_callback: Optional[Callable[[MissingMediaTask], bool]] = None,
    policy_check: Optional[Callable[[MissingMediaTask], bool]] = None,
    cooldown_seconds: float = _COOLDOWN_SECONDS
) -> bool:
    """
    Start the missing media auto-generation worker thread.
    
    Idempotent: safe to call multiple times; only starts once.
    
    Args:
        generation_callback: Custom generation function (default: portrait service)
        policy_check: Optional policy gate function (returns True to allow generation)
        cooldown_seconds: Cooldown window between enqueues for same key
        
    Returns:
        True if worker is running (started or already running), False on error
    """
    global _worker_thread, _stop_event, _COOLDOWN_SECONDS, _worker_stats
    
    with _state_lock:
        if _worker_thread is not None and _worker_thread.is_alive():
            debug(
                "MISSING_MEDIA_AUTOGEN: Worker already running",
                category="missing_media_autogen"
            )
            return True
        
        # Update settings
        _COOLDOWN_SECONDS = cooldown_seconds
        
        # Reset state
        _stop_event.clear()
        _worker_stats["start_time"] = datetime.now().isoformat()
        
        # Create and start worker thread
        callback = generation_callback or _generate_portrait_callback
        _worker_thread = threading.Thread(
            target=_worker_loop,
            args=(callback, policy_check),
            name="MissingMediaAutogenWorker",
            daemon=True
        )
        _worker_thread.start()
        
        info(
            f"MISSING_MEDIA_AUTOGEN: Worker started with cooldown={cooldown_seconds}s",
            category="missing_media_autogen"
        )
        return True


def stop_missing_media_autogen_worker(timeout: float = 5.0) -> bool:
    """
    Stop the missing media auto-generation worker gracefully.
    
    Args:
        timeout: Seconds to wait for worker thread to finish current task
        
    Returns:
        True if stopped successfully, False if timeout or not running
    """
    global _worker_thread, _stop_event
    
    with _state_lock:
        if _worker_thread is None or not _worker_thread.is_alive():
            return True
        
        _stop_event.set()
        worker_ref = _worker_thread
    
    # Wait for worker to finish (outside lock)
    worker_ref.join(timeout=timeout)
    
    with _state_lock:
        still_alive = _worker_thread.is_alive() if _worker_thread else False
        if not still_alive:
            _worker_thread = None
            info(
                "MISSING_MEDIA_AUTOGEN: Worker stopped",
                category="missing_media_autogen"
            )
            return True
        else:
            warning(
                f"MISSING_MEDIA_AUTOGEN: Worker did not stop within {timeout}s timeout",
                category="missing_media_autogen"
            )
            return False


def enqueue_missing_media_autogen_task(
    media_type: str,
    filename: str,
    character_data: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Enqueue a missing media generation task.
    
    Applies dedupe and cooldown logic before queueing.
    Thread-safe and non-blocking (returns immediately).
    
    Args:
        media_type: Type of media ('monsters', 'npcs', 'environment')
        filename: Name of the missing file
        character_data: Optional character context for generation prompt
        metadata: Optional additional context
        
    Returns:
        Dict with result status:
        - status: 'queued', 'suppressed_dedupe', 'suppressed_cooldown', 'disabled', 'error'
        - missing_key: The dedupe key
        - message: Human-readable status
        - queue_position: Approximate position if queued (None otherwise)
    """
    global _worker_stats
    
    # Normalize key
    missing_key = f"{media_type}/{filename}".lower().replace(" ", "_").replace("-", "_")
    
    with _state_lock:
        # Check if worker running
        if _worker_thread is None or not _worker_thread.is_alive():
            return {
                "status": "disabled",
                "missing_key": missing_key,
                "message": "Worker not running",
                "queue_position": None
            }
        
        # Check dedupe: already queued or active
        if missing_key in _queued_keys or missing_key in _active_keys:
            _worker_stats["suppressed_dedupe"] += 1
            return {
                "status": "suppressed_dedupe",
                "missing_key": missing_key,
                "message": f"Task already in queue or active for {missing_key}",
                "queue_position": None
            }
        
        # Check cooldown
        last_enqueue = _last_enqueue_timestamps.get(missing_key)
        if last_enqueue is not None:
            elapsed = time.time() - last_enqueue
            if elapsed < _COOLDOWN_SECONDS:
                _worker_stats["suppressed_cooldown"] += 1
                remaining = _COOLDOWN_SECONDS - elapsed
                return {
                    "status": "suppressed_cooldown",
                    "missing_key": missing_key,
                    "message": f"Cooldown active for {missing_key} ({remaining:.0f}s remaining)",
                    "queue_position": None
                }
        
        # Create and enqueue task
        task = MissingMediaTask(
            missing_key=missing_key,
            media_type=media_type,
            filename=filename,
            character_data=character_data,
            metadata=metadata or {}
        )
        
        try:
            _task_queue.put_nowait(task)
            _queued_keys.add(missing_key)
            _last_enqueue_timestamps[missing_key] = time.time()
            _worker_stats["tasks_enqueued"] += 1
            
            queue_size = _task_queue.qsize()
            
            debug(
                f"MISSING_MEDIA_AUTOGEN: Enqueued {missing_key} (queue size: {queue_size})",
                category="missing_media_autogen"
            )
            
            return {
                "status": "queued",
                "missing_key": missing_key,
                "message": f"Task queued for {missing_key}",
                "queue_position": queue_size
            }
            
        except queue.Full:
            return {
                "status": "error",
                "missing_key": missing_key,
                "message": f"Queue full, could not enqueue {missing_key}",
                "queue_position": None
            }


def is_allied_companion_check(
    task: MissingMediaTask,
    party_tracker_data: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Policy check: Determine if missing media is for an allied companion.
    
    MVP policy: Only allied NPC companions get auto-generated.
    Non-allied NPCs and monsters are skipped.
    
    Args:
        task: The media task to check
        party_tracker_data: Optional pre-loaded party tracker (for efficiency)
        
    Returns:
        True if task represents allied companion (allowed), False otherwise
    """
    try:
        # Only process npcs type
        if task.media_type != "npcs":
            return False
        
        # Load party tracker if not provided
        if party_tracker_data is None:
            from utils.file_operations import safe_read_json
            party_tracker_data = safe_read_json("party_tracker.json")
        
        if not party_tracker_data:
            return False
        
        # Get list of allied companion names from partyNPCs
        allied_names: Set[str] = set()
        for npc_info in party_tracker_data.get("partyNPCs", []):
            npc_name = npc_info.get("name", "")
            if npc_name:
                allied_names.add(npc_name.lower())
        
        # Also include active character
        active_character = party_tracker_data.get("active_character")
        if active_character:
            allied_names.add(active_character.lower())
        
        # Normalize task filename to extract character name
        # e.g., "grimjaw_thumb.jpg" -> "grimjaw"
        char_name = task.filename.replace("_thumb", "").replace(".jpg", "").replace(".png", "").lower()
        
        # Check if character is in allied set
        is_allied = char_name in allied_names
        
        if is_allied:
            debug(
                f"MISSING_MEDIA_AUTOGEN: {char_name} is allied companion - allowing generation",
                category="missing_media_autogen"
            )
        else:
            debug(
                f"MISSING_MEDIA_AUTOGEN: {char_name} is not allied companion - skipping",
                category="missing_media_autogen"
            )
        
        return is_allied
        
    except Exception as e:
        debug(
            f"MISSING_MEDIA_AUTOGEN: Error checking allied status for {task.missing_key}: {e}",
            category="missing_media_autogen"
        )
        return False


def get_missing_media_autogen_stats() -> Dict[str, Any]:
    """
    Get current worker statistics and state.
    
    Returns:
        Dict with worker stats including:
        - tasks_enqueued, tasks_completed, tasks_failed
        - suppressed_dedupe, suppressed_cooldown
        - active_keys, queued_keys counts
        - start_time, last_task_time
        - is_running
    """
    with _state_lock:
        stats = _worker_stats.copy()
        stats["active_keys_count"] = len(_active_keys)
        stats["queued_keys_count"] = len(_queued_keys)
        stats["queue_size"] = _task_queue.qsize()
        stats["is_running"] = _worker_thread is not None and _worker_thread.is_alive()
        stats["cooldown_seconds"] = _COOLDOWN_SECONDS
        return stats


def clear_missing_media_autogen_state() -> None:
    """
    Clear all worker state (for testing/reset purposes).
    
    Warning: Only use in controlled scenarios; clears dedupe/cooldown history.
    """
    global _queued_keys, _active_keys, _last_enqueue_timestamps, _worker_stats
    
    with _state_lock:
        _queued_keys.clear()
        _active_keys.clear()
        _last_enqueue_timestamps.clear()
        _worker_stats = {
            "tasks_enqueued": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "suppressed_dedupe": 0,
            "suppressed_cooldown": 0,
            "start_time": None,
            "last_task_time": None,
        }
        info(
            "MISSING_MEDIA_AUTOGEN: State cleared",
            category="missing_media_autogen"
        )


# Module-level exports
__all__ = [
    "MissingMediaTask",
    "start_missing_media_autogen_worker",
    "stop_missing_media_autogen_worker",
    "enqueue_missing_media_autogen_task",
    "is_allied_companion_check",
    "get_missing_media_autogen_stats",
    "clear_missing_media_autogen_state",
]
