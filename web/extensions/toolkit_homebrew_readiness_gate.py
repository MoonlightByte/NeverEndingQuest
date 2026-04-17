# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Web Extension - Toolkit Homebrew Structural Readiness Gate
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Post-build readiness orchestrator for packet-built Homebrew upload jobs.
"""

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from scripts.remediate_module_coordinates import remediate_module
from scripts.audit_module_readiness import audit_module_readiness
from utils.calendar_migration import MONTH_CONVERSION
from utils.enhanced_logger import error, info, warning
from utils.file_operations import safe_read_json, safe_write_json
from utils.toolkit_homebrew_upload_contract import (
    get_workspace_files,
    load_json_artifact,
    persist_readiness_audit_artifact,
    persist_readiness_validation_artifact,
    persist_repair_report_artifact,
)


VALID_GAME_MONTHS = {
    "Firstmonth",
    "Coldmonth",
    "Thawmonth",
    "Springmonth",
    "Bloommonth",
    "Sunmonth",
    "Heatmonth",
    "Harvestmonth",
    "Autumnmonth",
    "Fademonth",
    "Frostmonth",
    "Yearend",
}

MAX_DETERMINISTIC_PASSES = 2
MAX_SEMANTIC_PASSES = 2


def _utc_now_iso() -> str:
    """Return UTC timestamp in ISO-8601 format."""
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _safe_json_load(text: str) -> Dict[str, Any]:
    """Parse dict JSON from plain text or trailing mixed output."""
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass

    lines = text.strip().split("\n")
    for index in range(len(lines) - 1, -1, -1):
        if lines[index].strip().startswith("{"):
            try:
                payload = json.loads("\n".join(lines[index:]))
                if isinstance(payload, dict):
                    return payload
            except Exception:
                continue
    return {}


def _run_validator(module_slug: str) -> Dict[str, Any]:
    """Run module validator and capture structured output."""
    command = [
        sys.executable,
        "core/validation/validate_module_files.py",
        "--module",
        module_slug,
        "--json",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=180)
    payload = _safe_json_load(completed.stdout)
    module_report = _extract_module_validation_report(payload, module_slug)
    total_failed = int((module_report or {}).get("total_failed", 0) or 0)

    return {
        "status": "pass"
        if (completed.returncode == 0 and total_failed == 0)
        else "fail",
        "checked_at": _utc_now_iso(),
        "module": module_slug,
        "command": " ".join(command),
        "exit_code": completed.returncode,
        "total_failed": total_failed,
        "report": payload,
        "stdout_tail": (completed.stdout or "")[-2000:],
        "stderr_tail": (completed.stderr or "")[-2000:],
    }


def _extract_module_validation_report(
    validator_payload: Dict[str, Any],
    module_slug: str,
) -> Dict[str, Any]:
    """Extract module-scoped validation report from validator JSON output."""
    if not isinstance(validator_payload, dict):
        return {}

    modules = validator_payload.get("modules")
    if isinstance(modules, dict):
        module_report = modules.get(module_slug)
        if isinstance(module_report, dict):
            return module_report

    results = validator_payload.get("results")
    if isinstance(results, dict):
        return {
            "files": results,
            "total_failed": int(
                (validator_payload.get("summary") or {}).get("total_failed", 0) or 0
            ),
        }

    return {}


def _build_validation_signature(validation_report: Dict[str, Any]) -> str:
    """Build deterministic signature from grouped validation failures."""
    report = _extract_module_validation_report(
        validation_report.get("report") or {},
        str(validation_report.get("module") or "").strip(),
    )
    grouped = (report or {}).get("files") if isinstance(report, dict) else {}
    signature_items: List[str] = []

    for category in sorted(grouped.keys()):
        section = grouped.get(category) or {}
        failed_count = int(section.get("failed", 0) or 0)
        if failed_count <= 0:
            continue
        errors = section.get("errors") or []
        trimmed = [str(item).strip() for item in errors[:20]]
        signature_items.append(
            json.dumps(
                {
                    "category": category,
                    "failed": failed_count,
                    "errors": trimmed,
                },
                sort_keys=True,
            )
        )

    return "|".join(signature_items)


def _extract_failure_categories(validation_report: Dict[str, Any]) -> Dict[str, int]:
    """Return failing validator categories and counts."""
    result: Dict[str, int] = {}
    report = _extract_module_validation_report(
        validation_report.get("report") or {},
        str(validation_report.get("module") or "").strip(),
    )
    grouped = (report or {}).get("files") if isinstance(report, dict) else {}
    for category, section in grouped.items():
        failed_count = int((section or {}).get("failed", 0) or 0)
        if failed_count > 0:
            result[str(category)] = failed_count
    return result


def _detect_build_system_defect(
    build_result: Dict[str, Any],
    module_dir: Path,
    validation_report: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Classify obvious generator/runtime defects that should fail closed."""
    build_error = str(build_result.get("error") or "")
    lowered = build_error.lower()
    system_markers = [
        "handle_provider_error",
        "is not defined",
        "file name too long",
        "traceback",
    ]
    if any(marker in lowered for marker in system_markers):
        return {
            "status": "build_system_failed",
            "reason": "builder_runtime_exception",
            "error": build_error,
        }

    if not module_dir.exists():
        return {
            "status": "build_system_failed",
            "reason": "module_directory_missing",
            "module_dir": str(module_dir),
        }

    summary_path = module_dir / "MODULE_SUMMARY.md"
    try:
        summary_text = (
            summary_path.read_text(encoding="utf-8") if summary_path.exists() else ""
        )
    except Exception:
        summary_text = ""

    if "name 'handle_provider_error' is not defined" in summary_text:
        return {
            "status": "build_system_failed",
            "reason": "builder_runtime_exception_marker",
            "module_summary_path": str(summary_path),
        }

    stderr_tail = str(validation_report.get("stderr_tail") or "")
    if "jsonschema is not installed" in stderr_tail.lower():
        return {
            "status": "build_system_failed",
            "reason": "validator_dependency_missing",
            "stderr_tail": stderr_tail,
        }

    return None


