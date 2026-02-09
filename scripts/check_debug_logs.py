#!/usr/bin/env python3
"""
Tabletop Mode Debug Log Checker
Three-phase debug workflow: start -> check -> stop

Usage:
    # Phase 1: Start debugging (configure + enable)
    python scripts/check_debug_logs.py --enable
    
    # Phase 2: Check for errors (after restart)
    python scripts/check_debug_logs.py
    python scripts/check_debug_logs.py --warnings
    python scripts/check_debug_logs.py --verbose --lines 200
    
    # Phase 3: Stop debugging (disable + cleanup)
    python scripts/check_debug_logs.py --stop
    
    # Utility
    python scripts/check_debug_logs.py --status
"""

import sys
import os
import re
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def get_debug_status():
    """Check current debug configuration status."""
    status = {
        "tabletop_mode": None,
        "tabletop_verbose": None,
        "tabletop_debug_verbose": None,
        "config_readable": True
    }
    
    # Check debug_config.py
    debug_config_path = project_root / "debug_config.py"
    if debug_config_path.exists():
        try:
            with open(debug_config_path, 'r') as f:
                content = f.read()
            
            # Extract values using regex
            mode_match = re.search(r'"tabletop_mode":\s*(True|False)', content)
            verbose_match = re.search(r'"tabletop_verbose":\s*(True|False)', content)
            
            if mode_match:
                status["tabletop_mode"] = mode_match.group(1) == "True"
            if verbose_match:
                status["tabletop_verbose"] = verbose_match.group(1) == "True"
        except Exception:
            pass
    
    # Check config.py
    config_path = project_root / "config.py"
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                content = f.read()
            
            # Extract TABLETOP_DEBUG_VERBOSE value
            verbose_match = re.search(r'TABLETOP_DEBUG_VERBOSE\s*=\s*(True|False)', content)
            if verbose_match:
                status["tabletop_debug_verbose"] = verbose_match.group(1) == "True"
        except Exception:
            pass
    
    return status

def is_debug_enabled():
    """Check if TABLETOP MODE debugging is enabled."""
    status = get_debug_status()
    return status["tabletop_mode"] == True and status["tabletop_verbose"] == True and status["tabletop_debug_verbose"] == True

def enable_debug_mode():
    """Enable TABLETOP MODE debug configuration."""
    changes_made = []
    
    # Enable in debug_config.py
    debug_config_path = project_root / "debug_config.py"
    if debug_config_path.exists():
        try:
            with open(debug_config_path, 'r') as f:
                content = f.read()
            
            # Replace values
            original_content = content
            content = re.sub(r'("tabletop_mode"):\s*(True|False)', r'\1: True', content)
            content = re.sub(r'("tabletop_verbose"):\s*(True|False)', r'\1: True', content)
            
            if content != original_content:
                with open(debug_config_path, 'w') as f:
                    f.write(content)
                changes_made.append("debug_config.py: tabletop_mode = True, tabletop_verbose = True")
        except Exception as e:
            print(f"ERROR: Failed to update debug_config.py: {e}")
    
    # Enable in config.py
    config_path = project_root / "config.py"
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                content = f.read()
            
            # Replace TABLETOP_DEBUG_VERBOSE
            original_content = content
            content = re.sub(r'(TABLETOP_DEBUG_VERBOSE\s*=\s*)(True|False)', r'\1True', content)
            
            if content != original_content:
                with open(config_path, 'w') as f:
                    f.write(content)
                changes_made.append("config.py: TABLETOP_DEBUG_VERBOSE = True")
        except Exception as e:
            print(f"ERROR: Failed to update config.py: {e}")
    
    return changes_made

