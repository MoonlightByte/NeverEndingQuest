# SPDX-FileCopyrightText: 2026 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Script children of a frozen (PyInstaller) build (#1681).

The game starts some helpers as [sys.executable, <script>.py, ...]: the
provider child (utils/capture/live_provider_call.py), combat_builder and
monster_builder. In a frozen build sys.executable is the game's own exe and
the scripts exist only as bundled modules, so run_web calls
run_frozen_script() first thing: a script path inside the bundle runs as its
module under __main__, with the data root first on sys.path. Outside a
frozen build nothing here runs.
"""

import os
import runpy
import sys


def frozen_script_module(argv):
    """The bundled module name a frozen child was started to run, or None."""
    if not getattr(sys, "frozen", False) or len(argv) < 2:
        return None
    script = argv[1]
    if not script.endswith((".py", ".pyc")):
        return None
    bundle = os.path.realpath(getattr(sys, "_MEIPASS", os.path.dirname(sys.executable)))
    path = os.path.realpath(script)
    try:
        if os.path.commonpath([bundle, path]) != bundle:
            return None
    except ValueError:  # another drive on Windows
        return None
    return os.path.splitext(os.path.relpath(path, bundle))[0].replace(os.sep, ".")


def run_frozen_script(argv):
    """Run the script child named in argv as its module; False when argv is not one."""
    module = frozen_script_module(argv)
    if module is None:
        return False
    # The bundle holds config_template.py only; the player's config.py is in
    # the data root (inherited NEQ_DATA_DIR) or, without one, the working folder.
    from utils.data_root import apply_data_root_path
    if apply_data_root_path() is None:
        sys.path.insert(0, os.getcwd())
    sys.argv = [argv[1]] + list(argv[2:])
    runpy.run_module(module, run_name="__main__", alter_sys=True)
    return True
