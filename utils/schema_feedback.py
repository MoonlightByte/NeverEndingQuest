"""Deterministic schema feedback for generator retries.

The issue helpers moved here from core/generators/location_generator.py,
which keeps its private names as aliases. The correction builders turn a
failed reply into the next request's feedback text by code only; nothing is
parsed from the model's text, and the text goes only into that request.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

import jsonschema


@dataclass(frozen=True)
class SchemaIssue:
    """One deterministic, user-prompt-safe schema issue."""

    path: str
    message: str


def compact_issue_message(message: Any, limit: int = 240) -> str:
    """Bound model-derived validation text before it enters a retry prompt."""
    compact = " ".join(str(message).split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


def json_path(parts) -> str:
    """Render a jsonschema path deterministically as dotted/indexed JSON."""
    rendered = ""
    for part in parts:
        if isinstance(part, int):
            rendered += f"[{part}]"
        else:
            rendered += ("." if rendered else "") + str(part)
    return rendered or "$"


def schema_issues(
    instance: Any,
    schema: Dict[str, Any],
    prefix=(),
) -> List[SchemaIssue]:
    """Return all schema errors with stable paths and stable ordering."""
    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(
        validator.iter_errors(instance),
        key=lambda error: (
            tuple(str(part) for part in error.absolute_path),
            str(error.validator),
            error.message,
        ),
    )
    issues = []
    for error in errors:
        path_parts = tuple(prefix) + tuple(error.absolute_path)
        if error.validator == "required" and isinstance(error.instance, dict):
            missing = sorted(
                key
                for key in error.validator_value
                if key not in error.instance
            )
            for key in missing:
                issues.append(
                    SchemaIssue(
                        json_path(path_parts + (key,)),
                        "required property is missing",
                    )
                )
            continue
        issues.append(
            SchemaIssue(
                json_path(path_parts),
                compact_issue_message(error.message),
            )
        )
    return sorted(issues, key=lambda issue: (issue.path, issue.message))


def format_schema_issues(issues: List[SchemaIssue], limit: int = 24) -> str:
    """Compact schema feedback without embedding the full model response."""
    shown = issues[:limit]
    rendered = "; ".join(
        f"{issue.path}: {issue.message}" for issue in shown
    )
    if len(issues) > limit:
        rendered += f"; ... {len(issues) - limit} additional issue(s)"
    return rendered


def validation_issues(instance: Any, schema: Dict[str, Any], error) -> List[SchemaIssue]:
    """The schema's issues, or the one issue a code check raised after the schema passed."""
    issues = schema_issues(instance, schema)
    if not issues:
        issues = [SchemaIssue(json_path(error.absolute_path), compact_issue_message(error.message))]
    return issues


def schema_correction(instance: Any, schema: Dict[str, Any], error) -> str:
    """The next request's feedback for a reply that parsed but failed validation."""
    return (
        "Your previous reply did not match the schema. Validation issues: "
        f"{format_schema_issues(validation_issues(instance, schema, error))}. "
        "Return the complete corrected JSON object only, with no Markdown."
    )


def json_correction(error) -> str:
    """The next request's feedback for a reply that was not valid JSON."""
    return (
        f"Your previous reply was not valid JSON: {error.msg} at line {error.lineno} "
        f"column {error.colno}. Return the complete JSON object only, with no Markdown."
    )


def issue_paths_for_log(issues: List[SchemaIssue], limit: int = 8) -> str:
    """The failing paths for a console/log line: ASCII-escaped, no values."""
    shown = [ascii(issue.path)[1:-1] for issue in issues[:limit]]
    rendered = ", ".join(shown)
    if len(issues) > limit:
        rendered += f", ... {len(issues) - limit} more"
    return rendered


def informed_retry_messages(base_messages: List[Dict[str, Any]], reply: str, correction: str) -> List[Dict[str, Any]]:
    """The first request plus the failed reply and its correction, rebuilt each attempt."""
    return list(base_messages) + [
        {"role": "assistant", "content": reply},
        {"role": "user", "content": correction},
    ]
