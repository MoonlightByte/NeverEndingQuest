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
import argparse
import shutil
from pathlib import Path


_AUTO_NPM = object()


def _react_build_is_current(frontend_dir):
    """Return True when the compiled React entry point is newer than its inputs."""
    frontend_dir = Path(frontend_dir)
    index = frontend_dir / "dist" / "index.html"
    if not index.is_file():
        return False

    build_time = index.stat().st_mtime
    input_paths = [
        frontend_dir / "src",
        frontend_dir / "public",
        frontend_dir / "index.html",
        frontend_dir / "package.json",
        frontend_dir / "package-lock.json",
        frontend_dir / "vite.config.ts",
        frontend_dir / "tsconfig.json",
        frontend_dir / "tsconfig.app.json",
        frontend_dir / "tsconfig.node.json",
    ]
    for input_path in input_paths:
        files = input_path.rglob("*") if input_path.is_dir() else [input_path]
        if any(path.is_file() and path.stat().st_mtime > build_time for path in files):
            return False
    return True


def ensure_react_frontend(repo_root=None, npm_command=_AUTO_NPM, runner=subprocess.run):
    """Build the React player when missing/stale; return whether it is usable."""
    repo_root = Path(repo_root or Path(__file__).resolve().parent)
    frontend_dir = repo_root / "web" / "frontend"
    if _react_build_is_current(frontend_dir):
        print("[OK] React player is already built")
        return True

    if npm_command is _AUTO_NPM:
        npm_command = shutil.which("npm")
    if not npm_command:
        print("\n[WARNING] The React player needs to be built, but npm was not found.")
        print("Install Node.js LTS from https://nodejs.org/ and run the game again.")
        print("Starting the legacy interface instead.\n")
        return False

    print("\n[SETUP] Preparing the React player (first launch or frontend update)...")
    commands = ([npm_command, "ci"], [npm_command, "run", "build"])
    for command in commands:
        try:
            result = runner(command, cwd=frontend_dir)
        except OSError as exc:
            print(f"[WARNING] Could not run npm: {exc}")
            print("Starting the legacy interface instead.\n")
            return False
        if result.returncode != 0:
            print(f"[WARNING] Frontend setup failed while running: {' '.join(command)}")
            print("You can retry manually in web/frontend. Starting legacy instead.\n")
            return False

    print("[OK] React player built successfully\n")
    return True


def select_ui(requested, react_available, input_fn=input):
    """Resolve the requested startup interface, with a safe legacy fallback."""
    if requested == "legacy" or not react_available:
        return "legacy"
    if requested == "choose":
        print("Choose the player interface:")
        print("  1. React player (recommended)")
        print("  2. Legacy player")
        choice = input_fn("Selection [1]: ").strip().lower()
        if choice in {"2", "legacy", "l"}:
            return "legacy"
    return "react"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Launch the NeverEndingQuest web interface")
    parser.add_argument(
        "--ui",
        choices=("react", "legacy", "choose"),
        default="react",
        help="interface to open (default: react)",
    )
    return parser.parse_args(argv)

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

def main(ui="react"):
    # Check if config.py exists first
    if not os.path.exists('config.py'):
        print("[D20] Welcome to NeverEndingQuest! [D20]")
        print("\nFirst-time setup detected...")
        
        try:
            # Copy config_template.py to config.py
            shutil.copy('config_template.py', 'config.py')
            print("\n[OK] Created config.py from template")
            print("\n" + "="*60)
            print("AI Provider Setup")
            print("="*60)
            print("\nYour local config.py has been created.")
            print("Run the game again, then use Settings -> AI Provider to choose:")
            print("  - Legacy/OpenAI (OpenAI API key)")
            print("  - Gemini (Gemini API key)")
            print("  - Local (LM Studio or another compatible endpoint; no cloud key)")
            print("\nYou may also edit config.py directly before restarting.")
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

    # An explicit legacy launch must not require Node.js or spend time building React.
    react_available = False if ui == "legacy" else ensure_react_frontend()
    selected_ui = select_ui(ui, react_available)
    start_path = "/play/" if selected_ui == "react" else "/"
    
    print("Launching NeverEndingQuest Web Interface...")
    try:
        import config
        port = getattr(config, 'WEB_PORT', 8357)
    except ImportError:
        port = 8357  # Default port if config doesn't exist yet
    print(f"Starting the {selected_ui.title()} player")
    print(f"The browser should open automatically. If not, navigate to http://localhost:{port}{start_path}")
    
    # Run the web interface with restart capability
    while True:
        try:
            # Run the web interface and capture the return code
            child_env = os.environ.copy()
            child_env["NEQ_START_PATH"] = start_path
            result = subprocess.run([sys.executable, "web/web_interface.py"], env=child_env)
            
            # Check if it was a planned restart (exit code 0)
            if result.returncode == 0:
                print("\n[RESTART] Server shutdown detected. Restarting in 2 seconds...")
                time.sleep(2)
                print("[RESTART] Starting server again...")
                continue
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
    args = parse_args()
    # Check for updates before starting
    try:
        from utils.version_checker import check_for_updates
        status, local_ver, remote_ver, message = check_for_updates(silent=True)

        print(f"\nNeverEndingQuest v{local_ver}")

        if status == 'update_available':
            print(f"\n{'='*60}")
            print(f"  UPDATE AVAILABLE: v{local_ver} -> v{remote_ver}")
            print(f"{'='*60}")
            print("\nA new version is available!")
            print("\nTo update:")
            print("  1. Close the game")
            print("  2. Run: git pull")
            print("  3. Run: pip install -r requirements.txt (or venv\\Scripts\\activate then pip install)")
            print("  4. Restart the game")
            print()
            input("Press Enter to continue with current version...")

    except Exception as e:
        print(f"[VERSION_CHECK] Could not check for updates: {e}")

    main(args.ui)
