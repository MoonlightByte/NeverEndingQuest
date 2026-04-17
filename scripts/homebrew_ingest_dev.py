#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest CLI - Homebrew Ingest Orchestrator
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Developer-only orchestration pipeline for Homebrew ingest:
preflight -> transform -> dry-run -> duplicate guard -> strict ingest -> sidecar audit -> registry verify -> media extract -> media handles -> portrait prewarm.

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

# 1. Standard library imports
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.importers.homebrewery_importer import import_homebrewery_adventure_to_module
from utils.module_semantic_authority import enrich_module_semantic_authority
from utils.toolkit_homebrew_upload_contract import (
    SOURCE_RIGHTS_USER_AUTHORED,
    VALID_SOURCE_RIGHTS_CLASSES,
    build_normalized_packet_placeholder,
    compute_sha256,
    ensure_workspace_placeholders,
    persist_normalized_packet_artifact,
    persist_preflight_artifact,
)

# Local scripts (same directory)
try:
    from homebrew_preflight import assess_source_readiness
    from homebrew_registry_guard import check_duplicate, verify_present
    from homebrew_sidecar_audit import audit_sidecar
    from homebrew_transform_to_deterministic import transform_source_to_deterministic
    from continuity_cross_ref_enrichment import enrich_continuity_cross_refs
except ImportError:
    from scripts.homebrew_preflight import assess_source_readiness
    from scripts.homebrew_registry_guard import check_duplicate, verify_present
    from scripts.homebrew_sidecar_audit import audit_sidecar
    from scripts.homebrew_transform_to_deterministic import (
        transform_source_to_deterministic,
    )
    from scripts.continuity_cross_ref_enrichment import enrich_continuity_cross_refs
from utils.file_operations import safe_read_json, safe_write_json

# Shared entrypoint for watcher parity (Prompt 1)
__all__ = ["run_ingest_pipeline"]


def _infer_stage_exit_code(stage: str) -> int:
    mapping = {
        "preflight": 1,
        "transform": 2,
        "dry_run": 3,
        "guard": 4,
        "ingest": 5,
        "continuity": 11,
        "semantic_authority": 12,
        "audit": 6,
        "verify": 7,
        "media_extract": 8,
        "media_handles": 9,
        "portrait_prewarm": 10,
    }
    return mapping.get(stage, 7)


