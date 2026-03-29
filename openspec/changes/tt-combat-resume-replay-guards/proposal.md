## Why

Resumed multi-PC combat can replay already-applied enemy damage, causing positive-HP enemies to be dropped to 0 a second time and forcing a false auto-exit. The resumed-session handoff also appends an unguarded combat summary into main history, allowing post-combat XP and action side effects to be interpreted and applied again.

## What Changes

- Add a deterministic resumed-combat replay guard so already-applied enemy HP results are not re-applied during crash recovery or resumed combat turns.
- Mark resumed combat summaries as historical-only records using the same no-replay guardrails as the normal post-combat path.
- Add targeted regression coverage for resumed enemy-damage replay, false auto-exit prevention, and resumed post-combat XP duplication.
- Non-goals: redesign combat prompting, change normal non-resume combat flow, or widen reward formulas.

## Capabilities

### New Capabilities
- `tt-combat-resume-replay-guard`: Prevent resumed combat from reapplying already-committed combat state and prevent resumed combat summaries from being reinterpreted as fresh actionable rewards.

### Modified Capabilities
- None.

## Impact

- Affected code: `main.py`, `core/managers/combat_manager.py`, `updates/update_encounter.py`, and targeted regression scripts.
- Systems: resumed combat recovery, immediate encounter ops application, post-combat history handoff, and auto-exit correctness.
- Merge safety: MUST keep fixes additive and preserve existing single-player and non-resume tabletop behavior.
- Rollout risk: low-to-medium because the change touches resume-only combat flow and deterministic encounter update guards; fallback is to prefer no-op on detected duplicate replay instead of reapplying damage.
- Recovery path: if replay detection cannot prove idempotency, runtime SHOULD preserve current behavior and rely on authoritative encounter state rather than inventing new defeat transitions.
