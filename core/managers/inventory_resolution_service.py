# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Turn-scoped runtime access to T109 inventory resolution.

WHY THIS EXISTS
Gameplay code used to decide what an accepted response referred to by reading
words out of it: a party name found as a substring, a verb in a list, the
letters "storag" inside a free-text reason, a preposition anywhere in a
sentence. Every one of those is brittle in exactly the way that loses items and
refuses legitimate cross-actor storage.

This service is the single seam through which those decisions now get their
answer. It hands the T109 callsite the REAL roster, the REAL resource rows, and
the REAL containers, and caches the derived facts for the turn.

Boundaries:
  * It never decides anything. It resolves references; the deterministic
    helpers in utils/inventory_resolution.py derive facts, and the call sites
    own every conservation and arithmetic rule as before.
  * It never raises into gameplay. An unavailable resolution returns None,
    which means NO CLAIM. No claim is not permission: every call site must
    fail CLOSED on it and refuse the turn. It must never fall back to reading
    words, and it must never commit.
  * It is bounded, but the bound is sized for a WHOLE turn. A turn resolves
    one storage description plus one changes string per character action; the
    ceiling below covers that with room to spare, because silently degrading
    partway through a turn is not allowed. When the ceiling really is reached,
    the remaining strings get no claim and their call sites refuse.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Mapping, Optional, Sequence

from utils.encoding_utils import safe_json_load
from utils.enhanced_logger import debug, warning
from utils.inventory_resolution import (
    ResolvedTurn,
    build_resolution_snapshot,
    prose_key,
)

# One turn may legitimately name several distinct things (a storage
# description plus one changes string per character action). A response is
# capped well below this in practice; the ceiling is deliberately sized so an
# ordinary turn NEVER runs out mid-way, because a budget that quietly stops
# answering turns every downstream guard into a fail-open. Each distinct
# string costs at most two calls (one attempt plus one correction retry), so
# this covers twelve distinct strings in a single turn.
MAX_RESOLUTION_CALLS_PER_TURN = 24
# Per-string ceiling: the initial resolve plus one bounded correction retry.
MAX_CALLS_PER_STRING = 2
MAX_PARTY_SHEETS = 16


def _party_member_names(party_tracker: Mapping[str, Any]) -> tuple:
    names = []
    for value in party_tracker.get("partyMembers") or []:
        if isinstance(value, str) and value.strip():
            names.append(value.strip())
        elif isinstance(value, Mapping):
            name = value.get("name")
            if isinstance(name, str) and name.strip():
                names.append(name.strip())
    for value in party_tracker.get("partyNPCs") or []:
        if isinstance(value, Mapping):
            name = value.get("name")
            if isinstance(name, str) and name.strip():
                names.append(name.strip())
        elif isinstance(value, str) and value.strip():
            names.append(value.strip())
    return tuple(dict.fromkeys(names))[:MAX_PARTY_SHEETS]


def _character_sheets(names: Sequence[str]) -> tuple:
    from utils.module_path_manager import ModulePathManager

    try:
        party = safe_json_load("party_tracker.json")
        module = (
            str(party.get("module") or "").replace(" ", "_")
            if isinstance(party, Mapping)
            else None
        )
        path_manager = ModulePathManager(module) if module else ModulePathManager()
    except Exception:
        path_manager = ModulePathManager()
    sheets = []
    for name in names:
        try:
            path = path_manager.get_character_path(name)
            if not os.path.exists(path):
                continue
            sheet = safe_json_load(path)
        except Exception:
            continue
        if isinstance(sheet, Mapping) and sheet.get("name"):
            sheets.append(sheet)
    return tuple(sheets)


def _containers(location_id: str) -> tuple:
    from core.managers.storage_processor import build_accessible_storage_snapshot

    try:
        snapshot = build_accessible_storage_snapshot()
    except Exception:
        return ()
    if not snapshot.get("available"):
        # Bounds were exceeded or storage is malformed. Resolving against a
        # partial container set could name the wrong chest, so resolve
        # against no containers at all and let the site get no claim.
        return ()
    containers = list(snapshot.get("containers") or [])
    for remote in snapshot.get("knownContainersElsewhere") or []:
        if isinstance(remote, Mapping):
            containers.append(dict(remote))
    return tuple(containers)


