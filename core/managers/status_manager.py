# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Core Engine - Status Manager
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

"""
Status Manager for NeverEndingQuest

This module provides a centralized way to manage and display status messages
throughout the application, giving users feedback about what the system is doing.
"""

import threading
# ============================================================================
# STATUS_MANAGER.PY - USER INTERFACE LAYER - REAL-TIME FEEDBACK
# ============================================================================
# 
# ARCHITECTURE ROLE: User Interface Layer - Status and Progress Management
# 
# This module implements real-time user feedback and status tracking using
# the Observer Pattern. It provides immediate visual feedback for all system
# operations, enhancing user experience during AI processing delays.
# 
# KEY RESPONSIBILITIES:
# - Real-time status updates with colored console output
# - Progress tracking for long-running operations
# - Error state visualization and user notifications
# - Callback-based status reporting from subsystems
# - Graceful handling of interrupted operations
# 
# STATUS CATEGORIES:
# - Processing: AI model interactions and data processing
# - Validation: Schema compliance and rule checking
# - File Operations: Reading, writing, and backup operations
# - Combat: Turn-based combat state and action resolution
# - Error States: Detailed error reporting with recovery suggestions
# 
# VISUAL FEEDBACK SYSTEM:
# - Color-coded status messages (Green/Yellow/Red)
# - Progress indicators for multi-step operations
# - Contextual error messages with actionable information
# - Clear completion confirmations
# 
# ARCHITECTURAL INTEGRATION:
# - Used throughout the system for operation feedback
# - Integrates with all major subsystems (DM, combat, file ops)
# - Provides consistent user experience across all interactions
# - Implements our user-centric design philosophy
# 
# DESIGN PATTERNS:
# - Observer Pattern: Status change notifications
# - Singleton Pattern: Centralized status management
# - Strategy Pattern: Different feedback for different operation types
# 
# This module ensures users always understand system state and progress,
# maintaining engagement during complex AI-driven operations.
# ============================================================================

import time
from typing import Optional, Callable

class StatusManager:
    """Manages status messages for the NeverEndingQuest system"""
    
    def __init__(self):
        self._status = "Ready for input"
        self._is_processing = False
        self._lock = threading.Lock()
        self._status_callback = None
        self._compression_callback = None  # For compression progress events
        
    def set_callback(self, callback: Callable[[str, bool], None]):
        """Set a callback function to be called when status changes
        
        Args:
            callback: Function that takes (status_message, is_processing) as arguments
        """
        self._status_callback = callback
        
    def update_status(self, message: str, is_processing: bool = True):
        """Update the current status message
        
        Args:
            message: The status message to display
            is_processing: Whether the system is currently processing (disables input)
        """
        if not is_processing:
            try:
                from utils.capture.live_provider_call import get_live_turn_scope

                scope = get_live_turn_scope()
                if scope is not None and scope.phase != "QUIESCENT":
                    return False
            except ImportError:
                pass
        with self._lock:
            self._status = message
            self._is_processing = is_processing
            if self._status_callback:
                self._status_callback(message, is_processing)
        return True
                
    def get_status(self) -> tuple[str, bool]:
        """Get the current status and processing state
        
        Returns:
            Tuple of (status_message, is_processing)
        """
        with self._lock:
            return self._status, self._is_processing
            
    def set_ready(self):
        """Set status to ready for input"""
        self.update_status("Enter your command:", False)
    
    def set_compression_callback(self, callback: Callable[[str, dict], None]):
        """Set a callback for compression progress events
        
        Args:
            callback: Function that takes (event_type, data) as arguments
        """
        self._compression_callback = callback
    
    def emit_compression_event(self, event_type: str, data: dict):
        """Emit a compression progress event
        
        Args:
            event_type: Type of event ('compression_start', 'compression_progress', 'compression_complete')
            data: Event data dictionary
        """
        if self._compression_callback:
            try:
                self._compression_callback(event_type, data)
            except:
                pass  # Silently ignore callback errors
        
    def is_processing(self) -> bool:
        """Check if the system is currently processing"""
        with self._lock:
            return self._is_processing

    # --- Background startup-welcome channel (issue #214, D-214-4=A) -------
    # A SEPARATE presentational status for the off-thread startup welcome,
    # mirroring the compression-progress channel. It shows honest motion
    # ("The DM is recalling your journey...") WITHOUT driving the global
    # input-locking is_processing flag a foreground turn uses.

    def set_welcome_callback(self, callback: Callable[[str], None]):
        self._welcome_callback = callback

    def emit_welcome_event(self, message: str):
        callback = getattr(self, "_welcome_callback", None)
        if callback:
            try:
                callback(message)
            except Exception:
                pass  # presentational only; never affects gameplay