def _normalize_continuity_contract(
    module_context: Dict[str, Any],
    module_plot: Dict[str, Any],
    strict: bool = True,
    alias_registry: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Normalize and validate any-order continuity contract for a module.

    Checks for required continuity keys and normalizes cross-module references.
    In strict mode, missing required keys results in error status.
    In warn-first mode, missing keys generate warnings but don't block.

    Args:
        module_context: Parsed module_context.json dict
        module_plot: Parsed module_plot.json dict
        strict: If True, missing required keys cause error; if False, warnings only
        alias_registry: Optional registry for alias resolution

    Returns:
        Continuity contract dict with status, version, keys present/missing,
        warnings, errors, normalized refs count, and alias resolution stats.
    """
    contract: Dict[str, Any] = {
        "status": "success",
        "version": "v1",
        "required_keys_present": [],
        "missing_required_keys": [],
        "warnings": [],
        "errors": [],
        "normalized_refs_count": 0,
        "alias_resolution": {"resolved": 0, "ambiguous": 0, "unresolved": 0},
    }

    REQUIRED_KEYS = [
        "continuity_version",
        "entry_state_variants",
        "cross_module_refs",
        "standalone_fallback",
    ]

    # Extract continuity section from module_context (may be nested under module_context or top-level)
    continuity_data = module_context.get("continuity") or module_context.get(
        "module_context", {}
    ).get("continuity", {})

    # Check for required keys
    for key in REQUIRED_KEYS:
        if key in continuity_data and continuity_data[key] is not None:
            contract["required_keys_present"].append(key)
        else:
            contract["missing_required_keys"].append(key)

    # Determine status based on strict mode and missing keys
    if contract["missing_required_keys"]:
        if strict:
            contract["status"] = "error"
            contract["errors"].append(
                f"Missing required continuity keys: {contract['missing_required_keys']}"
            )
        else:
            contract["status"] = "warning"
            contract["warnings"].append(
                f"Missing recommended continuity keys: {contract['missing_required_keys']}"
            )

    # Validate continuity_version if present
    if "continuity_version" in continuity_data:
        version = continuity_data["continuity_version"]
        if version != "v1":
            contract["warnings"].append(
                f"Unexpected continuity_version: {version} (expected v1)"
            )

    # Validate entry_state_variants structure if present
    if "entry_state_variants" in continuity_data:
        variants = continuity_data["entry_state_variants"]
        expected_variant_keys = ["cold_start", "partial_context", "late_arc"]
        if not isinstance(variants, dict):
            message = "entry_state_variants should be an object with keys cold_start/partial_context/late_arc"
            if strict:
                contract["status"] = "error"
                contract["errors"].append(message)
            else:
                contract["warnings"].append(message)
        else:
            missing_variant_keys = [
                key for key in expected_variant_keys if key not in variants
            ]
            if missing_variant_keys:
                message = f"entry_state_variants missing keys: {missing_variant_keys}"
                if strict:
                    contract["status"] = "error"
                    contract["errors"].append(message)
                else:
                    contract["warnings"].append(message)

    # Normalize cross_module_refs if present
    if "cross_module_refs" in continuity_data:
        refs = continuity_data["cross_module_refs"]
        if isinstance(refs, list):
            normalized_count = 0
            required_ref_keys = ["target_module", "entity_id", "relation", "confidence"]
            for ref in refs:
                if isinstance(ref, dict) and "target_module" in ref:
                    normalized_count += 1
                    missing_ref_keys = [
                        key for key in required_ref_keys if not ref.get(key)
                    ]
                    if missing_ref_keys:
                        contract["warnings"].append(
                            f"cross_module_ref missing required fields: {missing_ref_keys}"
                        )
                    confidence = ref.get("confidence")
                    if confidence and confidence not in ["high", "medium", "low"]:
                        contract["warnings"].append(
                            f"cross_module_ref has invalid confidence '{confidence}' (expected high|medium|low)"
                        )
                    # Check for alias ambiguity if registry provided
                    if alias_registry and "alias" in ref:
                        alias = ref["alias"]
                        alias_matches = alias_registry.get(alias, [])
                        if len(alias_matches) > 1:
                            contract["alias_resolution"]["ambiguous"] += 1
                            contract["warnings"].append(
                                f"Ambiguous alias '{alias}' resolves to multiple targets"
                            )
                        elif len(alias_matches) == 1:
                            contract["alias_resolution"]["resolved"] += 1
                        else:
                            contract["alias_resolution"]["unresolved"] += 1
            contract["normalized_refs_count"] = normalized_count
        else:
            contract["warnings"].append("cross_module_refs should be a list")

    # Validate standalone_fallback if present
    if "standalone_fallback" in continuity_data:
        fallback = continuity_data["standalone_fallback"]
        if not isinstance(fallback, dict):
            contract["warnings"].append("standalone_fallback should be a dict")
        elif "enabled" not in fallback:
            contract["warnings"].append("standalone_fallback missing 'enabled' flag")

    return contract


def _default_continuity_contract(module_slug: str) -> Dict[str, Any]:
    """Return additive continuity v1 defaults for new/legacy modules."""
    module_label = module_slug.replace("_", " ")
    return {
        "continuity_version": "v1",
        "entry_state_variants": {
            "cold_start": {
                "summary": (
                    f"Party enters {module_label} with no prior continuity context. "
                    "Present the opening conflict and immediate objective clearly."
                )
            },
            "partial_context": {
                "summary": (
                    f"Party enters {module_label} with partial prior context. "
                    "Reinforce known clues before branch-critical decisions."
                )
            },
            "late_arc": {
                "summary": (
                    f"Party enters {module_label} in late-arc state. "
                    "Provide compact recap and preserve ending accessibility."
                )
            },
        },
        "cross_module_refs": [],
        "standalone_fallback": {
            "enabled": True,
            "clue_sources": ["module_context", "module_plot"],
            "notes": (
                f"{module_slug} remains playable as a standalone module when "
                "cross-module continuity is unavailable."
            ),
        },
    }


def _ensure_continuity_contract_keys(
    module_context: Dict[str, Any], module_slug: str
) -> Dict[str, Any]:
    """Ensure required continuity keys are present before strict audit.

    Returns shape:
      {
        "module_context": dict,
        "changed": bool,
        "injected_keys": list[str]
      }
    """
    injected_keys: List[str] = []
    defaults = _default_continuity_contract(module_slug)

    continuity = module_context.get("continuity")
    if not isinstance(continuity, dict):
        continuity = {}
        module_context["continuity"] = continuity
        injected_keys.append("continuity")

    if continuity.get("continuity_version") is None:
        continuity["continuity_version"] = defaults["continuity_version"]
        injected_keys.append("continuity.continuity_version")

    variants = continuity.get("entry_state_variants")
    if not isinstance(variants, dict):
        continuity["entry_state_variants"] = defaults["entry_state_variants"]
        injected_keys.append("continuity.entry_state_variants")
    else:
        for variant_key in ["cold_start", "partial_context", "late_arc"]:
            if variant_key not in variants or not isinstance(
                variants.get(variant_key), dict
            ):
                variants[variant_key] = defaults["entry_state_variants"][variant_key]
                injected_keys.append(f"continuity.entry_state_variants.{variant_key}")

    if not isinstance(continuity.get("cross_module_refs"), list):
        continuity["cross_module_refs"] = defaults["cross_module_refs"]
        injected_keys.append("continuity.cross_module_refs")

    fallback = continuity.get("standalone_fallback")
    if not isinstance(fallback, dict):
        continuity["standalone_fallback"] = defaults["standalone_fallback"]
        injected_keys.append("continuity.standalone_fallback")
    else:
        if "enabled" not in fallback:
            fallback["enabled"] = True
            injected_keys.append("continuity.standalone_fallback.enabled")
        if "clue_sources" not in fallback or not isinstance(
            fallback.get("clue_sources"), list
        ):
            fallback["clue_sources"] = defaults["standalone_fallback"]["clue_sources"]
            injected_keys.append("continuity.standalone_fallback.clue_sources")
        if "notes" not in fallback:
            fallback["notes"] = defaults["standalone_fallback"]["notes"]
            injected_keys.append("continuity.standalone_fallback.notes")

    return {
        "module_context": module_context,
        "changed": len(injected_keys) > 0,
        "injected_keys": injected_keys,
    }


def _run_subprocess_stage(
    script_name: str,
    args: List[str],
    timeout_seconds: int,
    suppress_output: bool = True,
) -> Dict[str, Any]:
    """Run a subprocess stage with timeout and JSON output capture."""
    start_time = time.time()
    result = {
        "status": "planned",
        "duration_ms": 0,
        "stdout": "",
        "stderr": "",
        "parsed_output": None,
        "error": None,
    }

    try:
        script_path = Path(__file__).parent / script_name
        cmd = [sys.executable, str(script_path)] + args + ["--json"]

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )

        duration_ms = int((time.time() - start_time) * 1000)
        result["duration_ms"] = duration_ms
        result["stdout"] = proc.stdout
        result["stderr"] = proc.stderr
        result["returncode"] = proc.returncode

        # Try to parse JSON output
        try:
            parsed = json.loads(proc.stdout)
            result["parsed_output"] = parsed
            # Infer status from parsed output
            if parsed.get("status") in ["success", "downloaded", "degraded"]:
                result["status"] = (
                    "success" if parsed.get("status") == "success" else "degraded"
                )
            elif parsed.get("status") in ["skipped"]:
                result["status"] = "skipped"
            else:
                result["status"] = "failed"
        except json.JSONDecodeError:
            # Non-JSON output is a failure
            result["status"] = "failed"
            result["error"] = f"Invalid JSON output from {script_name}"

        return result

    except subprocess.TimeoutExpired:
        duration_ms = int((time.time() - start_time) * 1000)
        result["duration_ms"] = duration_ms
        result["status"] = "failed"
        result["error"] = f"Timeout after {timeout_seconds}s"
        return result

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        result["duration_ms"] = duration_ms
        result["status"] = "failed"
        result["error"] = str(e)
        return result


def _cleanup_failed_ingest(
    module_slug: Optional[str],
    cleanup_enabled: bool = True,
) -> Dict[str, Any]:
    """Archive or clean up failed/quarantined ingest artifacts.

    TABLETOP MODE: Added to prevent orphan module folders in modules/ after failed runs.
    Returns structured cleanup report without raising exceptions (fail-open).
    """
    result = {
        "status": "skipped",
        "action": "none",
        "reason": None,
        "archived_path": None,
        "error": None,
    }

    if not cleanup_enabled:
        result["reason"] = "Cleanup disabled by flag"
        return result

    if not module_slug:
        result["reason"] = "No module slug provided"
        return result

    try:
        module_path = Path("modules") / module_slug

        # Guard: Check if path exists and is a directory
        if not module_path.exists() or not module_path.is_dir():
            result["reason"] = "Module directory does not exist"
            return result

        # Guard: Check if module is registered/active in registry
        try:
            verify_result = verify_present(module_slug)
            if verify_result.get("present", False):
                result["status"] = "skipped"
                result["action"] = "none"
                result["reason"] = (
                    "Module is registered/active - cleanup skipped for safety"
                )
                return result
        except Exception:
            # If verification fails, be conservative and continue with cleanup
            pass

        # Create archive directory with timestamp
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_dir = (
            Path("modules/ingest/archive") / f"failed_{timestamp}_{module_slug}"
        )
        archive_dir.parent.mkdir(parents=True, exist_ok=True)

        # Move module directory to archive
        module_path.rename(archive_dir)

        result["status"] = "success"
        result["action"] = "archived"
        result["archived_path"] = str(archive_dir)
        result["reason"] = f"Moved {module_slug} to archive"

    except Exception as e:
        result["status"] = "failed"
        result["action"] = "error"
        result["reason"] = f"Cleanup error: {e}"
        result["error"] = str(e)

    return result


def run_ingest_pipeline(
    source_path: str,
    strict: bool = True,
    dry_run_only: bool = False,
    cleanup_failed: bool = True,
    no_media_extract: bool = False,
    no_prewarm: bool = False,
    media_timeout: int = 30,
    allow_provider: bool = False,
    allow_normalization_routing: bool = False,
    artifact_workspace: Optional[str] = None,
    source_rights_class: str = SOURCE_RIGHTS_USER_AUTHORED,
) -> Dict[str, Any]:
    """Execute full developer ingest pipeline with stop-on-failure semantics."""
    source_file = Path(source_path)
    if not source_file.exists() or not source_file.is_file():
        return {
            "status": "failed",
            "stage": "preflight",
            "source": source_path,
            "error": f"Source not found: {source_path}",
            "exit_code": 1,
        }

    # Stage 1: Preflight
    preflight = assess_source_readiness(str(source_file))

    workspace_path: Optional[Path] = None
    if artifact_workspace:
        workspace_path = Path(artifact_workspace)
        ensure_workspace_placeholders(workspace_path)
        persist_preflight_artifact(workspace_path, preflight)

    if source_rights_class not in VALID_SOURCE_RIGHTS_CLASSES:
        source_rights_class = SOURCE_RIGHTS_USER_AUTHORED

    routing_outcome = str(preflight.get("routing_outcome") or "")
    source_readable = bool(preflight.get("source_readable", False))
    if allow_normalization_routing and source_readable and routing_outcome == "normalization_required":
        source_hash = compute_sha256(source_file)
        normalized_packet = build_normalized_packet_placeholder(
            source_path=source_file,
            source_hash=source_hash,
            preflight=preflight,
            source_rights_class=source_rights_class,
        )
        normalized_packet_path = None
        if workspace_path:
            persist_normalized_packet_artifact(workspace_path, normalized_packet)
            normalized_packet_path = str(
                (workspace_path / "normalized_packet.json")
            )
        return {
            "status": "normalization_required",
            "stage": "routing",
            "source": str(source_file),
            "routing_outcome": routing_outcome,
            "source_readable": source_readable,
            "preflight": preflight,
            "normalized_packet": normalized_packet,
            "normalized_packet_path": normalized_packet_path,
            "artifact_workspace": str(workspace_path) if workspace_path else None,
            "exit_code": 0,
            "note": "Readable source routed to normalization-required contract path",
        }

    if not preflight.get("ready") and not preflight.get("can_auto_transform"):
        return {
            "status": "failed",
            "stage": "preflight",
            "source": str(source_file),
            "preflight": preflight,
            "error": "Preflight failed and source cannot be auto-transformed",
            "exit_code": 1,
        }

    prepared_path = str(source_file)
    temp_prepared_file = None

    # Stage 2: Transform (conditional)
    if not preflight.get("ready") and preflight.get("can_auto_transform"):
        temp_dir = Path(tempfile.mkdtemp(prefix="neq_homebrew_"))
        transformed_name = f"prepared_{source_file.stem}.md"
        temp_prepared_file = temp_dir / transformed_name
        transform_result = transform_source_to_deterministic(
            str(source_file), str(temp_prepared_file)
        )

        if transform_result.get("status") != "success":
            return {
                "status": "failed",
                "stage": "transform",
                "source": str(source_file),
                "preflight": preflight,
                "transform": transform_result,
                "error": transform_result.get("error", "Transform failed"),
                "exit_code": 2,
            }
        prepared_path = str(temp_prepared_file)

    # Determine module slug from dry-run importer call.
    # Stage 3: Deterministic dry-run
    dry_run_result = import_homebrewery_adventure_to_module(
        source_path=prepared_path,
        strict=strict,
        use_deterministic=True,
        dry_run=True,
    )

    module_slug = dry_run_result.get("module_slug")

    if dry_run_result.get("status") != "dry_run" or not dry_run_result.get(
        "validation", {}
    ).get("passed", False):
        return {
            "status": "failed",
            "stage": "dry_run",
            "source": str(source_file),
            "prepared": prepared_path,
            "module_slug": module_slug,
            "dry_run": dry_run_result,
            "error": "Dry-run validation failed",
            "exit_code": 3,
        }

    # Stage 4: Registry guard
    guard_result = check_duplicate(module_slug)
    if not guard_result.get("safe_to_proceed", False):
        return {
            "status": "failed",
            "stage": "guard",
            "source": str(source_file),
            "prepared": prepared_path,
            "module_slug": module_slug,
            "guard": guard_result,
            "error": "Registry guard detected conflicts",
            "exit_code": 4,
        }

    # Handle dry-run only mode
    if dry_run_only:
        result = {
            "status": "success",
            "stage": "dry_run",
            "source": str(source_file),
            "prepared": prepared_path,
            "module_slug": module_slug,
            "dry_run": dry_run_result,
            "guard": guard_result,
            "registry_verified": False,
            "exit_code": 0,
            "note": "Dry-run only mode; strict ingest not executed",
        }

        # Add skipped media stages in dry-run mode
        if not no_media_extract:
            result["media_extraction"] = {"status": "skipped", "note": "Dry-run mode"}
            result["media_handles"] = {"status": "skipped", "note": "Dry-run mode"}
        if not no_prewarm:
            result["portrait_prewarm"] = {"status": "skipped", "note": "Dry-run mode"}

        return result

    # Stage 5: Strict ingest
    ingest_result = import_homebrewery_adventure_to_module(
        source_path=prepared_path,
        strict=strict,
        use_deterministic=True,
        dry_run=False,
    )

    if ingest_result.get("status") != "success":
        # TABLETOP MODE: Cleanup failed ingest artifacts before returning
        cleanup_result = _cleanup_failed_ingest(
            module_slug, cleanup_enabled=cleanup_failed
        )
        return {
            "status": "failed",
            "stage": "ingest",
            "source": str(source_file),
            "prepared": prepared_path,
            "module_slug": module_slug,
            "ingest": ingest_result,
            "cleanup_failed_ingest": cleanup_result,
            "error": "Strict ingest failed or quarantined",
            "exit_code": 5,
        }

    # Stage 6: Continuity normalization (any-order module support)
    continuity_contract = None
    continuity_patch = {"changed": False, "injected_keys": []}
    continuity_enrichment = {
        "status": "skipped",
        "changed": False,
        "added_refs": [],
        "existing_count": 0,
        "final_count": 0,
    }
    if module_slug:
        try:
            # Load module context and plot for continuity validation
            module_dir = Path("modules") / module_slug
            context_path = module_dir / "module_context.json"
            plot_path = module_dir / "module_plot.json"

            module_context = {}
            module_plot = {}

            if context_path.exists():
                with open(context_path, "r", encoding="utf-8") as f:
                    module_context = json.load(f)
            if plot_path.exists():
                with open(plot_path, "r", encoding="utf-8") as f:
                    module_plot = json.load(f)

            # TABLETOP MODE: Backfill required continuity keys before strict audit
            continuity_patch = _ensure_continuity_contract_keys(
                module_context, module_slug
            )
            module_context = continuity_patch["module_context"]

            # TABLETOP MODE: Enrich cross-module narrative refs before strict audit
            continuity_enrichment = enrich_continuity_cross_refs(
                module_slug=module_slug,
                module_context=module_context,
                module_plot=module_plot,
            )
            module_context = continuity_enrichment.get("module_context", module_context)

            if continuity_patch["changed"] or continuity_enrichment.get("changed"):
                write_ok = safe_write_json(str(context_path), module_context)
                if not write_ok:
                    error_msg = (
                        f"Failed to persist continuity normalization to {context_path}"
                    )
                    if strict:
                        return {
                            "status": "failed",
                            "stage": "continuity",
                            "source": str(source_file),
                            "prepared": prepared_path,
                            "module_slug": module_slug,
                            "continuity_contract": continuity_contract,
                            "continuity_patch": continuity_patch,
                            "continuity_enrichment": continuity_enrichment,
                            "error": error_msg,
                            "exit_code": 11,
                        }

            continuity_contract = _normalize_continuity_contract(
                module_context=module_context,
                module_plot=module_plot,
                strict=strict,
                alias_registry=None,  # Future: pass module alias registry
            )

            # Fail closed in strict mode if continuity contract has errors
            if strict and continuity_contract.get("status") == "error":
                error_msg = f"Continuity contract validation failed: {continuity_contract.get('errors', [])}"
                return {
                    "status": "failed",
                    "stage": "continuity",
                    "source": str(source_file),
                    "prepared": prepared_path,
                    "module_slug": module_slug,
                    "continuity_contract": continuity_contract,
                    "continuity_patch": continuity_patch,
                    "continuity_enrichment": continuity_enrichment,
                    "error": error_msg,
                    "exit_code": 11,
                }
        except Exception as e:
            # Fail-open in warn-first mode; strict mode treats as warning
            continuity_contract = {
                "status": "warning" if not strict else "error",
                "version": "v1",
                "required_keys_present": [],
                "missing_required_keys": [
                    "continuity_version",
                    "entry_state_variants",
                    "cross_module_refs",
                    "standalone_fallback",
                ],
                "warnings": [f"Continuity normalization exception: {e}"],
                "errors": [str(e)] if strict else [],
                "normalized_refs_count": 0,
                "alias_resolution": {"resolved": 0, "ambiguous": 0, "unresolved": 0},
            }

    # Stage 7: Sidecar audit (best effort; direct CLI ingest may not create sidecar)
    # TABLETOP MODE: Stage 6.5 - Semantic authority enrichment (fail-open)
    semantic_authority = {
        "status": "skipped",
        "changed": False,
        "warnings": [],
        "errors": [],
        "semantic_authority": {},
    }
    if module_slug:
        try:
            module_dir = Path("modules") / module_slug
            context_path = module_dir / "module_context.json"
            plot_path = module_dir / "module_plot.json"

            module_context = safe_read_json(str(context_path)) or {}
            module_plot = safe_read_json(str(plot_path)) or {}

            semantic_authority = enrich_module_semantic_authority(
                module_slug=module_slug,
                module_context=module_context,
                module_plot=module_plot,
                module_dir=module_dir,
            )

            if semantic_authority.get("changed"):
                write_ok = safe_write_json(
                    str(context_path),
                    semantic_authority.get("module_context") or module_context,
                )
                if not write_ok:
                    semantic_authority["status"] = "degraded"
                    semantic_authority.setdefault("warnings", []).append(
                        f"Failed to persist semantic_authority to {context_path}"
                    )
        except Exception as semantic_error:
            semantic_authority = {
                "status": "degraded",
                "changed": False,
                "warnings": [
                    f"Semantic authority enrichment exception: {semantic_error}"
                ],
                "errors": [],
                "semantic_authority": {},
            }

    # Stage 7: Sidecar audit (best effort; direct CLI ingest may not create sidecar)
    sidecar_audit = audit_sidecar(module_slug, require_success=True)
    if not sidecar_audit.get("valid"):
        sidecar_audit_note = (
            "Sidecar audit unavailable/invalid (expected for direct CLI ingest)"
        )
    else:
        sidecar_audit_note = None

    # Stage 7: Registry verification
    verify_result = verify_present(module_slug)
    if not verify_result.get("present", False):
        # TABLETOP MODE: Cleanup failed ingest artifacts before returning (carry-over fix from Prompt 1)
        cleanup_result = _cleanup_failed_ingest(
            module_slug, cleanup_enabled=cleanup_failed
        )
        return {
            "status": "failed",
            "stage": "verify",
            "source": str(source_file),
            "prepared": prepared_path,
            "module_slug": module_slug,
            "verify": verify_result,
            "cleanup_failed_ingest": cleanup_result,
            "error": "Module not present in registry after successful ingest",
            "exit_code": 7,
        }

    # TABLETOP MODE: Stage 7.5 - Monster materialization for combat readiness
    # Materialize module-local monster stat files from bestiary seeds
    mat_result = {"status": "skipped", "summary": {}}
    try:
        mat_script = Path(__file__).parent / "homebrew_materialize_monsters.py"
        if mat_script.exists() and module_slug:
            mat_args = [
                sys.executable,
                str(mat_script),
                "--module",
                module_slug,
                "--json",
            ]
            # Run materialization as subprocess to isolate errors
            mat_proc = subprocess.run(
                mat_args,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if mat_proc.returncode == 0 and mat_proc.stdout:
                try:
                    mat_result = json.loads(mat_proc.stdout)
                except json.JSONDecodeError:
                    mat_result = {
                        "status": "unknown",
                        "raw_output": mat_proc.stdout[:500],
                    }
            else:
                mat_result = {
                    "status": "error",
                    "returncode": mat_proc.returncode,
                    "stderr": mat_proc.stderr[:500] if mat_proc.stderr else None,
                }
    except Exception as e:
        mat_result = {"status": "error", "error": str(e)}

    # Determine overall status considering materialization
    overall_status = "success"
    if (
        mat_result.get("status") == "failed"
        or mat_result.get("missing_in_bestiary_count", 0) > 0
    ):
        overall_status = "degraded"

    # Initialize final result with core stages
    result = {
        "status": "success",
        "stage": "verify",
        "source": str(source_file),
        "prepared": prepared_path,
        "module_slug": module_slug,
        "areas": verify_result.get("areas_count", 0),
        "encounters": 0,
        "registry_verified": True,
        "dry_run": dry_run_result,
        "guard": guard_result,
        "ingest": ingest_result,
        "continuity_contract": continuity_contract,
        "continuity_patch": continuity_patch,
        "continuity_enrichment": continuity_enrichment,
        "semantic_authority": semantic_authority,
        "sidecar_audit": sidecar_audit,
        "sidecar_note": sidecar_audit_note,
        "verify": verify_result,
        "exit_code": 0,
    }

    # Aggregate warnings from media stages
    media_warnings = []

    # Stage 8: Media extraction (fail-open)
    if not no_media_extract:
        extract_result = _run_subprocess_stage(
            "homebrew_media_extract.py",
            ["--source", prepared_path, "--module-slug", module_slug],
            timeout_seconds=media_timeout,
        )
        result["media_extraction"] = extract_result

        # Collect warnings from extraction
        if extract_result.get("parsed_output", {}).get("warnings"):
            for warning in extract_result["parsed_output"]["warnings"]:
                media_warnings.append(
                    {
                        "stage": "media_extraction",
                        "type": warning.get("type", "warning"),
                        "message": warning.get("message", ""),
                        "url": warning.get("url"),
                    }
                )

        # Stage 9: Media handles (only if extraction attempted)
        if extract_result.get("status") in ["success", "degraded"]:
            handles_result = _run_subprocess_stage(
                "homebrew_media_handles.py",
                ["--slug", module_slug],
                timeout_seconds=media_timeout,
            )
            result["media_handles"] = handles_result

            # Note: handles stage doesn't typically have warnings, but check anyway
            if handles_result.get("status") == "failed":
                media_warnings.append(
                    {
                        "stage": "media_handles",
                        "type": "stage_failed",
                        "message": handles_result.get("error", "Unknown error"),
                    }
                )
    else:
        result["media_extraction"] = {
            "status": "skipped",
            "note": "--no-media-extract specified",
        }
        result["media_handles"] = {
            "status": "skipped",
            "note": "--no-media-extract specified",
        }

    # Stage 10: Portrait prewarm (fail-open)
    if not no_prewarm:
        prewarm_args = ["--slug", module_slug]
        if allow_provider:
            prewarm_args.append("--allow-provider")
        prewarm_result = _run_subprocess_stage(
            "homebrew_prewarm_portraits.py",
            prewarm_args,
            timeout_seconds=media_timeout * 2,  # Longer timeout for generation
        )
        result["portrait_prewarm"] = prewarm_result

        # Collect warnings from prewarm
        if prewarm_result.get("parsed_output", {}).get("warnings"):
            for warning in prewarm_result["parsed_output"]["warnings"]:
                media_warnings.append(
                    {
                        "stage": "portrait_prewarm",
                        "type": warning.get("type", "warning"),
                        "entity_type": warning.get("entity_type"),
                        "name": warning.get("name"),
                        "message": warning.get("message", ""),
                    }
                )

        # Check for failed generations
        prewarm_parsed = prewarm_result.get("parsed_output", {})
        npc_failed = prewarm_parsed.get("npcs", {}).get("failed", 0)
        monster_failed = prewarm_parsed.get("monsters", {}).get("failed", 0)
        if npc_failed > 0 or monster_failed > 0:
            media_warnings.append(
                {
                    "stage": "portrait_prewarm",
                    "type": "generation_failures",
                    "message": f"Failed: {npc_failed} NPCs, {monster_failed} monsters",
                }
            )
    else:
        result["portrait_prewarm"] = {
            "status": "skipped",
            "note": "--no-prewarm specified",
        }

    # Add aggregated warnings
    if media_warnings:
        result["media_warnings"] = media_warnings

        # Degrade overall status if any media stage failed (but don't fail ingest)
        has_failures = any(
            w.get("type") in ["stage_failed", "generation_failures"]
            for w in media_warnings
        )
        if has_failures and result["status"] == "success":
            result["status"] = "degraded"
            result["media_note"] = (
                "Some media stages encountered issues (see media_warnings)"
            )

    # Add monster materialization stage result
    result["monster_materialization"] = mat_result

    # Apply degraded status from materialization if applicable
    if overall_status == "degraded" and result["status"] == "success":
        result["status"] = "degraded"
        result["monster_materialization_note"] = (
            "Some seed monsters could not be resolved to bestiary entries"
        )

    # Add provider generation flag for cost transparency
    result["provider_generation_allowed"] = allow_provider

    if (
        semantic_authority.get("status") in {"degraded", "failed"}
        and result.get("status") == "success"
    ):
        result["status"] = "degraded"
        result["semantic_authority_note"] = (
            "Semantic authority enrichment reported non-blocking diagnostics; "
            "publishable gating is out of scope for this phase."
        )

    # Persist media stages to sidecar (if sidecar exists)
    sidecar_persistence = _persist_media_to_sidecar(
        module_slug=module_slug,
        media_extraction=result.get("media_extraction"),
        media_handles=result.get("media_handles"),
        portrait_prewarm=result.get("portrait_prewarm"),
        media_warnings=result.get("media_warnings"),
        continuity_contract=result.get("continuity_contract"),
        continuity_enrichment=result.get("continuity_enrichment"),
        semantic_authority=result.get("semantic_authority"),
    )
    if sidecar_persistence.get("success"):
        result["sidecar_persisted"] = True
    else:
        result["sidecar_persisted"] = False
        result["sidecar_persistence_note"] = sidecar_persistence.get(
            "error", "Unknown persistence issue"
        )

    return result


def _persist_media_to_sidecar(
    module_slug: Optional[str],
    media_extraction: Optional[Dict[str, Any]],
    media_handles: Optional[Dict[str, Any]],
    portrait_prewarm: Optional[Dict[str, Any]],
    media_warnings: Optional[List[Dict[str, Any]]],
    continuity_contract: Optional[Dict[str, Any]],
    continuity_enrichment: Optional[Dict[str, Any]] = None,
    semantic_authority: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Persist media stage blocks into existing sidecar artifact.

    TABLETOP MODE: Added to support homebrew ingest media stage persistence.
    Finds the latest sidecar for module_slug and appends media blocks.
    Fail-open: returns error but doesn't block if sidecar not found or unwritable.
    """
    from homebrew_sidecar_audit import find_latest_sidecar_for_slug

    result = {"success": False, "error": None, "sidecar_path": None}

    try:
        if not module_slug:
            result["error"] = "No module slug available for sidecar persistence"
            return result

        sidecar_path = find_latest_sidecar_for_slug(module_slug)
        if not sidecar_path:
            result["error"] = f"No sidecar found for slug: {module_slug}"
            return result

        # Load existing sidecar
        with open(sidecar_path, "r", encoding="utf-8") as f:
            sidecar_data = json.load(f)

        # Ensure result section exists
        if "result" not in sidecar_data:
            sidecar_data["result"] = {}

        # Add media stages to result section (canonical keys)
        if media_extraction:
            sidecar_data["result"]["media_extraction"] = _sanitize_stage_for_sidecar(
                media_extraction
            )
        if media_handles:
            sidecar_data["result"]["media_handles"] = _sanitize_stage_for_sidecar(
                media_handles
            )
        if portrait_prewarm:
            sidecar_data["result"]["portrait_prewarm"] = _sanitize_stage_for_sidecar(
                portrait_prewarm
            )
        if media_warnings:
            sidecar_data["result"]["media_warnings"] = media_warnings
        if continuity_contract:
            sidecar_data["result"]["continuity_contract"] = continuity_contract
        if continuity_enrichment:
            sidecar_data["result"]["continuity_enrichment"] = continuity_enrichment
        if semantic_authority:
            sidecar_data["result"]["semantic_authority"] = semantic_authority

        # Atomic write
        tmp_path = sidecar_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(sidecar_data, f, indent=2)
        tmp_path.replace(sidecar_path)

        result["success"] = True
        result["sidecar_path"] = str(sidecar_path)

    except Exception as e:
        result["error"] = f"Failed to persist ingest stages: {e}"

    return result


def _sanitize_stage_for_sidecar(stage_data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize stage data for sidecar persistence (remove large internal fields)."""
    sanitized = {
        "status": stage_data.get("status"),
        "duration_ms": stage_data.get("duration_ms"),
    }

    # Include parsed output summary if available
    parsed = stage_data.get("parsed_output")
    if parsed and isinstance(parsed, dict):
        # For media extraction: include summary counts
        if "detected_urls" in parsed:
            sanitized["detected_count"] = len(parsed.get("detected_urls", []))
            sanitized["extracted_count"] = parsed.get("extracted_count", 0)
            sanitized["warning_count"] = parsed.get("warning_count", 0)
        # For media handles: include handle count
        if "handle_count" in parsed:
            sanitized["handle_count"] = parsed.get("handle_count", 0)
        # For prewarm: include counters
        if "npcs" in parsed:
            sanitized["npcs"] = parsed.get("npcs")
        if "monsters" in parsed:
            sanitized["monsters"] = parsed.get("monsters")

    return sanitized


def _create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="homebrew_ingest_dev",
        description="Developer-only Homebrew ingest orchestration pipeline",
    )
    parser.add_argument(
        "--source", type=str, required=True, help="Source markdown/text path"
    )
    parser.add_argument(
        "--strict", action="store_true", default=True, help="Enable strict ingest mode"
    )
    parser.add_argument(
        "--no-strict", dest="strict", action="store_false", help="Disable strict mode"
    )
    parser.add_argument(
        "--dry-run", action="store_true", default=False, help="Stop after dry-run stage"
    )
    parser.add_argument(
        "--json", action="store_true", default=False, help="Output JSON"
    )

    # Cleanup flags
    parser.add_argument(
        "--cleanup-failed",
        action="store_true",
        default=True,
        help="Archive failed/quarantined module artifacts (default: enabled)",
    )
    parser.add_argument(
        "--no-cleanup-failed",
        dest="cleanup_failed",
        action="store_false",
        help="Disable cleanup of failed/quarantined artifacts",
    )

    # Media stage flags
    parser.add_argument(
        "--no-media-extract",
        action="store_true",
        default=False,
        help="Skip media extraction and handle generation stages",
    )
    parser.add_argument(
        "--no-prewarm",
        action="store_true",
        default=False,
        help="Skip portrait prewarm stage",
    )
    parser.add_argument(
        "--media-timeout",
        type=int,
        default=30,
        help="Timeout in seconds for media stage subprocess calls (default: 30)",
    )
    parser.add_argument(
        "--allow-provider",
        action="store_true",
        default=False,
        help="Allow paid provider image generation in prewarm stage (default: disabled)",
    )

    return parser


def _print_json_or_text(payload: Dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2))
    else:
        print("=" * 60)
        print("HOMEBREW INGEST DEV")
        print("=" * 60)
        print(f"status: {payload.get('status')}")
        print(f"stage: {payload.get('stage')}")
        print(f"source: {payload.get('source')}")
        print(f"prepared: {payload.get('prepared')}")
        print(f"module_slug: {payload.get('module_slug')}")

        # Core stages
        if payload.get("status") == "success" or payload.get("status") == "degraded":
            print(f"areas: {payload.get('areas')}")
            print(f"registry_verified: {payload.get('registry_verified')}")

            # Media stages summary
            if "media_extraction" in payload:
                me = payload["media_extraction"]
                print(
                    f"media_extraction: {me.get('status')} ({me.get('duration_ms', 0)}ms)"
                )
            if "media_handles" in payload:
                mh = payload["media_handles"]
                print(
                    f"media_handles: {mh.get('status')} ({mh.get('duration_ms', 0)}ms)"
                )
            if "portrait_prewarm" in payload:
                pp = payload["portrait_prewarm"]
                print(
                    f"portrait_prewarm: {pp.get('status')} ({pp.get('duration_ms', 0)}ms)"
                )

            # Media warnings
            if payload.get("media_warnings"):
                print(f"media_warnings: {len(payload['media_warnings'])} warning(s)")

            if payload.get("sidecar_note"):
                print(f"note: {payload.get('sidecar_note')}")
            if payload.get("media_note"):
                print(f"media_note: {payload.get('media_note')}")
        else:
            print(f"error: {payload.get('error')}")


def main() -> None:
    parser = _create_parser()
    args = parser.parse_args()

    payload = run_ingest_pipeline(
        args.source,
        strict=args.strict,
        dry_run_only=args.dry_run,
        cleanup_failed=args.cleanup_failed,
        no_media_extract=args.no_media_extract,
        no_prewarm=args.no_prewarm,
        media_timeout=args.media_timeout,
        allow_provider=args.allow_provider,
    )
    _print_json_or_text(payload, args.json)
    sys.exit(
        payload.get("exit_code", _infer_stage_exit_code(payload.get("stage", "verify")))
    )


if __name__ == "__main__":
    main()
