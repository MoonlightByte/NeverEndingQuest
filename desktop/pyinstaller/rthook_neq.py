# SPDX-FileCopyrightText: 2026 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

# PyInstaller runtime hook for the desktop server build (#1681): use the
# bundled tiktoken encoding file instead of downloading it on first use.
import os
import sys

_cache = os.path.join(sys._MEIPASS, "tiktoken_cache")
if os.path.isdir(_cache) and not os.environ.get("TIKTOKEN_CACHE_DIR"):
    os.environ["TIKTOKEN_CACHE_DIR"] = _cache
