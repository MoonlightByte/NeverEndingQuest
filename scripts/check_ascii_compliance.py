# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest ASCII Compliance Checker
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple


@dataclass
class Violation:
    """Represents one non-ASCII character violation."""

    path: str
    line: int
    column: int
    codepoint: str
    char: str


@dataclass
class ScanResult:
    """Aggregated scan result data."""

    scanned_files: int
    files_with_violations: int
    violation_count: int
    fixed_files: int
    fixed_count: int
    violations: List[Violation]


def _load_policy(policy_path: Path) -> Dict[str, Any]:
    """Load policy JSON from disk."""
    raw = json.loads(policy_path.read_text(encoding="utf-8"))
    return {
        "include_extensions": set(raw.get("include_extensions", [])),
        "exclude_paths": set(raw.get("exclude_paths", [])),
        "replacement_map": raw.get("replacement_map", {}),
    }


def _is_excluded(path: Path, exclude_paths: Sequence[str]) -> bool:
    """Return True if path should be skipped by policy exclusions."""
    parts = set(path.parts)
    return any(excluded in parts for excluded in exclude_paths)


def _iter_candidate_files(
    roots: Iterable[Path],
    include_extensions: Sequence[str],
    exclude_paths: Sequence[str],
) -> List[Path]:
    """Resolve candidate files from roots, honoring include/exclude policy."""
    candidates: List[Path] = []
    include_set = set(include_extensions)

    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            if root.suffix in include_set and not _is_excluded(root, exclude_paths):
                candidates.append(root)
            continue

        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in include_set:
                continue
            if _is_excluded(path, exclude_paths):
                continue
            candidates.append(path)

    deduped = sorted({path.resolve() for path in candidates})
    return deduped


def _apply_replacements(text: str, replacement_map: Dict[str, str]) -> Tuple[str, int]:
    """Apply configured Unicode-to-ASCII replacements and count replacements."""
    replaced = 0
    output_chars: List[str] = []

    for ch in text:
        if ch in replacement_map:
            output_chars.append(replacement_map[ch])
            replaced += 1
        else:
            output_chars.append(ch)

    return "".join(output_chars), replaced


def _scan_files(files: Sequence[Path], replacement_map: Dict[str, str], fix: bool) -> ScanResult:
    """Scan files for non-ASCII chars and optionally apply configured fixes."""
    violations: List[Violation] = []
    files_with_violations = 0
    fixed_files = 0
    fixed_count = 0

    for file_path in files:
        text = file_path.read_text(encoding="utf-8", errors="replace")

        if fix:
            fixed_text, replacements = _apply_replacements(text, replacement_map)
            if replacements > 0 and fixed_text != text:
                file_path.write_text(fixed_text, encoding="utf-8")
                text = fixed_text
                fixed_files += 1
                fixed_count += replacements

        file_had_violation = False
        line = 1
        column = 1

        for ch in text:
            if ord(ch) > 127:
                file_had_violation = True
                violations.append(
                    Violation(
                        path=str(file_path),
                        line=line,
                        column=column,
                        codepoint=f"U+{ord(ch):04X}",
                        char=ch,
                    )
                )

            if ch == "\n":
                line += 1
                column = 1
            else:
                column += 1

        if file_had_violation:
            files_with_violations += 1

    return ScanResult(
        scanned_files=len(files),
        files_with_violations=files_with_violations,
        violation_count=len(violations),
        fixed_files=fixed_files,
        fixed_count=fixed_count,
        violations=violations,
    )


def _build_cli() -> argparse.ArgumentParser:
    """Build CLI parser."""
    parser = argparse.ArgumentParser(
        description="Check source files for non-ASCII characters and enforce AGENTS policy."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Optional files/directories to scan. Defaults to repository root.",
    )
    parser.add_argument(
        "--policy",
        default="ascii_policy.json",
        help="Path to policy JSON (default: ascii_policy.json).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON output.",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Apply configured safe replacements before checking.",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Print only summary output (no per-violation lines).",
    )
    return parser


def _print_text_output(result: ScanResult, summary_only: bool = False) -> None:
    """Print plain-text scan output."""
    if not summary_only:
        for violation in result.violations:
            print(
                f"{violation.path}:{violation.line}:{violation.column} "
                f"{violation.codepoint} {repr(violation.char)}"
            )

    if result.violations:
        counts = Counter(violation.path for violation in result.violations)
        top_paths = counts.most_common(10)
        top_summary = ", ".join(f"{Path(path).as_posix()}={count}" for path, count in top_paths)
        print(f"ASCII_CHECK_TOP_FILES {top_summary}")

    print(
        "ASCII_CHECK "
        f"scanned_files={result.scanned_files} "
        f"files_with_violations={result.files_with_violations} "
        f"violations={result.violation_count} "
        f"fixed_files={result.fixed_files} "
        f"fixed_chars={result.fixed_count}"
    )


def _print_json_output(result: ScanResult) -> None:
    """Print JSON scan output."""
    payload = {
        "scanned_files": result.scanned_files,
        "files_with_violations": result.files_with_violations,
        "violation_count": result.violation_count,
        "fixed_files": result.fixed_files,
        "fixed_count": result.fixed_count,
        "violations": [
            {
                "path": violation.path,
                "line": violation.line,
                "column": violation.column,
                "codepoint": violation.codepoint,
                "char": violation.char,
            }
            for violation in result.violations
        ],
    }
    print(json.dumps(payload, ensure_ascii=True, indent=2))


def main() -> int:
    """Run ASCII compliance check."""
    parser = _build_cli()
    args = parser.parse_args()

    repo_root = Path.cwd()
    policy_path = (repo_root / args.policy).resolve()
    policy = _load_policy(policy_path)

    if args.paths:
        roots = [(repo_root / item).resolve() for item in args.paths]
    else:
        roots = [repo_root]

    files = _iter_candidate_files(
        roots=roots,
        include_extensions=policy["include_extensions"],
        exclude_paths=policy["exclude_paths"],
    )

    result = _scan_files(
        files=files,
        replacement_map=policy["replacement_map"],
        fix=args.fix,
    )

    if args.json:
        _print_json_output(result)
    else:
        _print_text_output(result, summary_only=args.summary_only)

    return 0 if result.violation_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
