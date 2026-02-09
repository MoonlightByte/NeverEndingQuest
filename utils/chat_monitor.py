# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Chat Monitor Utility
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Real-time chat log reader and formatter for NeverEndingQuest tabletop mode.
Provides convenient access to live chat monitoring logs for AI assistants,
developers, and live audience feeds.

This utility is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.

Examples:
    python utils/chat_monitor.py --latest 20
    python utils/chat_monitor.py --follow
    python utils/chat_monitor.py --character acheron --type user_input
    python utils/chat_monitor.py --export chat_export.json
"""

import json
import os
import sys
import argparse
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
import time

# Default log file location (matches TABLETOP MODE configuration)
DEFAULT_LOG_FILE = "debug/logs/live_chat_monitor.json"

def read_chat_log(log_file: str = DEFAULT_LOG_FILE) -> List[Dict[str, Any]]:
    """Read the chat log file and return entries."""
    try:
        if not os.path.exists(log_file):
            print(f"[ERROR] Chat log not found: {log_file}")
            return []
        
        with open(log_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"[ERROR] Invalid JSON in chat log: {log_file}")
        return []
    except Exception as e:
        print(f"[ERROR] Failed to read chat log: {e}")
        return []

def format_timestamp(timestamp_str: str) -> str:
    """Format ISO timestamp to readable format."""
    try:
        dt = datetime.fromisoformat(timestamp_str)
        return dt.strftime("%H:%M:%S")
    except:
        return timestamp_str[:8]  # Fallback to first 8 chars

def format_entry(entry: Dict[str, Any], compact: bool = False) -> str:
    """Format a single chat entry for display."""
    event_type = entry.get('event_type', 'unknown')
    character = entry.get('character')
    content = entry.get('content', '')
    timestamp = format_timestamp(entry.get('timestamp', ''))
    
    if compact:
        # Compact format for dense output
        char_tag = f"[{character}] " if character else ""
        return f"[{timestamp}] {event_type.upper():12} {char_tag}{content[:100]}"
    else:
        # Pretty format for readability
        lines = []
        lines.append(f"{'='*60}")
        lines.append(f"Time: {timestamp}")
        lines.append(f"Type: {event_type.upper()}")
        if character:
            lines.append(f"Character: {character}")
        lines.append(f"Content: {content}")
        return "\n".join(lines)

def filter_entries(
    entries: List[Dict[str, Any]],
    character: Optional[str] = None,
    event_type: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Filter chat entries based on criteria."""
    filtered = entries
    
    if character:
        filtered = [e for e in filtered if e.get('character') == character]
    
    if event_type:
        filtered = [e for e in filtered if e.get('event_type') == event_type]
    
    if since:
        filtered = [e for e in filtered if e.get('timestamp', '') >= since]
    
    if until:
        filtered = [e for e in filtered if e.get('timestamp', '') <= until]
    
    return filtered

def display_entries(entries: List[Dict[str, Any]], compact: bool = False, reverse: bool = False):
    """Display chat entries."""
    if not entries:
        print("[INFO] No chat entries found.")
        return
    
    if reverse:
        entries = list(reversed(entries))
    
    for entry in entries:
        print(format_entry(entry, compact))
        if not compact:
            print()  # Blank line between entries in pretty mode

def follow_log(log_file: str = DEFAULT_LOG_FILE, compact: bool = True, notify_ocnotes: bool = False):
    """Follow the log file in real-time (like tail -f)."""
    print(f"[INFO] Following chat log: {log_file}")
    print(f"[INFO] Press Ctrl+C to stop\n")
    
    last_size = 0
    last_entries = []
    
    try:
        while True:
            if os.path.exists(log_file):
                current_size = os.path.getsize(log_file)
                
                if current_size != last_size:
                    entries = read_chat_log(log_file)
                    
                    # Find new entries
                    new_entries = []
                    for entry in entries:
                        if entry not in last_entries:
                            new_entries.append(entry)
                    
                    if new_entries:
                        display_entries(new_entries, compact=compact)
                        
                        # TABLETOP MODE: Special notification for OCNotes
                        if notify_ocnotes:
                            for entry in new_entries:
                                content = entry.get('content', '')
                                if '[OCNote:' in content or '[ocnote:' in content:
                                    char = entry.get('character', 'Unknown')
                                    print(f"\n{'='*60}")
                                    print(f"[OCNOTE DETECTED] From {char}")
                                    print(f"{'='*60}")
                    
                    last_entries = entries
                    last_size = current_size
            
            time.sleep(0.5)  # Check every 500ms
            
    except KeyboardInterrupt:
        print("\n[INFO] Stopped following chat log.")

def export_entries(entries: List[Dict[str, Any]], output_file: str):
    """Export filtered entries to a JSON file."""
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(entries, f, indent=2)
        print(f"[SUCCESS] Exported {len(entries)} entries to {output_file}")
    except Exception as e:
        print(f"[ERROR] Failed to export: {e}")

