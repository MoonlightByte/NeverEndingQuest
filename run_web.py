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
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


_AUTO_NPM = object()


class _BundleReferences(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script" and attrs.get("src"):
            self.paths.append(attrs["src"])
        if tag == "link" and attrs.get("rel") in {"stylesheet", "modulepreload"}:
            if attrs.get("href"):
                self.paths.append(attrs["href"])


def _react_bundle_is_usable(dist):
    """Check actual entry dependencies, not just the presence of an HTML shell."""
    dist = Path(dist).resolve()
    try:
        parser = _BundleReferences()
        parser.feed((dist / "index.html").read_text(encoding="utf-8"))
        if not parser.paths:
            return False
        for reference in parser.paths:
            url = urlsplit(reference)
            if url.scheme or url.netloc:
                continue
            path = unquote(url.path)
            if path.startswith("/play/"):
                path = path[len("/play/"):]
            elif path.startswith("/"):
                return False
            target = (dist / path).resolve()
            if dist not in target.parents or not target.is_file():
                return False
        return True
    except (OSError, ValueError):
        return False


def _replace_frontend_file(source, target):
    """Sharing violations are busy, not a failed installation (#193 B2)."""
    while True:
        try:
            os.replace(source, target)
            return
        except OSError as exc:
            if getattr(exc, "winerror", None) not in {32, 33}:
                raise
            print("[SETUP] Waiting for the browser files to become available...")
            time.sleep(0.25)


def _publish_react_build(built, dist):
    """Publish dependencies first and index last; retain the previous shell on error."""
    built, dist = Path(built), Path(dist)
    if not _react_bundle_is_usable(built):
        raise ValueError("React build is incomplete; an entry dependency is missing")
    dist.mkdir(parents=True, exist_ok=True)
    originals = {}
    files = [p for p in built.rglob("*") if p.is_file() and p != built / "index.html"]
    files.append(built / "index.html")
    try:
        for source in files:
            target = dist / source.relative_to(built)
            target.parent.mkdir(parents=True, exist_ok=True)
            originals[target] = None
            if target.exists():
                previous = built.parent / 'previous' / source.relative_to(built)
                previous.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, previous)
                originals[target] = previous
            _replace_frontend_file(source, target)
    except BaseException:
        # No game state is touched. Roll back only files this publication replaced.
        for target in reversed(originals):
            rollback = built / target.relative_to(dist)
            # os.replace consumes its source only on success. Inspect that fact
            # even if Ctrl+C arrived between replacement and Python bookkeeping.
            # A failed/locked unchanged destination must not block restoration.
            if rollback.exists():
                continue
            previous = originals[target]
            if previous is None:
                target.unlink(missing_ok=True)
            else:
                _replace_frontend_file(previous, target)
        raise


def _react_build_is_current(frontend_dir):
    """Return True when the compiled React entry point is newer than its inputs."""
    frontend_dir = Path(frontend_dir)
    index = frontend_dir / "dist" / "index.html"
    if not _react_bundle_is_usable(frontend_dir / "dist"):
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
        # main.tsx imports this shared presentation source from outside src.
        # Watch the exact build dependency, not static media/toolkit-only files.
        frontend_dir.parent / "static" / "css" / "ember-tokens.css",
    ]
    for input_path in input_paths:
        files = input_path.rglob("*") if input_path.is_dir() else [input_path]
        if any(path.is_file() and path.stat().st_mtime > build_time for path in files):
            return False
    return True


