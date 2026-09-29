# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""A short or long rest for the whole party (the rest action).

The engine refills every pool the rest recovers on every party sheet in one
request (core/nql/resources.rest): a long rest restores hit points, spell slots
and every feature use pool; a short rest restores the pools tagged shortRest
and, for a pact caster, spell slots. Hit dice are not tracked (house rule); any
extra healing the table narrates on a short rest is an ordinary
updateCharacterInfo change. Rest-bound temporary effects are cleared by the
effects lifecycle after the sheets are written. All sheets are written together
or none is.
"""
from typing import Any, Dict, List, Optional

from core.managers.currency_transfer import _run
from core.nql import resources as nql_resources
from utils.encoding_utils import safe_json_load
from utils.enhanced_logger import info


def _party_paths(party: Dict[str, Any]) -> List[str]:
    from core.managers.effects_runtime import _party_sheets

    _sheets, paths = _party_sheets(party)
    return sorted(set(paths.values()))


def execute_rest(rest_type: Any, party_tracker: Optional[Dict[str, Any]] = None,
                 conversation_history: Optional[list] = None) -> Dict[str, Any]:
    kind = str(rest_type or "").strip().lower()
    if kind not in nql_resources.REST_KINDS:
        return {"success": False, "error": f"rest needs restType short or long, not {rest_type!r}"}
    party = party_tracker or safe_json_load("party_tracker.json") or {}
    paths = _party_paths(party)
    if not paths:
        return {"success": False, "error": "no party character sheet could be found"}
    result = _run(paths, lambda sheets, location: nql_resources.rest(sheets, kind, location=location), party)
    if not result.get("success"):
        return result
    outcome = result["outcome"]
    parts = []
    for name, labels in outcome.restored.items():
        parts.append(f"{name}: {', '.join(labels) if labels else 'nothing to recover'}")
    message = f"{kind} rest applied by the rules engine. " + "; ".join(parts) + "."
    from core.managers.effects_runtime import process_effect_lifecycle

    note = process_effect_lifecycle(conversation_history, rest_kind=f"{kind}_rest")
    info(f"REST: {message}", category="character_updates")
    return {"success": True, "message": message, "effects_note": note, "restored": outcome.restored}
