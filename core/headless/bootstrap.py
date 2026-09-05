# SPDX-FileCopyrightText: 2026 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Non-interactive first-run bootstrap for headless mode.

The stock entry points dead-end on input('Press Enter to exit...') when
config.py is missing (main.py main(), run_web.py), and the startup wizard
is 10 blocking prompts. Headless mode must never prompt, so this module:

- creates config.py from config_template.py, injecting OPENAI_API_KEY from
  the environment when available;
- prepares an isolated game directory (fixture) by copying the static
  content a cwd-relative engine needs (schemas/, prompts/, data/,
  modules/<module>/);
- seeds a player character + party_tracker.json through the SAME repair /
  validation / save chain the wizard uses, which makes
  startup_required() return False and skips the wizard entirely.

Nothing here imports the engine at module scope: config.py must exist
before engine modules load, so engine imports happen inside functions.
"""

import os
import re
import shutil

_STATIC_DIRS = ("schemas", "prompts", "data")

_RUNTIME_DIRS = (
    # Mirrors the required_dirs list in main.main(), which headless (like
    # web mode) bypasses by calling main_game_loop() directly.
    "modules/conversation_history",
    "modules/campaign_archives",
    "modules/campaign_summaries",
    "modules/backups",
    "modules/logs",
    "modules/encounters",
    "save_games",
    "characters",
    "combat_logs",
)


class BootstrapError(RuntimeError):
    """A non-interactive bootstrap step could not be completed."""


def ensure_config(repo_root):
    """Make sure config.py exists at the repo root. Never prompts.

    Returns one of: 'exists', 'created', 'created_without_key'.
    """
    config_path = os.path.join(repo_root, "config.py")
    if os.path.exists(config_path):
        return "exists"
    template_path = os.path.join(repo_root, "config_template.py")
    if not os.path.exists(template_path):
        raise BootstrapError(
            "config.py is missing and config_template.py was not found at %s"
            % repo_root)
    with open(template_path, "r", encoding="utf-8") as handle:
        contents = handle.read()
    env_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if env_key:
        contents, replaced = re.subn(
            r'^OPENAI_API_KEY\s*=\s*"[^"]*"',
            'OPENAI_API_KEY = "%s"' % env_key,
            contents,
            count=1,
            flags=re.MULTILINE,
        )
        if not replaced:
            raise BootstrapError(
                "could not find the OPENAI_API_KEY line in config_template.py")
    with open(config_path, "w", encoding="utf-8") as handle:
        handle.write(contents)
    try:
        os.chmod(config_path, 0o600)
    except OSError:
        pass
    return "created" if env_key else "created_without_key"


def ensure_runtime_dirs():
    """Create the runtime directories main.main() would have created."""
    for dir_path in _RUNTIME_DIRS:
        os.makedirs(dir_path, exist_ok=True)


def prepare_game_dir(game_dir, repo_root, module=None):
    """Populate an isolated game directory with the static content the
    cwd-relative engine needs. Copies are skipped when already present, so
    re-running against an existing fixture is cheap and non-destructive.

    Returns the list of copies performed (for logging).
    """
    game_dir = os.path.abspath(game_dir)
    repo_root = os.path.abspath(repo_root)
    os.makedirs(game_dir, exist_ok=True)
    copied = []
    if game_dir == repo_root:
        return copied
    for name in _STATIC_DIRS:
        src = os.path.join(repo_root, name)
        dst = os.path.join(game_dir, name)
        if os.path.isdir(src) and not os.path.exists(dst):
            ignore = None
            if name == "data":
                def ignore_private_runtime(directory, names):
                    normalized = os.path.normpath(directory).replace("\\", "/")
                    if normalized.endswith("/data/companion_memories"):
                        return [
                            value
                            for value in names
                            if value.endswith((".json", ".lock", ".tmp", ".bak"))
                        ]
                    return []

                ignore = ignore_private_runtime
            shutil.copytree(src, dst, ignore=ignore)
            copied.append(name)
    if module:
        dst = os.path.join(game_dir, "modules", module)
        if not os.path.exists(dst):
            # Copy from the repo only when the game dir does not already
            # hold the module (e.g. one just generated there by
            # build-module).
            src = os.path.join(repo_root, "modules", module)
            if not os.path.isdir(src):
                raise BootstrapError(
                    "module %r found in neither %s nor %s"
                    % (module, dst, src))
            shutil.copytree(src, dst)
            copied.append("modules/%s" % module)
    return copied


def run_engine_prechecks():
    """BU-template initialization + calendar migration, as main.main() does.

    Must be called with cwd set to the game directory and config.py present.
    """
    from utils.startup_wizard import initialize_game_files_from_bu
    initialize_game_files_from_bu()
    from utils.calendar_migration import run_calendar_migration
    run_calendar_migration()


def seed_character(character_file, module_name):
    """Install a pre-made character and point party_tracker at it.

    Runs the character through the wizard's own repair + schema validation
    chain before saving, so a bad seed fails loudly here instead of
    corrupting a session later. On success startup_required() is False and
    the interactive wizard never runs.

    Returns the character's display name.
    """
    import json
    try:
        with open(character_file, "r", encoding="utf-8") as handle:
            character_data = json.load(handle)
    except (OSError, ValueError) as exc:
        raise BootstrapError(
            "could not read character file %s: %s" % (character_file, exc))
    if not isinstance(character_data, dict) or not character_data.get("name"):
        raise BootstrapError(
            "character file %s must be a JSON object with a 'name'"
            % character_file)

    from utils.startup_wizard import (
        auto_fix_character_data,
        validate_character_with_recovery,
        save_character_to_module,
        update_party_tracker,
    )
    character_data = auto_fix_character_data(character_data)
    valid, validation_error = validate_character_with_recovery(character_data)
    if not valid:
        raise BootstrapError(
            "character file %s failed schema validation: %s"
            % (character_file, validation_error))
    if not save_character_to_module(character_data, module_name):
        raise BootstrapError(
            "failed to save character %r into module %r"
            % (character_data.get("name"), module_name))
    if not update_party_tracker(module_name, character_data["name"]):
        raise BootstrapError("failed to update party_tracker.json")
    return character_data["name"]
