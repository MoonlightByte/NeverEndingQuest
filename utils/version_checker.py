#!/usr/bin/env python3
"""
Version Checker - Check for NeverEndingQuest updates.
Fork-aware source resolution based on git origin remote.
"""

import re
import subprocess
from pathlib import Path
from typing import Dict, Optional, Tuple


def get_local_version() -> str:
    """Read local VERSION file."""
    version_file = Path("VERSION")
    if version_file.exists():
        return version_file.read_text(encoding="utf-8").strip()
    return "0.0.0"


def _run_git_command(args, repo_path: str = ".", timeout: int = 5) -> Optional[str]:
    """Run git command and return stdout on success, else None."""
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=repo_path,
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip()
    except Exception:
        return None


def _parse_github_owner_repo(remote_url: str) -> Optional[Tuple[str, str]]:
    """Parse GitHub owner/repo from origin URL."""
    patterns = [
        r"^https://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$",
        r"^git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$",
        r"^ssh://git@github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$",
        r"^git://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$",
    ]
    for pattern in patterns:
        match = re.match(pattern, remote_url)
        if match:
            owner = match.group(1)
            repo = match.group(2)
            return owner, repo
    return None


def resolve_update_target(repo_path: str = ".") -> Optional[Dict[str, str]]:
    """
    Resolve update target from git origin remote.

    Returns dict with keys:
      - remote
      - owner
      - repo
      - owner_repo
      - branch
    Or None on parse failure.
    """
    origin_url = _run_git_command(["git", "remote", "get-url", "origin"], repo_path=repo_path)
    if not origin_url:
        return None

    parsed = _parse_github_owner_repo(origin_url)
    if not parsed:
        return None

    owner, repo = parsed

    # Prefer origin default branch.
    origin_head = _run_git_command(
        ["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        repo_path=repo_path,
    )

    branch = None
    if origin_head and origin_head.startswith("origin/"):
        branch = origin_head.split("/", 1)[1]

    # Fallback to current branch.
    if not branch:
        current_branch = _run_git_command(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            repo_path=repo_path,
        )
        if current_branch and current_branch != "HEAD":
            branch = current_branch

    if not branch:
        branch = "main"

    return {
        "remote": "origin",
        "owner": owner,
        "repo": repo,
        "owner_repo": f"{owner}/{repo}",
        "branch": branch,
    }


def get_latest_remote_version(owner_repo: str, branch: str, silent: bool = False) -> Optional[str]:
    """Fetch latest remote version from resolved fork target."""
    try:
        import requests
    except Exception as exc:
        if not silent:
            print(f"[VERSION_CHECK] requests unavailable: {exc}")
        return None

    try:
        release_url = f"https://api.github.com/repos/{owner_repo}/releases/latest"
        response = requests.get(release_url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            tag_name = data.get("tag_name", "")
            if tag_name:
                return tag_name.lstrip("v")

        raw_url = f"https://raw.githubusercontent.com/{owner_repo}/{branch}/VERSION"
        response = requests.get(raw_url, timeout=5)
        if response.status_code == 200:
            return response.text.strip()

    except Exception as exc:
        if not silent:
            print(f"[VERSION_CHECK] Could not check for updates: {exc}")

    return None


def compare_versions(local: str, remote: Optional[str]) -> str:
    """Compare version strings. Returns update_available, up_to_date, or unknown."""
    if not remote:
        return "unknown"

    try:
        local_parts = [int(x) for x in local.split(".")]
        remote_parts = [int(x) for x in remote.split(".")]

        while len(local_parts) < len(remote_parts):
            local_parts.append(0)
        while len(remote_parts) < len(local_parts):
            remote_parts.append(0)

        if remote_parts > local_parts:
            return "update_available"
        return "up_to_date"
    except Exception:
        return "unknown"


def check_for_updates(silent: bool = False):
    """
    Check if updates are available.
    Returns: (status, local_version, remote_version, message)
    """
    local_version = get_local_version()
    target = resolve_update_target()

    if not target:
        message = f"Could not resolve fork update source from origin (v{local_version})"
        if not silent:
            print(f"[VERSION_CHECK] Local version: {local_version}")
            print("[VERSION_CHECK] Could not resolve update target from origin")
        return "unknown", local_version, None, message

    owner_repo = target["owner_repo"]
    branch = target["branch"]
    remote_version = get_latest_remote_version(owner_repo, branch, silent=silent)

    if not silent:
        print(f"[VERSION_CHECK] Local version: {local_version}")
        print(f"[VERSION_CHECK] Fork target: {owner_repo}@{branch}")
        if remote_version:
            print(f"[VERSION_CHECK] Remote version: {remote_version}")

    status = compare_versions(local_version, remote_version)

    if status == "update_available":
        message = (
            f"Fork update available from {owner_repo}@{branch}: "
            f"v{local_version} -> v{remote_version}"
        )
    elif status == "up_to_date":
        message = f"Fork channel up to date ({owner_repo}@{branch}, v{local_version})"
    else:
        message = (
            f"Could not check fork updates from {owner_repo}@{branch} "
            f"(v{local_version})"
        )

    return status, local_version, remote_version, message


def prompt_for_update() -> bool:
    """Prompt user to update if new version available."""
    status, local, remote, _message = check_for_updates()
    target = resolve_update_target() or {}
    branch = target.get("branch", "main")

    if status == "update_available":
        print()
        print("=" * 60)
        print(f"  FORK UPDATE AVAILABLE: v{local} -> v{remote}")
        print("=" * 60)
        print()
        print("A new fork-channel version of NeverEndingQuest is available.")
        print()
        print("To update:")
        print("  1. Close the game")
        print(f"  2. Run: git pull --ff-only origin {branch}")
        print("  3. Run: pip install -r requirements.txt")
        print("  4. Restart the game")
        print()

        response = input("Would you like to continue with current version? (y/n): ")
        return response.lower() != "y"

    return False


if __name__ == "__main__":
    status, local, remote, message = check_for_updates()
    print()
    print(message)

    if status == "update_available":
        target = resolve_update_target() or {}
        branch = target.get("branch", "main")
        print()
        print(f"Run 'git pull --ff-only origin {branch}' to update!")
