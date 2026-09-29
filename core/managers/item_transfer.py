# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""Give an item from one party character to another (the transferItem action).

The engine decides the move (core/nql/transfer.py); this module owns the
files: it resolves both sheets, holds both character leases, projects armor
class on the rewritten sheets, writes both with backup and rollback, and
reports a one-line result. A refusal writes nothing.
"""
import os
import shutil
from datetime import datetime
from typing import Any, Dict, Optional

from core.nql import armor_class
from core.nql import transfer as nql_transfer
from utils.encoding_utils import safe_json_load
from utils.enhanced_logger import debug, info, warning
from utils.file_operations import safe_read_json, safe_write_json


def _resolve(character_name: str) -> Optional[str]:
    """The sheet path for a display or file name, or None when no sheet exists."""
    from updates.update_character_info import (
        detect_character_role,
        fuzzy_match_character_name,
        get_character_path,
    )

    if not isinstance(character_name, str) or not character_name.strip():
        return None
    name = character_name.strip()
    path = get_character_path(name, detect_character_role(name))
    if os.path.exists(path):
        return path
    party = safe_json_load("party_tracker.json") or {}
    matched = fuzzy_match_character_name(name, party)
    if matched:
        path = get_character_path(matched, detect_character_role(matched))
        if os.path.exists(path):
            return path
    return None


def _backup(path: str) -> Optional[str]:
    if not os.path.exists(path):
        return None
    backup = f"{path}.transfer_backup_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    shutil.copy2(path, backup)
    return backup


def _restore(path: str, backup: Optional[str]) -> None:
    if backup and os.path.exists(backup):
        shutil.copy2(backup, path)


def _discard(backup: Optional[str]) -> None:
    if backup and os.path.exists(backup):
        try:
            os.remove(backup)
        except OSError:
            pass


def _projected(sheet: Dict[str, Any]) -> Dict[str, Any]:
    projection = armor_class.project(sheet)
    if projection.applied:
        return projection.sheet
    warning(f"TRANSFER: armor class projection not applied for {sheet.get('name')}: {projection.reason}",
            category="storage_operations")
    return sheet


def execute_transfer(from_character: str, to_character: str, item_name: str, quantity: Any,
                     party_tracker: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run one give. Returns {"success": bool, "message": str} or {"success": False, "error": str}."""
    from updates.update_character_info import _get_character_update_lock
    from utils.path_transaction_lock import path_transaction_lock

    giver_path = _resolve(from_character)
    receiver_path = _resolve(to_character)
    if giver_path is None:
        return {"success": False, "error": f"no character sheet for giver {from_character!r}"}
    if receiver_path is None:
        return {"success": False, "error": f"no character sheet for receiver {to_character!r}"}
    if os.path.normcase(os.path.realpath(giver_path)) == os.path.normcase(os.path.realpath(receiver_path)):
        return {"success": False, "error": "giver and receiver are the same character"}
    if quantity in (None, ""):
        quantity = 1

    party = party_tracker or safe_json_load("party_tracker.json") or {}
    location = str((party.get("worldConditions") or {}).get("currentLocationId") or "party")

    # Both leases, always in path order, so two concurrent gives cannot deadlock.
    first, second = sorted((giver_path, receiver_path))
    with _get_character_update_lock(os.path.basename(first)[:-5]), \
            _get_character_update_lock(os.path.basename(second)[:-5]):
        with path_transaction_lock(first, suffix=".effects.lock", timeout_seconds=30.0) as lease_a, \
                path_transaction_lock(second, suffix=".effects.lock", timeout_seconds=30.0) as lease_b:
            if lease_a is None or lease_b is None:
                return {"success": False, "error": "a character sheet is busy; nothing was moved"}
            giver = safe_read_json(giver_path)
            receiver = safe_read_json(receiver_path)
            if not giver or not receiver:
                return {"success": False, "error": "could not load both character sheets"}

            outcome = nql_transfer.transact(giver, receiver, item_name, quantity, location=location)
            for gap in outcome.gaps:
                debug(f"TRANSFER: genesis gap: {gap}", category="storage_operations")
            if not outcome.ok:
                return {"success": False, "error": outcome.reason}

            giver_out = _projected(outcome.giver)
            receiver_out = _projected(outcome.receiver)
            giver_backup = _backup(giver_path)
            receiver_backup = _backup(receiver_path)
            try:
                if not safe_write_json(giver_path, giver_out):
                    raise RuntimeError("failed to write the giver's sheet")
                if not safe_write_json(receiver_path, receiver_out):
                    raise RuntimeError("failed to write the receiver's sheet")
            except Exception as error:
                _restore(giver_path, giver_backup)
                _restore(receiver_path, receiver_backup)
                _discard(giver_backup)
                _discard(receiver_backup)
                return {"success": False, "error": f"{error}; both sheets restored"}
            _discard(giver_backup)
            _discard(receiver_backup)

    unit = outcome.item_name
    message = f"{giver.get('name')} gave {outcome.quantity} {unit} to {receiver.get('name')}"
    if outcome.unequipped:
        message += f" ({unit} was unequipped for the handoff)"
    if giver_out.get("armorClass") != giver.get("armorClass") or receiver_out.get("armorClass") != receiver.get("armorClass"):
        message += (f". Armor class now: {giver.get('name')} {giver_out.get('armorClass')}, "
                    f"{receiver.get('name')} {receiver_out.get('armorClass')}")
    info(f"SUCCESS: {message}", category="storage_operations")
    return {"success": True, "message": message}