def get_stats(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate statistics about the chat log."""
    if not entries:
        return {}
    
    stats = {
        'total_entries': len(entries),
        'user_inputs': len([e for e in entries if e.get('event_type') == 'user_input']),
        'ai_responses': len([e for e in entries if e.get('event_type') == 'ai_response']),
        'system_messages': len([e for e in entries if e.get('event_type') == 'system']),
        'unique_characters': list(set([e.get('character') for e in entries if e.get('character')])),
        'time_range': {
            'first': entries[0].get('timestamp') if entries else None,
            'last': entries[-1].get('timestamp') if entries else None
        }
    }
    
    return stats

def display_stats(stats: Dict[str, Any]):
    """Display chat statistics."""
    if not stats:
        print("[INFO] No statistics available (empty log).")
        return
    
    print("\n" + "="*60)
    print("CHAT LOG STATISTICS")
    print("="*60)
    print(f"Total Entries:      {stats['total_entries']}")
    print(f"User Inputs:          {stats['user_inputs']}")
    print(f"AI Responses:         {stats['ai_responses']}")
    print(f"System Messages:      {stats['system_messages']}")
    print(f"Unique Characters:    {', '.join(stats['unique_characters']) or 'None'}")
    print(f"Time Range:           {stats['time_range']['first'][:19] if stats['time_range']['first'] else 'N/A'}")
    print(f"                      to {stats['time_range']['last'][:19] if stats['time_range']['last'] else 'N/A'}")
    print("="*60 + "\n")

def main():
    """Main entry point for the chat monitor utility."""
    parser = argparse.ArgumentParser(
        description='NeverEndingQuest Chat Monitor - View and filter live chat logs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --latest 20                    # Show last 20 messages
  %(prog)s --follow                       # Real-time monitoring
  %(prog)s --follow --ocnotes             # Real-time with OCNote alerts
  %(prog)s --character acheron            # Filter by character
  %(prog)s --type user_input              # Show only player inputs
  %(prog)s --export chat_backup.json      # Export to file
  %(prog)s --stats                        # Show statistics
        """
    )
    
    parser.add_argument('--file', '-f', default=DEFAULT_LOG_FILE,
                        help=f'Chat log file path (default: {DEFAULT_LOG_FILE})')
    parser.add_argument('--latest', '-n', type=int, metavar='N',
                        help='Show only the last N entries')
    parser.add_argument('--follow', action='store_true',
                        help='Follow log in real-time (like tail -f)')
    parser.add_argument('--character', '-c',
                        help='Filter by character name (e.g., acheron, Xerxes)')
    parser.add_argument('--type', '-t', choices=['user_input', 'ai_response', 'system'],
                        help='Filter by event type')
    parser.add_argument('--since',
                        help='Show entries since timestamp (ISO format)')
    parser.add_argument('--until',
                        help='Show entries until timestamp (ISO format)')
    parser.add_argument('--compact', action='store_true',
                        help='Use compact single-line format')
    parser.add_argument('--reverse', '-r', action='store_true',
                        help='Show newest entries first')
    parser.add_argument('--export', '-o', metavar='FILE',
                        help='Export filtered results to JSON file')
    parser.add_argument('--stats', '-s', action='store_true',
                        help='Show chat statistics')
    parser.add_argument('--clear', action='store_true',
                        help='Clear the chat log file (with confirmation)')
    parser.add_argument('--ocnotes', action='store_true',
                        help='In follow mode, highlight OCNotes with special notifications')
    
    args = parser.parse_args()
    
    # Handle clear operation
    if args.clear:
        confirm = input("Are you sure you want to clear the chat log? (yes/no): ")
        if confirm.lower() == 'yes':
            try:
                with open(args.file, 'w', encoding='utf-8') as f:
                    json.dump([], f)
                print(f"[SUCCESS] Cleared chat log: {args.file}")
            except Exception as e:
                print(f"[ERROR] Failed to clear log: {e}")
        else:
            print("[INFO] Clear operation cancelled.")
        return
    
    # Handle follow mode
    if args.follow:
        follow_log(args.file, compact=args.compact, notify_ocnotes=args.ocnotes)
        return
    
    # Read chat log
    entries = read_chat_log(args.file)
    
    if not entries:
        sys.exit(1)
    
    # Filter entries
    filtered = filter_entries(
        entries,
        character=args.character,
        event_type=args.type,
        since=args.since,
        until=args.until
    )
    
    # Handle latest N
    if args.latest:
        filtered = filtered[-args.latest:]
    
    # Show statistics
    if args.stats:
        stats = get_stats(filtered if filtered else entries)
        display_stats(stats)
        return
    
    # Export mode
    if args.export:
        export_entries(filtered if filtered else entries, args.export)
        return
    
    # Display results
    display_entries(filtered if filtered else entries, 
                    compact=args.compact, 
                    reverse=args.reverse)
    
    # Summary
    total = len(entries)
    showing = len(filtered) if filtered else total
    if showing < total:
        print(f"\n[INFO] Showing {showing} of {total} total entries (filtered)")
    else:
        print(f"\n[INFO] Showing all {total} entries")

if __name__ == "__main__":
    main()