def _deterministic_fix_party_month(module_dir: Path) -> Dict[str, Any]:
    """Normalize party tracker month to allowed schema value."""
    party_path = module_dir / "party_tracker.json"
    if not party_path.exists():
        return {"status": "skipped", "reason": "party_tracker_missing"}

    party_data = safe_read_json(str(party_path))
    if not isinstance(party_data, dict):
        return {"status": "failed", "reason": "party_tracker_unreadable"}

    world = party_data.setdefault("worldConditions", {})
    if not isinstance(world, dict):
        party_data["worldConditions"] = {}
        world = party_data["worldConditions"]

    raw_month = str(world.get("month") or "").strip()
    if raw_month in VALID_GAME_MONTHS:
        return {
            "status": "skipped",
            "reason": "month_already_valid",
            "month": raw_month,
        }

    normalized = MONTH_CONVERSION.get(raw_month, "Springmonth")
    world["month"] = normalized
    write_ok = safe_write_json(str(party_path), party_data)
    if not write_ok:
        return {
            "status": "failed",
            "reason": "party_tracker_write_failed",
            "month_before": raw_month,
            "month_after": normalized,
        }

    return {
        "status": "changed",
        "reason": "month_normalized",
        "month_before": raw_month,
        "month_after": normalized,
    }


def _deterministic_materialize_monsters(module_slug: str) -> Dict[str, Any]:
    """Hydrate module monster references using the shared convergence contract."""
    from scripts.homebrew_materialize_monsters import materialize_monsters

    hydration_result = materialize_monsters(
        module_slug=module_slug,
        strict=False,
        dry_run=False,
    )

    blocked_count = int(hydration_result.get("blocked_count", 0) or 0)
    created_count = int(hydration_result.get("created_count", 0) or 0)
    status = str(hydration_result.get("status") or "success").strip().lower()

    if status == "failed" or blocked_count > 0:
        return {
            "status": "failed",
            "reason": "monster_hydration_blocked",
            "hydration_result": hydration_result,
        }

    return {
        "status": "changed" if created_count > 0 else "skipped",
        "reason": "shared_monster_hydration",
        "hydration_result": hydration_result,
    }


def _deterministic_fix_spatial_contract(module_dir: Path) -> Dict[str, Any]:
    """Repair spatial parity and directional contract using authored connectivity."""
    remediation = remediate_module(
        module_path=module_dir,
        apply=True,
        force_relayout=True,
    )
    errors = remediation.get("errors") or []
    if errors:
        return {
            "status": "failed",
            "reason": "spatial_remediation_errors",
            "remediation": remediation,
        }

    changed = int(remediation.get("changed", 0) or 0)
    return {
        "status": "changed" if changed > 0 else "skipped",
        "reason": "spatial_remediation",
        "remediation": remediation,
    }


