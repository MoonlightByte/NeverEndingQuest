#!/usr/bin/env python3
"""
Version Checker - Check for NeverEndingQuest updates
Compares local VERSION file with GitHub releases
"""

import os
import requests
from pathlib import Path

def get_local_version():
    """Read local VERSION file"""
    # The install folder's VERSION, not the working directory's (a data root has none; #1681/#1682).
    version_file = Path(__file__).resolve().parent.parent / "VERSION"
    if version_file.exists():
        return version_file.read_text().strip()
    return "0.0.0"

def get_latest_github_version():
    """Fetch latest version from GitHub"""
    try:
        # Check GitHub API for latest release
        response = requests.get(
            "https://api.github.com/repos/MoonlightByte/NeverEndingQuest/releases/latest",
            timeout=5
        )

        if response.status_code == 200:
            data = response.json()
            tag_name = data.get("tag_name", "")
            # Remove 'v' prefix if present
            return tag_name.lstrip('v')
        else:
            # Fallback: check raw VERSION file on main branch
            response = requests.get(
                "https://raw.githubusercontent.com/MoonlightByte/NeverEndingQuest/main/VERSION",
                timeout=5
            )
            if response.status_code == 200:
                return response.text.strip()

    except Exception as e:
        print(f"[VERSION_CHECK] Could not check for updates: {e}")

    return None

def compare_versions(local, remote):
    """
    Compare version strings.
    Returns: 'update_available', 'up_to_date', or 'unknown'
    """
    if not remote:
        return 'unknown'

    try:
        local_parts = [int(x) for x in local.split('.')]
        remote_parts = [int(x) for x in remote.split('.')]

        # Pad shorter version with zeros
        while len(local_parts) < len(remote_parts):
            local_parts.append(0)
        while len(remote_parts) < len(local_parts):
            remote_parts.append(0)

        # Compare
        if remote_parts > local_parts:
            return 'update_available'
        else:
            return 'up_to_date'

    except Exception:
        return 'unknown'

def check_for_updates(silent=False):
    """
    Check if updates are available.
    Returns: (status, local_version, remote_version, message)
    """
    local_version = get_local_version()
    remote_version = get_latest_github_version()

    if not silent:
        print(f"[VERSION_CHECK] Local version: {local_version}")
        if remote_version:
            print(f"[VERSION_CHECK] Latest version: {remote_version}")

    status = compare_versions(local_version, remote_version)

    if status == 'update_available':
        message = f"Update available! v{local_version} → v{remote_version}"
    elif status == 'up_to_date':
        message = f"You're up to date (v{local_version})"
    else:
        message = f"Could not check for updates (v{local_version})"

    return status, local_version, remote_version, message

def prompt_for_update():
    """
    Prompt user to update if new version available.
    Returns: True if user wants to update, False otherwise
    """
    status, local, remote, message = check_for_updates()

    if status == 'update_available':
        print()
        print("=" * 60)
        print(f"  UPDATE AVAILABLE: v{local} → v{remote}")
        print("=" * 60)
        print()
        print("A new version of NeverEndingQuest is available!")
        print()
        print("To update:")
        print("  1. Close the game")
        print("  2. Run: git pull")
        print("  3. Run: pip install -r requirements.txt")
        print("  4. Restart the game")
        print()
        print("Or use the update_game.bat script if available")
        print()

        response = input("Would you like to continue with current version? (y/n): ")
        return response.lower() != 'y'

    return False

if __name__ == "__main__":
    # Test the version checker
    status, local, remote, message = check_for_updates()
    print()
    print(message)

    if status == 'update_available':
        print()
        print("Run 'git pull' to update!")
