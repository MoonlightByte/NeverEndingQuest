"""Constrained contextual review for ambiguous travel segments.

Topology and unambiguous travel rules belong to deterministic code.  T021 is
only allowed to classify route segments whose recorded narrative and current
monster state need interpretation.  It cannot choose a route or stop location.
"""

import json
from typing import Any, Dict, List, Optional

import config
import model_config
from core.ai import api_client
from core.combat.invocation import (
    InvocationSupersededError,
    require_current_invocation,
)
from model_config import TRANSITION_VALIDATOR_TEMPERATURE
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
from utils.enhanced_logger import debug, error, info, warning


register_callsite("T021", "core/ai/transition_validator.py", 203)

_CLASSIFICATIONS = frozenset({"safe", "blocked", "uncertain"})
_AUTHORITATIVE_EVIDENCE_KEYS = frozenset(
    {
        "adventure_summary",
        "encounters",
        "gameplay_encounters",
        "monsters",
        "monster_names",
        "monster_count",
        "has_monsters",
        "has_encounter_entries",
        "status",
        "visit_evidence",
        "exploration_status",
    }
)


def load_transition_validation_prompt() -> str:
    """Load the T021 system prompt."""
    try:
        with open(
            "prompts/transition_validation_prompt.txt", "r", encoding="utf-8"
        ) as handle:
            return handle.read()
    except Exception as exc:
        error(
            f"Failed to load transition validation prompt: {exc}",
            category="transition_validation",
        )
        return ""


def _transition_config() -> Dict[str, Any]:
    """Return the existing provider-specific T021 configuration."""
    if model_config.MODEL_PROVIDER == "openai":
        return config.TRANSITION_VAL_GPT52_NONE
    if model_config.MODEL_PROVIDER == "gemini":
        return config.TRANSITION_VAL_GEMINI_FLASH_LOW
    if model_config.MODEL_PROVIDER == "lmstudio":
        return config.TRANSITION_VAL_LMSTUDIO
    return config.TRANSITION_VAL_LEGACY


def _uncertain_reviews(
    segments: List[Dict[str, Any]], reason: str
) -> List[Dict[str, Any]]:
    """Create an exact-coverage, fail-safe result for supplied segments."""
    return [
        {
            "location_id": segment["location_id"],
            "classification": "uncertain",
            "reason": reason,
            "evidence": [],
            "source_excerpts": [],
        }
        for segment in segments
    ]


