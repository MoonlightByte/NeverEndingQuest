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
from typing import Dict, List, Set, Tuple, Any, Optional, Literal


_NPC_MENTION_STOPWORDS: Set[str] = {
    "the", "a", "an", "and", "or", "of", "to", "for", "from",
    "in", "on", "at", "by", "with", "without", "into", "over",
    "under", "near", "around", "through"
}


_NPC_TOKEN_EQUIVALENTS: Dict[str, str] = {
    "prisoner": "captured",
    "captive": "captured",
    "detained": "captured",
    "detainee": "captured",
}


_EXPLICIT_ARRIVAL_VERBS: Set[str] = {
    "arrive", "arrives", "arrived", "arriving",
    "enter", "enters", "entered", "entering",
    "join", "joins", "joined", "joining",
    "appear", "appears", "appeared", "appearing",
    "emerge", "emerges", "emerged", "emerging",
    "approach", "approaches", "approached", "approaching",
    "step", "steps", "stepped", "stepping",
    "arrive from", "arrives from", "arrived from", "arriving from",
    "enter from", "enters from", "entered from", "entering from",
    "emerge from", "emerges from", "emerged from", "emerging from",
    "appear from", "appears from", "appeared from", "appearing from",
    "step out", "steps out", "stepped out", "stepping out",
    "come from", "comes from", "came from", "coming from"
}


_JOIN_SEMANTICS_PATTERNS = [
    r"\bjoin(?:s|ed|ing)?\s+(?:the\s+)?party\b",
    r"\btravel(?:s|ed|ing)?\s+with\s+(?:you|us|the\s+party)\b",
    r"\bcome(?:s|ing)?\s+with\s+(?:you|us)\b",
    r"\baccompany(?:ies|ied|ing)?\s+(?:you|us|the\s+party)\b",
    r"\bfollow(?:s|ed|ing)?\s+(?:you|us|the\s+party)\b",
]


_SCENE_PRESENCE_USER_CUE_PATTERNS = [
    r"\bcall\b",
    r"\bcall\s+out\b",
    r"\bhail\b",
    r"\bspeak\b",
    r"\btalk\b",
    r"\bask\b",
    r"\blook\s+for\b",
    r"\bfind\b",
    r"\bseek\b",
    r"\bwhere\s+is\b",
    r"\bhermit\b",
    r"\brefuge\b",
]


class IdentityResolutionResult:
    """
    Result container for NPC identity resolution.
    
    Attributes:
        status: One of "matched", "ambiguous", "unmatched"
        canonical_name: The resolved canonical name if status is "matched"
        candidates: List of ambiguous candidate names if status is "ambiguous"
    """
    def __init__(
        self,
        status: Literal["matched", "ambiguous", "unmatched"],
        canonical_name: Optional[str] = None,
        candidates: Optional[List[str]] = None
    ):
        self.status = status
        self.canonical_name = canonical_name
        self.candidates = candidates or []
    
    def __repr__(self):
        if self.status == "matched":
            return f"IdentityResolutionResult(status='matched', canonical_name='{self.canonical_name}')"
        elif self.status == "ambiguous":
            return f"IdentityResolutionResult(status='ambiguous', candidates={self.candidates})"
        else:
            return "IdentityResolutionResult(status='unmatched')"


def _normalize_name_for_matching(name: str) -> str:
    """
    Normalize a name for comparison.
    
    - Lowercase
    - Strip leading/trailing whitespace
    - Collapse internal whitespace to single space
    - Remove common punctuation (apostrophes, hyphens, periods)
    """
    if not name:
        return ""
    
    normalized = name.lower().strip()
    
    normalized = re.sub(r"['\-\._]", "", normalized)
    
    normalized = re.sub(r"\s+", " ", normalized)
    
    return normalized


def _extract_name_tokens(name: str) -> Set[str]:
    """
    Extract individual tokens/words from a name.
    
    Returns set of normalized tokens (lowercase, punctuation removed).
    """
    if not name:
        return set()
    
    normalized = _normalize_name_for_matching(name)
    
    tokens = set()
    for token in normalized.split():
        canonical_token = _NPC_TOKEN_EQUIVALENTS.get(token, token)
        tokens.add(canonical_token)
    
    return tokens


