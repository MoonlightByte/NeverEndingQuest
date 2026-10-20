# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""The typed creation picks of an engine-built hero (#1292; D-1292-1 and its amendment).

Setup archives its history as startup_conversation_archive_<ts>.json at the game root
(utils/startup_wizard.py cleanup_startup_conversation). The newest archive whose final
checkpoint saved this sheet (its character_path) is the creation's. Its startup_engine_build
record is paired by the checkpoint's startup_id, and the finalize proposal just before that
record holds the typed intent the record was built from. Names are never compared and
racialTraits is never read: no matching record is None (the caller's untyped gap).
"""
import glob
import json
import os
from typing import Any, Dict, Optional

from utils.file_operations import safe_read_json

ENGINE_BUILD_PURPOSE = "startup_engine_build"  # utils/startup_wizard.py ENGINE_BUILD_PURPOSE


def _record(item: Any) -> Optional[Dict[str, Any]]:
    try:
        value = json.loads(item.get("content") or "")
    except (AttributeError, TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _same_path(a: Any, b: str) -> bool:
    return isinstance(a, str) and bool(a) and \
        os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def creation_picks(character_path: str, root: str = ".") -> Optional[Dict[str, Any]]:
    """{species_key, choices} from the archived creation of the sheet at ``character_path``, or None."""
    for path in sorted(glob.glob(os.path.join(root, "startup_conversation_archive_*.json")), reverse=True):
        history = safe_read_json(path)
        if not isinstance(history, list):
            continue
        items = [(item.get("role"), _record(item)) for item in history if isinstance(item, dict)]
        checkpoints = [r for _, r in items if r and "startup_checkpoint_version" in r]
        if not checkpoints or not _same_path(checkpoints[-1].get("character_path"), character_path):
            continue
        startup_id = checkpoints[-1].get("startup_id")
        proposal, picks = None, None
        for role, record in items:
            if not record:
                continue
            if role == "assistant" and record.get("decision") == "finalize_character":
                proposal = record
            elif record.get("task_purpose") == ENGINE_BUILD_PURPOSE and startup_id \
                    and record.get("startup_id") == startup_id:
                intent = (proposal or {}).get("intent")
                if isinstance(intent, dict) and intent.get("species_key") and isinstance(intent.get("choices"), dict):
                    picks = {"species_key": intent["species_key"], "choices": intent["choices"],
                             "background_key": intent.get("background_key")}
        # The newest archive that saved this sheet decides: without an engine record it was not built
        # on the engine path, and an older archive of the same path belongs to an earlier game.
        return picks
    return None


def recover_feat_spell_bindings(sheet: Dict[str, Any], character_path: str, root: str = ".") -> bool:
    """Recover missing origin-feat grants from this sheet's paired typed creation."""
    feats = sheet.get("feats") or []
    if not any(isinstance(f, dict) and "grantedSpells" not in f for f in feats):
        return False
    from core.nql.creation_scope import _Data, _feat_spell_points
    data = _Data()
    if not data.ok:
        return False
    grants = {}
    for key, background in data.backgrounds().items():
        origin = next((f for f in data.origins.get("origin_feats") or []
                       if f.get("key") == (background.get("feat_ref") or {}).get("feat_key")), None)
        if origin is None:
            continue
        name = background.get("feat") or origin["name"]
        points = [sid for sid, point in _feat_spell_points(background, data)
                  if point.get("kind") != "cantrip"
                  and str(point.get("option_source") or "").startswith("spells:")]
        if points and any(isinstance(f, dict) and f.get("name") == name
                          and "grantedSpells" not in f for f in feats):
            grants[key] = (name, points)
    # Only typed spell-granting origins can need archive recovery. Ordinary feats never read it.
    if not grants:
        return False
    picked = creation_picks(character_path, root)
    if not picked or picked.get("background_key") not in grants:
        return False
    name, points = grants[picked["background_key"]]
    spells = [spell for sid in points for spell in picked["choices"].get(sid) or []]
    if not spells:
        return False
    changed = False
    for feat in feats:
        if isinstance(feat, dict) and feat.get("name") == name and "grantedSpells" not in feat:
            feat["grantedSpells"] = [{"spell": key, "resource": name} for key in spells]
            changed = True
    return changed
