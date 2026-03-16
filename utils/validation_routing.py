# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Validation Routing Helpers
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Helpers for deterministic validation routing decisions.
"""

from typing import Any, Dict, List, Optional, Tuple


HIGH_RISK_ACTIONS = {
    "createEncounter",
    "transitionLocation",
    "updatePartyTracker",
    "moveBackgroundNPC",
    "updatePartyNPCs",
    "createNewModule",
    "restoreGame",
    "deleteSave",
    "updateEncounter",
    "levelUp",
    "exitGame",
}

LOW_RISK_SKIP_ACTIONS = {
    "updateTime",
    "saveGame",
    "listSaves",
}


TRAVEL_DOMAIN = "travel_state_sync"
NPC_DOMAIN = "npc_state_sync"
MECHANICS_DOMAIN = "mechanics_precheck"


_TRAVEL_REASON_KEYWORDS = {
    "travel state sync",
    "transitionlocation",
    "updatetime",
    "updatepartytracker",
    "in_transit",
    "topology-safe",
    "same-location travel",
    "travel narration",
}

_NPC_REASON_KEYWORDS = {
    "npc arrival state sync",
    "movebackgroundnpc",
    "updatepartynpcs",
    "off-location",
    "not currently present at this location",
    "explicit arrival claim",
}

_MECHANICS_REASON_KEYWORDS = {
    "mechanics precheck",
    "hp",
    "spell slot",
    "inventory",
    "ammo",
    "exhaustion",
    "death save",
}

_UNRECONCILED_REASON_KEYWORDS = {
    "invalid action",
    "action schema",
    "missing parameters",
    "malformed json",
    "hallucination",
    "not in module",
    "semantic failure",
}


def _normalize_domain_decision(decision: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(decision, dict):
        return {}
    return decision


def _build_domain_payload(
    decision: Optional[Dict[str, Any]],
    authoritative: bool,
    reconciled_modes: Optional[set] = None,
) -> Dict[str, Any]:
    normalized = _normalize_domain_decision(decision)
    passed = bool(normalized.get("valid", True))
    mode = str(normalized.get("reconciliation", "none") or "none")
    reason = str(normalized.get("reason", "") or "")
    required_action = reason if not passed else ""
    reconciled = False
    if reconciled_modes and mode in reconciled_modes:
        reconciled = True
    if isinstance(normalized.get("inferred_actions"), list) and normalized.get("inferred_actions"):
        reconciled = True

    return {
        "passed": passed,
        "authoritative": bool(authoritative),
        "reconciled": bool(reconciled),
        "mode": mode,
        "reason": reason if not passed else "",
        "required_action": required_action,
    }


def build_authoritative_domain_handoff(
    travel_sync_decision: Optional[Dict[str, Any]],
    npc_sync_decision: Optional[Dict[str, Any]],
    mechanics_ok: bool,
    mechanics_reason: str = "",
    payload_version: str = "v1",
) -> Dict[str, Any]:
    """Build narrator deterministic handoff payload as domain-scoped metadata."""
    travel_payload = _build_domain_payload(
        decision=travel_sync_decision,
        authoritative=True,
        reconciled_modes={"arrival_autocommit", "progress_in_transit"},
    )
    npc_payload = _build_domain_payload(
        decision=npc_sync_decision,
        authoritative=True,
        reconciled_modes={"scene_presence_autocommit"},
    )
    mechanics_payload = {
        "passed": bool(mechanics_ok),
        "authoritative": True,
        "reconciled": False,
        "mode": "pass" if mechanics_ok else "hard_fail",
        "reason": "" if mechanics_ok else str(mechanics_reason or ""),
        "required_action": "" if mechanics_ok else str(mechanics_reason or ""),
    }

    domains = {
        TRAVEL_DOMAIN: travel_payload,
        NPC_DOMAIN: npc_payload,
        MECHANICS_DOMAIN: mechanics_payload,
    }

    authoritative_failures = [
        name for name, payload in domains.items()
        if bool(payload.get("authoritative", False)) and not bool(payload.get("passed", False))
    ]
    reconciled_domains = [
        name for name, payload in domains.items()
        if bool(payload.get("reconciled", False))
    ]

    return {
        "payload_version": str(payload_version),
        "domains": domains,
        "summary": {
            "all_authoritative_domains_passed": len(authoritative_failures) == 0,
            "authoritative_failures": authoritative_failures,
            "reconciled_domains": reconciled_domains,
        },
    }


def classify_validator_failure_domains(reason: str) -> List[str]:
    """Classify validator failure reason into deterministic domains."""
    reason_lower = str(reason or "").lower()
    domains: List[str] = []

    if any(keyword in reason_lower for keyword in _TRAVEL_REASON_KEYWORDS):
        domains.append(TRAVEL_DOMAIN)
    if any(keyword in reason_lower for keyword in _NPC_REASON_KEYWORDS):
        domains.append(NPC_DOMAIN)
    if any(keyword in reason_lower for keyword in _MECHANICS_REASON_KEYWORDS):
        domains.append(MECHANICS_DOMAIN)

    if any(keyword in reason_lower for keyword in _UNRECONCILED_REASON_KEYWORDS):
        domains.append("unknown")

    if not domains:
        domains.append("unknown")
    return sorted(set(domains))


def apply_authoritative_domain_deconfliction(
    is_valid: bool,
    reason: str,
    deterministic_handoff: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Apply domain-based deconfliction against deterministic handoff payload."""
    outcome = {
        "is_valid": bool(is_valid),
        "reason": str(reason or ""),
        "authoritative_domain_conflict": False,
        "suppressed_domains": [],
        "remaining_failure_domains": [],
        "suppression_applied": False,
    }
    if outcome["is_valid"]:
        return outcome

    handoff = deterministic_handoff if isinstance(deterministic_handoff, dict) else {}
    domains_payload = handoff.get("domains", {}) if isinstance(handoff.get("domains", {}), dict) else {}

    failure_domains = classify_validator_failure_domains(outcome["reason"])
    suppressed_domains: List[str] = []
    remaining_domains: List[str] = []

    for domain in failure_domains:
        payload = domains_payload.get(domain)
        if isinstance(payload, dict):
            authoritative = bool(payload.get("authoritative", False))
            passed = bool(payload.get("passed", False))
            if authoritative and passed:
                suppressed_domains.append(domain)
            else:
                remaining_domains.append(domain)
        else:
            remaining_domains.append(domain)

    outcome["suppressed_domains"] = sorted(set(suppressed_domains))
    outcome["remaining_failure_domains"] = sorted(set(remaining_domains))

    if outcome["suppressed_domains"]:
        outcome["authoritative_domain_conflict"] = True

    if outcome["suppressed_domains"] and not outcome["remaining_failure_domains"]:
        outcome["is_valid"] = True
        outcome["suppression_applied"] = True
    elif outcome["suppressed_domains"] and outcome["remaining_failure_domains"]:
        remaining = ", ".join(outcome["remaining_failure_domains"])
        outcome["reason"] = (
            "Validation failed on unreconciled domain(s): "
            f"{remaining}."
        )

    return outcome


