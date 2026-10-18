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


def _projection_world(party):
    """The party's world read for a projection: read-only, so a missing
    live_state.json is neither created nor converted here."""
    from core.nql import occupants

    world = party.get("worldConditions") if isinstance(party.get("worldConditions"), dict) else {}
    return occupants.party_world(
        str(party.get("module") or ""), str(world.get("currentLocationId") or ""), create=False,
    )


def membership_proposals(candidate: str, party: dict, *, turn_roster=None) -> list[dict]:
    """Inspect already-normalized actions, never narration or player prose.

    Proposed rosters are a transient structural projection: each
    updatePartyNPCs is planned by the same planner as the change itself
    (its unfinished roster_after; a refused change leaves the roster as it
    is), with no sheet built and no file written. Preserve each change even
    when a later action would reverse it. `turn_roster` numbers the [slot]
    rows (default: the party's roster).
    """
    from core.ai.action_handler import plan_party_change

    actions = json.loads(candidate).get("actions", [])
    roster = copy.deepcopy(party.get("partyNPCs", []))
    turn = copy.deepcopy(turn_roster) if isinstance(turn_roster, list) else copy.deepcopy(roster)
    world = None
    world_read = False
    world_conditions = party.get("worldConditions") if isinstance(party.get("worldConditions"), dict) else {}
    proposals = []
    for index, action in enumerate(actions):
        if action.get("action") != "updatePartyNPCs":
            continue
        parameters = action.get("parameters")
        after = None
        if isinstance(parameters, dict) and _roster_members(roster) is not None:
            if not world_read:
                world, world_read = _projection_world(party), True
            outcome = plan_party_change(
                roster, parameters, world, turn_roster=turn,
                module=str(party.get("module") or ""),
                location=str(world_conditions.get("currentLocationId") or ""),
                request_id=None,
            )
            after = outcome["roster_after"]
        proposals.append({
            "action_index": index,
            "action": "updatePartyNPCs",
            "parameters": copy.deepcopy(parameters),
            "roster_before": copy.deepcopy(roster),
            "proposed_roster_after": copy.deepcopy(after),
        })
        roster = copy.deepcopy(after)
    return proposals


def _consent_npc(parameters):
    """The guardian judges who joins or leaves, not the companion's sheet.

    Level and class/role are mechanical fields the engine fills (an omitted
    level becomes the party level), so the review packet carries only the
    name. Otherwise the guardian can reject a supplied level as invented and
    a missing one as incomplete, leaving no draft it would approve.
    """
    if not isinstance(parameters, dict) or not isinstance(parameters.get("npc"), dict):
        return parameters
    view = copy.deepcopy(parameters)
    view["npc"] = {"name": parameters["npc"].get("name")}
    return view


def consent_view(candidate: str, proposals: list[dict]):
    """Candidate and proposals as the guardian sees them; never published."""
    data = json.loads(candidate)
    for action in data.get("actions", []):
        if isinstance(action, dict) and action.get("action") == "updatePartyNPCs":
            action["parameters"] = _consent_npc(action.get("parameters"))
    view = copy.deepcopy(proposals)
    for proposal in view:
        if proposal["action"] == "updatePartyNPCs":
            proposal["parameters"] = _consent_npc(proposal["parameters"])
    return json.dumps(data, ensure_ascii=True), view


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
    invocation_claim, detached_context=None, turn_roster=None,
):
    """One required review call, with no nested semantic retry or state writes."""
    import model_config
    from core.ai import api_client
    from core.ai.action_handler import TurnRoster, party_note_lines, turn_key
    from core.combat.invocation import require_current_invocation
    from utils.capture.live_provider_call import LiveProviderSuperseded
    from utils.capture.multi_model_capture import capture_and_fanout, register_callsite

    if invocation_claim is not None:
        require_current_invocation(invocation_claim)
    context = detached_context or {}
    scope = context.get("scope")
    if scope is not None and scope.is_superseded():
        raise LiveProviderSuperseded("party membership review superseded")
    if turn_roster is None:
        turn_roster = TurnRoster.get(turn_key(invocation_claim))
    proposals = membership_proposals(candidate, party, turn_roster=turn_roster)
    if not proposals:
        return True, ""
    party_line, orphan_sentence = party_note_lines(party, _projection_world(party), turn_roster)

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
    review_candidate, review_proposals = consent_view(candidate, proposals)
    packet = {
        "player_input": player_input,
        "accepted_history": accepted_history,
        "canonical_party": party,
        "party_line": party_line + orphan_sentence,
        "candidate": review_candidate,
        "membership_proposals": review_proposals,
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
