"""
Transition Validator - AI-powered validation of location transition requests

This module uses a specialized AI agent to evaluate whether travel requests
are appropriate given exploration status, encounters, and plot progression.
"""

import json
import os
from typing import Dict, List, Any, Optional
from model_config import TRANSITION_VALIDATOR_MODEL, TRANSITION_VALIDATOR_TEMPERATURE
from utils.enhanced_logger import debug, info, warning, error
from utils.file_operations import safe_read_json
from utils.ai_client_factory import create_chat_client, get_chat_model_name, handle_provider_error


# Initialize AI client using factory (supports OpenAI and OpenRouter)
client = create_chat_client()


def load_transition_validation_prompt() -> str:
    """Load the transition validation system prompt"""
    prompt_path = "prompts/transition_validation_prompt.txt"
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        error(f"Failed to load transition validation prompt: {e}", category="transition_validation")
        return ""


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
    party_level: int = 1
) -> Dict[str, Any]:
    """
    Call AI agent to validate transition request and check for blocking conditions.

    Args:
        player_request: Original user message requesting travel
        current_location_id: Current location ID (e.g., "A01")
        current_location_name: Current location name
        current_area_id: Current area ID (e.g., "HFG001")
        current_area_name: Current area name
        target_location_id: Requested destination ID (e.g., "D01")
        path: List of location IDs in calculated path
        path_analysis: Result from analyze_path_for_encounters()
        transition_atlas: Atlas with exploration status markers (from transition_atlas_builder)
        plot_data: Module plot progression data
        party_level: Current party level

    Returns:
        Dict with:
        {
            "approved": bool,
            "stop_location": str or None,
            "stop_location_name": str or None,
            "reason": str,
            "narrative_guidance": str,
            "requires_encounter": bool,
            "plot_guidance": str or None
        }
    """
    debug(f"Calling transition intelligence agent: {current_location_id} -> {target_location_id}", category="transition_validation")

    # Load validation prompt
    system_prompt = load_transition_validation_prompt()
    if not system_prompt:
        # Fallback: approve if prompt loading fails
        warning("Transition validation prompt missing, approving by default", category="transition_validation")
        return {
            "approved": True,
            "stop_location": None,
            "stop_location_name": None,
            "reason": "Validation prompt unavailable",
            "narrative_guidance": "",
            "requires_encounter": False,
            "plot_guidance": None
        }

    # Get target location details from path analysis
    target_segment = None
    for segment in path_analysis.get("path_segments", []):
        if segment["location_id"] == target_location_id:
            target_segment = segment
            break

    target_location_name = target_segment["location_name"] if target_segment else "Unknown"
    target_area_name = target_segment["area_name"] if target_segment else "Unknown"

    # Get current plot point
    current_plot_point = "Unknown"
    for pp in plot_data.get("plotPoints", []):
        if pp.get("status") == "in progress":
            current_plot_point = pp.get("id", "Unknown")
            break

    # Build path context from path_analysis
    from utils.path_encounter_analyzer import build_path_context_for_ai
    path_context = build_path_context_for_ai(path_analysis)

    # Build compact plot summary
    plot_summary = _build_plot_summary(plot_data)

    # Construct user message with all context
    user_message = f"""TRAVEL REQUEST VALIDATION

PLAYER REQUEST:
"{player_request}"

CURRENT STATE:
- Location: {current_location_id} ({current_location_name})
- Area: {current_area_id} ({current_area_name})
- Current Plot Point: {current_plot_point}
- Party Level: {party_level}

TARGET DESTINATION:
- Location: {target_location_id} ({target_location_name})
- Area: {target_area_name}

CALCULATED PATH:
{' -> '.join(path)}

{path_context}

TRANSITION ATLAS:
{transition_atlas}

PLOT PROGRESSION:
{plot_summary}

DECISION REQUIRED:
Evaluate if this travel request should be approved or if the party must stop
at an intermediate location due to unexplored encounters. Respond with JSON only.
"""

    try:
        # Call AI agent
        debug("Sending request to transition validator AI", category="transition_validation")
        model_name = get_chat_model_name()
        actual_model_used = model_name

        try:
            response = client.chat.completions.create(
                model=model_name,
                temperature=TRANSITION_VALIDATOR_TEMPERATURE,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ]
            )
        except Exception as api_error:
            error_result = handle_provider_error(api_error, context="Transition validation")
            if error_result["should_fallback"]:
                warning(f"Falling back to OpenAI: {api_error}", category="ai_provider")
                fallback_client = create_chat_client(use_fallback=True)
                response = fallback_client.chat.completions.create(
                model=actual_model_used,
                    temperature=TRANSITION_VALIDATOR_TEMPERATURE,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ]
                )
                actual_model_used = TRANSITION_VALIDATOR_MODEL
            else:
                raise

        # Log API call
        try:
            from utils.api_logger import log_api_call
            log_api_call(
                call_type="transition_agent",
                model=TRANSITION_VALIDATOR_MODEL,
                request_data={
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    "temperature": TRANSITION_VALIDATOR_TEMPERATURE
                },
                response_content=response.choices[0].message.content,
                usage=response.usage.model_dump() if hasattr(response, 'usage') else None
            )
        except Exception as e:
            debug(f"Failed to log transition agent API call: {e}", category="transition_validation")

        # Parse response
        response_text = response.choices[0].message.content.strip()
        debug(f"Transition validator response: {response_text[:200]}...", category="transition_validation")

        # Parse JSON response
        result = json.loads(response_text)

        # Validate response structure
        if "approved" not in result:
            warning("Transition validator returned invalid JSON (missing 'approved')", category="transition_validation")
            result["approved"] = True  # Default to approve on error

        # Ensure all required fields exist
        result.setdefault("stop_location", None)
        result.setdefault("stop_location_name", None)
        result.setdefault("reason", "")
        result.setdefault("narrative_guidance", "")
        result.setdefault("requires_encounter", False)
        result.setdefault("plot_guidance", None)

        # Log decision
        if result["approved"]:
            info(f"Transition approved: {current_location_id} -> {target_location_id}", category="transition_validation")
        else:
            info(f"Transition blocked: Must stop at {result['stop_location']}", category="transition_validation")
            debug(f"Block reason: {result['reason']}", category="transition_validation")

        return result

    except json.JSONDecodeError as e:
        error(f"Failed to parse transition validator JSON: {e}", category="transition_validation")
        error(f"Response was: {response_text}", category="transition_validation")
        # Fallback: approve on parse error
        return {
            "approved": True,
            "stop_location": None,
            "stop_location_name": None,
            "reason": "JSON parse error in validator",
            "narrative_guidance": "",
            "requires_encounter": False,
            "plot_guidance": None
        }

    except Exception as e:
        error(f"Transition validator failed: {e}", category="transition_validation")
        # Fallback: approve on error
        return {
            "approved": True,
            "stop_location": None,
            "stop_location_name": None,
            "reason": f"Validator error: {str(e)}",
            "narrative_guidance": "",
            "requires_encounter": False,
            "plot_guidance": None
        }


def _build_plot_summary(plot_data: Dict) -> str:
    """Build compact plot summary for AI context"""
    if not plot_data:
        return "No plot data available"

    lines = ["Plot Points:"]

    for pp in plot_data.get("plotPoints", []):
        pp_id = pp.get("id", "Unknown")
        title = pp.get("title", "Untitled")
        status = pp.get("status", "unknown")
        location = pp.get("location", "Unknown")

        status_marker = "[IN PROGRESS]" if status == "in progress" else "[NOT STARTED]" if status == "not started" else "[COMPLETED]"

        lines.append(f"  {pp_id}: {title} ({location}) {status_marker}")

    return "\n".join(lines)
