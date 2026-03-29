## Why

Mixed `updateCharacterInfo` payloads currently hard-fail at runtime when syntactically valid deterministic ops reference a real target through an alternate but semantically equivalent label such as `DivineSense` versus `Divine Sense`. This is no longer just a bug-tester issue: from a facilitator UX perspective these failures freeze the turn, surface opaque system errors, and leave ordinary players with no recovery path.

This change is needed now to close a growing class of runtime edges before more structured ops are adopted across narration and combat. The runtime MUST preserve mechanical authority for true contradictions, but it SHOULD degrade gracefully when a mixed `changes + ops` payload is recoverable through target normalization or prose fallback.

## What Changes

- Add deterministic target normalization for structured character ops so runtime can match semantically equivalent class feature, item, ammunition, and other supported target labels before apply-time failure.
- Define an explicit recoverable-vs-authoritative failure split for deterministic character ops application.
- Change mixed `changes + ops` runtime behavior so recoverable deterministic apply failures fall back to the existing prose `changes` path instead of freezing the turn.
- Preserve fail-closed behavior for true mechanical contradictions such as underflow, overflow, impossible removals, and other authoritative invalid-state operations.
- Add user-safe recovery behavior and clearer diagnostics so character update failures do not surface as opaque generic unknown errors.
- Expand regression coverage for alias drift, normalization parity, mixed-payload fallback, and hard-fail preservation for authoritative contradictions.

### Non-Goals

- This change MUST NOT weaken deterministic enforcement for true mechanical contradictions.
- This change MUST NOT replace structured ops with prose-only updates or remove the deterministic ops pathway.
- This change MUST NOT broaden gameplay rules or alter 5e mechanics semantics.
- This change SHOULD NOT require broad prompt rewrites beyond contract alignment needed for the new recovery behavior.

## Capabilities

### New Capabilities
- `tt-character-update-ux-recovery`: Recoverable structured character update failures degrade safely and surface user-safe feedback instead of freezing gameplay.

### Modified Capabilities
- `tt-structured-character-ops-contract`: Character ops requirements change to include canonical target normalization and mixed-payload recoverable fallback behavior.
- `tt-deterministic-character-ops-application`: Deterministic character ops application requirements change to distinguish recoverable normalization/shape failures from authoritative invalid-state failures.

## Impact

- Affected code: `updates/update_character_info.py`, `utils/character_ops_routing.py`, `core/ai/action_handler.py`, `main.py`, and any helper introduced for canonical target matching.
- Affected tests: structured character ops contract tests, mechanical followthrough tests, and new runtime recovery regressions for mixed payloads.
- APIs/contracts: `updateCharacterInfo.parameters.ops` runtime behavior changes at apply time for mixed payloads with prose fallback present.
- Rollout risk: moderate. Relaxing hard-fail behavior too far could hide true state contradictions, so the recoverable-vs-authoritative split MUST be explicit and test-locked.
- Fallback strategy: where prose `changes` exists, recoverable deterministic failures MUST degrade to prose fallback; where no safe fallback exists, runtime MUST fail closed with a specific user-safe error.
- Merge safety: implementation SHOULD live in helper functions and narrow host-file edits, with any host changes marked `# TABLETOP MODE:` where required.
- SP/MP compatibility: behavior MUST remain backward compatible for single-player and tabletop multi-PC modes; recovery logic SHOULD be mode-agnostic.