def disable_debug_mode():
    """Disable TABLETOP MODE debug configuration and clean up logs."""
    changes_made = []
    files_deleted = []
    
    # Disable in debug_config.py
    debug_config_path = project_root / "debug_config.py"
    if debug_config_path.exists():
        try:
            with open(debug_config_path, 'r') as f:
                content = f.read()
            
            # Replace values to False
            original_content = content
            content = re.sub(r'("tabletop_mode"):\s*(True|False)', r'\1: False', content)
            content = re.sub(r'("tabletop_verbose"):\s*(True|False)', r'\1: False', content)
            
            if content != original_content:
                with open(debug_config_path, 'w') as f:
                    f.write(content)
                changes_made.append("debug_config.py: tabletop_mode = False, tabletop_verbose = False")
        except Exception as e:
            print(f"ERROR: Failed to update debug_config.py: {e}")
    
    # Disable in config.py
    config_path = project_root / "config.py"
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                content = f.read()
            
            # Replace TABLETOP_DEBUG_VERBOSE to False
            original_content = content
            content = re.sub(r'(TABLETOP_DEBUG_VERBOSE\s*=\s*)(True|False)', r'\1False', content)
            
            if content != original_content:
                with open(config_path, 'w') as f:
                    f.write(content)
                changes_made.append("config.py: TABLETOP_DEBUG_VERBOSE = False")
        except Exception as e:
            print(f"ERROR: Failed to update config.py: {e}")
    
    # Clean up log files
    logs_dir = project_root / "modules" / "logs"
    if logs_dir.exists():
        log_patterns = ['game_debug.log*', 'game_errors.log*']
        
        for pattern in log_patterns:
            for log_file in logs_dir.glob(pattern):
                try:
                    log_file.unlink()
                    files_deleted.append(log_file.name)
                except Exception as e:
                    print(f"Warning: Failed to delete {log_file}: {e}")
    
    return changes_made, files_deleted

def show_restart_message():
    """Display the restart notification message."""
    print()
    print("=" * 60)
    print("🔄  ACTION REQUIRED: Restart your server")
    print("=" * 60)
    print()
    print("Please stop and restart your server in your terminal.")
    print("The config changes only take effect on restart.")
    print()
    print("Once restarted, run 'check debug logs' again to see output.")
    print()

def check_debug_logs(lines=100, show_warnings=False, show_verbose=False, auto_enable=False):
    """Check game debug logs for errors."""
    
    # First check if debug is enabled
    if not is_debug_enabled():
        print("=" * 60)
        print("TABLETOP MODE Debug Status")
        print("=" * 60)
        print()
        print("TABLETOP MODE debugging is currently DISABLED.")
        print()
        
        status = get_debug_status()
        print("Current settings:")
        print(f"  - debug_config.py -> tabletop_mode: {status['tabletop_mode']}")
        print(f"  - debug_config.py -> tabletop_verbose: {status['tabletop_verbose']}")
        print(f"  - config.py -> TABLETOP_DEBUG_VERBOSE: {status['tabletop_debug_verbose']}")
        print()
        
        if auto_enable:
            print("✅ Enabling TABLETOP MODE debug automatically...")
            changes = enable_debug_mode()
            
            if changes:
                print()
                print("Changes made:")
                for change in changes:
                    print(f"  ✓ {change}")
                show_restart_message()
            else:
                print("No changes needed or failed to update files.")
            return
        else:
            print("Run with --enable flag to enable debug mode:")
            print("  python scripts/check_debug_logs.py --enable")
            print()
            return
    
    # Debug is enabled, proceed to check logs
    log_file = project_root / "modules" / "logs" / "game_debug.log"
    
    if not log_file.exists():
        print(f"ERROR: Log file not found: {log_file}")
        print()
        print("This is normal if the server hasn't generated any logs yet.")
        print("Start the server and run some combat to generate logs.")
        return
    
    # Read last N lines
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
    except Exception as e:
        print(f"ERROR: Failed to read log file: {e}")
        return
    
    # Parse and categorize
    critical = []
    errors = []
    warnings = []
    tabletop = []
    verbose_entries = []
    
    for line in recent_lines:
        line = line.strip()
        if not line:
            continue
            
        # Categorize by severity
        if 'CRITICAL' in line.upper():
            critical.append(line)
        elif 'ERROR' in line.upper() and 'tabletop' not in line.lower():
            errors.append(line)
        elif 'WARNING' in line.upper():
            warnings.append(line)
        
        # Check for tabletop entries
        if 'tabletop' in line.lower() or 'TABLETOP MODE' in line:
            if 'verbose' in line.lower():
                verbose_entries.append(line)
            else:
                tabletop.append(line)
    
    # Display summary
    print("=" * 60)
    print("TABLETOP MODE Debug Summary")
    print("=" * 60)
    print(f"Source: {log_file}")
    print(f"Lines analyzed: {len(recent_lines)} of {len(all_lines)}")
    print(f"File size: {log_file.stat().st_size / 1024:.1f} KB")
    print()
    
    # Always show critical
    if critical:
        print(f"⚠️  CRITICAL ({len(critical)}):")
        for entry in critical[-5:]:  # Show last 5
            print(f"  {entry[:200]}")
        print()
    
    # Always show errors
    if errors:
        print(f"❌ ERRORS ({len(errors)}):")
        for entry in errors[-10:]:  # Show last 10
            print(f"  {entry[:200]}")
        print()
    
    # Show warnings if requested
    if show_warnings and warnings:
        print(f"⚠️  WARNINGS ({len(warnings)}):")
        for entry in warnings[-5:]:
            print(f"  {entry[:200]}")
        print()
    
    # Show tabletop activity
    print(f"🎲 TABLETOP MODE Activity: {len(tabletop)} entries")
    if tabletop:
        print(f"Latest: {tabletop[-1][:100]}")
    print()
    
    # Show verbose if requested
    if show_verbose and verbose_entries:
        print(f"🔍 VERBOSE Entries: {len(verbose_entries)}")
        for entry in verbose_entries[-5:]:
            print(f"  {entry[:150]}")
        print()
    
    # Configuration status
    print("=" * 60)
    print("Configuration Status")
    print("=" * 60)
    status = get_debug_status()
    print(f"tabletop_mode: {status['tabletop_mode']}")
    print(f"tabletop_verbose: {status['tabletop_verbose']}")
    print(f"TABLETOP_DEBUG_VERBOSE: {status['tabletop_debug_verbose']}")
    print()
    
    # Summary
    total_issues = len(critical) + len(errors)
    if total_issues > 0:
        print(f"[FOUND {total_issues} ISSUE(S) - See above]")
    else:
        print("[✅ NO CRITICAL ERRORS OR ERRORS FOUND]")