def _is_negated_mention(narration_lower: str, match_start: int, match_end: int) -> bool:
    """
    Detect whether a matched NPC name/token appears in explicit absence context.

    Prevents false positives for phrases like:
    - "There are no Harvest Witnesses here"
    - "No gathering of the Harvest Witnesses is present"
    - "Harvest Witnesses are not present"
    """
    prefix_context = narration_lower[max(0, match_start - 48):match_start]
    suffix_context = narration_lower[match_end:min(len(narration_lower), match_end + 48)]

    prefix_patterns = [
        r"\bno\s+(?:\w+\s+){0,6}$",
        r"\bwithout\s+(?:\w+\s+){0,6}$",
        r"\bthere\s+(?:is|are|was|were)\s+no\s+(?:\w+\s+){0,6}$",
        r"\bnot\s+(?:a|an|any)\s+(?:\w+\s+){0,5}$",
    ]

    suffix_patterns = [
        r"^\s*(?:are|is|were|was)\s+not\s+(?:present|here|visible)\b",
        r"^\s*not\s+(?:present|here|visible)\b",
        r"^\s*(?:remain|remains)\s+absent\b",
        r"^\s*(?:are|is|were|was)\s+absent\b",
    ]

    for pattern in prefix_patterns:
        if re.search(pattern, prefix_context):
            return True

    for pattern in suffix_patterns:
        if re.search(pattern, suffix_context):
            return True

    return False


def resolve_npc_identity(
    input_name: str,
    candidate_names: Set[str]
) -> IdentityResolutionResult:
    """
    Resolve an input name to a canonical NPC identity from candidate set.
    
    Matching order:
    1) Exact normalized equality
    2) Unique token-subset match (input tokens are subset of one candidate)
    3) Otherwise ambiguous (multiple matches) or unmatched
    
    Args:
        input_name: The name to resolve (may be short form or variant)
        candidate_names: Set of canonical candidate names to match against
    
    Returns:
        IdentityResolutionResult with status and resolved/candidate info
    """
    if not input_name or not candidate_names:
        return IdentityResolutionResult(status="unmatched")
    
    input_normalized = _normalize_name_for_matching(input_name)
    input_tokens = _extract_name_tokens(input_name)
    
    if not input_normalized:
        return IdentityResolutionResult(status="unmatched")
    
    for candidate in candidate_names:
        candidate_normalized = _normalize_name_for_matching(candidate)
        if candidate_normalized == input_normalized:
            return IdentityResolutionResult(status="matched", canonical_name=candidate)
    
    token_match_candidates = []
    
    for candidate in candidate_names:
        candidate_tokens = _extract_name_tokens(candidate)
        
        if input_tokens and input_tokens.issubset(candidate_tokens):
            token_match_candidates.append(candidate)
    
    if len(token_match_candidates) == 1:
        return IdentityResolutionResult(
            status="matched",
            canonical_name=token_match_candidates[0]
        )
    elif len(token_match_candidates) > 1:
        return IdentityResolutionResult(
            status="ambiguous",
            candidates=token_match_candidates
        )
    
    return IdentityResolutionResult(status="unmatched")


def resolve_npc_identity_batch(
    input_names: Set[str],
    candidate_names: Set[str]
) -> Tuple[Set[str], Set[str], Set[str]]:
    """
    Resolve multiple input names against a candidate set.
    
    Args:
        input_names: Set of input names to resolve
        candidate_names: Set of canonical candidate names
    
    Returns:
        Tuple of (matched_canonical_names, ambiguous_input_names, unmatched_input_names)
        - matched_canonical_names: Set of canonical names that were matched
        - ambiguous_input_names: Set of original input names that matched multiple candidates
        - unmatched_input_names: Set of original input names that matched no candidates
    """
    matched_canonical = set()
    ambiguous_inputs = set()
    unmatched_inputs = set()
    
    for input_name in input_names:
        result = resolve_npc_identity(input_name, candidate_names)
        
        if result.status == "matched" and result.canonical_name:
            matched_canonical.add(result.canonical_name)
        elif result.status == "ambiguous":
            ambiguous_inputs.add(input_name)
        else:
            unmatched_inputs.add(input_name)
    
    return matched_canonical, ambiguous_inputs, unmatched_inputs


