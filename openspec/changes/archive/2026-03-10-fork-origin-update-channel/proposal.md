# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

## Why

The current update flow is upstream-biased and can pull from MoonlightByte instead of the NEQ-TTRPG fork:

- `utils/version_checker.py` hardcodes `MoonlightByte/NeverEndingQuest` for release and VERSION checks.
- `web/web_interface.py` runs `git pull` without explicit remote/branch, so behavior follows local tracking config.
- Current local branch tracking is `main -> upstream/main`, which can update from upstream during GUI update.

This conflicts with fork-first maintenance where upstream merges are intentional operator actions.

## What Changes

MUST changes:
- Update source resolution SHALL derive owner/repo from `origin` remote URL at runtime.
- Version checks SHALL target fork repository metadata (release tag or `VERSION` on fork default branch).
- GUI-triggered update SHALL use explicit fork pull commands (`origin`, branch) with `--ff-only`.
- GUI-triggered update SHALL fail closed on dirty worktree and report deterministic operator guidance.
- Startup version notice in `run_web.py` SHALL use the same fork-aware version checker path.
- Update dialog and logs SHALL state that updates are fork-sourced.

SHOULD changes:
- Add concise telemetry logs indicating resolved update target (`owner/repo`, branch).
- Keep implementation additive with minimal host-file edits.
- Add small regression tests for target resolution and command contract.

Non-goals:
- No automatic upstream merge or upstream remote mutation.
- No forced branch-tracking rewrites from runtime code.
- No changes to save/reset/restore lifecycle.

## Impact

Affected files:
- `utils/version_checker.py`
- `web/web_interface.py`
- `run_web.py`
- `web/templates/game_interface.html`
- `scripts/test_version_checker_fork_update.py` (new)

Risk and mitigation:
- Risk: `origin` missing/malformed URL causes false "unknown" state.
  - Mitigation: deterministic fallback message and hidden update button.
- Risk: strict `--ff-only` blocks updates on diverged local history.
  - Mitigation: fail with explicit operator guidance instead of silent merge behavior.

Fallback strategy (MUST):
- If fork target cannot be resolved, version check returns `unknown` and updater does not attempt git mutation.
- If update preflight fails (dirty tree, git failure, ff-only refusal), emit `update_error` with actionable text and keep process running.
