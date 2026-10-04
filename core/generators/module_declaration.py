# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""The module declaration (module_declaration.json): the typed facts about a
module's people, start and links that the roster world reads
(utils/roster_conversion.py).

Shared by the two writers: the module builder (at publication) and the module
stitcher (when a module without a declaration joins the world).
"""
import os
from pathlib import Path

from utils.enhanced_logger import info, warning
from utils.file_operations import safe_write_json


def load_declared_world(module_path, module_name):
    """Engine load of the roster world with the module's declaration, before
    the module is live. Never a gate on publication: a world the engine
    refuses with the declaration but accepts without it sets the declaration
    aside (module_declaration.refused.json), and the module derives as
    before. The module's quests are not part of this load (they are read from
    the live module path); the declaration does not touch them.
    """
    from core.nql import apply
    from utils import roster_conversion

    declared = Path(module_path) / roster_conversion.DECLARATION
    refused = Path(module_path) / "module_declaration.refused.json"

    def world():
        modules = [m for m in roster_conversion.installed_modules(".") if m != module_name]
        modules.append(module_name)
        game = roster_conversion.Game(".", modules, paths={module_name: os.fspath(module_path)})
        source, _ = roster_conversion.world_source(game, roster_conversion.seeds(game, []))
        return source

    try:
        response = apply.call({"world": world()})
        if response.get("ok"):
            info(f"MODULE_DECLARATION: {module_name} loads in the engine with its declaration",
                 category="module_creation")
            return
        reason = response.get("error")
        os.replace(declared, refused)
        try:
            loads_without = bool(apply.call({"world": world()}).get("ok"))
        except Exception:
            os.replace(refused, declared)
            raise
        if loads_without:
            warning(f"MODULE_DECLARATION: the engine refused {module_name} with its declaration "
                    f"({reason}); set aside, the module derives as before",
                    category="module_creation")
            report_path = Path(module_path) / "validation_report.json"
            from utils.file_operations import safe_read_json
            report = safe_read_json(os.fspath(report_path))
            if isinstance(report, dict) and isinstance(report.get("issues"), list):
                report["issues"].append(f"module declaration refused by the engine and set aside: {reason}")
                safe_write_json(os.fspath(report_path), report)
            return
        # Refused either way: the declaration is not the cause; keep it.
        os.replace(refused, declared)
        warning(f"MODULE_DECLARATION: the engine refuses the world with or without "
                f"{module_name}'s declaration ({reason}); declaration kept",
                category="module_creation")
    except apply.EngineUnavailable as exc:
        warning(f"MODULE_DECLARATION: engine unavailable ({exc}); {module_name} published "
                "without the build-time load", category="module_creation")
    except Exception as exc:
        warning(f"MODULE_DECLARATION: build-time load skipped for {module_name} ({exc})",
                category="module_creation")
