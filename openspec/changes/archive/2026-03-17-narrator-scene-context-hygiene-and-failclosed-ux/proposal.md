## Why

Live narrator turns currently receive a mixed payload that combines current-scene truth with rich historical location chronicles, remote module atlas data, and verbose completed-plot prose. In practice this can cause off-location NPC bleed, stale scene recall, and user-facing soft fails when validation exhausts without a clear in-UI explanation.

This change is needed now because recent live play exposed a concrete Bandit Trail failure where the narrator likely pulled an off-scene captive/bandit thread back into the current turn, then failed closed with poor player-facing UX. The fix should reduce narrator noise without weakening validator authority or rewriting canonical history.

## What Changes

### MUST

- Add narrator-only outbound payload hygiene for live DM generation in `main.py`.
- Exclude historical assistant `=== LOCATION SUMMARY ===` and `=== LOCATION CHRONICLE ===` blocks from the narrator payload while preserving canonical stored history.
- Exclude the full `=== COMPLETE MODULE WORLD ATLAS ===` system payload from the narrator turn payload while preserving current location truth.
- Compact narrator-facing plot status so active and upcoming pressure remain visible but verbose completed-beat prose does not dominate the live scene prompt.
- Emit an immediate, player-visible, non-technical `[SYSTEM]` message when validation retries exhaust, while keeping the runtime fail-closed.
- Log rejected narrator turns to a dedicated debug channel with rejection reason and enough turn context for diagnosis.

### SHOULD

- Keep the first implementation local to `main.py` so the change is easy to verify and revert.
- Preserve current companion-memory injection and recent raw conversation turns for narrator continuity.
- Treat `memory.db` and world-narrative retrieval as a separate future change rather than mixing it into this hygiene pass.

### Non-Goals

- No rewrite of canonical conversation-history storage or compression caches.
- No module-specific Thornwood exception rules.
- No new runtime retrieval path from `data/memory.db` or world-narrative tables in this change.
- No weakening of deterministic NPC scene-presence or validation fail-closed behavior.

## Capabilities

### New Capabilities
- `tt-narrator-scene-context-hygiene`: keep live narrator payloads scene-first by filtering historical chronicles, remote atlas data, and verbose completed-plot prose.
- `tt-rejected-turn-observability`: capture rejected narrator turns in a dedicated debug log with fail-open logging behavior.

### Modified Capabilities
- `tt-validation-retry-hygiene`: retry exhaustion must surface player-visible, non-technical guidance while preserving fail-closed runtime semantics and detailed diagnostic logging.

## Impact

- Primary code: `main.py`
- Primary tests: `scripts/test_narrator_prompt_validation_refactor.py`
- New/updated debug output under `debug/quality_control/`
- No schema changes, no DB migration, no prompt-file rewrite required for the conservative pass
- Merge safety impact is low because the first slice is a narrator-payload wrapper in an existing host file rather than a broad architecture refactor

## Rollout Risk / Fallback

- Risk: narrator payload may become too lean and omit helpful continuity.
  - Fallback: keep the sanitizer local, additive, and easy to disable or relax per message class.
- Risk: player-facing fail-closed copy could mask deterministic root cause during debugging.
  - Fallback: keep detailed rejection reasons in dedicated logs while using concise user-facing copy in the UI.
- Risk: future memory retrieval work could be conflated with this change.
  - Fallback: explicitly keep DB-backed retrieval out of scope for this slice.
