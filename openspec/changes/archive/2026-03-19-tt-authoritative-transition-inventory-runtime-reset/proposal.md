## Why

Recent gametest fixes exposed a deeper runtime problem: movement and inventory truth are currently split across multiple competing layers. Transition validation, transition narration, inventory persistence, inventory context injection, and validator skip routing can all disagree, which lets failed movement still become narrated history and lets missing item ownership devolve into narration-only hallucination.

The immediate bugs are no longer isolated prompt failures. They come from a patchwork authority model where Python sometimes enforces state, sometimes defers to narration, and sometimes tries to reconcile after the fact. This change is needed now to reset authority for same-module transitions and item possession back to deterministic Python control before more narrow recovery patches make the runtime harder to reason about.

## What Changes

- MUST make Python the authoritative execution path for same-module location transitions, using fresh topology data rather than stale cached graph state when validating local moves.
- MUST fail closed when a `transitionLocation` action cannot be committed; failed movement SHALL NOT generate arrival narration, stitched transition prose, or rewritten conversation history.
- MUST make Python the authoritative source of truth for tracked inventory possession and party-to-party transfers; possession questions SHALL resolve from committed character state, not narration memory.
- MUST prevent possession contradiction turns from bypassing validation as `narration_only` when the player is explicitly checking for a tracked item.
- MUST correct multi-PC inventory grounding so inventory context is built from the active character rather than implicitly falling back to the first party member.
- MUST treat the LLM-based seamless transition post-processor as disabled/dormant in active runtime flow until a future validated change explicitly re-enables or removes it.
- SHOULD consolidate transition validation and execution behind one coherent service boundary rather than continuing to patch independent helpers.
- SHOULD preserve existing upstream-compatible structure and keep host-file edits narrow and clearly marked.

Non-goals:

- No broad rewrite of the entire narrator pipeline.
- No OpenRouter/provider routing work.
- No UI redesign.
- No generic event-ledger or database migration.
- No attempt to make the old seamless transition layer smarter before authority is restored.

## Capabilities

### New Capabilities
- `tt-authoritative-same-module-transition`: deterministic Python-owned validation and execution contract for same-module movement.
- `tt-transition-failure-history-hygiene`: fail-closed handling so rejected transitions never produce synthetic arrival narration or false history.
- `tt-inventory-possession-authority`: deterministic Python-owned possession, transfer, and possession-query contract for tracked items.
- `tt-disabled-transition-postprocessor-doc`: explicit repository documentation contract for dormant seamless transition post-processor status and cleanup intent.

### Modified Capabilities
- `tt-validation-efficiency-routing`: narration-only skip rules change so explicit possession contradictions and other authoritative runtime checks happen before a turn can be skipped.

## Impact

- Primary code likely affected:
  - `main.py`
  - `core/ai/action_handler.py`
  - `core/ai/inventory_context_integration.py`
  - `utils/location_path_finder.py`
  - transition helpers and/or a new authoritative transition service file
  - inventory persistence/runtime helper path(s)
- Primary tests likely affected:
  - same-module local move regression for `NIG04 -> NIG05`
  - failed transition no-arrival-narration regression
  - reliquary transfer and possession-query regressions
  - multi-PC active-character inventory-context regression
  - existing validation-routing and narrated-location suites
- SP/MP impact:
  - MUST remain compatible with both single-player and tabletop modes because transition and inventory state are shared runtime infrastructure.
- Merge-safety impact:
  - SHOULD prefer additive helpers and narrow host hooks, with `# TABLETOP MODE:` comments where host files must change.
- Rollout risk:
  - Tighter fail-closed behavior may initially expose more rejected turns until prompt/runtime alignment is complete.
  - Inventory authority reset may surface pre-existing inconsistent character files that were previously hidden by narration drift.
- Fallback strategy:
  - The seamless transition post-processor will remain present but disabled/dormant until cleanup or future re-enable validation is complete.
  - If needed, new authoritative helpers can be landed behind narrow callsite switches before removing old paths.