def check_frontend_tools(repo_root=None):
    """Let npm validate this checkout's complete locked engine contract, offline."""
    repo_root = Path(repo_root or Path(__file__).resolve().parent)
    node, npm = shutil.which("node"), shutil.which("npm")
    if not node or not npm:
        print("[SETUP] Node.js and npm are required to build React.")
        return False
    try:
        for command in ([node, "--version"], [npm, "--version"]):
            if subprocess.run(command).returncode:
                return False
        # No package downloads, scripts, lockfile edits or node_modules changes.
        result = subprocess.run(
            [npm, "ci", "--dry-run", "--ignore-scripts", "--engine-strict",
             "--offline", "--no-audit", "--include=dev"],
            cwd=repo_root / "web" / "frontend",
        )
        if result.returncode:
            print("[SETUP] This checkout's frontend dependency check failed. See npm's error above.")
            print("For an unsupported engine, install Node.js LTS from https://nodejs.org/en/download.")
            return False
        return True
    except OSError as exc:
        print(f"[SETUP] Cannot run Node.js/npm: {exc}")
        return False


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
        print("Or explicitly run: python run_web.py --ui legacy\n")
        return False

    print("\n[SETUP] Preparing the React player (first launch or frontend update)...")
    workspace = None
    try:
        workspace = tempfile.TemporaryDirectory(prefix=".react-build-", dir=frontend_dir)
        built = Path(workspace.name) / "dist"
        commands = (
            [npm_command, "ci", "--engine-strict", "--include=dev"],
            [npm_command, "run", "build", "--", "--outDir", str(built)],
        )
        for command in commands:
            result = runner(command, cwd=frontend_dir)
            if result.returncode != 0:
                print(f"[WARNING] Frontend setup failed: {' '.join(command)}")
                print("Review the error above, repair the dependency or build problem, then retry.")
                print("Or explicitly run: python run_web.py --ui legacy")
                return False
        _publish_react_build(built, frontend_dir / "dist")
        print("[OK] React player built and verified\n")
        return True
    except (OSError, ValueError) as exc:
        print(f"[WARNING] React preparation failed: {exc}")
        print("Retry setup, or explicitly run: python run_web.py --ui legacy")
        return False
    finally:
        try:
            if workspace is not None:
                workspace.cleanup()
        except OSError as exc:
            print(f"[WARNING] Temporary React build cleanup: {exc}")


def select_ui(requested, react_available, input_fn=input):
    """Legacy requires explicit consent; unavailable React is a setup outcome."""
    if requested == "legacy":
        return "legacy"
    if requested == "choose":
        print("[INFO] --ui choose now opens React. Use --ui legacy to request legacy.")
    return "react" if react_available else None


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Launch the NeverEndingQuest web interface")
    parser.add_argument(
        "--ui",
        choices=("react", "legacy", "choose"),
        default="react",
        help="interface to open (default: react; --ui legacy explicitly selects legacy)",
    )
    parser.add_argument("--toolkit", action="store_true", help="open the module toolkit without building the player")
    parser.add_argument("--prepare-frontend", action="store_true", help="prepare React assets without starting a game")
    parser.add_argument("--check-frontend-tools", action="store_true", help="check Node/npm against locked dependencies without installing")
    parser.add_argument("--frontend-ready", action="store_true", help="check current React assets without requiring Node/npm")
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

def main(ui="react", toolkit=False):
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
    react_available = False if ui == "legacy" or toolkit else ensure_react_frontend()
    selected_ui = "react" if toolkit else select_ui(ui, react_available)
    if selected_ui is None:
        print("[SETUP] React is not ready. No game was started; your saves are unchanged.")
        return 1
    start_path = "/toolkit" if toolkit else ("/play/" if selected_ui == "react" else "/")
    
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
            child_env.pop("NEQ_START_PATH", None)
            command = [sys.executable, "web/web_interface.py", "--ui", selected_ui]
            if toolkit:
                command.append("--toolkit")
            result = subprocess.run(command, env=child_env)
            
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
    if args.frontend_ready:
        sys.exit(0 if _react_build_is_current(Path(__file__).resolve().parent / "web/frontend") else 1)
    if args.check_frontend_tools:
        sys.exit(0 if check_frontend_tools() else 1)
    if args.prepare_frontend:
        sys.exit(0 if ensure_react_frontend() else 1)
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

    sys.exit(main(args.ui, toolkit=args.toolkit))