def _has_explicit_arrival_semantics(narration: str, npc_mentions: Set[str]) -> bool:
    """
    Detect if narration contains explicit arrival semantics for NPC mentions.
    
    Explicit arrival = verbs like arrive, enter, join, appear, emerge, approach, etc.
    These verbs signal intentional NPC movement rather than incidental narration.
    
    Args:
        narration: The narration text
        npc_mentions: Set of NPC names/tokens mentioned (lowercase)
    
    Returns:
        True if any explicit arrival verb found in proximity to NPC mentions
    """
    narration_lower = narration.lower()
    
    # Check for explicit arrival verbs in the narration
    for verb_phrase in _EXPLICIT_ARRIVAL_VERBS:
        if verb_phrase in narration_lower:
            # If an arrival verb exists, verify it's near an NPC mention
            # to avoid false positives on generic "arrive" usage
            for npc in npc_mentions:
                # Look for patterns like "NPC arrives" or "arrives NPC"
                # within reasonable proximity (within 100 chars of mention)
                for match in re.finditer(r'\b' + re.escape(npc) + r'\b', narration_lower):
                    start = max(0, match.start() - 100)
                    end = min(len(narration_lower), match.end() + 100)
                    context = narration_lower[start:end]
                    if verb_phrase in context:
                        return True
    
    return False


def _has_join_semantics(narration: str) -> bool:
    """Return True when narration implies durable party membership semantics."""
    narration_lower = narration.lower()
    return any(re.search(pattern, narration_lower) for pattern in _JOIN_SEMANTICS_PATTERNS)


def _has_scene_presence_user_cue(user_utterance: Optional[str]) -> bool:
    """Return True when user input indicates local NPC interaction intent."""
    if not isinstance(user_utterance, str):
        return False
    utterance_lower = user_utterance.lower().strip()
    if not utterance_lower:
        return False
    return any(re.search(pattern, utterance_lower) for pattern in _SCENE_PRESENCE_USER_CUE_PATTERNS)


def _build_scene_presence_inferred_action(
    canonical_npc_name: str,
    current_location_hint: str,
) -> Dict[str, Any]:
    """Build inferred move action for safe scene-presence reconciliation."""
    return {
        "action": "moveBackgroundNPC",
        "parameters": {
            "npcName": canonical_npc_name,
            "context": "Reconcile-first scene presence inferred from narration",
            "currentLocation": current_location_hint,
        },
    }


