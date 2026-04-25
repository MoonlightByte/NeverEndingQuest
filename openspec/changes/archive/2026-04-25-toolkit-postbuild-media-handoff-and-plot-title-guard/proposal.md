# toolkit-postbuild-media-handoff-and-plot-title-guard

## Why

`Murder_at_the_Drowning_Lass` is currently failing the post-build finisher for two deterministic reasons that belong in the existing Python authority path, not in future LLM builder integration:

- toolkit-source readiness still hard-fails when the only gameplay blockers are structural monster media findings already classified as manual-only handoff debt;
- semantic enrichment still mines unresolved player-facing destination phrases from plot titles like `Echoes Beneath: Unrest in the Catacombs` even when the same plot point already binds to canonical location `CBTC004`.

This creates a false mixed-failure outcome: the build is structurally valid, monster hydration succeeded, schema passed, and the remaining failures should be split into explicit manual media handoff plus true semantic blockers only.

## What Changes

### New Capabilities

- Define a toolkit readiness boundary where structural monster media debt classified as manual-only handoff does not keep an otherwise valid toolkit build in `ready_status: fail`.
- Define a semantic-authority boundary where plot titles with authoritative location binding do not generate free-floating canonical destination blockers.

### Modified Capabilities

- `module-publishability-reporting` SHALL preserve toolkit structural media debt in reporting while allowing readiness to pass when that debt is the only gameplay blocker class.
- `module-semantic-authority-enrichment` SHALL stop promoting plot-title phrases into destination blockers when the plot point already has authoritative location identity.
- `toolkit-module-postbuild-finishing` SHALL preserve explicit manual media handoff guidance after the readiness false-negative is removed.

## Capability Scope

### MUST

- The implementation SHALL remain deterministic and Python-authoritative.
- Toolkit-source readiness SHALL only relax gameplay failure when every gameplay blocker is explainable by structural monster media findings whose outcomes are `provider_disabled_missing` or `attempted_but_unresolved`.
- The media debt payload and manual remediation workflow SHALL remain visible in readiness and publishability output.
- Plot-title destination extraction SHALL remain disabled only when the plot point already provides authoritative location binding through `location` or `involvedLocations`.
- Plot titles without authoritative location binding SHALL preserve existing destination extraction behavior.
- The change SHALL include targeted regression coverage for both the readiness-handoff path and the authoritative-plot-title suppression path.

### SHOULD

- Relaxed toolkit gameplay gates should preserve explicit reason metadata so the report remains reviewable.
- Semantic enrichment should continue to surface the plot point title as non-destination evidence for NPC/reveal/diagnostic flows.

## Non-Goals

- Broad media-policy changes for watcher or ingest-source readiness.
- LLM-assisted semantic classification.
- General prose-mining redesign outside authoritative plot-title binding.
- Reclassifying true semantic contradictions or mixed blocker states as non-blocking.

## Impact

- Affected code:
  - `scripts/audit_module_readiness.py`
  - `utils/module_semantic_authority.py`
  - targeted regression tests under `scripts/`
- Affected workflows:
  - toolkit post-build readiness classification
  - toolkit finisher / publishability reporting
  - semantic authority enrichment for authored plot data

## Risks

- Over-relaxing toolkit readiness could hide real gameplay blockers if the media-only boundary is too broad.
- Over-suppressing plot-title extraction could remove legitimate destination phrases when authoritative location binding is absent.

## Fallback

- If toolkit gameplay blockers are not fully explainable by structural manual-only monster media debt, keep readiness failed.
- If a plot point does not provide authoritative location binding, preserve the current title-based destination extraction path.
