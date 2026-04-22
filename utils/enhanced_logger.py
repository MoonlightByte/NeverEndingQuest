# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Enhanced logging system for NeverEndingQuest
Provides cleaner console output and detailed file logging
"""

import logging
import sys
import os
import re
from datetime import datetime
from logging.handlers import RotatingFileHandler
from debug_config import *

class CategoryFilter(logging.Filter):
    """Filter logs based on debug categories"""
    def filter(self, record):
        # Check if message should be logged
        return should_log_message(record.getMessage(), getattr(record, 'category', None))

class CleanConsoleFormatter(logging.Formatter):
    """Simplified formatter for console output"""
    
    # Color codes for different log levels
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        # Skip certain verbose messages
        msg = record.getMessage()
        
        # Ensure no Unicode characters in output
        msg = self._sanitize_unicode(msg)
        
        # Simplify module loading messages
        if "ModulePathManager loaded module" in msg:
            return None  # Skip these entirely
            
        # Format character update messages prominently
        if "[Character Update]" in msg:
            # Extract just the character update part for cleaner display
            if "] [Character Update]" in msg:
                # Remove script prefix for cleaner output
                parts = msg.split("] [Character Update]")
                if len(parts) >= 2:
                    return f"[Character Update]{parts[1]}"
            return msg  # Keep these messages visible
            
        # Simplify file operation messages
        if "Successfully updated" in msg and "attempt" in msg:
            # Extract just the important part
            parts = msg.split(" on attempt")
            return f"[OK] {parts[0]}"
            
        # Format time updates more concisely
        if "Current Time:" in msg and "Time Advanced:" in msg:
            parts = msg.split(", ")
            new_time = parts[2].split(": ")[1] if len(parts) > 2 else "Unknown"
            return f"[TIME] {new_time}"
            
        # Simplify validation messages
        if "Validation passed successfully" in msg:
            return "[OK] Response validated"
            
        # Format location transitions
        if "Transitioning from" in msg:
            parts = msg.split("'")
            if len(parts) >= 4:
                return f"[LOCATION] {parts[1]} -> {parts[3]}"
                
        # Format errors with color
        levelname = record.levelname
        if levelname in self.COLORS:
            color = self.COLORS[levelname]
            
            # Special formatting for errors
            if levelname == 'ERROR':
                # If there's an exception, include its type and message for clarity
                if record.exc_info:
                    exc_type, exc_value, exc_traceback = record.exc_info
                    return f"{color}[ERROR] {msg} ({exc_type.__name__}: {exc_value}){self.RESET}"
                return f"{color}[ERROR] {msg}{self.RESET}"
            elif levelname == 'WARNING':
                return f"{color}[WARNING] {msg}{self.RESET}"
            else:
                return msg
                
        return msg
    
    def _sanitize_unicode(self, text):
        """Replace Unicode characters with ASCII equivalents"""
        replacements = {
            '[PASS]': '[OK]', '[PASS]': '[OK]', '[PASS]': '[OK]',
            '[FAIL]': '[FAIL]', '[FAIL]': '[FAIL]', '[FAIL]': '[FAIL]',
            '->': '->', '<-': '<-', '^': '^', 'v': 'v',
            '->': '->', '=>': '=>',
            '*': '*', 'o': 'o', '*': '*', '*': '*',
            '[#]': '[#]', '[ ]': '[ ]', '-': '*', '*': '*',
            '-': '--', '-': '-', '...': '...',
            '<<': '<<', '>>': '>>',
            '"': '"', '"': '"', ''': "'", ''': "'"
        }
        
        for unicode_char, ascii_char in replacements.items():
            text = text.replace(unicode_char, ascii_char)
        
        # Remove any remaining non-ASCII characters
        text = re.sub(r'[^\x00-\x7F]+', '?', text)
        
        return text

class GameLogger:
    """Main logger class for the game"""
    
    def __init__(self):
        self.logger = logging.getLogger('NeverEndingQuest')
        self.logger.setLevel(logging.DEBUG)
        self.script_name = None  # Will be set by set_script_name()
        
        # Remove existing handlers
        self.logger.handlers = []
        
        # Console handler with clean formatting
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(CleanConsoleFormatter())
        console_handler.addFilter(CategoryFilter())
        self.logger.addHandler(console_handler)
        
        # Create sanitizing formatter for file handlers
        class SanitizingFormatter(logging.Formatter):
            def format(self, record):
                # Sanitize the message before formatting
                original_msg = str(record.msg)
                sanitized_msg = self._sanitize_unicode(original_msg)
                record.msg = sanitized_msg
                record.args = ()
                return super().format(record)
            
            def _sanitize_unicode(self, text):
                replacements = {
                    '[PASS]': '[OK]', '[PASS]': '[OK]', '[PASS]': '[OK]',
                    '[FAIL]': '[FAIL]', '[FAIL]': '[FAIL]', '[FAIL]': '[FAIL]',
                    '->': '->', '<-': '<-', '^': '^', 'v': 'v',
                    '->': '->', '=>': '=>',
                    '*': '*', 'o': 'o', '*': '*', '*': '*',
                    '[#]': '[#]', '[ ]': '[ ]', '-': '*', '*': '*',
                    '-': '--', '-': '-', '...': '...',
                    '<<': '<<', '>>': '>>',
                    '"': '"', '"': '"', ''': "'", ''': "'"
                }
                
                for unicode_char, ascii_char in replacements.items():
                    text = text.replace(unicode_char, ascii_char)
                
                # Remove any remaining non-ASCII characters
                text = re.sub(r'[^\x00-\x7F]+', '?', text)
                
                return text
        
        # Ensure log directory exists
        import os
        log_dir = os.path.dirname(ERROR_LOG_FILE)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        # Error file handler
        error_handler = RotatingFileHandler(
            ERROR_LOG_FILE,
            maxBytes=MAX_LOG_SIZE_MB * 1024 * 1024,
            backupCount=3
        )
        error_formatter = SanitizingFormatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        error_handler.setFormatter(error_formatter)
        error_handler.setLevel(logging.WARNING)
        self.logger.addHandler(error_handler)
        
        # Debug file handler (everything)
        debug_handler = RotatingFileHandler(
            DEBUG_LOG_FILE,
            maxBytes=MAX_LOG_SIZE_MB * 1024 * 1024,
            backupCount=3
        )
        debug_handler.setFormatter(error_formatter)
        debug_handler.setLevel(logging.DEBUG)
        self.logger.addHandler(debug_handler)
    
    def _format_message(self, message):
        """Add script name prefix if set"""
        if self.script_name:
            # Extract just the module name from full path
            script_name = self.script_name.split('.')[-1]
            # Capitalize first letter and add prefix
            script_prefix = script_name.replace('_', ' ').title().replace(' ', '')
            return f"[{script_prefix}] {message}"
        return message
    
    def debug(self, message, category=None):
        """Log debug message with optional category"""
        formatted_message = self._format_message(message)
        record = self.logger.makeRecord(
            self.logger.name, logging.DEBUG, "", 0, formatted_message, [], None
        )
        if category:
            record.category = category
        self.logger.handle(record)
    
    def info(self, message, category=None):
        """Log info message with optional category"""
        formatted_message = self._format_message(message)
        record = self.logger.makeRecord(
            self.logger.name, logging.INFO, "", 0, formatted_message, [], None
        )
        if category:
            record.category = category
        self.logger.handle(record)
    
    def warning(self, message, category=None):
        """Log warning message"""
        formatted_message = self._format_message(message)
        self.logger.warning(formatted_message)
    
    def error(self, message, exception=None, category=None):
        """Log error message with optional exception"""
        formatted_message = self._format_message(message)
        
        # Let the logging module handle the exception formatting safely.
        # It will automatically append the exception info and traceback to the log file.
        if exception:
            self.logger.error(formatted_message, exc_info=exception)
        else:
            self.logger.error(formatted_message)
    
    def game_event(self, event_type, details):
        """Log a game event in a structured way"""
        # Note: These already get script prefix from info() method
        if event_type == "location_transition":
            self.info(f"LOCATION: {details['from']} -> {details['to']}", category="location_transitions")
        elif event_type == "plot_update":
            self.info(f"PLOT: {details['plot_id']} - {details['status']}", category="plot_updates")
        elif event_type == "inventory_change":
            self.info(f"INVENTORY: {details['action']}: {details['item']}", category="inventory_changes")
        elif event_type == "character_update":
            self.info(f"CHARACTER: {details['character']}: {details['change']}", category="character_updates")
        elif event_type == "combat_start":
            self.info(f"COMBAT: {details.get('enemies', 'Unknown enemies')}", category="combat_events")
        elif event_type == "combat_end":
            self.info(f"COMBAT: Ended - {details.get('result', 'Unknown result')}", category="combat_events")
        elif event_type == "module_transition":
            self.info(f"MODULE: {details['from']} -> {details['to']}", category="module_loading")
        elif event_type == "save_game":
            self.info(f"SAVE: {details.get('description', 'Game saved')}", category="file_operations")
        elif event_type == "load_game":
            self.info(f"LOAD: {details.get('save_name', 'Game loaded')}", category="file_operations")
        else:
            self.info(f"{event_type.upper()}: {details}")

# Global logger instance
game_logger = GameLogger()

# Script name management
def set_script_name(name):
    """Set the script name for logging prefix"""
    game_logger.script_name = name

# Convenience functions
def debug(message, category=None):
    game_logger.debug(message, category)

def info(message, category=None):
    game_logger.info(message, category)

def warning(message, category=None):
    game_logger.warning(message, category)

def error(message, exception=None, category=None):
    game_logger.error(message, exception, category)

def game_event(event_type, details):
    game_logger.game_event(event_type, details)