def evaluate_npc_arrival_state_sync_decision(
    response_json: Dict[str, Any],
    party_tracker_data: Dict[str, Any],
    location_data: Optional[Dict[str, Any]] = None,
    module_npc_names: Optional[Set[str]] = None,
    is_travel_intent: bool = False,
    user_utterance: Optional[str] = None,
    destination_location_data: Optional[Dict[str, Any]] = None,
    source_location_hint: str = "",
) -> Dict[str, Any]:
    """Evaluate deterministic NPC state-sync decision with optional reconciliation."""
    narration = response_json.get("narration", "")
    actions = response_json.get("actions", [])

    if not isinstance(narration, str):
        narration = str(narration or "")
    if not isinstance(actions, list):
        actions = []

    party_members_canonical = _build_party_member_canonical_set(party_tracker_data)

    present_npcs_canonical = _build_present_npc_canonical_set(party_tracker_data, location_data)
    destination_present_npcs_canonical = _build_present_npc_canonical_set({}, destination_location_data)

    known_npcs_lower = _build_known_npc_set(party_tracker_data, location_data, module_npc_names)
    known_npcs_canonical = _build_known_npc_canonical_set(party_tracker_data, location_data, module_npc_names)

    has_transition_action = any(
        isinstance(action, dict) and action.get("action") in {"transitionLocation", "updatePartyTracker"}
        for action in actions
    )

    mentioned_npcs_lower = _extract_npc_mentions(narration, known_npcs_lower)
    if not mentioned_npcs_lower:
        return {
            "valid": True,
            "reason": "",
            "inferred_actions": [],
            "reconciliation": "none",
            "missing_actions": [],
        }

    has_explicit_arrival = _has_explicit_arrival_semantics(narration, mentioned_npcs_lower)
    has_join_semantics = _has_join_semantics(narration)

    missing_actions: Set[str] = set()
    ambiguous_mentions = set()

    for mentioned_lower in mentioned_npcs_lower:
        for party_member in party_members_canonical:
            if party_member.lower() == mentioned_lower:
                mentioned_lower = None
                break
            result = resolve_npc_identity(mentioned_lower, {party_member})
            if result.status == "matched":
                mentioned_lower = None
                break
            mentioned_tokens = _extract_name_tokens(mentioned_lower)
            party_tokens = _extract_name_tokens(party_member)
            if mentioned_tokens and party_tokens and party_tokens.issubset(mentioned_tokens):
                mentioned_lower = None
                break

        if mentioned_lower is None:
            continue

        for present_npc in present_npcs_canonical:
            if present_npc.lower() == mentioned_lower:
                mentioned_lower = None
                break
            result = resolve_npc_identity(mentioned_lower, {present_npc})
            if result.status == "matched":
                mentioned_lower = None
                break

        if mentioned_lower is None:
            continue

        resolve_result = resolve_npc_identity(mentioned_lower, known_npcs_canonical)

        if resolve_result.status == "ambiguous":
            ambiguous_mentions.add(mentioned_lower)
            continue

        if resolve_result.status == "unmatched":
            continue

        canonical_name = resolve_result.canonical_name
        if not canonical_name:
            continue

        exempt = False
        for party_member in party_members_canonical:
            if party_member.lower() == canonical_name.lower():
                exempt = True
                break
            result = resolve_npc_identity(canonical_name, {party_member})
            if result.status == "matched":
                exempt = True
                break
            canonical_tokens = _extract_name_tokens(canonical_name)
            party_tokens = _extract_name_tokens(party_member)
            if canonical_tokens and party_tokens and party_tokens.issubset(canonical_tokens):
                exempt = True
                break

        if exempt:
            continue

        if has_transition_action:
            for destination_npc in destination_present_npcs_canonical:
                result = resolve_npc_identity(canonical_name, {destination_npc})
                if result.status == "matched":
                    exempt = True
                    break

        if exempt:
            continue

        has_action = _has_arrival_action_for_npc(
            canonical_name,
            actions,
            known_npcs_canonical,
        )

        if not has_action:
            missing_actions.add(canonical_name)

    missing_sorted = sorted(missing_actions)

    if missing_sorted:
        can_reconcile_travel_companions = (
            bool(missing_sorted)
            and not ambiguous_mentions
            and is_travel_intent
            and has_transition_action
            and not has_join_semantics
            and isinstance(user_utterance, str)
            and bool(user_utterance.strip())
        )

        if can_reconcile_travel_companions:
            inferred_actions = []
            current_location_hint = source_location_hint
            if not current_location_hint and isinstance(party_tracker_data, dict):
                world_conditions = party_tracker_data.get("worldConditions", {})
                if isinstance(world_conditions, dict):
                    current_location_hint = str(world_conditions.get("currentLocationId", "") or "").strip()

            user_utterance_lower = user_utterance.lower()
            for canonical_name in missing_sorted:
                if canonical_name.lower() in user_utterance_lower:
                    inferred_actions.append(
                        _build_scene_presence_inferred_action(
                            canonical_npc_name=canonical_name,
                            current_location_hint=current_location_hint,
                        )
                    )

            if inferred_actions:
                return {
                    "valid": True,
                    "reason": "",
                    "inferred_actions": inferred_actions,
                    "reconciliation": "travel_companion_autocommit",
                    "missing_actions": missing_sorted,
                }

        if not has_explicit_arrival:
            return {
                "valid": True,
                "reason": "",
                "inferred_actions": [],
                "reconciliation": "mention_only",
                "missing_actions": missing_sorted,
            }

        # TABLETOP MODE: G3 narrow reconcile-first gate for scene-compatible
        # explicit presence (not durable party joins).
        can_reconcile_scene_presence = (
            len(missing_sorted) == 1
            and not ambiguous_mentions
            and not is_travel_intent
            and not has_join_semantics
            and _has_scene_presence_user_cue(user_utterance)
        )

        if can_reconcile_scene_presence:
            current_location_hint = source_location_hint
            if not current_location_hint and isinstance(party_tracker_data, dict):
                world_conditions = party_tracker_data.get("worldConditions", {})
                if isinstance(world_conditions, dict):
                    current_location_hint = str(world_conditions.get("currentLocationId", "") or "").strip()

            inferred_action = _build_scene_presence_inferred_action(
                canonical_npc_name=missing_sorted[0],
                current_location_hint=current_location_hint,
            )
            return {
                "valid": True,
                "reason": "",
                "inferred_actions": [inferred_action],
                "reconciliation": "scene_presence_autocommit",
                "missing_actions": missing_sorted,
            }

        reason = _format_failure_reason(missing_sorted)
        return {
            "valid": False,
            "reason": reason,
            "inferred_actions": [],
            "reconciliation": "none",
            "missing_actions": missing_sorted,
        }

    return {
        "valid": True,
        "reason": "",
        "inferred_actions": [],
        "reconciliation": "none",
        "missing_actions": [],
    }