def _slugify_name(raw_name: str) -> str:
    """Create stable lowercase slug for context keys."""
    lowered = str(raw_name or "").strip().lower().replace("'", "")
    lowered = re.sub(r"[^a-z0-9]+", "_", lowered)
    return lowered.strip("_")


def _collect_area_location_index(module_dir: Path) -> Dict[str, Dict[str, str]]:
    """Build location index from area files."""
    index: Dict[str, Dict[str, str]] = {}
    areas_dir = module_dir / "areas"
    if not areas_dir.exists():
        return index

    for area_path in sorted(areas_dir.glob("*.json")):
        if "_BU" in area_path.name:
            continue
        area_data = safe_read_json(str(area_path)) or {}
        area_id = str(area_data.get("areaId") or "").strip()
        area_name = str(area_data.get("areaName") or "").strip()
        locations = area_data.get("locations") or []
        if not isinstance(locations, list):
            continue
        for location in locations:
            if not isinstance(location, dict):
                continue
            location_id = str(location.get("locationId") or "").strip()
            location_name = str(location.get("name") or "").strip()
            if not location_id:
                continue
            index[location_id] = {
                "area": area_id,
                "area_name": area_name,
                "name": location_name,
            }
    return index


def _deterministic_regenerate_derived_artifacts(module_dir: Path) -> Dict[str, Any]:
    """Regenerate minimal derived context and summary artifacts deterministically."""
    changed_items: List[str] = []
    failures: List[str] = []
    module_slug = module_dir.name

    context_path = module_dir / "module_context.json"
    context = safe_read_json(str(context_path)) if context_path.exists() else {}
    if not isinstance(context, dict):
        context = {}

    location_index = _collect_area_location_index(module_dir)
    existing_locations = (
        context.get("locations") if isinstance(context.get("locations"), dict) else {}
    )
    merged_locations = dict(existing_locations)
    for location_id, location_meta in location_index.items():
        merged_locations[location_id] = {
            "name": location_meta.get("name", ""),
            "area": location_meta.get("area", ""),
        }

    if merged_locations != existing_locations:
        context["locations"] = merged_locations
        changed_items.append("module_context.locations")

    areas = context.get("areas") if isinstance(context.get("areas"), dict) else {}
    if isinstance(areas, dict) and areas:
        for area_id, area_payload in areas.items():
            if not isinstance(area_payload, dict):
                continue
            area_location_ids = [
                location_id
                for location_id, location_meta in location_index.items()
                if location_meta.get("area") == area_id
            ]
            if not area_location_ids:
                continue
            existing_area_locations = area_payload.get("locations")
            if (
                not isinstance(existing_area_locations, list)
                or len(existing_area_locations) == 0
            ):
                area_payload["locations"] = area_location_ids
                changed_items.append(f"module_context.areas.{area_id}.locations")

    if changed_items:
        context.setdefault("module_id", module_slug)
        write_ok = safe_write_json(str(context_path), context)
        if not write_ok:
            failures.append("module_context_write_failed")

    summary_path = module_dir / "MODULE_SUMMARY.md"
    plot_path = module_dir / "module_plot.json"
    plot_data = safe_read_json(str(plot_path)) if plot_path.exists() else {}
    objective = str(plot_data.get("mainObjective") or "(missing)").strip()
    antagonist = str(plot_data.get("antagonist") or "(missing)").strip()

    try:
        summary_text = (
            summary_path.read_text(encoding="utf-8") if summary_path.exists() else ""
        )
    except Exception:
        summary_text = ""

    placeholder_present = "{self.module_data['mainPlot'" in summary_text
    if not summary_text or placeholder_present:
        module_title = str(
            context.get("module_name") or module_slug.replace("_", " ")
        ).strip()
        refreshed_summary = (
            f"# {module_title} - Module Summary\n\n"
            "## Main Plot\n"
            f"**Objective**: {objective}\n"
            f"**Antagonist**: {antagonist}\n"
        )
        try:
            summary_path.write_text(refreshed_summary, encoding="utf-8")
            changed_items.append("MODULE_SUMMARY.md")
        except Exception:
            failures.append("module_summary_write_failed")

    if failures:
        return {
            "status": "failed",
            "reason": "derived_regeneration_failed",
            "changed_items": changed_items,
            "failures": failures,
        }

    if changed_items:
        return {
            "status": "changed",
            "reason": "derived_artifacts_regenerated",
            "changed_items": sorted(set(changed_items)),
        }

    return {
        "status": "skipped",
        "reason": "derived_artifacts_already_stable",
    }


