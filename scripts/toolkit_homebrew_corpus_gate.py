# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Script Utilities - Toolkit Homebrew Corpus Gate
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Shared fixture discovery and outcome classification helpers for
Phase 8 corpus-based quality gate validation.

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional


_TRACKED_FIXTURE_SPECS = [
    {
        "fixture_id": "pumpkin_king",
        "filename": "the_pumpkin_king.md",
        "label": "The Pumpkin King",
    },
    {
        "fixture_id": "garden_of_demons",
        "filename": "the_garden_of_demons.md",
        "label": "The Garden of Demons",
    },
    {
        "fixture_id": "pottsfield_burial",
        "filename": "a_pottsfield_burial.md",
        "label": "A Pottsfield Burial",
    },
    {
        "fixture_id": "drowning_lass",
        "filename": "murder_at_the_drowning_lass.md",
        "label": "Murder at the Drowning Lass",
    },
]

_ALLOWED_TERMINAL_STATUSES = {
    "completed",
    "not_publishable",
    "finishing_failed",
    "quarantined",
}

_CLASSIFICATION_MAP = {
    "completed": "publishable_pass",
    "not_publishable": "not_publishable_bounded",
    "finishing_failed": "finishing_failed_bounded",
    "quarantined": "quarantined_bounded",
}


def get_repo_root() -> Path:
    """Return repository root path for this script context."""
    return Path(__file__).resolve().parents[1]


def get_tracked_fixture_directory(repo_root: Optional[Path] = None) -> Path:
    """Return canonical tracked fixture directory for corpus gate tests."""
    base = repo_root or get_repo_root()
    return base / "scripts" / "fixtures" / "toolkit_homebrew_corpus"


def list_tracked_corpus_fixtures(repo_root: Optional[Path] = None) -> Dict[str, Any]:
    """Return tracked fixture list and missing fixture reports."""
    fixture_dir = get_tracked_fixture_directory(repo_root=repo_root)
    fixtures: List[Dict[str, Any]] = []
    skipped: List[Dict[str, str]] = []

    for spec in _TRACKED_FIXTURE_SPECS:
        fixture_path = fixture_dir / spec["filename"]
        fixture_entry = {
            "fixture_id": spec["fixture_id"],
            "label": spec["label"],
            "path": str(fixture_path),
            "source": "tracked",
            "exists": fixture_path.exists(),
        }
        fixtures.append(fixture_entry)
        if not fixture_path.exists():
            skipped.append(
                {
                    "fixture_id": spec["fixture_id"],
                    "source": "tracked",
                    "reason": "tracked_fixture_missing",
                    "path": str(fixture_path),
                }
            )

    return {
        "fixture_dir": str(fixture_dir),
        "fixtures": fixtures,
        "skipped": skipped,
    }


def list_external_corpus_fixtures(external_corpus_path: Optional[str]) -> Dict[str, Any]:
    """Return optional external fixtures with explicit skip reasons.

    No default external path is assumed. External fixtures are only loaded when
    an operator supplies a path.
    """
    fixtures: List[Dict[str, Any]] = []
    skipped: List[Dict[str, str]] = []

    raw_path = str(external_corpus_path or "").strip()
    if not raw_path:
        return {
            "fixtures": fixtures,
            "skipped": skipped,
            "external_path": "",
        }

    external_path = Path(raw_path)
    if not external_path.exists() or not external_path.is_dir():
        skipped.append(
            {
                "fixture_id": "external_corpus",
                "source": "external",
                "reason": "external_corpus_path_missing",
                "path": str(external_path),
            }
        )
        return {
            "fixtures": fixtures,
            "skipped": skipped,
            "external_path": str(external_path),
        }

    markdown_files = sorted(external_path.glob("*.md"))
    if not markdown_files:
        skipped.append(
            {
                "fixture_id": "external_corpus",
                "source": "external",
                "reason": "external_corpus_no_markdown",
                "path": str(external_path),
            }
        )
        return {
            "fixtures": fixtures,
            "skipped": skipped,
            "external_path": str(external_path),
        }

    for file_path in markdown_files:
        fixtures.append(
            {
                "fixture_id": f"external_{file_path.stem.lower().replace(' ', '_')}",
                "label": file_path.stem,
                "path": str(file_path),
                "source": "external",
                "exists": True,
            }
        )

    return {
        "fixtures": fixtures,
        "skipped": skipped,
        "external_path": str(external_path),
    }


def classify_uploader_terminal_status(status: str) -> str:
    """Map uploader terminal status to bounded corpus gate classification."""
    normalized = str(status or "").strip().lower()
    return _CLASSIFICATION_MAP.get(normalized, "unclassified_error")


def evaluate_terminal_outcome(status: str) -> Dict[str, Any]:
    """Return pass/fail evaluation for one uploader terminal status."""
    normalized = str(status or "").strip().lower()
    classification = classify_uploader_terminal_status(normalized)
    if normalized in _ALLOWED_TERMINAL_STATUSES:
        return {
            "status": normalized,
            "classification": classification,
            "pass": True,
            "reason": "bounded_terminal_outcome",
        }

    return {
        "status": normalized,
        "classification": classification,
        "pass": False,
        "reason": "unclassified_terminal_outcome",
    }


def evaluate_developer_upload_parity(
    ready_status: str,
    publishable_status: str,
    uploader_status: str,
) -> Dict[str, Any]:
    """Evaluate contract-level parity between developer and uploader outcomes."""
    normalized_ready = str(ready_status or "").strip().lower()
    normalized_publishable = str(publishable_status or "").strip().lower()
    normalized_uploader = str(uploader_status or "").strip().lower()

    if normalized_ready != "pass":
        return {
            "applicable": False,
            "pass": True,
            "reason": "ready_status_not_pass",
            "expected_uploader_status": "",
            "actual_uploader_status": normalized_uploader,
        }

    expected = "completed" if normalized_publishable == "pass" else "not_publishable"
    parity_pass = normalized_uploader == expected

    return {
        "applicable": True,
        "pass": parity_pass,
        "reason": "parity_match" if parity_pass else "parity_mismatch",
        "expected_uploader_status": expected,
        "actual_uploader_status": normalized_uploader,
    }


def build_corpus_gate_summary(
    run_results: List[Dict[str, Any]],
    skipped_fixtures: List[Dict[str, Any]],
    parity_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build bounded operator-facing summary for corpus gate runs."""
    attempted = len(run_results)
    skipped = len(skipped_fixtures)
    failed_runs = [result for result in run_results if not bool(result.get("pass"))]
    failed_parity = [result for result in parity_results if bool(result.get("applicable")) and not bool(result.get("pass"))]

    overall_pass = not failed_runs and not failed_parity

    classification_counts: Dict[str, int] = {}
    for result in run_results:
        key = str(result.get("classification") or "unknown")
        classification_counts[key] = classification_counts.get(key, 0) + 1

    return {
        "status": "pass" if overall_pass else "fail",
        "attempted": attempted,
        "skipped": skipped,
        "classification_counts": classification_counts,
        "failed_runs": failed_runs,
        "failed_parity": failed_parity,
        "run_results": run_results,
        "skipped_fixtures": skipped_fixtures,
        "parity_results": parity_results,
    }
