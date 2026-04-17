#!/usr/bin/env python3
"""
Auto-Updater - One-click update for NeverEndingQuest
Performs git pull and pip install automatically
"""

import subprocess
import sys
import os

def is_in_venv():
    """Check if running in a virtual environment"""
    return hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)

def run_auto_update():
    """
    Perform automatic update: git pull + pip install
    Returns: (success, message)
    """

    print("\n" + "="*60)
    print("  Starting Auto-Update...")
    print("="*60)
    print()

    # Step 1: Git pull
    print("Step 1: Pulling latest code from GitHub...")
    try:
        result = subprocess.run(
            ["git", "pull"],
            capture_output=True,
            text=True,
            timeout=30
        )

        print(result.stdout)

        if result.returncode != 0:
            return False, f"Git pull failed: {result.stderr}"

        if "Already up to date" in result.stdout:
            print("[OK] Already up to date!")
            return True, "Already up to date"

        print("[OK] Code updated successfully!")

    except Exception as e:
        return False, f"Git pull error: {e}"

    # Step 2: Update dependencies
    print("\nStep 2: Updating dependencies...")
    try:
        # Use pip from current Python environment
        pip_cmd = [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--upgrade"]

        result = subprocess.run(
            pip_cmd,
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode != 0:
            return False, f"Pip install failed: {result.stderr}"

        print("[OK] Dependencies updated!")

    except Exception as e:
        return False, f"Dependency update error: {e}"

    print()
    print("="*60)
    print("  Update Complete!")
    print("="*60)
    print("\nPlease restart the game to use the new version.")
    print()

    return True, "Update completed successfully. Please restart the game."

if __name__ == "__main__":
    success, message = run_auto_update()
    print(message)
    sys.exit(0 if success else 1)