class InventoryResolutionService(ResolvedTurn):
    """Lazily resolve accepted prose against real state, once per string."""

    def __init__(
        self,
        party_tracker: Optional[Mapping[str, Any]] = None,
        *,
        speaker: Any = None,
        budget: int = MAX_RESOLUTION_CALLS_PER_TURN,
    ) -> None:
        super().__init__()
        self._party_tracker = party_tracker if isinstance(party_tracker, Mapping) else {}
        self._speaker = speaker
        self._budget = int(budget) if isinstance(budget, int) and budget > 0 else 0
        self._cache: Dict[str, Optional[Dict[str, Any]]] = {}
        self._base: Optional[Dict[str, Any]] = None
        self._base_failed = False

    # -- state packet ------------------------------------------------------
    def _base_state(self) -> Optional[Dict[str, Any]]:
        if self._base is not None or self._base_failed:
            return self._base
        try:
            party_tracker = self._party_tracker
            if not party_tracker:
                loaded = safe_json_load("party_tracker.json")
                party_tracker = loaded if isinstance(loaded, Mapping) else {}
            world = party_tracker.get("worldConditions") or {}
            location = {
                "id": world.get("currentLocationId") or "",
                "name": world.get("currentLocation") or "",
            }
            names = _party_member_names(party_tracker)
            sheets = _character_sheets(names)
            if not names or not sheets:
                self._base_failed = True
                return None
            self._base = {
                "party": names,
                "characters": sheets,
                "containers": _containers(str(location["id"])),
                "location": location,
                "speaker": self._speaker or (names[0] if names else ""),
            }
        except Exception as exc:
            self._base_failed = True
            warning(
                f"T109 state packet unavailable; resolution disabled this turn: {exc}",
                category="character_updates",
            )
            return None
        return self._base

    # -- resolution --------------------------------------------------------
    def facts_for(self, text: Any) -> Optional[Dict[str, Any]]:
        """Return derived facts for one accepted prose string, or None.

        None means "no claim": the caller must not decide anything from the
        prose itself.
        """
        key = prose_key(text)
        if not key:
            return None
        if key in self._cache:
            return self._cache[key]
        facts = self._resolve(text)
        self._cache[key] = facts
        return facts

    def _resolve(self, text: Any) -> Optional[Dict[str, Any]]:
        base = self._base_state()
        if base is None or self._budget <= 0:
            return None
        try:
            snapshot = build_resolution_snapshot(
                party=base["party"],
                characters=base["characters"],
                containers=base["containers"],
                location=base["location"],
                speaker=base["speaker"],
                action=text,
            )
        except Exception as exc:
            warning(
                f"T109 snapshot construction failed: {exc}",
                category="character_updates",
            )
            return None

        from core.ai.inventory_resolver import (
            InventoryResolutionError,
            resolve_inventory_facts,
        )

        correction = None
        # One initial call plus at most one correction retry, each charged to
        # the turn ceiling. Running out returns None, which every call site
        # treats as a refusal -- never as permission.
        for _attempt in range(MAX_CALLS_PER_STRING):
            if self._budget <= 0:
                warning(
                    "T109 per-turn resolution budget exhausted; the remaining "
                    "references have no claim and their guards fail closed",
                    category="character_updates",
                )
                return None
            self._budget -= 1
            try:
                resolved = resolve_inventory_facts(snapshot, correction=correction)
            except InventoryResolutionError as exc:
                correction = getattr(exc, "correction", None)
                debug(
                    f"T109 resolution attempt failed: {exc}",
                    category="character_updates",
                )
                if not correction:
                    return None
                continue
            except Exception as exc:
                warning(
                    f"T109 resolution unavailable: {exc}",
                    category="character_updates",
                )
                return None
            facts = resolved.get("facts")
            if not isinstance(facts, Mapping):
                return None
            # Proof of execution for acceptance runs: this line only appears
            # when a real T109 call resolved real state.
            debug(
                "T109 resolved intent="
                f"{facts.get('intent')} actor="
                f"{(facts.get('actor') or {}).get('resolved')} rows="
                f"{len(facts.get('facts') or ())}",
                category="character_updates",
            )
            return facts
        return None
