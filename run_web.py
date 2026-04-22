#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

# ============================================================================
# RUN_WEB.PY - WEB INTERFACE LAUNCHER
# ============================================================================
#
# ARCHITECTURE ROLE: User Interface Layer - Web Application Launcher
#
# This launcher script provides the entry point for the web-based user interface,
# coordinating Flask server startup and browser integration for cross-platform
# web-based game access.
#
# KEY RESPONSIBILITIES:
# - Web interface process management and startup coordination
# - Automatic browser launching for seamless user experience
# - Cross-platform compatibility for web server deployment
# - Integration with Flask + SocketIO web interface architecture
# - Error handling and graceful startup failure management
#

"""
Launcher script for the NeverEndingQuest web interface.
This script starts the Flask server and automatically opens the browser.
"""
import subprocess
import sys
import os
import time

def create_default_party_tracker():
    """Create a default party_tracker.json if it doesn't exist"""
    if not os.path.exists('party_tracker.json'):
        default_tracker = {}
        
        try:
            import json
            with open('party_tracker.json', 'w', encoding='utf-8') as f:
                json.dump(default_tracker, f, indent=2, ensure_ascii=False)
            print("[INFO] Created default party_tracker.json for first-time setup")
            return True
        except Exception as e:
            print(f"[ERROR] Could not create party_tracker.json: {e}")
            return False
    return True

def main():
    import shutil
    
    # Check if config.py exists first
    if not os.path.exists('config.py'):
        print("[D20] Welcome to NeverEndingQuest! [D20]")
        print("\nFirst-time setup detected...")
        
        try:
            # Copy config_template.py to config.py
            shutil.copy('config_template.py', 'config.py')
            print("\n[PASS] Created config.py from template")
            print("\n" + "="*60)
            print("IMPORTANT: OpenAI API Key Required")
            print("="*60)
            print("\n1. Open config.py in a text editor")
            print("2. Find the line: OPENAI_API_KEY = \"your_openai_api_key_here\"")
            print("3. Replace \"your_openai_api_key_here\" with your actual OpenAI API key")
            print("4. Save the file and run the game again")
            print("\nGet your API key at: https://platform.openai.com/api-keys")
            print("\n" + "="*60)
            input("\nPress Enter to exit...")
            return
        except Exception as e:
            print(f"[ERROR] Failed to create config.py: {e}")
            print("Please manually copy config_template.py to config.py")
            input("\nPress Enter to exit...")
            return
    
    # DISABLED FOR DEBUGGING - Create default party_tracker.json if it doesn't exist
    # if not create_default_party_tracker():
    #     print("[WARNING] Could not create party_tracker.json - some features may not work")
    
    # Initialize all required directories
    required_dirs = [
        "modules/conversation_history",
        "modules/campaign_archives", 
        "modules/campaign_summaries",
        "modules/backups",
        "modules/logs",
        "save_games",
        "characters",
        "combat_logs"
    ]
    
    for dir_path in required_dirs:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
    
    print("Launching NeverEndingQuest Web Interface...")
    try:
        import config
        port = getattr(config, 'WEB_PORT', 8357)
    except ImportError:
        port = 8357  # Default port if config doesn't exist yet
    print(f"The browser should open automatically. If not, navigate to http://localhost:{port}")
    
    # Run the web interface with restart capability
    # TABLETOP MODE: One-shot browser open per launcher session to prevent duplicate tabs on restart
    should_open_browser = True
    while True:
        try:
            # Prepare environment for child process
            # First spawn: open browser; subsequent restarts: skip browser open
            child_env = os.environ.copy()
            child_env["NEQ_OPEN_BROWSER"] = "1" if should_open_browser else "0"
            
            # Run the web interface and capture the return code
            result = subprocess.run([sys.executable, "web/web_interface.py"], env=child_env)
            
            # Check if it was a planned restart (exit code 0)
            if result.returncode == 0:
                print("\n[RESTART] Server shutdown detected. Restarting in 2 seconds...")
                time.sleep(2)
                print("[RESTART] Starting server again...")
                should_open_browser = False  # Skip browser open on restart
                continue
            elif result.returncode == 91:
                # TABLETOP MODE: Intentional GUI shutdown
                print("\n[SHUTDOWN] User initiated exit. Shutting down NeverEndingQuest Web Interface...")
                break
            else:
                # Non-zero exit code means an error occurred
                print(f"\n[ERROR] Server exited with code {result.returncode}")
                break
                
        except KeyboardInterrupt:
            print("\nShutting down NeverEndingQuest Web Interface...")
            break
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

if __name__ == "__main__":
    # Check for updates before starting
    try:
        from utils.version_checker import check_for_updates, resolve_update_target
        status, local_ver, remote_ver, message = check_for_updates(silent=True)
        target = resolve_update_target() or {}
        target_owner_repo = target.get('owner_repo', 'origin-unresolved')
        target_branch = target.get('branch', 'main')

        print(f"\nNeverEndingQuest v{local_ver}")
        print(f"Update channel: {target_owner_repo}@{target_branch}")

        if status == 'update_available':
            print(f"\n{'='*60}")
            print(f"  FORK UPDATE AVAILABLE: v{local_ver} -> v{remote_ver}")
            print(f"{'='*60}")
            print("\nA new fork-channel version is available.")
            print("\nTo update:")
            print("  1. Close the game")
            print(f"  2. Run: git pull --ff-only origin {target_branch}")
            print("  3. Run: pip install -r requirements.txt (or venv\\Scripts\\activate then pip install)")
            print("  4. Restart the game")
            print()
            input("Press Enter to continue with current version...")
        elif status == 'unknown':
            print(f"[VERSION_CHECK] {message}")

    except Exception as e:
        print(f"[VERSION_CHECK] Could not check for updates: {e}")

    main()