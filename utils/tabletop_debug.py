# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Tabletop Mode Debug Utilities
Plugin-safe debugging support for TABLETOP MODE features.
Provides centralized logging and state management for debug sessions.

TABLETOP MODE: This entire file is part of the tabletop mode plugin.
"""

import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional

# Import existing logger
from utils.enhanced_logger import debug, info, error

# Import config for verbose flag
try:
    from config import TABLETOP_DEBUG_VERBOSE
except ImportError:
    TABLETOP_DEBUG_VERBOSE = False

# Session tracking
_session_id: Optional[str] = None
_session_start: Optional[datetime] = None


def get_debug_session_id() -> str:
    """
    Get or create the current debug session ID.
    
    Returns:
        Session identifier in format: tt_debug_YYYYMMDD_HHMMSS
    """
    global _session_id, _session_start
    
    if _session_id is None:
        _session_start = datetime.now()
        _session_id = f"tt_debug_{_session_start.strftime('%Y%m%d_%H%M%S')}"
        info(f"TABLETOP MODE: Debug session started: {_session_id}", 
             category="tabletop_mode")
    
    return _session_id


def is_tabletop_debug_enabled() -> bool:
    """
    Check if tabletop debug mode is enabled.
    
    Returns:
        True if debug_config has tabletop_mode enabled
    """
    try:
        from debug_config import DEBUG_CATEGORIES
        return DEBUG_CATEGORIES.get("tabletop_mode", False)
    except ImportError:
        return False


def set_tabletop_verbose(enabled: bool) -> None:
    """
    Enable or disable verbose debug mode.
    
    Args:
        enabled: True for verbose, False for normal
    """
    global TABLETOP_DEBUG_VERBOSE
    
    try:
        # Update runtime flag
        TABLETOP_DEBUG_VERBOSE = enabled
        
        # Update config file
        import importlib
        import debug_config
        
        debug_config.DEBUG_CATEGORIES["tabletop_verbose"] = enabled
        
        info(f"TABLETOP MODE: Verbose mode {'enabled' if enabled else 'disabled'}",
             category="tabletop_mode")
             
    except Exception as e:
        error(f"TABLETOP MODE: Failed to set verbose mode: {e}",
              category="tabletop_mode")


def is_tabletop_verbose() -> bool:
    """
    Check if verbose mode is enabled.
    
    Returns:
        True if verbose mode active
    """
    try:
        from debug_config import DEBUG_CATEGORIES
        return DEBUG_CATEGORIES.get("tabletop_verbose", False)
    except ImportError:
        return TABLETOP_DEBUG_VERBOSE


def log_tabletop_event(event_type: str, details: Dict[str, Any], 
                       verbose: bool = False) -> None:
    """
    Log a tabletop mode event.
    
    Args:
        event_type: Type of event (e.g., "combat_command", "state_transition")
        details: Dictionary of event details
        verbose: If True, only log when verbose mode enabled
    """
    # Check if we should log based on verbose flag
    if verbose and not is_tabletop_verbose():
        return
    
    # Check if tabletop debug enabled
    if not is_tabletop_debug_enabled():
        return
    
    # Format event
    session_id = get_debug_session_id()
    details_str = ", ".join([f"{k}={v}" for k, v in details.items()])
    
    # Log based on severity
    if event_type.endswith("_error") or event_type.endswith("_exception"):
        error(f"TABLETOP MODE: [{session_id}] {event_type}: {details_str}",
              category="tabletop_mode")
    else:
        debug(f"TABLETOP MODE: [{session_id}] {event_type}: {details_str}",
              category="tabletop_mode")


def log_combat_command_flow(cmd: str, feedback: Optional[str], 
                           log_msg: Optional[str], result: str) -> None:
    """
    Log combat command processing flow.
    
    Args:
        cmd: The command entered
        feedback: User feedback message
        log_msg: System log message
        result: Result action (e.g., "continue_to_llm", "wait_for_damage")
    """
    log_tabletop_event("combat_command_flow", {
        "cmd": cmd[:50] if cmd else None,  # Truncate long commands
        "has_feedback": feedback is not None,
        "has_log_msg": log_msg is not None,
        "result": result
    }, verbose=True)


def log_state_transition(pc_name: str, from_state: str, to_state: str,
                        reason: Optional[str] = None) -> None:
    """
    Log a PC state transition.
    
    Args:
        pc_name: Character name
        from_state: Previous state
        to_state: New state
        reason: Optional reason for transition
    """
    details = {
        "pc": pc_name,
        "from": from_state,
        "to": to_state
    }
    if reason:
        details["reason"] = reason
    
    log_tabletop_event("state_transition", details, verbose=True)


def get_session_summary() -> Dict[str, Any]:
    """
    Get current session summary statistics.
    
    Returns:
        Dictionary with session info
    """
    global _session_id, _session_start
    
    if _session_id is None:
        return {
            "active": False,
            "session_id": None,
            "duration_minutes": 0
        }
    
    duration = datetime.now() - _session_start if _session_start else None
    duration_min = duration.total_seconds() / 60 if duration else 0
    
    return {
        "active": True,
        "session_id": _session_id,
        "started": _session_start.isoformat() if _session_start else None,
        "duration_minutes": round(duration_min, 2),
        "verbose": is_tabletop_verbose()
    }


def end_debug_session() -> None:
    """
    End the current debug session and reset state.
    """
    global _session_id, _session_start
    
    if _session_id:
        duration = datetime.now() - _session_start if _session_start else None
        duration_min = duration.total_seconds() / 60 if duration else 0
        
        info(f"TABLETOP MODE: Debug session ended: {_session_id} "
             f"(duration: {duration_min:.1f}min)",
             category="tabletop_mode")
        
        _session_id = None
        _session_start = None