def validate_npc_arrival_state_sync(
    response_json: Dict[str, Any],
    party_tracker_data: Dict[str, Any],
    location_data: Optional[Dict[str, Any]] = None,
    module_npc_names: Optional[Set[str]] = None,
    is_travel_intent: bool = False,
    user_utterance: Optional[str] = None,
    destination_location_data: Optional[Dict[str, Any]] = None,
    source_location_hint: str = "",
) -> Tuple[bool, str]:
    """
    Validate that narration does not introduce off-location known NPCs
    without accompanying state synchronization actions.

    Args:
        response_json: Parsed AI response with 'narration' and 'actions' fields
        party_tracker_data: Current party tracker state
        location_data: Current location data with npcs list (optional)
        module_npc_names: Set of all canonical NPC names in the module (optional)
        is_travel_intent: Whether this is a travel/transition turn (fail-soft for non-explicit arrivals)
        user_utterance: Optional raw user utterance for detecting travel intent

    Returns:
        Tuple of (is_valid, reason_message)
        - is_valid: True if validation passes, False if failed
        - reason_message: Empty string if valid, actionable error message if invalid
    """
    decision = evaluate_npc_arrival_state_sync_decision(
        response_json=response_json,
        party_tracker_data=party_tracker_data,
        location_data=location_data,
        module_npc_names=module_npc_names,
        is_travel_intent=is_travel_intent,
        user_utterance=user_utterance,
        destination_location_data=destination_location_data,
        source_location_hint=source_location_hint,
    )
    return bool(decision.get("valid", True)), str(decision.get("reason", "") or "")


def _build_party_member_set(party_tracker_data: Dict[str, Any]) -> Set[str]:
    """
    Build set of party member (PC) names.
    Party members are PCs, not NPCs, and should be exempt from NPC arrival checks.
    
    Returns lowercase set for backward compatibility.
    """
    party_members = set()
    for member_name in party_tracker_data.get("partyMembers", []):
        if member_name and isinstance(member_name, str):
            party_members.add(member_name.lower())
    return party_members


def _build_party_member_canonical_set(party_tracker_data: Dict[str, Any]) -> Set[str]:
    """
    Build set of party member (PC) names in canonical (original) case.
    Used for identity resolution matching.
    """
    party_members = set()
    for member_name in party_tracker_data.get("partyMembers", []):
        if member_name and isinstance(member_name, str):
            party_members.add(member_name)
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


def _build_present_npc_canonical_set(
    party_tracker_data: Dict[str, Any],
    location_data: Optional[Dict[str, Any]] = None
) -> Set[str]:
    """
    Build set of currently present NPC names in canonical (original) case.
    Used for identity resolution matching.
    """
    present = set()

    if location_data and "npcs" in location_data:
        for npc in location_data["npcs"]:
            if isinstance(npc, dict):
                npc_name = npc.get("name", "")
                if npc_name:
                    present.add(npc_name)
            elif isinstance(npc, str):
                present.add(npc)

    party_npcs = party_tracker_data.get("partyNPCs", [])
    for npc in party_npcs:
        if isinstance(npc, dict):
            npc_name = npc.get("name", "")
            if npc_name:
                present.add(npc_name)
        elif isinstance(npc, str):
            present.add(npc)

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