def show_status():
    """Show detailed debug configuration status."""
    print("=" * 60)
    print("TABLETOP MODE Debug Configuration Status")
    print("=" * 60)
    print()
    
    status = get_debug_status()
    
    print("Current Settings:")
    print(f"  debug_config.py:")
    print(f"    - tabletop_mode: {status['tabletop_mode']}")
    print(f"    - tabletop_verbose: {status['tabletop_verbose']}")
    print()
    print(f"  config.py:")
    print(f"    - TABLETOP_DEBUG_VERBOSE: {status['tabletop_debug_verbose']}")
    print()
    
    if is_debug_enabled():
        print("✅ Status: DEBUG MODE ENABLED")
        print()
        print("Debug logging is active. Run combat to see output.")
    else:
        print("⚠️  Status: DEBUG MODE DISABLED")
        print()
        print("To enable debug mode, run:")
        print("  python scripts/check_debug_logs.py --enable")
    print()

def show_stop_restart_message():
    """Display the stop/restart notification message."""
    print()
    print("=" * 60)
    print("🔄  ACTION REQUIRED: Restart your server")
    print("=" * 60)
    print()
    print("Please stop and restart your server in your terminal.")
    print()
    print("After restart, debug mode will be OFF.")
    print("Logs cleaned and ready for next session.")
    print()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Check TABLETOP MODE debug logs")
    parser.add_argument("--lines", type=int, default=100, help="Number of lines to read")
    parser.add_argument("--warnings", action="store_true", help="Include warnings")
    parser.add_argument("--verbose", action="store_true", help="Include verbose entries")
    parser.add_argument("--enable", action="store_true", help="Enable debug mode")
    parser.add_argument("--stop", action="store_true", help="Stop debug mode and clean up logs")
    parser.add_argument("--status", action="store_true", help="Show configuration status")
    
    args = parser.parse_args()
    
    if args.status:
        show_status()
    elif args.stop:
        print("=" * 60)
        print("Stopping TABLETOP MODE Debug")
        print("=" * 60)
        print()
        
        changes, files_deleted = disable_debug_mode()
        
        if changes or files_deleted:
            print("✅ TABLETOP MODE debug disabled!")
            print()
            
            if changes:
                print("Configuration changes:")
                for change in changes:
                    print(f"  ✓ {change}")
                print()
            
            if files_deleted:
                print("Log files cleaned:")
                for filename in files_deleted[:10]:  # Show first 10
                    print(f"  ✓ Deleted {filename}")
                if len(files_deleted) > 10:
                    print(f"  ... and {len(files_deleted) - 10} more files")
                print()
            
            show_stop_restart_message()
        else:
            print("⚠️  No changes made (already disabled or failed to update)")
    elif args.enable:
        print("=" * 60)
        print("Enabling TABLETOP MODE Debug")
        print("=" * 60)
        print()
        changes = enable_debug_mode()
        
        if changes:
            print("✅ TABLETOP MODE debug enabled!")
            print()
            print("Changes made:")
            for change in changes:
                print(f"  ✓ {change}")
            show_restart_message()
        else:
            print("⚠️  No changes made (already enabled or failed to update)")
    else:
        check_debug_logs(
            lines=args.lines,
            show_warnings=args.warnings,
            show_verbose=args.verbose,
            auto_enable=False
        )
