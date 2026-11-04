# SPDX-FileCopyrightText: 2026 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Bring a data root's shipped adventures up to the install's (#1810).

A data root keeps its own copy of each shipped module, so an update never
reached it and a new game or Reset read the old files. Reset now replaces those
files from the install, and a launch with no game on disk runs Reset when one
is out of date. Nothing is deleted, and a game in progress is left alone.

A folder counts as shipped by typed values only: its name is in the install's
modules/ and its declaration names the same module and start. "Out of date" is
a plain compare with the install's file.

A Reset that replaces files writes {"resetInProgress": true} to the tracker
first and {} last, so a stop anywhere between makes the next launch run it
again. Every other Reset writes {} as it always did.
"""

import filecmp
import json
import os

from utils.data_root import install_root

RESET_UNFINISHED = {"resetInProgress": True}

_STARTUP_CHECKPOINT = "modules/conversation_history/startup_conversation.json"
_TOP_LEVEL_FILES = (
    "module_declaration.json", "module_plot_BU.json", "party_tracker_BU.json",
    "module_context_BU.json", "PLAYER_GUIDE.md", "README.md",
)


def _identity(module_folder):
    """(module, areaId, locationId) from a folder's declaration, or None."""
    try:
        with open(os.path.join(module_folder, "module_declaration.json"),
                  encoding="utf-8") as handle:
            declaration = json.load(handle)
    except (OSError, ValueError):
        return None
    start = declaration.get("start") if isinstance(declaration, dict) else None
    if not isinstance(start, dict):
        return None
    return declaration.get("module"), start.get("areaId"), start.get("locationId")


def _shipped_files(module_folder):
    """Paths under a module folder that the install owns; played files are not listed."""
    for directory, _, filenames in os.walk(module_folder):
        for filename in filenames:
            path = os.path.relpath(os.path.join(directory, filename), module_folder)
            parts = path.split(os.sep)
            if parts[0] in ("monsters", "media"):
                yield path
            elif parts[0] == "areas" and len(parts) == 2 and filename.endswith("_BU.json"):
                yield path
            elif len(parts) == 1 and (filename in _TOP_LEVEL_FILES or (
                    filename.startswith("map_") and filename.endswith("_BU.json"))):
                yield path


def stale_files(root="."):
    """(module, path) of each shipped file this root lacks or holds different."""
    installed = os.path.join(install_root(), "modules")
    if os.path.realpath(root) == os.path.realpath(install_root()) or not os.path.isdir(installed):
        return []
    stale = []
    for name in sorted(os.listdir(installed)):
        shipped = _identity(os.path.join(installed, name))
        if shipped is None or _identity(os.path.join(root, "modules", name)) != shipped:
            continue
        for path in sorted(_shipped_files(os.path.join(installed, name))):
            source = os.path.join(installed, name, path)
            target = os.path.join(root, "modules", name, path)
            if not os.path.isfile(target) or not filecmp.cmp(source, target, shallow=False):
                stale.append((name, path))
    return stale


def refresh_shipped_files(root="."):
    """Replace each stale shipped file from the install, one whole file at a time."""
    from core.nql import occupants
    from utils.module_lifecycle import copy_file_verified

    installed = os.path.join(install_root(), "modules")
    for name, path in stale_files(root):
        target = os.path.join(root, "modules", name, path)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        copy_file_verified(os.path.join(installed, name, path), target)
    # Keyed by root and module list, not file stamp, so it would keep old masters.
    occupants._AUTHORED_CACHE.clear()


def reset_unfinished():
    """True when a Reset that replaces shipped files has not reached its last act."""
    try:
        with open("party_tracker.json", encoding="utf-8") as handle:
            return json.load(handle) == RESET_UNFINISHED
    except (OSError, ValueError):
        return False


def no_game():
    """True only when nothing on disk says a game exists. Unreadable is not absent."""
    if os.path.lexists("party_tracker.json"):
        try:
            with open("party_tracker.json", encoding="utf-8") as handle:
                if json.load(handle) != {}:
                    return False
        except (OSError, ValueError):
            return False
    if any(os.path.lexists(path) for path in (
            "live_state.json", "modules/campaign.json", "player_storage.json")):
        return False
    if os.path.lexists(_STARTUP_CHECKPOINT):
        from utils.startup_contract import parse_startup_checkpoint
        try:
            with open(_STARTUP_CHECKPOINT, encoding="utf-8") as handle:
                progress = parse_startup_checkpoint(json.load(handle))
        except (OSError, ValueError):
            return False
        if not progress or progress.get("phase") != "module_selection" or progress.get("module"):
            return False
    return True


def _launch_reset_needed():
    return reset_unfinished() or (no_game() and bool(stale_files()))


def launch_reset():
    """Finish a stopped Reset, or run one for an update when no game exists.

    The check runs again inside Reset's lock, so a second launch does nothing. A
    Reset that fails shows the failure line and the launch goes on.
    """
    try:
        if _launch_reset_needed():
            from utils.reset_campaign import perform_reset_logic

            perform_reset_logic(only_if=_launch_reset_needed)
    except (OSError, ValueError) as exc:
        from utils.player_notice import show_reset_failed

        show_reset_failed(exc)