def _build_known_npc_canonical_set(
    party_tracker_data: Dict[str, Any],
    location_data: Optional[Dict[str, Any]] = None,
    module_npc_names: Optional[Set[str]] = None
) -> Set[str]:
    """
    Build set of all known canonical NPC names in original case.
    Used for identity resolution matching.
    """
    known = set()

    if module_npc_names:
        known.update(module_npc_names)

    if location_data and "npcs" in location_data:
        for npc in location_data["npcs"]:
            if isinstance(npc, dict):
                npc_name = npc.get("name", "")
                if npc_name:
                    known.add(npc_name)
            elif isinstance(npc, str):
                known.add(npc)

    party_npcs = party_tracker_data.get("partyNPCs", [])
    for npc in party_npcs:
        if isinstance(npc, dict):
            npc_name = npc.get("name", "")
            if npc_name:
                known.add(npc_name)
        elif isinstance(npc, str):
            known.add(npc)

    return known


def _extract_npc_mentions(narration: str, known_npcs: Set[str]) -> Set[str]:
    """
    Extract mentions of known NPCs from narration text.
    
    Matches both full canonical names AND individual name tokens (short forms).
    The resolver will determine if short forms map to known NPCs.

    Returns set of lowercase NPC names/tokens that are mentioned.
    """
    mentioned = set()
    narration_lower = narration.lower()

    for npc_name in known_npcs:
        pattern = r'\b' + re.escape(npc_name) + r'\b'
        for match in re.finditer(pattern, narration_lower):
            if not _is_negated_mention(narration_lower, match.start(), match.end()):
                mentioned.add(npc_name)
                break

        tokens = _extract_name_tokens(npc_name)
        for token in tokens:
            if len(token) < 3:
                continue
            if token in _NPC_MENTION_STOPWORDS:
                continue

            token_pattern = r'\b' + re.escape(token) + r'\b'
            for match in re.finditer(token_pattern, narration_lower):
                if not _is_negated_mention(narration_lower, match.start(), match.end()):
                    mentioned.add(token)
                    break

    return mentioned


def _has_arrival_action_for_npc(
    npc_name: str,
    actions: List[Dict[str, Any]],
    known_npc_canonical: Optional[Set[str]] = None
) -> bool:
    """
    Check if actions include a valid arrival action for the given NPC.
    
    Uses identity resolver for alias-aware matching when known_npc_canonical is provided.
    Falls back to strict lowercase equality when resolver not available.

    Valid actions:
    - moveBackgroundNPC with matching npcName
    - updatePartyNPCs with operation: "add" and matching NPC identity
    """
    action_npc_names = set()
    
    for action in actions:
        if not isinstance(action, dict):
            continue

        action_type = action.get("action", "")
        params = action.get("parameters", {})

        if action_type == "moveBackgroundNPC":
            action_npc_name = params.get("npcName", "")
            if action_npc_name:
                action_npc_names.add(action_npc_name)

        elif action_type == "updatePartyNPCs":
            operation = params.get("operation", "").lower()
            if operation == "add":
                npc_data = params.get("npc", {})
                if isinstance(npc_data, dict):
                    npc_data_name = npc_data.get("name", "")
                    if npc_data_name:
                        action_npc_names.add(npc_data_name)
                elif isinstance(npc_data, str):
                    if npc_data:
                        action_npc_names.add(npc_data)
    
    if not action_npc_names:
        return False
    
    if known_npc_canonical:
        for action_name in action_npc_names:
            result = resolve_npc_identity(action_name, known_npc_canonical)
            if result.status == "matched" and result.canonical_name == npc_name:
                return True
            result = resolve_npc_identity(npc_name, {action_name})
            if result.status == "matched":
                return True
        return False
    else:
        npc_name_lower = npc_name.lower()
        for action_name in action_npc_names:
            if action_name.lower() == npc_name_lower:
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
            f"or 'updatePartyNPCs' operation='add' for this NPC, "
            f"or remove explicit arrival wording from narration."
        )
    else:
        npcs = ", ".join(f"'{n}'" for n in missing_actions)
        return (
            f"NPC arrival state sync failed: NPCs {npcs} are mentioned in narration "
            f"but are not currently present at this location. "
            f"Required: Include 'moveBackgroundNPC' or 'updatePartyNPCs add' actions "
            f"for each arriving NPC, or remove explicit arrival wording for NPCs that do not arrive."
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