# Global status manager instance
status_manager = StatusManager()

# --- Input-poll lifecycle pump hook (issue #214) ---------------------------
# The blocking input adapters (WebInput.readline / HeadlessInput.readline)
# poll their queue every 0.5s ON THE GAME THREAD. Registering a pump here
# lets the game thread service the off-thread welcome lifecycle (lease
# renewal, handback apply/discard, quiescence) between polls without fake
# player input. Absent hook = zero behavior change.
_input_poll_hook = None


def set_input_poll_hook(hook):
    global _input_poll_hook
    _input_poll_hook = hook


def run_input_poll_hook():
    hook = _input_poll_hook
    if hook is None:
        return
    try:
        hook()
    except Exception:
        # The pump must never break the input loop; failures surface through
        # the lifecycle's own terminal handling, not the adapter.
        pass

# Convenience functions for common status updates
def status_processing_ai():
    """Set status for AI processing"""
    status_manager.update_status("Processing AI response...", True)

def status_validating():
    """Set status for response validation"""
    status_manager.update_status("Validating response format...", True)

def status_retrying(attempt: int, max_attempts: int = None):
    """Set status for retry attempts"""
    if max_attempts is None:
        message = f"Retrying response (attempt {attempt})..."
    else:
        message = f"Retrying response (attempt {attempt}/{max_attempts})..."
    status_manager.update_status(message, True)

def status_transitioning_location():
    """Set status for location transition"""
    status_manager.update_status("Transitioning location...", True)

def status_loading_location():
    """Set status for loading location data"""
    status_manager.update_status("Loading location data...", True)

def status_generating_summary():
    """Set status for generating adventure summary"""
    status_manager.update_status("Generating adventure summary...", True)

def status_updating_journal():
    """Set status for updating journal"""
    status_manager.update_status("Updating journal entry...", True)

def status_compressing_history():
    """Set status for compressing conversation history"""
    status_manager.update_status("Compressing conversation history...", True)

def status_initializing_combat():
    """Set status for combat initialization"""
    status_manager.update_status("Initializing encounter...", True)

def status_processing_combat():
    """Set status for combat processing"""
    status_manager.update_status("Processing combat round...", True)

def status_updating_character():
    """Set status for character updates"""
    status_manager.update_status("Updating character info...", True)

def status_processing_levelup():
    """Set status for level up processing"""
    status_manager.update_status("Processing level up...", True)

def status_updating_party():
    """Set status for party tracker updates"""
    status_manager.update_status("Updating party tracker...", True)

def status_updating_plot():
    """Set status for plot updates"""
    status_manager.update_status("Updating plot progression...", True)

def status_advancing_time():
    """Set status for time advancement"""
    status_manager.update_status("Advancing world time...", True)

def status_saving():
    """Set status for saving data"""
    status_manager.update_status("Saving game state...", True)

def status_loading():
    """Set status for loading data"""
    status_manager.update_status("Loading module data...", True)

def status_ready():
    """Set status to ready"""
    status_manager.set_ready()

def status_busy():
    """Set generic busy status"""
    status_manager.update_status("System busy...", True)

# Global function to set the status callback
def set_status_callback(callback: Callable[[str, bool], None]):
    """Set the global status callback function
    
    Args:
        callback: Function that takes (status_message, is_processing) as arguments
    """
    status_manager.set_callback(callback)

def set_compression_callback(callback: Callable[[str, dict], None]):
    """Set the global compression callback function
    
    Args:
        callback: Function that takes (event_type, data) as arguments
    """
    status_manager.set_compression_callback(callback)