def _extract_action_names(response_json: Dict[str, Any]) -> List[str]:
    actions = response_json.get("actions", [])
    if not isinstance(actions, list):
        return []

    action_names: List[str] = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        action_name = action.get("action")
        if isinstance(action_name, str) and action_name.strip():
            action_names.append(action_name.strip())
    return action_names


def should_compress_validation_context(
    total_chars: int,
    compression_enabled: bool,
    threshold_chars: int,
) -> bool:
    """Return True when validation context should be compressed."""
    should_compress, _reason = get_validation_compression_decision(
        total_chars=total_chars,
        compression_enabled=compression_enabled,
        threshold_chars=threshold_chars,
    )
    return should_compress


def get_validation_compression_decision(
    total_chars: int,
    compression_enabled: bool,
    threshold_chars: int,
) -> Tuple[bool, str]:
    """Return compression decision with deterministic reason code."""
    if not compression_enabled:
        return (False, "compression_disabled")
    if threshold_chars <= 0:
        return (True, "threshold_disabled")
    if total_chars >= threshold_chars:
        return (True, "at_or_above_threshold")
    return (False, "below_threshold")


def should_skip_llm_validation(
    response_json: Dict[str, Any],
    deterministic_passed: bool,
    reconciled_domains: Optional[List[str]] = None,
) -> Tuple[bool, str]:
    """Conservative skip decision for low-risk turns.

    Returns (should_skip, reason).
    """
    if not deterministic_passed:
        return (False, "deterministic_failed")

    if isinstance(reconciled_domains, list) and reconciled_domains:
        action_names = _extract_action_names(response_json)
        if action_names:
            if set(action_names).issubset({"transitionLocation", "updateTime", "moveBackgroundNPC", "updatePartyTracker"}):
                return (True, "reconciled_soft_state_only")

    action_names = _extract_action_names(response_json)
    if not action_names:
        return (True, "narration_only")

    for action_name in action_names:
        if action_name in HIGH_RISK_ACTIONS:
            return (False, f"high_risk_action:{action_name}")

    for action_name in action_names:
        if action_name not in LOW_RISK_SKIP_ACTIONS:
            return (False, f"non_low_risk_action:{action_name}")

    return (True, "low_risk_actions_only")


def build_validation_routing_telemetry(
    skip_llm_validation: bool,
    skip_reason: str,
    used_validation_compression: bool,
    compression_reason: str,
    validation_payload_chars: int,
    authoritative_domain_conflict: bool = False,
    suppressed_domains: Optional[List[str]] = None,
    remaining_failure_domains: Optional[List[str]] = None,
    deterministic_payload_version: str = "",
) -> Dict[str, Any]:
    """Build normalized validation routing telemetry payload."""
    return {
        "skip_llm_validation": bool(skip_llm_validation),
        "skip_reason": str(skip_reason),
        "used_validation_compression": bool(used_validation_compression),
        "compression_reason": str(compression_reason),
        "validation_payload_chars": int(validation_payload_chars),
        "authoritative_domain_conflict": bool(authoritative_domain_conflict),
        "suppressed_domains": list(suppressed_domains or []),
        "remaining_failure_domains": list(remaining_failure_domains or []),
        "deterministic_payload_version": str(deterministic_payload_version or ""),
    }
