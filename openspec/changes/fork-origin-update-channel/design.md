# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

# OpenSpec Design: fork-origin-update-channel

## Architecture Boundaries

### Update Source Resolution (MUST)
- `utils/version_checker.py` SHALL be the single source of truth for update target resolution.
- Resolver SHALL parse `git remote get-url origin` and return canonical `owner/repo` and branch target.
- Resolver SHALL fail safe (`unknown`) if remote cannot be parsed.

### Version Status Contract (MUST)
- `check_for_updates()` SHALL compare local `VERSION` against fork remote metadata.
- Remote metadata strategy SHALL be:
  1. GitHub releases endpoint for resolved fork repo.
  2. Raw `VERSION` fallback for resolved fork repo default branch.
- If metadata unavailable, status SHALL be `unknown` (no false update).

### GUI Update Execution Contract (MUST)
- `trigger_update` handler SHALL run deterministic preflight before mutation:
  - clean working tree check
  - explicit remote/branch selection (`origin`, `main` or resolved branch)
- Update path SHALL use explicit commands with fast-forward-only semantics.
- Handler SHALL emit `update_error` and stop on any preflight or git failure.

### UI Contract (MUST)
- Header button and update dialog copy SHALL indicate fork-source updates.
- Status messaging SHALL avoid implying upstream ownership.

## Compatibility

MUST:
- Preserve existing SocketIO event names (`version_status`, `trigger_update`, `update_log`, `update_error`, `update_complete`).
- Preserve restart behavior after successful update.
- Preserve no-op behavior when no update is available.

SHOULD:
- Keep existing UX flow and button placement unchanged.
- Keep runtime dependencies unchanged (fail open if `requests` missing).

## Verification Strategy

1. Compile checks for modified Python files.
2. Unit tests for fork target resolution and status fallback behavior.
3. Smoke command contract verification for updater command sequence.
4. OpenSpec validation for this change.

## Rollback Plan

- Roll back in reverse risk order:
  1. `trigger_update` command contract changes.
  2. `version_checker` origin resolution logic.
  3. UI copy changes.
- Keep added tests where possible as regression guards.
