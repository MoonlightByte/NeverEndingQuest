# SPDX-FileCopyrightText: 2026 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Player data root for packaged and hosted worlds (#1681, #1682).

The game reads and writes its state relative to the working directory. A
desktop install or a hosted world keeps that state in its own folder (the
data root) instead of the install folder, so the server changes into the
data root at startup and every cwd-relative path keeps working unchanged.

- resolve_data_root(): --data-dir, else env NEQ_DATA_DIR, else None. None
  means today's behaviour exactly: no chdir, no seeding, no sys.path change.
- prepare_data_root(): first run seeds the root; later launches refresh the
  read-only content (prompts/, schemas/, data/) file by file from the install
  folder, never touching the game-written paths, and add only the modules and
  graphic packs the root lacks. Nothing the game wrote is ever overwritten.
- enter_data_root(): chdir into the root and put it first on sys.path, so the
  config.py saved there is the one every `import config` finds. Children
  inherit NEQ_DATA_DIR and call apply_data_root_path() at their entry point.

Nothing here imports the engine or config.
"""

import os
import shutil
import sys

# Top-level folders whose entries the game writes in place (module files,
# saves, conversation history, pack backups, generated portraits): an entry
# the root lacks is copied; an entry it has is never touched.
_ADD_MISSING_DIRS = ("modules", "graphic_packs")


def install_root():
    """The folder holding the shipped game files (this repository)."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resolve_data_root(argv_dir=None):
    """The data root as an absolute path, or None when none is configured."""
    value = argv_dir or os.environ.get("NEQ_DATA_DIR", "")
    value = value.strip() if isinstance(value, str) else ""
    if not value:
        return None
    return os.path.abspath(os.path.expanduser(value))


_SEED_TMP = ".seed-tmp"


def _seed_entry(source, target, staging):
    """Copy source to target atomically: build it under staging, then rename.

    An interrupted copy leaves only a staging leftover (cleaned on the next
    launch), never a half-copied module, pack or config.py at its real name.
    """
    os.makedirs(staging, exist_ok=True)
    partial = os.path.join(staging, os.path.basename(target))
    if os.path.lexists(partial):
        _remove(partial)
    if os.path.isdir(source):
        shutil.copytree(source, partial)
    else:
        shutil.copy2(source, partial)
    os.replace(partial, target)


def _remove(path):
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path)
    else:
        os.remove(path)


def _add_missing(src_dir, dst_dir, staging):
    """Copy each top-level entry of src_dir that dst_dir lacks; return their names."""
    added = []
    if not os.path.isdir(src_dir):
        return added
    os.makedirs(dst_dir, exist_ok=True)
    for name in sorted(os.listdir(src_dir)):
        source = os.path.join(src_dir, name)
        target = os.path.join(dst_dir, name)
        if os.path.lexists(target):
            continue
        _seed_entry(source, target, os.path.join(staging, os.path.basename(dst_dir)))
        added.append(name)
    return added


def prepare_data_root(root, source=None):
    """Seed or refresh the data root from the install folder.

    Returns the list of copies performed, for the startup log.
    """
    from core.headless.bootstrap import prepare_game_dir

    source = os.path.abspath(source or install_root())
    root = os.path.abspath(root)
    os.makedirs(root, exist_ok=True)
    if root == source:
        return []
    staging = os.path.join(root, _SEED_TMP)
    if os.path.lexists(staging):
        _remove(staging)   # leftovers of an interrupted seed
    # prompts/, schemas/, data/: copied on first run, refreshed file by file
    # afterwards with the game-written data paths kept (#899); a partial first
    # copy is completed by the next launch's refresh.
    copied = prepare_game_dir(root, source)
    for name in _ADD_MISSING_DIRS:
        for entry in _add_missing(os.path.join(source, name), os.path.join(root, name), staging):
            copied.append("%s/%s" % (name, entry))
    config_path = os.path.join(root, "config.py")
    template = os.path.join(source, "config_template.py")
    if not os.path.lexists(config_path) and os.path.isfile(template):
        os.makedirs(staging, exist_ok=True)
        partial = os.path.join(staging, "config.py")
        shutil.copy(template, partial)
        try:
            os.chmod(partial, 0o600)
        except OSError:
            pass
        os.replace(partial, config_path)
        copied.append("config.py")
    if os.path.lexists(staging):
        _remove(staging)
    return copied


def apply_data_root_path():
    """Put NEQ_DATA_DIR first on sys.path; no-op when it is not set."""
    root = resolve_data_root()
    if root is None:
        return None
    while root in sys.path:
        sys.path.remove(root)
    sys.path.insert(0, root)
    return root


def enter_data_root(root):
    """Make root the working directory and the first import location."""
    root = os.path.abspath(root)
    os.environ["NEQ_DATA_DIR"] = root
    os.chdir(root)
    apply_data_root_path()
    return root
