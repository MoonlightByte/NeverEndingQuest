# Proposal: tt-transition-time-failopen-sync

## Why

World time can remain mechanically frozen (for example `06:55:00 [BOO001:V04]`) across multiple location transitions when the model emits `transitionLocation` without `updateTime`.

This creates dual-reality narration:
- Python mechanical truth says dawn and fixed time.
- Narrative memory/history may continue night progression language.

The result is player-facing confusion and reduced trust in state continuity.

## What Changes

1. Add deterministic fail-open fallback for movement time:
   - When a response contains `transitionLocation` but no `updateTime`, runtime auto-applies a bounded `updateTime` estimate and logs `STATE_SYNC`.
   - Fallback is deterministic, not probabilistic.

2. Tighten model contract for travel bundles:
   - Prompt and validation text explicitly require pairing `transitionLocation` with `updateTime`.
   - Keep gameplay fail-open at runtime even when model misses the contract.

3. Add targeted regressions:
   - Missing `updateTime` with transition triggers fallback minutes.
   - Existing valid travel bundle is unchanged (no double-time updates).
   - Non-transition turns are unchanged.

## Capabilities

- `tt-transition-time-bundle-contract`
- `tt-transition-time-failopen-runtime-fallback`

## Impact

Files expected:
- `main.py` (or a tightly-scoped runtime action bundle helper)
- `prompts/system_prompt_compressed.txt`
- `prompts/validation/validation_prompt_compressed.txt`
- `prompts/validation/validation_prompt.txt`
- `scripts/` regression tests (new or extended)

Non-goals:
- No refactor of `update_world_time()` mechanics.
- No broad travel simulation overhaul.
- No changes to archive/history compression formats in this change.