def _semantic_fix_npc_placement(module_dir: Path) -> Dict[str, Any]:
    """Apply narrow semantic patch for unplaced NPCs using existing locations only."""
    context_path = module_dir / "module_context.json"
    context = safe_read_json(str(context_path)) if context_path.exists() else {}
    if not isinstance(context, dict):
        return {"status": "failed", "reason": "module_context_unreadable"}

    npcs = context.get("npcs") if isinstance(context.get("npcs"), dict) else {}
    if not npcs:
        return {"status": "skipped", "reason": "no_npcs_in_context"}

    location_index = _collect_area_location_index(module_dir)
    if not location_index:
        return {"status": "skipped", "reason": "no_locations_available"}

    issues = (
        context.get("validation_issues")
        if isinstance(context.get("validation_issues"), list)
        else []
    )
    missing_names: List[str] = []
    for issue in issues:
        issue_text = str(issue)
        marker = "NPC '"
        if marker not in issue_text or "not placed in any location" not in issue_text:
            continue
        start = issue_text.find(marker) + len(marker)
        end = issue_text.find("'", start)
        if end > start:
            missing_names.append(issue_text[start:end])

    if not missing_names:
        return {"status": "skipped", "reason": "no_missing_npc_placement_issues"}

    first_location_id = sorted(location_index.keys())[0]
    first_location = location_index[first_location_id]
    placements_applied: List[Dict[str, str]] = []

    for npc_name in missing_names:
        slug = _slugify_name(npc_name)
        npc_entry = npcs.get(slug)
        if not isinstance(npc_entry, dict):
            # Fallback scan by exact display name.
            for _, candidate_entry in npcs.items():
                if not isinstance(candidate_entry, dict):
                    continue
                if str(candidate_entry.get("name") or "").strip() == npc_name:
                    npc_entry = candidate_entry
                    break
        if not isinstance(npc_entry, dict):
            continue

        appears_in = (
            npc_entry.get("appears_in")
            if isinstance(npc_entry.get("appears_in"), list)
            else []
        )
        if appears_in:
            continue

        npc_entry["appears_in"] = [
            {
                "area": first_location.get("area", ""),
                "location": first_location_id,
            }
        ]
        placements_applied.append(
            {
                "npc": str(npc_entry.get("name") or npc_name),
                "area": first_location.get("area", ""),
                "location": first_location_id,
            }
        )

    if not placements_applied:
        return {
            "status": "skipped",
            "reason": "no_semantic_npc_changes_applied",
            "missing_names": missing_names,
        }

    write_ok = safe_write_json(str(context_path), context)
    if not write_ok:
        return {
            "status": "failed",
            "reason": "module_context_write_failed",
            "placements_applied": placements_applied,
        }

    return {
        "status": "changed",
        "reason": "npc_placement_backfilled",
        "placements_applied": placements_applied,
    }


def _semantic_align_summary(module_dir: Path) -> Dict[str, Any]:
    """Apply narrow semantic patch to keep summary objective/antagonist coherent."""
    summary_path = module_dir / "MODULE_SUMMARY.md"
    plot_path = module_dir / "module_plot.json"
    if not summary_path.exists() or not plot_path.exists():
        return {"status": "skipped", "reason": "summary_or_plot_missing"}

    plot_data = safe_read_json(str(plot_path)) or {}
    objective = str(plot_data.get("mainObjective") or "").strip()
    antagonist = str(plot_data.get("antagonist") or "").strip()
    if not objective and not antagonist:
        return {"status": "skipped", "reason": "plot_objective_missing"}

    try:
        summary_text = summary_path.read_text(encoding="utf-8")
    except Exception:
        return {"status": "failed", "reason": "summary_unreadable"}

    updated_text = summary_text
    if objective:
        updated_text = re.sub(
            r"\*\*Objective\*\*:.*",
            f"**Objective**: {objective}",
            updated_text,
            count=1,
        )
    if antagonist:
        updated_text = re.sub(
            r"\*\*Antagonist\*\*:.*",
            f"**Antagonist**: {antagonist}",
            updated_text,
            count=1,
        )

    if updated_text == summary_text:
        return {"status": "skipped", "reason": "summary_already_aligned"}

    try:
        summary_path.write_text(updated_text, encoding="utf-8")
    except Exception:
        return {"status": "failed", "reason": "summary_write_failed"}

    return {
        "status": "changed",
        "reason": "summary_aligned_with_plot",
    }


