# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Utility - Toolkit Homebrew Normalizer
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Source-faithful normalization service for toolkit Homebrew markdown uploads.

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from model_config import DM_MAIN_MODEL
from utils.ai_client_factory import create_chat_client, get_model_config
from utils.enhanced_logger import warning
from utils.toolkit_homebrew_upload_contract import (
    build_normalized_packet_placeholder,
    compute_sha256,
    persist_builder_narrative_artifact,
    persist_normalization_report_artifact,
    persist_normalized_packet_artifact,
)


NORMALIZATION_PROMPT_PATH = Path("prompts") / "toolkit" / "homebrew_upload_normalization_prompt.txt"
MAX_NORMALIZATION_SOURCE_CHARS = 120000


def _load_prompt() -> str:
    """Load normalization prompt template from disk."""
    try:
        return NORMALIZATION_PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return (
            "You are a strict source-faithful module normalizer. "
            "Return ONLY JSON with grounded fields and assumptions separated."
        )


def _extract_json_payload(raw_text: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Extract JSON object from model response text."""
    text = str(raw_text or "").strip()
    if not text:
        return None, "empty_model_response"

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed, None
        return None, "model_response_not_object"
    except Exception:
        pass

    marker = "```json"
    lower_text = text.lower()
    start_index = lower_text.find(marker)
    if start_index == -1:
        start_index = text.find("```")
    if start_index != -1:
        fence_start = text.find("\n", start_index)
        if fence_start != -1:
            fence_end = text.find("```", fence_start + 1)
            if fence_end != -1:
                candidate = text[fence_start + 1:fence_end].strip()
                try:
                    parsed = json.loads(candidate)
                    if isinstance(parsed, dict):
                        return parsed, None
                    return None, "model_fenced_payload_not_object"
                except Exception:
                    return None, "model_fenced_payload_invalid_json"

    return None, "model_response_invalid_json"


def _as_list(value: Any) -> List[Any]:
    """Normalize potentially singular values to list."""
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _as_string(value: Any) -> str:
    """Normalize arbitrary value to stripped string."""
    return str(value or "").strip()


def _build_builder_narrative(packet: Dict[str, Any], model_payload: Dict[str, Any]) -> str:
    """Build builder narrative text derived from normalized packet/model output."""
    candidate = _as_string(model_payload.get("builder_narrative"))
    if candidate:
        return candidate

    title = _as_string(packet.get("title")) or "Untitled Module"
    summary = _as_string(packet.get("adventure_summary"))
    tone = _as_string(packet.get("module_tone"))
    location_count = len(_as_list(packet.get("locations")))
    npc_count = len(_as_list(packet.get("npc_seeds")))
    monster_count = len(_as_list(packet.get("monster_refs")))

    parts = [f"Module: {title}"]
    if summary:
        parts.append(f"Summary: {summary}")
    if tone:
        parts.append(f"Tone: {tone}")
    parts.append(
        f"Scope: {location_count} locations, {npc_count} NPC seeds, {monster_count} monster references."
    )
    assumptions = _as_list(packet.get("assumptions"))
    if assumptions:
        parts.append("Assumptions: " + "; ".join(_as_string(a) for a in assumptions if _as_string(a)))
    return "\n".join(parts)


def _build_normalized_packet(
    source_path: Path,
    preflight: Dict[str, Any],
    source_rights_class: str,
    model_payload: Dict[str, Any],
    source_was_truncated: bool,
) -> Dict[str, Any]:
    """Build normalized packet by merging model payload onto canonical placeholder."""
    base_packet = build_normalized_packet_placeholder(
        source_path=source_path,
        source_hash=compute_sha256(source_path),
        preflight=preflight,
        source_rights_class=source_rights_class,
    )

    # TABLETOP MODE: Mark packet as model-normalized for review gate validation.
    base_packet["normalization_state"] = "normalized"

    string_fields = [
        "title",
        "author",
        "description",
        "adventure_summary",
        "module_tone",
    ]
    for field in string_fields:
        candidate = _as_string(model_payload.get(field))
        if candidate:
            base_packet[field] = candidate

    level_min = model_payload.get("estimated_level_min")
    level_max = model_payload.get("estimated_level_max")
    if isinstance(level_min, int):
        base_packet["estimated_level_min"] = level_min
    if isinstance(level_max, int):
        base_packet["estimated_level_max"] = level_max

    list_fields = [
        "acts",
        "locations",
        "connectivity_hints",
        "encounter_seeds",
        "npc_seeds",
        "monster_refs",
        "plot_progression",
        "continuity_hints",
        "media_hints",
        "assumptions",
        "warnings",
    ]
    for field in list_fields:
        base_packet[field] = _as_list(model_payload.get(field))

    grounded_facts = _as_list(model_payload.get("grounded_facts"))
    if grounded_facts:
        base_packet["confidence_notes"]["grounded_facts"] = grounded_facts

    if source_was_truncated:
        base_packet["warnings"].append(
            {
                "type": "source_truncated",
                "message": "Source was truncated for normalization token safety.",
            }
        )

    return base_packet


def normalize_homebrew_upload(
    source_path: Path,
    workspace: Path,
    preflight: Dict[str, Any],
    source_rights_class: str,
) -> Dict[str, Any]:
    """Run LLM normalization for a readable Homebrew upload source."""
    try:
        source_text = source_path.read_text(encoding="utf-8", errors="replace")
    except Exception as read_error:
        report = {
            "status": "failed",
            "stage": "normalizing",
            "error": f"source_read_failed: {read_error}",
        }
        persist_normalization_report_artifact(workspace, report)
        return report

    source_was_truncated = False
    normalized_source_text = source_text
    if len(normalized_source_text) > MAX_NORMALIZATION_SOURCE_CHARS:
        normalized_source_text = normalized_source_text[:MAX_NORMALIZATION_SOURCE_CHARS]
        source_was_truncated = True

    prompt_template = _load_prompt()
    model_config = get_model_config("builders", DM_MAIN_MODEL)
    model_name = model_config.get("model", DM_MAIN_MODEL)

    request_payload = {
        "source_filename": source_path.name,
        "preflight": preflight,
        "source_text": normalized_source_text,
    }
    user_prompt = (
        "Normalize the uploaded Homebrew markdown into the required JSON contract.\n"
        "Return JSON only.\n\n"
        f"INPUT_PAYLOAD:\n{json.dumps(request_payload, ensure_ascii=True)}"
    )

    try:
        client = create_chat_client()
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": prompt_template},
                {"role": "user", "content": user_prompt},
            ],
            temperature=model_config.get("temperature", 0.3),
            timeout=120,
            **model_config.get("extra_body", {}),
        )
        model_text = _as_string(response.choices[0].message.content)
    except Exception as provider_error:
        report = {
            "status": "failed",
            "stage": "normalizing",
            "error": f"normalizer_provider_failed: {provider_error}",
            "model": model_name,
        }
        persist_normalization_report_artifact(workspace, report)
        return report

    model_payload, parse_error = _extract_json_payload(model_text)
    if parse_error:
        report = {
            "status": "failed",
            "stage": "normalizing",
            "error": parse_error,
            "model": model_name,
            "response_preview": model_text[:1000],
        }
        persist_normalization_report_artifact(workspace, report)
        return report

    packet = _build_normalized_packet(
        source_path=source_path,
        preflight=preflight,
        source_rights_class=source_rights_class,
        model_payload=model_payload or {},
        source_was_truncated=source_was_truncated,
    )
    builder_narrative = _build_builder_narrative(packet, model_payload or {})

    report = {
        "status": "success",
        "stage": "normalizing",
        "model": model_name,
        "source_chars": len(source_text),
        "normalized_source_chars": len(normalized_source_text),
        "source_truncated": source_was_truncated,
        "assumptions_count": len(_as_list(packet.get("assumptions"))),
        "warnings_count": len(_as_list(packet.get("warnings"))),
        "grounded_facts_count": len(_as_list(packet.get("confidence_notes", {}).get("grounded_facts"))),
    }

    packet_ok = persist_normalized_packet_artifact(workspace, packet)
    report_ok = persist_normalization_report_artifact(workspace, report)
    narrative_ok = persist_builder_narrative_artifact(workspace, builder_narrative)

    if not (packet_ok and report_ok and narrative_ok):
        warning(
            "TOOLKIT_HOMEBREW: Normalization artifact persistence failed",
            category="web_interface",
        )
        failed_report = dict(report)
        failed_report["status"] = "failed"
        failed_report["error"] = "normalization_artifact_persistence_failed"
        failed_report["packet_persisted"] = packet_ok
        failed_report["report_persisted"] = report_ok
        failed_report["builder_narrative_persisted"] = narrative_ok
        persist_normalization_report_artifact(workspace, failed_report)
        return {
            "status": "failed",
            "stage": "normalizing",
            "error": "normalization_artifact_persistence_failed",
            "model": model_name,
            "packet_persisted": packet_ok,
            "report_persisted": report_ok,
            "builder_narrative_persisted": narrative_ok,
            "normalized_packet": packet,
            "normalization_report": failed_report,
        }

    return {
        "status": "success",
        "stage": "normalizing",
        "model": model_name,
        "normalized_packet": packet,
        "normalization_report": report,
        "builder_narrative": builder_narrative,
        "source_truncated": source_was_truncated,
    }