def _validate_supplied_segments(
    segments: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Validate and copy the evidence boundary passed to T021.

    Duplicate or malformed input is a caller programming error.  Model and
    provider failures are handled separately as uncertain classifications.
    """
    if not isinstance(segments, list) or not segments:
        raise ValueError("ambiguous_segments must be a non-empty list")

    normalized = []
    seen_ids = set()
    for segment in segments:
        if not isinstance(segment, dict):
            raise ValueError("each ambiguous segment must be an object")
        location_id = segment.get("location_id")
        evidence = segment.get("evidence")
        if not isinstance(location_id, str) or not location_id.strip():
            raise ValueError("each ambiguous segment requires a location_id")
        if location_id in seen_ids:
            raise ValueError(f"duplicate ambiguous location_id: {location_id}")
        if not isinstance(evidence, dict):
            raise ValueError(f"segment {location_id} requires an evidence object")
        if any(not isinstance(key, str) or not key for key in evidence):
            raise ValueError(f"segment {location_id} has an invalid evidence key")
        seen_ids.add(location_id)
        normalized.append(
            {
                "location_id": location_id,
                "location_name": segment.get("location_name", "Unknown"),
                "route_position": segment.get("route_position", "intermediate"),
                "evidence": dict(evidence),
            }
        )
    return normalized


def _evidence_text(value: Any) -> str:
    """Render supplied evidence exactly as it appears in the model packet."""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _normalize_reviews(
    result: Any, segments: List[Dict[str, Any]]
) -> Optional[List[Dict[str, Any]]]:
    """Accept only an exact, evidence-bounded review set.

    Any defect invalidates the whole batch.  Partial acceptance would allow a
    missing or duplicated segment to disappear from the safety decision.
    """
    if not isinstance(result, dict) or set(result) != {"reviews"}:
        return None
    reviews = result.get("reviews")
    if not isinstance(reviews, list) or len(reviews) != len(segments):
        return None

    supplied_by_id = {segment["location_id"]: segment for segment in segments}
    supplied_ids = set(supplied_by_id)
    review_ids = []
    normalized_by_id = {}

    for review in reviews:
        if not isinstance(review, dict):
            return None
        allowed_fields = {
            "location_id",
            "classification",
            "reason",
            "evidence",
            "source_excerpts",
        }
        if not set(review).issubset(allowed_fields):
            return None

        location_id = review.get("location_id")
        classification = review.get("classification")
        reason = review.get("reason")
        evidence_refs = review.get("evidence")
        excerpts = review.get("source_excerpts", [])

        if type(location_id) is not str or location_id not in supplied_ids:
            return None
        if location_id in review_ids:
            return None
        if classification not in _CLASSIFICATIONS:
            return None
        if not isinstance(reason, str) or not reason.strip():
            return None
        if not isinstance(evidence_refs, list) or any(
            not isinstance(key, str) for key in evidence_refs
        ):
            return None
        if len(evidence_refs) != len(set(evidence_refs)):
            return None
        # A model-supplied mechanical conclusion must point to at least one
        # authoritative fact. ``uncertain`` intentionally permits no citation:
        # missing or contradictory evidence is itself why review could not
        # establish safe passage or a definite obstruction.
        if classification in {"safe", "blocked"} and not evidence_refs:
            return None

        supplied_evidence = supplied_by_id[location_id]["evidence"]
        if any(key not in supplied_evidence for key in evidence_refs):
            return None
        if not isinstance(excerpts, list):
            return None
        normalized_excerpts = []
        for excerpt_record in excerpts:
            if not isinstance(excerpt_record, dict) or set(excerpt_record) != {
                "evidence_key",
                "excerpt",
            }:
                return None
            evidence_key = excerpt_record.get("evidence_key")
            excerpt = excerpt_record.get("excerpt")
            if evidence_key not in supplied_evidence:
                return None
            if not isinstance(excerpt, str) or not excerpt:
                return None
            if excerpt not in _evidence_text(supplied_evidence[evidence_key]):
                return None
            normalized_excerpts.append(
                {"evidence_key": evidence_key, "excerpt": excerpt}
            )

        review_ids.append(location_id)
        normalized_by_id[location_id] = {
            "location_id": location_id,
            "classification": classification,
            "reason": reason.strip(),
            "evidence": list(evidence_refs),
            "source_excerpts": normalized_excerpts,
        }

    if set(review_ids) != supplied_ids:
        return None
    return [normalized_by_id[segment["location_id"]] for segment in segments]


def review_ambiguous_segments(
    ambiguous_segments: List[Dict[str, Any]],
    travel_context: Optional[Dict[str, Any]] = None,
    invocation_claim=None,
) -> List[Dict[str, Any]]:
    """Use T021 to classify only the supplied ambiguous route segments.

    The output always covers every supplied location exactly once.  Any prompt,
    provider, response, JSON, or contract failure produces ``uncertain`` for
    every segment; it never produces an implicit travel approval.
    """
    segments = _validate_supplied_segments(ambiguous_segments)
    prompt = load_transition_validation_prompt()
    if not prompt.strip():
        warning(
            "Transition review prompt unavailable; classifying as uncertain",
            category="transition_validation",
        )
        return _uncertain_reviews(segments, "Transition review prompt unavailable")

    packet = {
        "travel_context": travel_context if isinstance(travel_context, dict) else {},
        "ambiguous_segments": segments,
    }
    user_message = (
        "Review every ambiguous segment in this evidence packet. "
        "Return JSON only.\n\n" + json.dumps(packet, ensure_ascii=False, sort_keys=True)
    )

    while True:
        if invocation_claim is not None:
            require_current_invocation(invocation_claim)
        transition_config = _transition_config()
        response = capture_and_fanout(
            "T021",
            api_client.create_completion,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_message},
            ],
            _request_provider=model_config.MODEL_PROVIDER,
            _live_selected=True,
            model=transition_config["model"],
            temperature=TRANSITION_VALIDATOR_TEMPERATURE,
            **{
                key: value for key, value in transition_config.items() if key != "model"
            },
        )
        if invocation_claim is not None:
            require_current_invocation(invocation_claim)
        response_text = response.choices[0].message.content

        try:
            from utils.api_logger import log_api_call

            log_api_call(
                "transition_agent",
                [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_message},
                ],
                response,
                metadata={
                    "configured_model": transition_config["model"],
                    "temperature": TRANSITION_VALIDATOR_TEMPERATURE,
                },
            )
        except Exception as exc:
            debug(
                f"Failed to log transition review call: {exc}",
                category="transition_validation",
            )

        try:
            decoded = json.loads(response_text)
        except json.JSONDecodeError:
            warning(
                "Transition reviewer returned malformed JSON; reissuing the "
                "same evidence packet",
                category="transition_validation",
            )
            continue
        normalized = _normalize_reviews(decoded, segments)
        if normalized is None:
            warning(
                "Transition reviewer returned an invalid contract; reissuing "
                "the same evidence packet",
                category="transition_validation",
            )
            continue
        info(
            f"Transition reviewer classified {len(normalized)} ambiguous segment(s)",
            category="transition_validation",
        )
        return normalized


def _legacy_blocked_result(segment: Dict[str, Any], reason: str) -> Dict[str, Any]:
    """Translate a deterministic/review stop into the historical interface."""
    return {
        "approved": False,
        "stop_location": segment["location_id"],
        "stop_location_name": segment.get("location_name", "Unknown"),
        "reason": reason,
        "narrative_guidance": (
            "The party travels only as far as this location because safe passage "
            "beyond it has not been established. Describe the arrival and let the "
            "player resolve or investigate the obstruction."
        ),
        "requires_encounter": bool(segment.get("has_monsters")),
        "plot_guidance": None,
    }


def _legacy_approved_result(reason: str) -> Dict[str, Any]:
    return {
        "approved": True,
        "stop_location": None,
        "stop_location_name": None,
        "reason": reason,
        "narrative_guidance": "",
        "requires_encounter": False,
        "plot_guidance": None,
    }


def validate_transition_request(
    player_request: str,
    current_location_id: str,
    current_location_name: str,
    current_area_id: str,
    current_area_name: str,
    target_location_id: str,
    path: List[str],
    path_analysis: Dict,
    transition_atlas: str,
    plot_data: Dict,
    party_level: int = 1,
    invocation_claim=None,
) -> Dict[str, Any]:
    """Backward-compatible bridge for the existing action-handler callsite.

    Clear intermediate blockers are handled deterministically.  T021 reviews
    only intermediate locations that are visited while monster records remain.
    An uncertain review is a safe stop, never approval.
    """
    del transition_atlas  # The constrained reviewer consumes evidence, not a second atlas.
    segments_by_id = {
        segment.get("location_id"): segment
        for segment in path_analysis.get("path_segments", [])
        if isinstance(segment, dict)
    }
    intermediates = [
        segments_by_id[location_id]
        for location_id in path[1:-1]
        if location_id in segments_by_id
    ]

    ambiguous = []
    for segment in intermediates:
        if segment.get("status") == "visited" and segment.get("has_monsters"):
            evidence = {
                key: value
                for key, value in segment.items()
                if key in _AUTHORITATIVE_EVIDENCE_KEYS
            }
            if isinstance(segment.get("evidence"), dict):
                evidence.update(
                    {
                        key: value
                        for key, value in segment["evidence"].items()
                        if key in _AUTHORITATIVE_EVIDENCE_KEYS
                    }
                )
            ambiguous.append(
                {
                    "location_id": segment["location_id"],
                    "location_name": segment.get("location_name", "Unknown"),
                    "route_position": "intermediate",
                    "evidence": evidence,
                }
            )

    reviews_by_id = {}
    if ambiguous:
        reviews = review_ambiguous_segments(
            ambiguous,
            travel_context={
                "player_request": player_request,
                "origin": {
                    "location_id": current_location_id,
                    "location_name": current_location_name,
                    "area_id": current_area_id,
                    "area_name": current_area_name,
                },
                "target_location_id": target_location_id,
                "path": path,
                "plot_data": plot_data,
                "party_level": party_level,
            },
            invocation_claim=invocation_claim,
        )
        reviews_by_id = {review["location_id"]: review for review in reviews}

    # Resolve stops in physical route order.  In particular, an earlier
    # ambiguous location must be reviewed before a later deterministic blocker;
    # otherwise the corrective response could incorrectly teleport past the
    # first unresolved segment.
    for segment in intermediates:
        if segment.get("status") == "unexplored" and segment.get("has_monsters"):
            return _legacy_blocked_result(
                segment, "Unexplored intermediate location has recorded monsters"
            )
        if segment.get("status") == "visited" and segment.get("has_monsters"):
            review = reviews_by_id.get(segment.get("location_id"))
            if not review or review.get("classification") != "safe":
                classification = review.get("classification") if review else "uncertain"
                reason = review.get("reason") if review else "No valid review returned"
                return _legacy_blocked_result(
                    segment,
                    f"Context review classified this segment as {classification}: "
                    f"{reason}",
                )

    return _legacy_approved_result(
        "All ambiguous intermediate locations have evidence-supported safe passage"
    )


def _build_plot_summary(plot_data: Dict) -> str:
    """Retained for imports by older extensions."""
    if not plot_data:
        return "No plot data available"
    lines = ["Plot Points:"]
    for point in plot_data.get("plotPoints", []):
        lines.append(
            f"  {point.get('id', 'Unknown')}: {point.get('title', 'Untitled')} "
            f"({point.get('location', 'Unknown')}) [{point.get('status', 'unknown')}]"
        )
    return "\n".join(lines)
