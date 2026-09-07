"""Action-triggered membership review (#193 D-NPC-PARTY-2..4).

The model judges consent/story grounding; this service only packages structured
proposals and parses its verdict. It never persists or publishes a candidate.
The shared review owner, not this service, owns semantic correction/reissue.
"""

import copy
import json
from pathlib import Path


TASK_ID = "T114"


def _roster_members(roster):
    """Compare typed names, preserving duplicates; metadata/order is not consent."""
    if not isinstance(roster, list):
        return None
    names = []
    for member in roster:
        if not isinstance(member, dict):
            return None
        name = member.get("name")
        if not isinstance(name, str) or not name.strip():
            return None
        names.append(name)
    return sorted(names)


def membership_proposals(candidate: str, party: dict) -> list[dict]:
    """Inspect already-normalized actions, never narration or player prose.

    Proposed rosters are a transient structural projection, not identity
    resolution or an executable replacement for the existing state writer.
    Preserve each change even when a later action would reverse it.
    """
    actions = json.loads(candidate).get("actions", [])
    roster = copy.deepcopy(party.get("partyNPCs", []))
    proposals = []
    for index, action in enumerate(actions):
        kind = action.get("action")
        parameters = action.get("parameters")
        if kind == "updatePartyNPCs":
            after = None
            if isinstance(parameters, dict) and _roster_members(roster) is not None:
                npc = parameters.get("npc")
                operation = parameters.get("operation")
                if isinstance(npc, dict) and isinstance(npc.get("name"), str):
                    if operation == "remove":
                        after = [m for m in roster if m["name"] != npc["name"]]
                    elif operation == "add":
                        after = copy.deepcopy(roster)
                        if npc["name"] not in _roster_members(roster):
                            after.append({
                                "name": npc["name"],
                                "role": npc.get("role", npc.get("class", "Companion")),
                            })
        elif kind == "updatePartyTracker" and isinstance(parameters, dict) and "partyNPCs" in parameters:
            after = parameters["partyNPCs"]
            before_names, after_names = _roster_members(roster), _roster_members(after)
            if before_names is not None and after_names is not None and before_names == after_names:
                roster = copy.deepcopy(after)
                continue
        else:
            continue
        proposals.append({
            "action_index": index,
            "action": kind,
            "parameters": copy.deepcopy(parameters),
            "roster_before": copy.deepcopy(roster),
            "proposed_roster_after": copy.deepcopy(after),
        })
        roster = copy.deepcopy(after)
    return proposals


def _parse_verdict(raw):
    """None is a malformed verdict, never permission or a made-up correction."""
    try:
        verdict = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(verdict, dict) or type(verdict.get("valid")) is not bool:
        return None
    if verdict["valid"]:
        return True, ""
    reason = verdict.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        return None
    return False, reason


def review_party_membership(
    candidate, *, accepted_history, player_input, party, review_feedback,
    invocation_claim, detached_context=None,
):
    """One required review call, with no nested semantic retry or state writes."""
    import model_config
    from core.ai import api_client
    from core.combat.invocation import require_current_invocation
    from utils.capture.live_provider_call import LiveProviderSuperseded
    from utils.capture.multi_model_capture import capture_and_fanout, register_callsite

    if invocation_claim is not None:
        require_current_invocation(invocation_claim)
    context = detached_context or {}
    scope = context.get("scope")
    if scope is not None and scope.is_superseded():
        raise LiveProviderSuperseded("party membership review superseded")
    proposals = membership_proposals(candidate, party)
    if not proposals:
        return True, ""

    provider = model_config.get_provider()
    config = model_config.resolve_callsite_config(TASK_ID, provider)
    if provider == "gemini":
        config["response_schema"] = model_config.convert_to_gemini_schema({
            "type": "object",
            "properties": {"valid": {"type": "boolean"}, "reason": {"type": "string"}},
            "required": ["valid"],
        })
        config["response_format"] = {"type": "json_object"}
    elif provider == "lmstudio":
        config["response_format"] = None
    else:
        config["response_format"] = {"type": "json_object"}
    prompt = Path("prompts/validation/party_guardian_prompt.txt").read_text(encoding="utf-8")
    packet = {
        "player_input": player_input,
        "accepted_history": accepted_history,
        "canonical_party": party,
        "candidate": candidate,
        "membership_proposals": proposals,
        "review_feedback": review_feedback,
    }
    register_callsite(TASK_ID, "core/npc/party_guardian.py", 138)
    response = capture_and_fanout(
        TASK_ID, api_client.create_completion,
        _request_provider=provider,
        _live_selected=True,
        _detached_scope=scope,
        _detached_status=context.get("status"),
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(packet, ensure_ascii=True)},
        ],
        **config,
    )
    if invocation_claim is not None:
        require_current_invocation(invocation_claim)
    if scope is not None and scope.is_superseded():
        raise LiveProviderSuperseded("party membership review superseded")
    return _parse_verdict(response.choices[0].message.content)
