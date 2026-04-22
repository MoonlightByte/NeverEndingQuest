#!/usr/bin/env python3
"""
Enhanced Debug Error Reporter for OpenCode Agent
Parses game logs and provides structured critical error reports.

Usage:
    python scripts/debug_error_reporter.py
    python scripts/debug_error_reporter.py --critical-only
    python scripts/debug_error_reporter.py --last-hour
    python scripts/debug_error_reporter.py --session
"""

import sys
import os
import re
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict, Tuple, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class ErrorEntry:
    """Represents a single error entry with parsed metadata."""
    
    def __init__(self, timestamp: str, level: str, source: str, message: str, 
                 exception_type: Optional[str] = None, file_location: Optional[str] = None):
        self.timestamp = timestamp
        self.level = level  # CRITICAL, ERROR, WARNING
        self.source = source  # Component that logged the error
        self.message = message
        self.exception_type = exception_type
        self.file_location = file_location
        self.count = 1  # For deduplication
    
    def __str__(self):
        lines = [f"[{self.timestamp}] {self.source}"]
        if self.file_location:
            lines.append(f"  Location: {self.file_location}")
        if self.exception_type:
            lines.append(f"  Exception: {self.exception_type}")
        lines.append(f"  {self.message}")
        return "\n".join(lines)
    
    def get_summary(self) -> str:
        """Get brief one-line summary for quick scanning."""
        exc_info = f" ({self.exception_type})" if self.exception_type else ""
        return f"[{self.timestamp}] {self.source}{exc_info}: {self.message[:80]}"


