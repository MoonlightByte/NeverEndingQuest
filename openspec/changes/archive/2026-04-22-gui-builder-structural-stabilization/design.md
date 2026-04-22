## Context

The GUI Module Builder already has the broad shape the project wants: upload, normalize, review, build, finish, and report. The current failure mode is not that the pipeline is missing entire stages. The problem is that several adjacent stages are using mismatched contracts, and illusion-heavy authored prose exposes where deterministic publication logic is over-promoting narrative text into canonical world state.

`The_Hidden_City_of_Numillian` is the clearest current proof. Its failure was a mix of:

1. a real execution bug in finisher monster materialization,
2. a provenance mismatch between toolkit builds and ingest-sidecar readiness expectations,
3. overly aggressive destination-phrase mining from evocative prose,
4. probe logic that treats visible NPCs as if they must also satisfy hidden/reveal-only contracts,
5. legitimate gameplay/media blockers for structured combatants that currently sit beside false positives in the same report.

This change is the structural stabilization slice. It does not add new LLM review behavior. It restores deterministic contract clarity so the builder can fail for real reasons instead of blended system noise.

## Goals / Non-Goals

**Goals:**
- MUST replace fragile subprocess-based monster materialization in toolkit finishing with the shared in-process materialization path.
- MUST make readiness and publishability provenance source-aware so toolkit builds are not forced through ingest-sidecar requirements.
- MUST narrow semantic destination authority so freeform prose does not become canonical travel truth without strong canonical evidence.
- MUST distinguish visible NPC authority from hidden/reveal-only NPC authority in semantic probes.
- MUST preserve strict gameplay/media blocking for real structured combatants.
- MUST preserve the existing scene-entity escape hatch for scene-only illusion content.
- MUST add regression coverage that exercises the real finisher/readiness/materialization path instead of only mocked subprocess behavior.
- SHOULD support bulk re-runs against existing modules once the structural fixes land.

**Non-Goals:**
- NOT adding the Phase 2 LLM classification/review layer in this change.
- NOT weakening media/readiness requirements for true structured monsters.
- NOT redesigning the builder packet/build/review flow.
- NOT introducing new runtime gameplay authority or changing SP/MP play behavior.
- NOT auto-remediating arbitrary semantic ambiguity by broad regeneration.

## Decisions

### Decision: Shared in-process monster materialization is the canonical execution path
- Rationale: the readiness gate already proves that `materialize_monsters(...)` can be called in-process with stable repo imports. The finisher and ingest helper are the outliers because they still spawn `scripts/homebrew_materialize_monsters.py` via subprocess and rely on incidental cwd/import state.
- MUST update `web/extensions/toolkit_module_finisher.py` to call the shared materialization function directly.
- SHOULD update `scripts/homebrew_ingest_dev.py` to use the same in-process path so developer ingest and toolkit finishing stay aligned.
- MUST return structured stage results directly from the materializer rather than reconstructing them from subprocess stdout/stderr.
- Alternative considered: keep subprocess execution but pin `cwd` and `PYTHONPATH`.
- Rejected because it preserves a second execution contract and leaves avoidable process/parsing failure modes in place.

### Decision: Readiness provenance must be source-aware
- Rationale: watcher/CLI ingest and GUI toolkit builds do not emit the same provenance artifacts. Requiring ingest sidecars for toolkit builds creates a guaranteed false fail even when the toolkit path itself succeeded.
- MUST introduce an explicit source contract such as `toolkit` vs `watcher` for readiness/publishability evaluation.
- MUST treat ingest archive sidecars as authoritative for watcher/CLI flows.
- MUST allow toolkit flows to satisfy provenance using toolkit-native artifacts, with `modules/<slug>/toolkit_build_report.json` as the baseline provenance-equivalent artifact.
- MUST fail with explicit source-contract diagnostics when provenance for the declared source is missing, rather than collapsing to a generic `sidecar_missing` result.
- Alternative considered: make sidecar optional for all sources.
- Rejected because it weakens ingest provenance guarantees unnecessarily.

