# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Debug configuration for NeverEndingQuest
Controls what debug messages are shown and logged
"""

# Debug categories - set to True to enable, False to disable
DEBUG_CATEGORIES = {
    "errors": True,  # 
    "module_loading": False,  # 
    "file_operations": True,  # 
    "file_success": False,  # 
    "conversation_cleanup": False,  # 
    "summary_building": True,  # 
    "summary_details": False,  # 
    "location_transitions": True,  # 
    "plot_updates": True,  # 
    "validation": False,  # 
    "time_updates": False,  # 
    "character_updates": True,  # 
    "inventory_changes": True,  # 
    "combat_events": True,  # Combat initialization and results
    "hex_strings": False,  # 
    "schema_processing": False,  # 
    "attempt_counts": False,  # 
    "session_management": True,  # 
    "narrative_generation": True,  # 
    "npc_management": True,  # 
    "ai_validation": True,  # 
    "module_management": True,  # 
    "conversation_management": True,  # 
    "level_up": True,  # 
    "startup": True,  # 
    "xp_tracking": True,  # 
    "encounter_setup": True,  # 
    "encounter_management": True,  # 
    "character_validation": True,  # 
    "ai_processing": True,  # 
    "testing": True,  # 
    "save_game": True,  # 
    "module_transitions": True,  # 
    "storage_operations": True,  # 
    "combat_validation": True,  # Combat response validation
    "combat_logs": True,  # Combat logging and summaries
    "subprocess_output": True,  # 
    "combat_processing": True,  # Combat encounter creation
    "party_management": True,  # 
    "main_debug": False,  # 
    "action_handler_debug": False,  # 
    "character_updater_debug": False,  # 
    "combat_manager_debug": False,  # 
    "save_manager_debug": False,  # 
    "path_manager_debug": False,  # 
    "campaign_manager_debug": False,  # 
    "location_manager_debug": False,  # 
    "storage_manager_debug": False,  # 
    "tabletop_mode": True,  # TT-specific combat and UI debugging
    "tabletop_verbose": True,  # Full method call tracing
}

# Log file settings
ERROR_LOG_FILE = "modules/logs/game_errors.log"
DEBUG_LOG_FILE = "modules/logs/game_debug.log"
MAX_LOG_SIZE_MB = 10  # Rotate logs when they exceed this size

# Message filters - messages containing these strings will be filtered out
FILTER_PATTERNS = [
    "load_ssl_context",
    "httpx",
    "httpcore",
    "receive_response_body",
    "HTTP Request:",
    "Lightweight chat history updated",
    "System messages removed:",
    "User messages:",
    "Assistant messages:",
]

def should_log_message(message: str, category: str = None) -> bool:
    """Determine if a message should be logged based on configuration"""
    # Filter out patterns
    for pattern in FILTER_PATTERNS:
        if pattern in message:
            return False
    
    # Check category if provided
    if category:
        return DEBUG_CATEGORIES.get(category, True)
    
    # Default to logging if no category specified
    return True

def get_log_level_from_message(message: str) -> str:
    """Determine log level from message content"""
    message_lower = message.lower()
    
    if any(word in message_lower for word in ["error", "failed", "exception"]):
        return "ERROR"
    elif any(word in message_lower for word in ["warning", "warn"]):
        return "WARNING"
    elif "debug:" in message_lower:
        return "DEBUG"
    else:
        return "INFO"