# -*- mode: python ; coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
#
# PyInstaller one-folder build of the game server for the desktop app (#1681).
# Run through build.ps1 (Windows) or:
#   pyinstaller --noconfirm --distpath dist-server --workpath build-server desktop/pyinstaller/neq-server.spec
# Output: dist-server/neq-server/run_web(.exe) with its files in _internal/.
#
# Shipped data is the git-tracked content of the listed folders, so local
# saves, logs and caches in a working copy never enter the build. The React
# player (web/frontend/dist) is build output and must be current first.

import os
import subprocess
import sys

from PyInstaller.utils.hooks import copy_metadata

ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))
WINDOWS = sys.platform == "win32"


def tracked(folder):
    """(file, destination folder) for every git-tracked file under folder."""
    names = subprocess.run(["git", "-C", ROOT, "ls-files", "-z", "--", folder], check=True,
                           capture_output=True).stdout.decode("utf-8").split("\0")
    pairs = [(os.path.join(ROOT, name), os.path.dirname(name)) for name in names if name]
    if not pairs:
        raise SystemExit("neq-server.spec: no tracked files under %s" % folder)
    return pairs


def built(folder):
    """(file, destination folder) for every file under a build-output folder."""
    base = os.path.join(ROOT, folder)
    pairs = []
    for dirpath, _dirs, files in os.walk(base):
        for name in files:
            path = os.path.join(dirpath, name)
            pairs.append((path, os.path.dirname(os.path.relpath(path, ROOT))))
    return pairs


dist_index = os.path.join(ROOT, "web", "frontend", "dist", "index.html")
if not os.path.isfile(dist_index):
    raise SystemExit("neq-server.spec: web/frontend/dist is missing; run python run_web.py --prepare-frontend first")

datas = []
# Package metadata read at runtime (verified on Windows, w2 probe B).
for dist_name in ("flask-socketio", "python-socketio", "python-engineio", "pillow", "openai"):
    datas += copy_metadata(dist_name)
for folder in ("prompts", "data", "schemas", "modules", "graphic_packs", "web/templates", "web/static"):
    datas += tracked(folder)
datas += built("web/frontend/dist")
for name in ("config_template.py", "VERSION", "LICENSE", "LICENSE-APACHE", "LICENSE-SRD", "LICENSING.md"):
    datas.append((os.path.join(ROOT, name), "."))
# The rules engine: the binaries for this platform and their version files.
engine_suffix = ".exe" if WINDOWS else ""
for name in ("firelight-apply" + engine_suffix, "nql-apply" + engine_suffix,
             "FIRELIGHT_ENGINE_VERSION.txt", "NQL_ENGINE_VERSION.txt"):
    datas.append((os.path.join(ROOT, "bin", name), "bin"))
# tiktoken's cl100k_base file, fetched and hash-checked by build.ps1, so the
# token counter never downloads it at run time (see rthook_neq.py).
tiktoken_cache = os.environ.get("NEQ_TIKTOKEN_CACHE")
if tiktoken_cache:
    for name in os.listdir(tiktoken_cache):
        datas.append((os.path.join(tiktoken_cache, name), "tiktoken_cache"))

hiddenimports = [
    "engineio.async_drivers.threading",
    "tiktoken_ext",
    "tiktoken_ext.openai_public",
    # Started as script children; run as modules by utils/frozen_dispatch.py.
    "utils.capture.live_provider_call",
    "core.generators.combat_builder",
    "core.generators.monster_builder",
]
if WINDOWS:
    hiddenimports.append("keyring.backends.Windows")

a = Analysis(
    [os.path.join(ROOT, "run_web.py")],
    pathex=[ROOT],
    datas=datas,
    hiddenimports=hiddenimports,
    runtime_hooks=[os.path.join(SPECPATH, "rthook_neq.py")],
    excludes=["tests", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="run_web",
    console=True,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, upx=False, name="neq-server")
