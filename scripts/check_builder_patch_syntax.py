# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Builder Syntax Guard - Compile Check Utility
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Purpose:
    Validate Python file syntax/indentation before applying patches.
    Fails fast on malformed code to prevent cascading errors.

Usage:
    Explicit file mode (recommended):
        python3 scripts/check_builder_patch_syntax.py <file1> <file2> ...
        python3 scripts/check_builder_patch_syntax.py core/managers/combat_manager.py
        python3 scripts/check_builder_patch_syntax.py core/managers/combat_manager.py core/managers/combat_state_sync.py

    Convenience mode (no args):
        python3 scripts/check_builder_patch_syntax.py
        # Compiles changed .py files from git diff (staged + unstaged)

    Check multiple files:
        python3 scripts/check_builder_patch_syntax.py core/managers/*.py

Exit codes:
    0  - All files compiled successfully
    1  - One or more files failed to compile
    2  - Invalid arguments or file not found

Output format:
    [PASS] <path>
    [FAIL] <path>: <error message>
"""

import ast
import subprocess
import sys
from pathlib import Path


def check_file(filepath: str) -> tuple[bool, str]:
    """
    Check if a Python file compiles successfully.
    
    Returns:
        tuple: (success: bool, diagnostic: str)
    """
    try:
        path = Path(filepath)
        if not path.exists():
            return False, f"File not found: {filepath}"
        
        if not path.is_file():
            return False, f"Not a file: {filepath}"
        
        source = path.read_text(encoding='utf-8')
        
        # Validate syntax using AST (no bytecode generation, no side effects)
        ast.parse(source, filename=str(path))
        
        return True, ""
        
    except SyntaxError as e:
        return False, f"SyntaxError at line {e.lineno}: {e.msg}"
    except UnicodeDecodeError as e:
        return False, f"UnicodeDecodeError: {e}"
    except PermissionError:
        return False, f"Permission denied: {filepath}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def get_changed_python_files() -> tuple[bool, list[str], str]:
    """
    Detect changed Python files from git diff (staged + unstaged).

    Returns:
        tuple: (success, files, diagnostic)
    """
    try:
        unstaged = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True,
            text=True,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--name-only", "--cached"],
            capture_output=True,
            text=True,
            check=False,
        )

        if unstaged.returncode != 0:
            return False, [], f"git diff failed: {unstaged.stderr.strip() or 'unknown error'}"
        if staged.returncode != 0:
            return False, [], f"git diff --cached failed: {staged.stderr.strip() or 'unknown error'}"

        candidates = set()
        for output in (unstaged.stdout, staged.stdout):
            for line in output.splitlines():
                entry = line.strip()
                if entry.endswith(".py"):
                    candidates.add(entry)

        files = sorted(candidates)
        return True, files, ""
    except Exception as e:
        return False, [], f"Failed to detect changed files: {type(e).__name__}: {e}"


def main():
    """Main entry point."""
    files = sys.argv[1:]
    if not files:
        ok, files, diagnostic = get_changed_python_files()
        if not ok:
            print(f"[ERROR] {diagnostic}", file=sys.stderr)
            sys.exit(2)
        if not files:
            print("[ERROR] No Python files specified and no changed Python files found via git diff", file=sys.stderr)
            print("Usage: python3 scripts/check_builder_patch_syntax.py <file1> [file2 ...]", file=sys.stderr)
            sys.exit(2)

        print("[INFO] No file args supplied, using changed Python files from git diff:")
        for filepath in files:
            print(f"[INFO]   {filepath}")

    all_passed = True
    
    for filepath in files:
        success, diagnostic = check_file(filepath)
        
        if success:
            print(f"[PASS] {filepath}")
        else:
            print(f"[FAIL] {filepath}: {diagnostic}")
            all_passed = False
    
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
