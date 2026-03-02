# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NPC Arrival State Sync Validator

Validates that narration cannot introduce off-location known NPCs unless
the same response includes a matching state action (moveBackgroundNPC or
updatePartyNPCs add).

This module provides deterministic validation for NPC arrival state sync,
enforcing the rule that known canonical NPCs must not appear in narration
unless they are already present OR the response includes appropriate
state synchronization actions.
"""

import json
import re
from typing import Dict, List, Set, Tuple, Any, Optional


def validate_npc_arrival_state_sync(
    response_json: Dict[str, Any],
    party_tracker_data: Dict[str, Any],
    location_data: Optional[Dict[str, Any]] = None,
    module_npc_names: Optional[Set[str]] = None
) -> Tuple[bool, str]:
    """
    Validate that narration does not introduce off-location known NPCs
    without accompanying state synchronization actions.

    Args:
        response_json: Parsed AI response with 'narration' and 'actions' fields
        party_tracker_data: Current party tracker state
        location_data: Current location data with npcs list (optional)
        module_npc_names: Set of all canonical NPC names in the module (optional)

    Returns:
        Tuple of (is_valid, reason_message)
        - is_valid: True if validation passes, False if failed
        - reason_message: Empty string if valid, actionable error message if invalid
    """
    narration = response_json.get("narration", "")
    actions = response_json.get("actions", [])

    # Build deterministic state sets
    party_members = _build_party_member_set(party_tracker_data)
    present_npcs = _build_present_npc_set(party_tracker_data, location_data)
    known_npcs = _build_known_npc_set(party_tracker_data, location_data, module_npc_names)

    # Detect NPC mentions in narration (case-insensitive, canonical full-name matching)
    mentioned_npcs = _extract_npc_mentions(narration, known_npcs)

    # Find newly mentioned non-present NPCs
    # CRITICAL FIX: Exclude party members (PCs) from NPC arrival checks
    # Party members are controlled by players, not background NPCs
    newly_mentioned = (mentioned_npcs - party_members) - present_npcs

    if not newly_mentioned:
        # All mentioned NPCs are already present - validation passes
        return (True, "")

    # Check for required state actions for each newly mentioned NPC
    missing_actions = []
    for npc_name in sorted(newly_mentioned):
        has_valid_action = _has_arrival_action_for_npc(npc_name, actions)
        if not has_valid_action:
            missing_actions.append(npc_name)

    if missing_actions:
        reason = _format_failure_reason(missing_actions)
        return (False, reason)

    return (True, "")


def _build_party_member_set(party_tracker_data: Dict[str, Any]) -> Set[str]:
    """
    Build set of party member (PC) names.
    Party members are PCs, not NPCs, and should be exempt from NPC arrival checks.
    """
    party_members = set()
    for member_name in party_tracker_data.get("partyMembers", []):
        if member_name and isinstance(member_name, str):
            party_members.add(member_name.lower())
    return party_members


def _build_present_npc_set(
    party_tracker_data: Dict[str, Any],
    location_data: Optional[Dict[str, Any]] = None
) -> Set[str]:
    """
    Build set of currently present NPC names.
    Present = current location NPCs + partyNPCs
    Note: partyMembers (PCs) are not included here - they are tracked separately
    """
    present = set()

    # Add location NPCs
    if location_data and "npcs" in location_data:
        for npc in location_data["npcs"]:
            if isinstance(npc, dict):
                npc_name = npc.get("name", "")
                if npc_name:
                    present.add(npc_name.lower())
            elif isinstance(npc, str):
                present.add(npc.lower())

    # Add party NPCs
    party_npcs = party_tracker_data.get("partyNPCs", [])
    for npc in party_npcs:
        if isinstance(npc, dict):
            npc_name = npc.get("name", "")
            if npc_name:
                present.add(npc_name.lower())
        elif isinstance(npc, str):
            present.add(npc.lower())

    return present


def _build_known_npc_set(
    party_tracker_data: Dict[str, Any],
    location_data: Optional[Dict[str, Any]] = None,
    module_npc_names: Optional[Set[str]] = None
) -> Set[str]:
    """
    Build set of all known canonical NPC names.
    Known = all module NPCs + partyNPCs + location NPCs
    """
    known = set()

    # Add module-level NPCs if provided
    if module_npc_names:
        known.update(name.lower() for name in module_npc_names)

    # Add location NPCs
    if location_data and "npcs" in location_data:
        for npc in location_data["npcs"]:
            if isinstance(npc, dict):
                npc_name = npc.get("name", "")
                if npc_name:
                    known.add(npc_name.lower())
            elif isinstance(npc, str):
                known.add(npc.lower())

    # Add party NPCs
    party_npcs = party_tracker_data.get("partyNPCs", [])
    for npc in party_npcs:
        if isinstance(npc, dict):
            npc_name = npc.get("name", "")
            if npc_name:
                known.add(npc_name.lower())
        elif isinstance(npc, str):
            known.add(npc.lower())

    return known


def _extract_npc_mentions(narration: str, known_npcs: Set[str]) -> Set[str]:
    """
    Extract mentions of known NPCs from narration text.
    Uses case-insensitive canonical full-name matching.

    Returns set of lowercase NPC names that are mentioned.
    """
    mentioned = set()
    narration_lower = narration.lower()

    for npc_name in known_npcs:
        # Use word boundary matching for full canonical names
        # This prevents partial matches (e.g., "Li" matching "Liri")
        pattern = r'\b' + re.escape(npc_name) + r'\b'
        if re.search(pattern, narration_lower):
            mentioned.add(npc_name)

    return mentioned


def _has_arrival_action_for_npc(npc_name: str, actions: List[Dict[str, Any]]) -> bool:
    """
    Check if actions include a valid arrival action for the given NPC.

    Valid actions:
    - moveBackgroundNPC with matching npcName
    - updatePartyNPCs with operation: "add" and matching NPC identity
    """
    npc_name_lower = npc_name.lower()

    for action in actions:
        if not isinstance(action, dict):
            continue

        action_type = action.get("action", "")
        params = action.get("parameters", {})

        if action_type == "moveBackgroundNPC":
            action_npc_name = params.get("npcName", "").lower()
            if action_npc_name == npc_name_lower:
                return True

        elif action_type == "updatePartyNPCs":
            operation = params.get("operation", "").lower()
            if operation == "add":
                npc_data = params.get("npc", {})
                if isinstance(npc_data, dict):
                    npc_data_name = npc_data.get("name", "").lower()
                    if npc_data_name == npc_name_lower:
                        return True
                elif isinstance(npc_data, str):
                    if npc_data.lower() == npc_name_lower:
                        return True

    return False


def _format_failure_reason(missing_actions: List[str]) -> str:
    """
    Format a concise, actionable failure reason message.
    """
    if len(missing_actions) == 1:
        npc = missing_actions[0]
        return (
            f"NPC arrival state sync failed: '{npc}' is mentioned in narration "
            f"but is not currently present at this location. "
            f"Required: Include either 'moveBackgroundNPC' action with npcName='{npc}' "
            f"or 'updatePartyNPCs' operation='add' for this NPC."
        )
    else:
        npcs = ", ".join(f"'{n}'" for n in missing_actions)
        return (
            f"NPC arrival state sync failed: NPCs {npcs} are mentioned in narration "
            f"but are not currently present at this location. "
            f"Required: Include 'moveBackgroundNPC' or 'updatePartyNPCs add' actions "
            f"for each arriving NPC."
        )


class NPCValidationContextError(Exception):
    """Raised when NPC validation context cannot be loaded deterministically."""
    pass


def load_module_npc_names(module_name: str) -> Set[str]:
    """
    Load all canonical NPC names from a module's area files.
    This is a helper for building the full module NPC set.

    Args:
        module_name: The module name (will be normalized with underscores)

    Returns:
        Set of canonical NPC names (lowercase)

    Raises:
        NPCValidationContextError: If module context cannot be loaded
    """
    if not module_name or not module_name.strip():
        raise NPCValidationContextError("Module name is required for NPC validation context")

    npc_names = set()

    try:
        from utils.module_path_manager import ModulePathManager

        normalized_module = module_name.replace(" ", "_")
        path_manager = ModulePathManager(normalized_module)

        # Get all area IDs and iterate through area files
        area_ids = path_manager.get_area_ids()
        
        if not area_ids:
            raise NPCValidationContextError(f"No area files found for module '{module_name}'")
        
        for area_id in area_ids:
            try:
                area_file = path_manager.get_area_path(area_id)
                with open(area_file, "r", encoding="utf-8") as f:
                    area_data = json.load(f)
                for location in area_data.get("locations", []):
                    for npc in location.get("npcs", []):
                        if isinstance(npc, dict):
                            npc_name = npc.get("name", "")
                            if npc_name:
                                npc_names.add(npc_name.lower())
                        elif isinstance(npc, str):
                            npc_names.add(npc.lower())
            except (FileNotFoundError, json.JSONDecodeError) as e:
                raise NPCValidationContextError(f"Failed to load area file for '{area_id}': {str(e)}")

    except NPCValidationContextError:
        raise
    except Exception as e:
        raise NPCValidationContextError(f"Failed to load module NPC context: {str(e)}")

    return npc_names