class DebugErrorReporter:
    """Analyzes game logs and reports critical errors."""
    
    CRITICAL_PATTERNS = [
        r"AttributeError",
        r"KeyError",
        r"IndexError",
        r"TypeError",
        r"ValueError",
        r"FAILURE",
        r"CRITICAL",
        r"Exception",
        r"Traceback",
    ]
    
    ERROR_PATTERNS = [
        r"ERROR",
        r"Failed",
        r"failure",
    ]
    
    WARNING_PATTERNS = [
        r"WARNING",
        r"WARN",
        r"Missing",
    ]
    
    def __init__(self, log_file: Path = None):
        self.log_file = log_file or project_root / "modules" / "logs" / "game_errors.log"
        self.debug_log = project_root / "modules" / "logs" / "game_debug.log"
        self.errors: List[ErrorEntry] = []
        self.warnings: List[ErrorEntry] = []
        self.critical: List[ErrorEntry] = []
        self.session_start: Optional[datetime] = None
    
    def parse_timestamp(self, line: str) -> Optional[str]:
        """Extract timestamp from log line."""
        # Match patterns like "2026-02-06 11:57:16" or "2026-02-06 11:57:16,123"
        match = re.match(r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})", line)
        if match:
            return match.group(1)
        return None
    
    def determine_level(self, line: str) -> str:
        """Determine error level from log line content."""
        line_upper = line.upper()
        
        # Check for critical patterns first
        for pattern in self.CRITICAL_PATTERNS:
            if pattern.upper() in line_upper or pattern in line:
                return "CRITICAL"
        
        # Check for error patterns
        for pattern in self.ERROR_PATTERNS:
            if pattern.upper() in line_upper:
                return "ERROR"
        
        # Check for warning patterns
        for pattern in self.WARNING_PATTERNS:
            if pattern.upper() in line_upper:
                return "WARNING"
        
        return "INFO"
    
    def extract_source(self, line: str) -> str:
        """Extract the source component from log line."""
        # Match patterns like "[WebInterface]", "[CombatManager]", "[Py]"
        match = re.search(r"\[([^\]]+)\]", line)
        if match:
            return match.group(1)
        
        # Match patterns like "- ERROR - [Source]"
        match = re.search(r"-\s*(?:ERROR|WARNING|CRITICAL)\s*-\s*\[?([^\]]+)\]?", line)
        if match:
            return match.group(1).strip()
        
        return "Unknown"
    
    def extract_exception(self, line: str) -> Optional[str]:
        """Extract exception type if present."""
        exception_patterns = [
            r"(AttributeError)",
            r"(KeyError)",
            r"(IndexError)",
            r"(TypeError)",
            r"(ValueError)",
            r"(FileNotFoundError)",
            r"(JSONDecodeError)",
        ]
        
        for pattern in exception_patterns:
            match = re.search(pattern, line)
            if match:
                return match.group(1)
        
        return None
    
    def extract_file_location(self, line: str) -> Optional[str]:
        """Extract file path and line number if present."""
        # Match patterns like "core/managers/multi_pc_combat.py:867"
        match = re.search(r"([\w/\\]+\.py):(\d+)", line)
        if match:
            return f"{match.group(1)}:{match.group(2)}"
        return None
    
    def parse_log_line(self, line: str) -> Optional[ErrorEntry]:
        """Parse a single log line into an ErrorEntry."""
        line = line.strip()
        if not line:
            return None
        
        timestamp = self.parse_timestamp(line)
        level = self.determine_level(line)
        source = self.extract_source(line)
        message = line
        
        # Clean up message - remove timestamp and level indicators
        message = re.sub(r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(,\d+)?\s*", "", message)
        message = re.sub(r"-\s*(ERROR|WARNING|CRITICAL|INFO|DEBUG)\s*-", "", message)
        message = message.strip()
        
        exception = self.extract_exception(line)
        file_loc = self.extract_file_location(line)
        
        return ErrorEntry(
            timestamp=timestamp or "Unknown",
            level=level,
            source=source,
            message=message,
            exception_type=exception,
            file_location=file_loc
        )
    
    def scan_logs(self, lines: int = 500, since: Optional[datetime] = None) -> None:
        """Scan both error and debug logs for issues."""
        self.errors = []
        self.warnings = []
        self.critical = []
        
        # Read error log
        if self.log_file.exists():
            self._parse_log_file(self.log_file, lines, since)
        
        # Also check debug log for errors
        if self.debug_log.exists():
            self._parse_log_file(self.debug_log, lines, since, is_debug=True)
        
        # Sort by timestamp
        self.critical.sort(key=lambda x: x.timestamp, reverse=True)
        self.errors.sort(key=lambda x: x.timestamp, reverse=True)
        self.warnings.sort(key=lambda x: x.timestamp, reverse=True)
    
    def _parse_log_file(self, log_path: Path, lines: int, since: Optional[datetime], is_debug: bool = False):
        """Parse a single log file."""
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
                recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
            
            for line in recent_lines:
                entry = self.parse_log_line(line)
                if not entry:
                    continue
                
                # Filter by time if specified
                if since:
                    try:
                        entry_time = datetime.strptime(entry.timestamp, "%Y-%m-%d %H:%M:%S")
                        if entry_time < since:
                            continue
                    except:
                        pass
                
                # Categorize
                if entry.level == "CRITICAL":
                    self.critical.append(entry)
                elif entry.level == "ERROR":
                    self.errors.append(entry)
                elif entry.level == "WARNING":
                    self.warnings.append(entry)
                    
        except Exception as e:
            print(f"Warning: Failed to parse {log_path}: {e}")
    
    def group_by_type(self) -> Dict[str, List[ErrorEntry]]:
        """Group errors by exception type or source."""
        groups = defaultdict(list)
        
        for entry in self.critical + self.errors:
            key = entry.exception_type or entry.source
            groups[key].append(entry)
        
        return dict(groups)
    
    def generate_critical_report(self) -> str:
        """Generate a focused report on critical errors."""
        lines = []
        lines.append("=" * 70)
        lines.append("CRITICAL ERROR REPORT")
        lines.append("=" * 70)
        lines.append("")
        
        total_issues = len(self.critical) + len(self.errors)
        
        if total_issues == 0:
            lines.append("[PASS] No critical errors or errors found in recent logs.")
            lines.append("")
            return "\n".join(lines)
        
        # Critical errors section
        if self.critical:
            lines.append(f"[CRITICAL] CRITICAL ERRORS ({len(self.critical)}):")
            lines.append("-" * 70)
            
            for i, entry in enumerate(self.critical[:10], 1):  # Show top 10
                lines.append(f"\n{i}. {entry}")
            
            if len(self.critical) > 10:
                lines.append(f"\n... and {len(self.critical) - 10} more critical errors")
            
            lines.append("")
        
        # Regular errors section
        if self.errors:
            lines.append(f"[FAIL] ERRORS ({len(self.errors)}):")
            lines.append("-" * 70)
            
            # Group by type for better overview
            groups = self.group_by_type()
            for error_type, entries in sorted(groups.items(), key=lambda x: -len(x[1])):
                if entries and entries[0].level == "ERROR":
                    lines.append(f"\n{error_type}: {len(entries)} occurrence(s)")
                    # Show latest example
                    lines.append(f"  Latest: {entries[0].get_summary()}")
            
            lines.append("")
        
        # Quick fixes suggestion
        lines.append("=" * 70)
        lines.append("SUGGESTED ACTIONS")
        lines.append("=" * 70)
        lines.append("")
        
        if any(e.exception_type == "AttributeError" for e in self.critical + self.errors):
            lines.append("- AttributeError detected - Likely a missing attribute or property")
            lines.append("  -> Check recent code changes for renamed/moved attributes")
            lines.append("")
        
        if any(e.exception_type == "KeyError" for e in self.critical + self.errors):
            lines.append("- KeyError detected - Missing dictionary key")
            lines.append("  -> Check data loading and JSON parsing")
            lines.append("")
        
        if any("combat" in e.source.lower() for e in self.critical + self.errors):
            lines.append("- Combat-related errors detected")
            lines.append("  -> Check party_tracker.json and encounter files")
            lines.append("")
        
        lines.append(f"Log files analyzed:")
        lines.append(f"  - {self.log_file}")
        lines.append(f"  - {self.debug_log}")
        
        return "\n".join(lines)
    
    def generate_summary(self) -> str:
        """Generate a brief summary for quick status checks."""
        lines = []
        lines.append("=" * 60)
        lines.append("DEBUG STATUS SUMMARY")
        lines.append("=" * 60)
        lines.append("")
        
        total_issues = len(self.critical) + len(self.errors)
        
        if total_issues == 0:
            lines.append("[PASS] System Status: HEALTHY")
            lines.append("   No critical errors or errors detected.")
        elif len(self.critical) > 0:
            lines.append(f"[CRITICAL] System Status: CRITICAL ISSUES DETECTED")
            lines.append(f"   Critical: {len(self.critical)} | Errors: {len(self.errors)} | Warnings: {len(self.warnings)}")
        else:
            lines.append(f"[WARNING]  System Status: ERRORS DETECTED")
            lines.append(f"   Errors: {len(self.errors)} | Warnings: {len(self.warnings)}")
        
        lines.append("")
        
        if self.critical:
            lines.append("Latest Critical:")
            for entry in self.critical[:3]:
                lines.append(f"  - {entry.get_summary()}")
            lines.append("")
        
        if self.errors and not self.critical:
            lines.append("Latest Errors:")
            for entry in self.errors[:3]:
                lines.append(f"  - {entry.get_summary()}")
            lines.append("")
        
        lines.append("Run with --detailed for full error report")
        
        return "\n".join(lines)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Debug Error Reporter")
    parser.add_argument("--lines", type=int, default=500, help="Lines to scan")
    parser.add_argument("--critical-only", action="store_true", help="Show only critical errors")
    parser.add_argument("--last-hour", action="store_true", help="Only show errors from last hour")
    parser.add_argument("--session", action="store_true", help="Show current session errors")
    parser.add_argument("--detailed", action="store_true", help="Show detailed report")
    
    args = parser.parse_args()
    
    reporter = DebugErrorReporter()
    
    since = None
    if args.last_hour:
        since = datetime.now() - timedelta(hours=1)
    elif args.session:
        # Assume session started in last 4 hours for "current session"
        since = datetime.now() - timedelta(hours=4)
    
    reporter.scan_logs(lines=args.lines, since=since)
    
    if args.detailed or args.critical_only:
        print(reporter.generate_critical_report())
    else:
        print(reporter.generate_summary())


if __name__ == "__main__":
    main()