### Decision: Destination authority must come from canonical identity evidence, not evocative prose mining
- Rationale: the current destination extractor promotes phrases like `find sanctuary`, `next hall`, and `vast crypt` into canonical travel authority because it scans descriptive prose for terminal words such as `hall`, `chamber`, and `sanctuary`. This is structurally precise code producing semantically imprecise outcomes.
- MUST restrict canonical destination extraction to high-confidence identity fields such as:
  1. `location.name`
  2. `location.aliases`
  3. `location.source_room_title`
  4. narrowly-approved plot/title identity fields if they map cleanly to locations
- SHOULD permit travel-phrase extraction from prose only when paired with strong travel verbs and a canonical alias match.
- MUST stop treating generic descriptive prose fields as direct canonical destination sources by default.
- Alternative considered: keep current wide extraction and downgrade findings from fail to warn.
- Rejected because it preserves incorrect authority derivation and just hides it behind weaker severity.

### Decision: Visible NPC authority and hidden/reveal authority are separate semantic cases
- Rationale: an NPC visibly authored in a location should not need reveal bindings to satisfy publication probes. Reveal authority matters only when the authored contract is hidden/reveal-oriented or when the NPC lacks visible authority entirely.
- MUST treat NPCs with valid `visible_location_ids` as satisfying baseline scene authority.
- MUST reserve hidden-NPC probe failures for NPCs that are authored as hidden/reveal-only and still lack both visible authority and reveal authority.
- SHOULD keep warnings for catalog drift cases such as empty `appears_in` when authored text suggests the NPC matters, but these should not collapse visible NPCs into hidden-authority blockers.
- Alternative considered: keep current probe strictness and require all NPCs to have both visible and reveal forms.
- Rejected because it does not match authored module semantics and creates false blockers for ordinary visible NPCs.

### Decision: Gameplay/media blocking stays strict for combat-valid entities, with scene-only illusion content handled structurally
- Rationale: the gameplay/media gate is doing legitimate work when a module declares real monsters in structured combat fields. The mistake is not the gate; it is allowing scene-only illusion content to enter combat-valid structures.
- MUST keep media/readiness blocking for entities in `locations[].monsters[]`, encounter payloads, and other combat-valid structural fields.
- SHOULD rely on the existing scene-entity contract for illusion, mindscape, apparition, or narrator-only entities that are not intended to be real combatants.
- MUST avoid special-casing individual illusion modules inside gameplay audit logic.
- Alternative considered: weaken gameplay/media gates whenever semantic authority is uncertain.
- Rejected because it would blur the line between real combatants and flavor content and undermine runtime integrity.

### Decision: Real-path regression coverage is required for this slice
- Rationale: the current finisher bug escaped because tests mocked subprocess behavior and never exercised the real execution contract. Structural fixes in this area are only trustworthy if tests cover the actual helper path and source-aware reporting outcomes.
- MUST add regression tests for:
  1. toolkit finisher in-process monster materialization,
  2. source-aware readiness provenance behavior,
  3. destination extraction with Numillian-style evocative prose fixtures,
  4. visible-vs-hidden NPC authority probe behavior.
- SHOULD add parity tests proving toolkit and watcher flows remain intentionally different where provenance differs and aligned where materialization/semantic logic is shared.

## Architecture

### Pipeline shape after this change

The structural pipeline remains the same at a high level:

1. toolkit upload and normalization
2. review approval
3. module build output under `modules/<slug>/`
4. toolkit finisher
5. readiness and publishability evaluation
6. final `toolkit_build_report.json`

The important changes are inside steps 4 and 5.

### Finisher contract

Recommended finisher orchestration:

1. continuity enrichment
2. semantic authority enrichment
3. monster materialization via direct in-process call
4. registry integration checks
5. readiness/publishability evaluation with explicit `source="toolkit"`

The finisher report should preserve stage-level outcomes, but stage outputs should come from direct Python return values rather than subprocess returncode plus stderr parsing.

### Readiness and publishability contract

Recommended provenance model:

1. `source="watcher"`
   - requires ingest sidecar contract
   - continues using archive-sidecar expectations
2. `source="toolkit"`
   - does not require watcher sidecar
   - requires toolkit-native build provenance/report artifact

This keeps the publication system strict while allowing strictness to match the source that actually produced the module.

### Semantic authority contract

Recommended authority tiers:

1. **Canonical identity fields**
   - safe to feed destination authority maps directly
2. **Strong travel phrasing with canonical alias match**
   - admissible only when clearly anchored to a canonical location identity
3. **Evocative prose / quest objectives / atmosphere**
   - not canonical travel authority
   - may remain visible in narrative text, but must not become blocker-generating destination phrases by default

This design intentionally prefers under-inference over false canonicalization.

### NPC scene authority contract

Recommended NPC authority states in deterministic publication logic:

1. **Visible authority present**
   - passes baseline scene authority checks
2. **Reveal authority present without visible authority**
   - valid for hidden/reveal-only authored cases
3. **Neither visible nor reveal authority present**
   - failure or warning depending on authored evidence strength

This slice does not need a new explicit LLM classifier. It only needs the probe harness and authority builder to stop collapsing state 1 into state 3.

## Risks / Trade-offs

- [Toolkit provenance becomes too permissive] -> Mitigation: source-aware logic must still require a toolkit-native artifact, not silently skip provenance entirely.
- [Destination extraction becomes too narrow and misses real aliases] -> Mitigation: allow explicitly enumerated canonical fields and narrowly-scoped travel-verb plus alias patterns, then re-run across existing modules to measure fallout.
- [Visible-vs-hidden NPC distinction masks real hidden-authority gaps] -> Mitigation: only visible NPCs bypass reveal requirements; hidden/reveal-only NPCs still fail when both authority paths are absent.
- [Developers accidentally bypass the materializer's script entry path assumptions] -> Mitigation: centralize shared materialization function usage and keep the script wrapper as a thin CLI adapter only.
- [Illusion content remains authored into structured monster fields] -> Mitigation: keep gameplay/media gates strict so the bad modeling choice stays visible until corrected through scene-entity modeling.

## Migration Plan

1. Refactor toolkit finisher monster materialization to use the shared in-process helper.
2. Align developer ingest helper to the same materialization path for parity.
3. Add source-aware provenance handling in readiness/publishability evaluation.
4. Narrow destination extraction inputs and update probe derivation rules accordingly.
5. Correct visible-vs-hidden NPC authority handling in authority builder and probe harness.
6. Extend regression suites to cover real-path materialization, source-aware provenance, prose-heavy destination fixtures, and NPC authority distinctions.
7. Re-run the improved structural pipeline against representative existing modules.
8. Re-ingest `The_Hidden_City_of_Numillian` after the structural fixes are green.

Rollback strategy:

1. Restore previous finisher materialization orchestration if direct helper wiring proves unstable.
2. Revert source-aware provenance handling and return to the previous sidecar gate behavior only if toolkit-native reporting cannot be made deterministic.
3. Preserve any new regression fixtures and reports as inert artifacts even if code rollback is required.

## Verification Plan

Minimum verification for this change should include:

1. unit/regression tests for direct finisher materialization behavior,
2. tests proving toolkit source skips watcher-sidecar gating while watcher source still requires it,
3. semantic authority tests proving evocative prose like `find sanctuary` does not become a canonical destination blocker,
4. semantic probe tests proving visible NPCs do not fail hidden-authority checks,
5. at least one representative full pipeline re-run against existing modules,
6. a targeted re-run or re-ingest of `The_Hidden_City_of_Numillian` after the above pass.

## Open Questions

- Should toolkit provenance be represented only by `toolkit_build_report.json`, or should the finisher also emit a compact dedicated provenance artifact for readiness/publishability consumers?
- Which existing modules should be part of the mandatory post-change re-run set so we measure both prose-heavy and more ordinary module behavior?
- Should the semantic authority layer continue to record non-canonical evocative phrases as diagnostics for author review, or drop them entirely from persisted semantic outputs in this slice?