def _run_deterministic_repairs(
    module_slug: str,
    module_dir: Path,
    failure_categories: Dict[str, int],
) -> Dict[str, Any]:
    """Run deterministic repair domains for structural failures."""
    report: Dict[str, Any] = {
        "status": "success",
        "mode": "deterministic",
        "started_at": _utc_now_iso(),
        "categories": failure_categories,
        "repairs": {},
        "changed": False,
    }

    month_result = _deterministic_fix_party_month(module_dir)
    report["repairs"]["party_month"] = month_result

    if "reference_integrity" in failure_categories:
        monster_result = _deterministic_materialize_monsters(module_slug)
    else:
        monster_result = {
            "status": "skipped",
            "reason": "reference_integrity_not_failing",
        }
    report["repairs"]["monster_materialization"] = monster_result

    if "spatial_contract" in failure_categories:
        spatial_result = _deterministic_fix_spatial_contract(module_dir)
    else:
        spatial_result = {
            "status": "skipped",
            "reason": "spatial_contract_not_failing",
        }
    report["repairs"]["spatial_contract"] = spatial_result

    derived_result = _deterministic_regenerate_derived_artifacts(module_dir)
    report["repairs"]["derived_artifacts"] = derived_result

    if any(
        str((result or {}).get("status") or "") == "failed"
        for result in report["repairs"].values()
    ):
        report["status"] = "failed"

    report["changed"] = any(
        str((result or {}).get("status") or "") == "changed"
        for result in report["repairs"].values()
    )
    report["completed_at"] = _utc_now_iso()
    return report


def _run_semantic_repairs(module_dir: Path) -> Dict[str, Any]:
    """Run narrow semantic repair domains after deterministic passes."""
    report: Dict[str, Any] = {
        "status": "success",
        "mode": "semantic",
        "started_at": _utc_now_iso(),
        "repairs": {},
        "changed": False,
    }

    npc_result = _semantic_fix_npc_placement(module_dir)
    summary_result = _semantic_align_summary(module_dir)
    report["repairs"]["npc_placement"] = npc_result
    report["repairs"]["summary_alignment"] = summary_result

    if any(
        str((result or {}).get("status") or "") == "failed"
        for result in report["repairs"].values()
    ):
        report["status"] = "failed"

    report["changed"] = any(
        str((result or {}).get("status") or "") == "changed"
        for result in report["repairs"].values()
    )
    report["completed_at"] = _utc_now_iso()
    return report


def _run_structural_readiness_audit(module_slug: str) -> Dict[str, Any]:
    """Run readiness audit in structural profile and normalize result."""
    report = audit_module_readiness(
        module_slug=module_slug,
        include_gameplay_gate=False,
        include_sidecar_gate=False,
        include_continuity_gate=False,
        include_schema_gate=True,
        strict_gameplay=False,
        strict_continuity=False,
    )

    gates = report.get("gates") if isinstance(report, dict) else {}
    schema_gate = (gates or {}).get("schema") if isinstance(gates, dict) else {}
    gameplay_gate = (gates or {}).get("gameplay") if isinstance(gates, dict) else {}

    return {
        "status": "pass" if str(schema_gate.get("status") or "") == "pass" else "fail",
        "profile": "structural_pre_finisher_v1",
        "checked_at": _utc_now_iso(),
        "schema_gate": schema_gate,
        "gameplay_gate": gameplay_gate,
        "report": report,
    }


