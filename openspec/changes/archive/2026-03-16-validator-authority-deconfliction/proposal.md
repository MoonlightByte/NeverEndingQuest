## Why

G1-G3 moved travel and NPC scene presence into Python reconcile-first behavior, but the narrator validation pipeline still lets the LLM validator re-litigate domains that runtime has already resolved. That creates brittle override hacks, duplicate failure paths, and unnecessary retry loops exactly where the new architecture is supposed to be authoritative.

## What Changes

- Introduce a structured deterministic validation domain payload instead of a single flat `deterministic_passed` flag.
- Define authoritative handoff rules so the LLM validator cannot veto Python-reconciled travel and NPC state-sync domains.
- Replace ad hoc arrival-only override logic with generic domain-based deconfliction in the narrator validation path.
- Extend validation routing telemetry so skips, suppressions, and mixed-domain review decisions are explainable.
- Narrow retry behavior so already-reconciled domains do not generate pointless correction loops.

## Capabilities

### New Capabilities
- `tt-validator-authoritative-domain-handoff`: structured domain-level handoff between deterministic Python reconciliation and LLM validation.

### Modified Capabilities
- `tt-narrator-validation-contract`: narrator validation authority changes from arrival-only suppression to domain-scoped deterministic handoff.
- `tt-validation-routing-telemetry`: telemetry expands to report authoritative-domain suppression and mixed-domain review routing.
- `tt-validation-efficiency-routing`: skip/routing behavior expands for reconcile-first soft-state turns.
- `tt-validation-retry-hygiene`: retry behavior changes so reconciled-domain failures do not keep re-priming correction loops.

## Impact

- Primary files likely affected in implementation:
  - `main.py`
  - `utils/validation_routing.py`
  - `prompts/validation/validation_prompt_compressed.txt`
  - `prompts/validation/validation_prompt.txt`
- Likely tests to add or update:
  - new G4 transcript-driven validation authority tests in `scripts/`
  - existing retry/validation routing regressions
- Merge-safety impact:
  - SHOULD stay localized to validation handoff and prompt wording.
  - MUST remain additive and keep host-file edits marked with `# TABLETOP MODE:` comments.
- SP/MP compatibility:
  - MUST preserve single-player compatibility because validation authority changes are runtime-general, not tabletop-roster specific.
- Rollout risk and fallback:
  - Risk: suppressing too much could let unrelated LLM failures slip through.
  - Fallback: keep domain-scoped suppression narrow and preserve blocking on unreconciled semantic or mechanical failures.
