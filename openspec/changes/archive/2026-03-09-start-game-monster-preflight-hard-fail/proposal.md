## Why

`Start Game` currently blocks when unresolved monster references are detected, but it does not attempt deterministic repair before failing. This causes avoidable operator interruptions when a module is recoverable and should only hard-fail after one bounded repair attempt.

## What Changes

- Add a start-game preflight contract that MUST run monster reference integrity validation before launching gameplay.
- Add a single deterministic auto-remediation attempt for unresolved references.
- Require mandatory revalidation after remediation and retain hard fail if unresolved references remain.
- Standardize actionable startup failure messaging as a publish-blocking integrity gate.
- SHOULD keep changes additive with minimal host-file edits and clear `# TABLETOP MODE:` markers.

## Capabilities

### New Capabilities
- `tt-start-game-monster-preflight-gate`: start-game preflight SHALL validate monster reference integrity, attempt one deterministic remediation pass, and hard-fail if unresolved references remain.

### Modified Capabilities
- `tt-monster-reference-integrity-validation`: reference-integrity outputs SHALL include startup-gate compatibility semantics for remediation + revalidation consumption.

## Impact

- Affected code:
  - `web/web_interface.py` (start_game preflight orchestration)
  - `web/extensions/` (new preflight helper module)
  - `scripts/test_*` (startup preflight regression coverage)
- Runtime behavior:
  - Start-game remains strict for unresolved monster references, with exactly one auto-repair attempt first.
- Risk:
  - Startup delay when auto-remediation executes.
  - MUST mitigate false pass risk with required post-remediation revalidation.
- Fallback strategy (MUST):
  - If remediation errors or unresolved references remain, block startup and emit deterministic actionable error.
- Merge safety / compatibility:
  - MUST preserve single-player behavior outside unresolved-reference path.
  - MUST keep host-flow structure stable and additive.