def run_toolkit_homebrew_readiness_gate(
    workspace: Path,
    job_id: str,
    state_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    """Run post-build structural readiness validation and bounded repair loops."""
    files = get_workspace_files(workspace)
    build_result = load_json_artifact(files["build_result"])
    module_slug = str(build_result.get("module_name") or "").strip()
    if not module_slug:
        return {
            "status": "build_system_failed",
            "stage": "readiness",
            "reason": "module_name_missing_in_build_result",
            "job_id": job_id,
        }

    module_dir = Path("modules") / module_slug
    repair_attempts: List[Dict[str, Any]] = []

    def _emit_state(status: str, payload: Optional[Dict[str, Any]] = None) -> None:
        if state_callback is None:
            return
        try:
            state_callback(status, payload or {})
        except Exception as callback_error:
            warning(
                f"TOOLKIT_HOMEBREW: Readiness state callback failed for {job_id}: {callback_error}",
                category="web_interface",
            )

    _emit_state("validating", {"module_name": module_slug})
    validation_report = _run_validator(module_slug)
    persist_readiness_validation_artifact(workspace, validation_report)

    defect = _detect_build_system_defect(build_result, module_dir, validation_report)
    if defect:
        readiness_result = {
            "status": "build_system_failed",
            "stage": "readiness",
            "job_id": job_id,
            "module_name": module_slug,
            "build_result": build_result,
            "validation": validation_report,
            "repair_attempts": repair_attempts,
            "defect": defect,
            "completed_at": _utc_now_iso(),
        }
        persist_repair_report_artifact(
            workspace,
            {
                "status": "failed",
                "reason": "build_system_failed",
                "repair_attempts": repair_attempts,
                "defect": defect,
                "updated_at": _utc_now_iso(),
            },
        )
        return readiness_result

    previous_signature = _build_validation_signature(validation_report)
    deterministic_passes = 0
    semantic_passes = 0

    while validation_report.get("status") != "pass":
        failure_categories = _extract_failure_categories(validation_report)

        if deterministic_passes < MAX_DETERMINISTIC_PASSES:
            deterministic_passes += 1
            _emit_state(
                "repairing_deterministic",
                {
                    "pass": deterministic_passes,
                    "max_passes": MAX_DETERMINISTIC_PASSES,
                    "categories": failure_categories,
                },
            )
            det_report = _run_deterministic_repairs(
                module_slug, module_dir, failure_categories
            )
            det_report["pass"] = deterministic_passes
            repair_attempts.append(det_report)
            if det_report.get("status") == "failed":
                break
        elif semantic_passes < MAX_SEMANTIC_PASSES:
            semantic_passes += 1
            _emit_state(
                "repairing_semantic",
                {
                    "pass": semantic_passes,
                    "max_passes": MAX_SEMANTIC_PASSES,
                    "categories": failure_categories,
                },
            )
            semantic_report = _run_semantic_repairs(module_dir)
            semantic_report["pass"] = semantic_passes
            repair_attempts.append(semantic_report)
            if semantic_report.get("status") == "failed":
                break
        else:
            break

        _emit_state("validating", {"module_name": module_slug, "revalidation": True})
        validation_report = _run_validator(module_slug)
        persist_readiness_validation_artifact(workspace, validation_report)
        current_signature = _build_validation_signature(validation_report)

        if validation_report.get("status") == "pass":
            previous_signature = current_signature
            break

        if current_signature == previous_signature:
            info(
                (
                    f"TOOLKIT_HOMEBREW: Readiness validation signature unchanged for "
                    f"job={job_id} module={module_slug}; stopping automatic repair"
                ),
                category="web_interface",
            )
            previous_signature = current_signature
            break

        previous_signature = current_signature

    _emit_state("validating", {"module_name": module_slug, "audit": True})
    audit_report = _run_structural_readiness_audit(module_slug)
    persist_readiness_audit_artifact(workspace, audit_report)

    persist_repair_report_artifact(
        workspace,
        {
            "status": "success",
            "updated_at": _utc_now_iso(),
            "module_name": module_slug,
            "repair_attempts": repair_attempts,
            "deterministic_passes": deterministic_passes,
            "semantic_passes": semantic_passes,
            "validation_signature": previous_signature,
        },
    )

    readiness_ok = (
        validation_report.get("status") == "pass"
        and audit_report.get("status") == "pass"
    )

    final_status = "ready_for_finishing" if readiness_ok else "repair_budget_exhausted"
    return {
        "status": final_status,
        "stage": "readiness",
        "job_id": job_id,
        "module_name": module_slug,
        "build_result": build_result,
        "validation": validation_report,
        "readiness_audit": audit_report,
        "repair_attempts": repair_attempts,
        "deterministic_passes": deterministic_passes,
        "semantic_passes": semantic_passes,
        "ready_for_finishing": readiness_ok,
        "workspace_artifacts": {
            "readiness_validation_report": str(files["readiness_validation_report"]),
            "readiness_audit_report": str(files["readiness_audit_report"]),
            "repair_report": str(files["repair_report"]),
        },
        "completed_at": _utc_now_iso(),
    }
