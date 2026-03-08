## Why

Travel turns are entering retry loops where the DM repeats defensive narration instead of executing movement. The current stack over-constrains the model by combining:

- dense system-level MUST rules,
- a large per-turn DM note instruction tail,
- deterministic fail-closed guards,
- and retry notes that re-inject failing phrasing.

This causes "constrained but confused" behavior: safe state guards are intact, but player-facing flow stalls.

## What Changes

This change simplifies and clarifies the turn contract while preserving deterministic safety:

1. Remove duplicated instruction injection in multi-PC turns (single source of rules).
2. Feed transition validator the raw player travel intent, not DM note payload.
3. Keep NPC arrival sync strict by default, but apply fail-soft behavior on travel turns unless narration makes an explicit arrival claim.
4. De-loop retries for deterministic guard failures (especially NPC arrival sync).

## Scope

- `main.py`
- `core/ai/action_handler.py`
- `utils/npc_arrival_validator.py`
- `prompts/system_prompt_compressed.txt`
- `prompts/validation/validation_prompt_compressed.txt`
- `scripts/test_npc_arrival_state_sync.py`
- `scripts/test_transition_time_failopen.py` (if needed)
- `scripts/` new regression test file(s) for retry-loop behavior

## Impact

- Multi-PC DM remains constrained by mechanics/state truth.
- Travel turns should resume quickly without repeated "no NPCs here" narration loops.
- Fail-closed safety remains for true off-location NPC arrivals.
- Token waste and user-visible dead turns are reduced.
