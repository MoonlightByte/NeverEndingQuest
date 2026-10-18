# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""A module's human title, read from the module's own declared name."""

import os

from utils.encoding_utils import safe_json_load


def module_display_title(module_id, modules_root="modules"):
    """A module's human title: its declared name, else the id with spaces.

    The declared name is module_context.json's ``module_name`` (older modules:
    ``campaign_name``), so punctuation such as an apostrophe survives. An id
    written with spaces names the same folder as its underscored form. Never
    raises.
    """
    module_id = str(module_id or "").strip().replace(" ", "_")
    fallback = module_id.replace("_", " ").strip()
    declared = ""
    if module_id and "/" not in module_id and "\\" not in module_id and module_id not in (".", ".."):
        try:
            context = safe_json_load(os.path.join(modules_root, module_id, "module_context.json"))
            if isinstance(context, dict):
                for key in ("module_name", "campaign_name"):
                    value = context.get(key)
                    if isinstance(value, str) and value.strip():
                        declared = value.strip()
                        break
        except Exception:
            declared = ""
    return declared or fallback
