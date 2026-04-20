## Why

`The_Hidden_City_of_Numillian` no longer fails because of broad structural instability. The re-ingest canary proves the structural slice landed: hydration/materialization succeeds, schema is green, spatial parity is green, and hidden-NPC precision is green. The remaining failures are narrower and policy-shaped:

1. toolkit finisher reports missing base monster media because the active toolkit route does not enable provider-backed monster media generation and the finisher audits module-local monster media without running the existing manual monster-image workflow,
2. semantic publication still surfaces `paradox sanctuary` as an unresolved player-facing destination phrase even though this is now understood to be a bounded Phase 2 ambiguity case rather than a structural extraction bug.

This change is needed now so the post-reingest pipeline reports the remaining debt honestly and consistently before any Phase 2 LLM-assisted ambiguity handling begins.

## What Changes

- Make toolkit finisher and publishability reporting explicitly describe monster media outcome in terms of toolkit media debt, provider policy, and the existing manual toolkit remediation workflow, rather than leaving the failure to look like missing structural generation.
- Reuse the existing monster-prewarm contract in toolkit-facing reporting so provider-disabled runs remain strict but interpretable, while directing operators to the existing toolkit monster-image generation surfaces.
- Classify bounded unresolved phrases like `paradox sanctuary` as explicit Phase 2 semantic ambiguity debt rather than as misleading structural contradiction.
- Preserve the repo distinction between readiness and publishability so structurally valid modules can remain distinguishable from release-incomplete modules.
- Add targeted verification/reporting coverage around the Numillian post-reingest canary outcome.

## Capabilities

### New Capabilities
- `toolkit-numillian-postreingest-gate-reconciliation`: Make post-reingest Numillian outcomes report explicit monster-media policy debt and explicit Phase 2 semantic ambiguity debt.

### Modified Capabilities
- `toolkit-module-postbuild-finishing`: toolkit finishing MUST expose the monster-media policy/generation outcome as an explicit stage-level result for toolkit builds and point to the existing manual toolkit media workflow when assets are still missing.
- `homebrew-monster-prewarm-provider-fallback`: provider-disabled toolkit-facing flows MUST report missing monster media as explicit non-generated media debt, not as if generation had already been attempted and succeeded, and MUST preserve manual operator remediation as the next step.
- `module-semantic-publication-audit`: semantic publication audit MUST distinguish bounded Phase 2 ambiguity debt from deterministic structural contradiction when the phrase is explicitly classified for later intelligent handling.
- `module-publishable-gate`: readiness and publishability reporting MUST keep structural readiness distinct from toolkit media debt and Phase 2 semantic ambiguity debt.

## Impact

- Affected code:
  - `web/extensions/toolkit_module_finisher.py`
  - `scripts/homebrew_prewarm_portraits.py`
  - `scripts/audit_module_gameplay.py`
  - `scripts/audit_module_readiness.py`
  - `scripts/audit_module_publishability.py`
  - `scripts/module_semantic_authority_audit.py`
  - targeted tests and canary/report artifacts
- Merge safety:
  - MUST prefer extension/script/reporting changes over broad builder/runtime rewrites.
- Runtime compatibility:
  - MUST NOT alter SP/MP gameplay authority or weaken combat-valid monster requirements.
- Rollout/fallback:
  - MUST keep provider generation opt-in.
  - MUST fail closed on true publishability debt.
  - SHOULD classify residual ambiguity explicitly instead of broadening deterministic phrase heuristics.
