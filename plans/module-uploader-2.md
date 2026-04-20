# Module Uploader 2 - GUI Builder Stabilization and Narrative Classification

## Status

- Draft for review
- Scope approved for structural fixes first, LLM integration second
- Apply to future ingests and re-run against existing modules
- Re-ingest `The_Hidden_City_of_Numillian` after the new flow lands

## Objective

Reduce constant GUI Module Builder failures by fixing builder/finisher contract bugs, tightening deterministic publication checks so they stop over-reading narrative prose as hard world state, and then adding bounded LLM-assisted classification at the right review-time decision points.

This plan keeps Python as the source of truth for emitted module JSON, validation, and publication gates.

## Confirmed Decisions

1. Fix B confirmed: readiness sidecar gate becomes conditional on build source.
2. Gameplay/media policy revised: missing module monster/NPC media is a post-build handoff issue for toolkit builds, not a reason to fail an otherwise successful module build; remediation stays manual via `Module Builder -> Module Media Generator`.
3. Implementation order confirmed: structural fixes first, LLM integration in Phase 2.
4. Re-run the improved pipeline against existing modules.
5. Re-ingest `The_Hidden_City_of_Numillian` after the improved pipeline lands.

## Problem Summary

Current GUI toolkit builds can fail for four different reasons that are being conflated into one generic bad outcome:

1. Real builder/finisher defects.
2. Contract mismatches between toolkit builds and ingest-watcher expectations.
3. Deterministic semantic publication logic that over-classifies evocative prose as canonical travel/NPC authority.
4. Post-build media handoff/reporting mismatches where structured monsters are present but module media generation has not been run yet.

`The_Hidden_City_of_Numillian` is a strong test case because it uses illusion-heavy mindscape prose, scene ambiguity, and DM-authored atmosphere that sits right on the boundary between:

- canonical world state,
- narrator-only flavor,
- scene-only entities,
- real combatants.

## Current GUI Build Flow

```text
Upload markdown
  -> normalize upload
  -> review snapshot and approval
  -> build module JSON
  -> toolkit finisher
       continuity
       semantic authority
       registry
       monster materialization
       publishability audit
  -> toolkit_build_report.json
```

More specifically:

1. `web/routes/toolkit_homebrew_routes.py`
   - accepts upload
   - normalizes source package
   - persists review artifacts
   - invokes builder path
2. Module builder emits module files under `modules/<slug>/`
3. `web/extensions/toolkit_module_finisher.py`
   - runs continuity enrichment
   - runs semantic authority enrichment
   - runs registry integration checks
   - runs monster materialization
   - runs publishability audit
4. `scripts/audit_module_publishability.py`
   - composes readiness, semantic audit, and semantic probes
5. `modules/<slug>/toolkit_build_report.json`
   - captures final status, stage details, readiness, and publishability

## Root Causes Exposed by Numillian

### 1. Finisher monster materialization bug

`web/extensions/toolkit_module_finisher.py` launches `scripts/homebrew_materialize_monsters.py` via subprocess with a relative path and no pinned repo-root execution context.

Result:

- `ModuleNotFoundError: No module named 'utils'`
- monster materialization stage fails even when the underlying materializer logic is valid

This is a real bug.

### 2. Toolkit build vs sidecar gate mismatch

`scripts/audit_module_readiness.py` always requires a sidecar success artifact from the ingest archive.

Toolkit GUI builds do not naturally produce the ingest watcher sidecar format in `modules/ingest/archive/`, so readiness currently fails even when the module was built successfully through the toolkit path.

This is a contract bug.

### 3. Semantic destination extraction over-mines prose

`utils/module_semantic_authority.py` extracts destination phrase candidates from freeform descriptive fields. This causes terms like:

- `find sanctuary`
- `vast crypt`
- `next hall`
- `ancient stone chamber`

to be treated as canonical travel phrases and publication blockers.

This is not an LLM hallucination problem. It is an over-aggressive deterministic mining problem.

### 4. Hidden-NPC probe is too strict

NPCs with valid `visible_location_ids` can still fail hidden-NPC probe expectations because reveal bindings are treated as required even when the NPC is already visibly authored in the same location.

This is another deterministic audit precision problem.

### 5. Gameplay/media gate is doing legitimate work

If a module structurally declares monsters in `locations[].monsters[]`, those entities are being treated as real combatants and therefore must meet media/readiness expectations.

This is correct for real combatants.

The mistake is allowing scene-only illusion content to reach structured combatant fields at all.

## Guiding Principle

Python enforces canonical emitted structure.

LLMs should help classify ambiguous authored intent before Python commits it to canonical JSON, not after the fact by silently modifying published module truth.

The correct contract is:

- LLM proposes classifications
- Python validates and applies allowed transforms
- Human approves review-time ambiguity when needed

## Phase 1 - Structural Stabilization

### Goal

Stop the current false failures without weakening legitimate publication/readiness protections.

### 1. Replace finisher subprocess monster materialization with in-process call

Files:

- `web/extensions/toolkit_module_finisher.py`
- `scripts/homebrew_ingest_dev.py`

Plan:

- replace `subprocess.run([... homebrew_materialize_monsters.py ...])`
- import and call `materialize_monsters(...)` directly in-process
- align with the already-correct pattern used in `web/extensions/toolkit_homebrew_readiness_gate.py`

Expected benefits:

- removes cwd/PYTHONPATH fragility
- removes stdout/stderr JSON parsing surface area
- reduces avoidable failure modes
- improves parity between readiness gate and finisher behavior

### 2. Make sidecar gate conditional on build source

Files:

- `scripts/audit_module_readiness.py`
- `scripts/audit_module_publishability.py`
- `web/extensions/toolkit_module_finisher.py`
- any callsites that invoke readiness/publishability

Plan:

- add a build-source contract such as `source="toolkit" | "watcher"`
- for `source="toolkit"`, disable ingest-sidecar requirement
- treat `modules/<slug>/toolkit_build_report.json` as the provenance-equivalent artifact for toolkit builds

Confirmed policy:

- this change is approved

Expected benefits:

- readiness becomes achievable for GUI-built modules
- watcher pipeline remains strict and unchanged for watcher builds
- eliminates a guaranteed false negative in toolkit workflows

### 3. Tighten destination phrase extraction

Files:

- `utils/module_semantic_authority.py`
- `scripts/module_semantic_probe_harness.py`

Plan:

- restrict destination extraction to canonical fields only:
  - `location.name`
  - `location.aliases`
  - `location.source_room_title`
  - optionally `plotPoints[].title`
- stop mining freeform narrative fields for destination phrases:
  - `description`
  - `dmInstructions`
  - `plotImpact`
  - `dcChecks`
  - `features.description`
  - `investigation_hooks.*`
- if any prose mining remains, require strong travel patterns such as:
  - `go to`
  - `travel to`
  - `enter`
  - `return to`
  - `head to`
  - `seek` plus canonical alias

Expected benefits:

- reduces false `unresolved_destination_phrase` blockers
- preserves real canonical travel validation
- stops poetic module prose from being misread as topological truth

### 4. Relax hidden-NPC probe requirements for visible NPCs

Files:

- `utils/module_semantic_authority.py`
- `scripts/module_semantic_probe_harness.py`

Plan:

- NPCs with valid `visible_location_ids` should pass without needing reveal bindings
- reserve hidden-NPC failures for NPCs that are authored as hidden/reveal-only and lack both:
  - visible location authority
  - reveal authority

Expected benefits:

- reduces false semantic-probe failures
- keeps real hidden/reveal contracts enforced
- better matches authored module intent

### 5. Scene-only illusion policy and post-build media handoff

Files:

- builder output shaping
- gameplay audit path
- any scene-entity consumers

Confirmed policy:

- keep scene-only illusions out of structured combatant fields via scene-entity modeling
- keep manual media generation user-invoked
- toolkit finisher should complete successful builds and hand the user off to `Module Builder -> Module Media Generator` when module monster/NPC media is still missing

Plan:

- real monsters stay in `locations[].monsters[]` and must pass hydration/materialization requirements
- scene-only illusion content should be emitted as `sceneEntity` or equivalent narrative metadata, not as structured combatants
- for toolkit builds, missing module monster/NPC media should surface as explicit post-build handoff guidance to `Module Builder -> Module Media Generator`
- finisher automation should not duplicate the existing manual media-generation workflow

Expected benefits:

- preserves runtime realism and combatant/materialization rigor
- preserves DM freedom to narrate illusion-heavy scenes
- avoids poisoning gameplay gates with non-combat flavor content
- gives module authors a clean successful build plus the correct next manual step for media generation

### 6. Strengthen regression coverage around real execution paths

Files:

- `scripts/test_toolkit_module_build_publication_parity.py`
- readiness/publishability tests
- materialization tests

Plan:

- stop relying only on mocked subprocess behavior in parity tests
- add coverage that exercises the real in-process materialization path
- add toolkit-source readiness tests proving sidecar gate is skipped only for toolkit builds
- add semantic extraction tests using Numillian-style evocative prose fixtures
- add hidden-NPC tests covering visible-only, reveal-only, and hidden-without-authority cases

Expected benefits:

- catches the exact class of bugs that slipped through
- reduces regressions in future uploader changes

## Phase 2 - LLM-Assisted Narrative Classification

### Goal

Add bounded LLM assistance at review-time decision points to help classify ambiguous authored narrative intent before Python emits canonical module JSON.

This phase happens after structural fixes land.

### Design Rule

The LLM is not the final authority.

The LLM may classify ambiguous authored material into structured categories. Python validates those categories and only then emits canonical JSON.

### Decision Point 1 - Entity triage

Purpose:

- distinguish real combatants from illusion-only or narrator-only entities

Input:

- candidate monster/NPC/entity name
- local authored context
- surrounding room/location prose

Structured outputs:

- `combatant`
- `scene_illusion`
- `narrator_flavor`

Python actions:

- `combatant` -> keep in structured combat fields, require full readiness/media
- `scene_illusion` -> emit as scene entity / illusion metadata
- `narrator_flavor` -> keep in prose-only fields, not combat schema

Why this matters:

- directly addresses the illusionist mindscape problem
- keeps scene drama without turning every strange entity into a JSON monster

### Decision Point 2 - Destination phrase classification

Purpose:

- distinguish canonical travel references from evocative quest prose

Structured outputs:

- `canonical_alias`
- `quest_objective`
- `evocative_prose`

Python actions:

- only `canonical_alias` feeds travel authority maps
- `quest_objective` remains plot guidance, not travel topology
- `evocative_prose` is ignored by travel probes

### Decision Point 3 - NPC visibility classification

Purpose:

- clarify whether NPC authored mentions imply:
  - visible presence
  - hidden/reveal structure
  - lore-only reference

Structured outputs:

- `visible`
- `hidden_reveal`
- `lore_only`

Python actions:

- populate `visible_location_ids`
- populate reveal authority when appropriate
- prevent probe confusion for visible NPCs mentioned in prose

### Decision Point 4 - Post-audit remediation proposals

Purpose:

- turn blocker reports into actionable author-review suggestions

Examples:

- move illusion entity from `monsters[]` to `sceneEntity`
- add canonical alias to location
- suppress evocative prose from travel map
- add visible/reveal authority to NPC catalog

Contract:

- LLM proposes
- Python validates transform safety
- GUI review accepts/rejects per proposal

## Re-run and Migration Plan

After Phase 1 structural fixes:

1. Re-run readiness/publishability against existing modules.
2. Identify modules whose failures were false positives from destination extraction or hidden-NPC precision.
3. Re-run materialization using the in-process path.
4. Re-baseline toolkit build parity tests.

After Phase 2 classification support:

1. Re-ingest `The_Hidden_City_of_Numillian` from markdown.
2. Re-ingest other illusion-heavy or prose-heavy modules where useful.
3. Compare:
   - blocker count before/after
   - number of scene-only entities correctly emitted
   - semantic probe failure reduction

## 6.2 Baseline Outcomes After Structural Stabilization

The first structural slice did what it was supposed to do: it separated source-contract failures from real module-quality failures instead of blending them together.

Baseline artifact:

- `docs/operations/gui_builder_structural_baseline_report.json`

Scope:

- 8 existing modules audited under both `source="watcher"` and `source="toolkit"`

Key results:

1. `watcher` and `toolkit` are now behaving as distinct, intentional contracts.
2. Legacy modules that were never built through the GUI toolkit correctly fail `toolkit` provenance or toolkit-ordering expectations rather than being misclassified as generic finisher failures.
3. `The_Hidden_City_of_Numillian` is the only current baseline module whose toolkit-side failure signature no longer centers on provenance-ordering, making it the correct canary for toolkit remediation work.
4. Watcher-side failures are now easier to interpret as either:
   - real module blocker debt,
   - legacy watcher-sidecar absence,
   - or publication/content issues unrelated to the original structural finisher bug.

Observed matrix:

- `A_Pottsfield_Burial`
  - watcher=`pass/pass`
  - toolkit=`fail/fail`, categories=`["provenance_ordering_bug"]`
- `The_Thornwood_Watch`
  - watcher=`pass/pass`
  - toolkit=`fail/fail`, categories=`["provenance_ordering_bug"]`
- `The_Pumpkin_Kings_Curse`
  - watcher=`pass/fail`
  - toolkit=`fail/fail`, categories=`["provenance_ordering_bug", "semantic_tooling_debt"]`
- `Keep_of_Doom`
  - watcher=`fail/fail`
  - toolkit=`fail/fail`, categories=`["provenance_ordering_bug"]`
- `Night_of_the_Restless_Dead`
  - watcher=`fail/fail`
  - toolkit=`fail/fail`, categories=`["provenance_ordering_bug", "semantic_tooling_debt"]`
- `Murder_at_the_Drowning_Lass`
  - watcher=`fail/fail` because `sidecar_missing`
  - toolkit=`fail/fail`, categories=`["provenance_ordering_bug", "semantic_tooling_debt"]`
- `The_Ancients_Lab`
  - watcher=`fail/fail` because `sidecar_missing`
  - toolkit=`fail/fail`, categories=`["provenance_ordering_bug", "semantic_tooling_debt"]`
- `The_Hidden_City_of_Numillian`
  - watcher=`fail/fail` because `sidecar_missing`
  - toolkit=`fail/fail`, categories=`["semantic_warning_only", "semantic_tooling_debt"]`

Implications:

1. The next change should not try to make every legacy module pass `toolkit`.
2. The next change must define explicit provenance expectations by source and module history.
3. Baseline rerun matrices should become acceptance criteria and persisted regression artifacts, not just exploratory reporting.
4. The structural stabilization slice should stay focused on contracts already fixed; the next slice should move to remediation, rollout policy, and then repair convergence hardening.

## 6.3 Numillian Re-Ingest Findings

The first Numillian re-ingest after structural stabilization showed that the original structural changes were necessary and effective, but it also exposed the next layer of workflow issues.

### What improved

Monster hydration/materialization is no longer the primary failure.

Confirmed from the 6.3 payload:

- hydration/materialization succeeded
- `blocked=0`
- hydration modes resolved as `existing=18`
- all 18 monsters resolved against existing files/json rather than failing in the finisher stage

This means the old subprocess/import-context failure is resolved for the toolkit path.

### What still failed

The run still ended with:

- `ready_status=fail`
- `publishable_status=fail`

But the remaining blockers are now in three much cleaner categories.

### 1. New structural bug: toolkit provenance ordering/self-check

`toolkit` readiness still reported `toolkit_provenance_missing` during the same finisher run that produced the toolkit build report.

Diagnosis:

- `web/extensions/toolkit_module_finisher.py` runs publishability/readiness before it writes `modules/<slug>/toolkit_build_report.json`
- the toolkit provenance gate correctly requires the artifact
- but the finisher is asking readiness to validate toolkit provenance before the current run has persisted it

This is a self-referential ordering bug, not a module-content failure.

### 2. Real content blockers: missing base monster media

Gameplay gate still failed because Numillian structurally declares 18 real monster/media entries under module monster media expectations, and the base `.jpg` media files are absent.

This is a legitimate blocker class.

Implication:

- these entities are currently modeled as real combatants, not scene-only illusions
- if they are intended to remain real combatants, the media debt must be remediated
- if some are actually scene-only illusions, they should be re-authored out of structured combatant fields and into scene-entity style metadata

### 3. Policy question: degraded semantic outcomes vs true publishability blockers

Numillian's semantic systems improved substantially:

- unresolved destination phrase blockers are gone
- hidden-NPC probes passed
- semantic audit was only `degraded`
- semantic probes were only `degraded`

Residual issues were warning-level, not hard semantic contradictions:

- one NPC authority warning for `Surviving Faction Leaders`
- one probe/tooling warning: `handoff_probe_fixture_missing`

This raises a policy question for the next slice:

- should `degraded` semantic status automatically fail `publishable_status`
- or should only semantic blocking errors fail publishability, while warning-only/tooling-debt degradation remains non-blocking

Current recommendation:

- treat pure warning/tooling-debt semantic degradation as distinct from true module semantic failure
- especially where no semantic blocking errors remain

## 6.4 Numillian Convergence Findings

The next Numillian canary rerun (`4.2`) showed that the bottleneck has moved again.

It did not fail because monster hydration is broken.
It failed because the readiness repair loop reached a fixed point without converging past schema validation.

Top-level canary outcome:

- `stage=readiness`
- `status=repair_budget_exhausted`
- `ready_for_finishing=false`
- `deterministic_passes=2`
- `semantic_passes=0`

### What the canary proved

Hydration is healthy enough for this phase.

Confirmed from the rerun payload:

- `blocked=0`
- second-pass hydration modes resolved as `existing=12`
- `seed_missing_fallback_used=true`
- sampled authored monsters were all resolving from existing files by the second pass

That means the current failure is no longer monster-hydration throughput or import-context wiring.

### What actually blocked convergence

The readiness loop fixed what it currently knows how to fix on pass 1, then hit the same blocker set again on pass 2 with `changed=false`.

Residual deterministic blocker classes were:

1. Monster schema completion gap
   - `salt_wraith.json` still missing required fields:
     - `size`
     - `alignment`
     - `armorClass`
2. Monster reference closure gap
   - missing `monsters/echoes_of_the_party.json`
3. Plot prerequisite enforcement gap
   - finale plot `PP018` missing explicit prerequisite on `PP017`
4. Spatial remediation convergence gap
   - `GLQ001` / `TUS001` and related maps still fail cardinal adjacency for connected rooms `G03 <-> G04`

This is the key interpretation:

- pass 1 repaired what current repairers cover
- pass 2 produced no further delta
- the repair budget exhausted correctly because more retries would only loop

### Planning implication

Do not increase repair budget yet.

The right next step is to add convergent deterministic repair capability for the four residual blocker classes above, then rerun the Numillian canary.

The next change should therefore treat `repair_budget_exhausted` as a classification signal:

- not a request for more retries
- but evidence that the repair engine lacks handlers for specific validator families

Recommended acceptance criteria for that workstream:

1. If two consecutive repair passes produce the same blocker set, stop and classify rather than looping.
2. Add targeted repair coverage for monster schema completion, monster reference closure, plot prerequisite repair, and spatial adjacency convergence.
3. Numillian should advance past schema gate without `repair_budget_exhausted` once those repairers exist.
4. Any remaining Numillian failures after that point should be content-remediation or policy failures, not repair-engine convergence failures.

## 6.5 Readiness Convergence Hardening Results

That convergence-hardening slice has now landed and is doing useful work, but it did not close the Numillian canary.

Artifacts:

- `docs/operations/gui_builder_readiness_convergence_canary_report.json`
- `openspec/changes/gui-builder-readiness-convergence-hardening/`

What the completed slice accomplished:

1. Added convergence-aware readiness reporting:
   - `convergence_outcome`
   - `fixed_point_detected`
   - `residual_blocker_classes`
   - `residual_failure_categories`
   - `residual_failure_errors`
2. Added deterministic repair coverage for:
   - monster schema completion attempts
   - finale prerequisite backfill attempts
   - explicit residual classification for unresolved monster, plot, and spatial failures
3. Added regression coverage proving those paths execute and report correctly.

What the real Numillian canary still shows:

- `status=repair_budget_exhausted`
- `convergence_outcome=repair_budget_exhausted`
- `fixed_point_detected=false`
- `deterministic_passes=1`
- `semantic_passes=0`
- `ready_for_finishing=false`

Residual blocker classes remain:

1. `monster_reference_closure_gap`
2. `monster_schema_completion_gap`
3. `plot_prerequisite_gap`
4. `spatial_adjacency_convergence_gap`

Observed residual details from the canary artifact:

- reference integrity still expects `monsters/echoes_of_the_party.json`
- `salt_wraith.json` still lacks `size`, `alignment`, and `armorClass`
- `PP018` still lacks the explicit prerequisite gate from `PP017`
- `GLQ001` and `TUS001` still have unchanged `G03 <-> G04` non-cardinal adjacency contradictions

This means the next slice should not re-open broad convergence instrumentation.
It should close the residual convergence gaps exposed by the canary.

## 6.6 Residual Convergence Closure Results

That residual-closure slice has now also landed, and it improved diagnosis plus repair coverage, but it still did not advance the Numillian canary beyond the current blocker set.

Artifacts:

- `docs/operations/gui_builder_residual_convergence_closure_canary_report.json`
- `openspec/changes/gui-builder-residual-convergence-closure/`

What the completed slice added:

1. Validator-derived monster reference closure against missing `expected monsters/<slug>.json` paths.
2. Live-shape plot prerequisite repair support for `module_plot.json` files whose `plotPoints` are stored as lists of objects with `id` fields.
3. Stronger spatial contradiction escalation that distinguishes unchanged contradictions from ordinary repair misses and classifies them as `spatial_structural_debt` when the repair engine cannot materially reduce them.
4. Residual closure reporting with canary comparison fields, including:
   - `residual_closure_advanced`
   - `removed_residual_classes`
   - `added_residual_classes`
   - `advanced_beyond_previous`

What the real residual-closure canary still shows:

- `status=repair_budget_exhausted`
- `ready_for_finishing=false`
- `convergence_outcome=repair_budget_exhausted`
- `fixed_point_detected=false`
- `residual_closure_advanced=true`
- `advanced_beyond_previous=false`
- `previous_total_failure_count=5`
- `current_total_failure_count=5`

Residual blocker classes are now:

1. `monster_reference_closure_gap`
2. `monster_schema_completion_gap`
3. `plot_prerequisite_gap`
4. `spatial_adjacency_convergence_gap`
5. `spatial_structural_debt`

Interpretation:

- residual closure is no longer blocked by missing repair instrumentation alone,
- but the real Numillian blockers are still not being removed from the live validator result,
- and the next slice must focus on direct resolution of those specific blockers rather than more general pipeline hardening.

The most important implication is that the remaining work is now module-specific and validator-specific:

1. `monsters/echoes_of_the_party.json` still is not being materialized or reused into the expected location.
2. `salt_wraith.json` still is not being completed with authoritative `size`, `alignment`, and `armorClass` values.
3. `PP018 <- PP017` prerequisite repair still is not surfacing as a cleared live validator result in the canary.
4. `GLQ001` / `TUS001` still contain unresolved `G03 <-> G04` adjacency contradictions, and those now partly classify as author/content debt rather than pure repair-engine gaps.

## 6.7 Numillian Live Blocker Diagnosis

The focused blocker-resolution diagnosis has now narrowed the remaining failure set to four exact live mismatches.

This is no longer a broad pipeline-hardening problem.
It is a reconciliation problem between what the validator reads, what the readiness repairers target, and what the Numillian module actually contains.

### Blocker 1 - Monster authority mismatch for `Echoes of the Party`

The validator is correct to expect `modules/The_Hidden_City_of_Numillian/monsters/echoes_of_the_party.json` because `TMS001.json` authors `Echoes of the Party` as a `locations[].monsters[]` entry in `Twilight Cachehouse`.

But readiness repair still fails to materialize it because the authority layer excludes that identity before authorization:

- `module_context.json` currently lists `echoes_of_the_party` under `npcs`
- `utils/module_monster_authority.py` loads known NPC identities from `module_context.json`
- `build_module_monster_authority(...)` skips authored monster names whose normalized slug is in the known-NPC set

Result:

- validator sees a structured monster reference
- authority builder treats the same identity as NPC-like and excludes it
- repair then fails with `unauthorized_monster_reference`

So the next slice must reconcile validator-visible structured monsters with authority filtering, at least for this class of authored projection/echo entities.

### Blocker 2 - Schema completion misses canonical recovery for `salt_wraith`

`modules/The_Hidden_City_of_Numillian/monsters/salt_wraith.json` is still missing:

- `size`
- `alignment`
- `armorClass`

The current schema repairer only tries exact compendium slug lookup.
Diagnosis against `data/bestiary/monster_compendium.json` shows the authoritative entry is present as `salt_wraiths` (plural), not `salt_wraith` (singular).

That means the remaining failure is not lack of source data.
It is canonical-recovery weakness in the repair path.

The next slice should therefore add safe canonical fallback matching for schema repair (for example singular/plural recovery) before classifying the monster as irreducible.

### Blocker 3 - Plot repair targets the wrong finale node

The validator flags:

- `PP018` missing explicit prerequisite gate from `PP017`

Live Numillian plot shape confirms:

- `PP017.nextPoints = ["PP018"]`
- `PP018.nextPoints = ["PP019"]`
- `PP018` has no `prerequisites`
- `PP019` is the final terminal node

The current repairer selected the numerically last node (`PP019`) and concluded finale prerequisites were already present or not needed.
That misses the actual validator-failing conclusion edge.

So the next slice must target the validator-identified failing plot node, not the numerically terminal node.

### Blocker 4 - Spatial failure is now proven to be area/map parity drift

The diagnosis resolved the earlier uncertainty here.

Active area files now show repaired cardinal layouts for `GLQ001.json` and `TUS001.json`, but the paired map files still contain the old non-cardinal coordinates:

- `map_GLQ001.json`: `G03=X10Y11`, `G04=X12Y10`
- `map_TUS001.json`: `G03=X10Y11`, `G04=X12Y10`

So the residual spatial failure is not primarily validator staleness.
It is live area/map parity drift where room coordinates were corrected in the area files but not synchronized into the paired `map_*.json` files.

This gives the next slice a clear target:

1. repair or synchronize the paired map files deterministically when area coordinates advance, or
2. explicitly classify unmatched map-file contradictions as author/content debt only after deterministic parity repair has been attempted.

## Updated Next-Step Recommendation

The next OpenSpec slice should now be narrower than residual convergence closure and narrower than generic Numillian blocker resolution.

It should be a Numillian live blocker reconciliation slice focused on the exact mismatches now diagnosed.

Recommended scope for the next change:

1. Reconcile `Echoes of the Party` between validator-visible monster references and authority-layer NPC filtering.
2. Add authoritative canonical recovery for monster schema completion so `salt_wraith` can resolve against known source data.
3. Make plot prerequisite repair follow the validator-failing conclusion edge (`PP018 <- PP017`) instead of the numeric terminal point.
4. Repair live area/map parity drift for `GLQ001` and `TUS001`, or cleanly classify remaining map contradictions after parity sync is attempted.
5. Re-run the Numillian canary after those exact reconciliations and require measurable advancement in live validator output.
6. Persist updated reconciliation artifacts that distinguish resolved repair-engine mismatches from true remaining authored debt.

This keeps the work sequenced correctly:

- Phase 1 structural stabilization
- Phase 1b remediation and rollout workflow
- Phase 1c readiness convergence hardening
- Phase 1c.1 residual convergence closure
- Phase 1c.2 Numillian live blocker reconciliation
- Phase 1c.3 Numillian post-reingest gate reconciliation
- Phase 2 LLM-assisted narrative classification

## 6.8 Numillian Post-Reingest Gate Findings

The latest full toolkit finisher re-ingest confirms that the earlier structural reconciliation work is holding, but it also exposed the next gate-level slice that must close before Phase 2.

What is now proven green:

- monster materialization succeeded in-process
- schema validation passed cleanly for `The_Hidden_City_of_Numillian`
- spatial contract and map/area parity passed cleanly
- hidden-NPC probe precision remained healthy

The new finisher failure is therefore not a rollback of structural work.
It is a narrower post-reingest gate problem.

### Residual blocker class 1 - gameplay gate media handoff contract

The finisher now resolves all authored monsters as existing JSON successfully, but `scripts/audit_module_gameplay.py` still treats missing base monster media as a hard blocker for structurally-authored monsters.

Observed from the latest toolkit payload:

- `hydration_modes.existing = 16`
- `json_valid = 16`
- `media_base_coverage = 0`
- gameplay gate exit reason = `gameplay_audit_exit_nonzero`

Blocking errors are all of the form:

- `Missing base media for: <monster_slug> (from <area>.json:locations[i].monsters[j])`

Interpretation:

- this is not a monster-hydration failure
- this is a toolkit UX/handoff failure, not evidence that the module build itself failed
- the next slice must change toolkit finisher semantics so otherwise successful builds complete and explicitly route the user to `Module Builder -> Module Media Generator`

Current recommendation:

- toolkit finisher/build should not fail on missing module monster/NPC media when the rest of the build succeeds
- gameplay/readiness reporting should still surface the missing media debt clearly and accurately
- remediation remains manual and user-invoked through `Module Builder -> Module Media Generator`
- treat this as a Phase 1 Python/UX contract fix, not a Phase 2 LLM classification problem

### Residual blocker class 2 - unresolved destination alias contraction

Semantic authority now fails on exactly one player-facing unresolved destination phrase:

- `paradox sanctuary`

At the same time, the canonical authored location remains:

- `Veiled Paradox Sanctuary` -> `H01`

And the semantic output already resolves:

- `veiled paradox sanctuary` -> `H01`

Interpretation:

- the remaining destination issue is not broad travel-topology debt
- it is a narrow alias-contraction problem at the boundary between canonical location naming and observed player-facing phrase extraction
- this is the strongest current candidate for the later Phase 2 ambiguity lane (`travel alias vs evocative prose`), unless a bounded deterministic normalization rule can close it safely without widening false positives

### Planning implication

The next slice should not jump straight into broad LLM integration.

It should first reconcile these post-reingest toolkit outcomes:

1. post-build media handoff semantics for otherwise successful toolkit builds
2. toolkit IA/UX ordering so `Module Builder` workflow comes before graphic-pack tooling
3. exact handling of the single unresolved destination phrase `paradox sanctuary`
4. deterministic payload normalization so gameplay/readiness reporting shows structured monster-media debt correctly

Acceptance target for this slice:

1. re-running toolkit finisher for a module like `Murder_at_the_Drowning_Lass` must complete the build when JSON/materialization/schema/semantic gates are green, even if module monster/NPC media is still missing
2. post-build output must explicitly hand the user off to `Module Builder -> Module Media Generator`
3. readiness/publishability payloads must reflect structural media debt correctly instead of losing details due to payload-shape mismatch
4. semantic authority must classify `paradox sanctuary` as an ambiguity boundary explicitly deferred to Phase 2 with no misleading structural-failure wording
5. once these are reconciled, only true ambiguity-classification work should remain before Phase 2

## 6.9 Murder at the Drowning Lass UX Contract Update

`Murder_at_the_Drowning_Lass` clarified the actual toolkit product contract more explicitly than Numillian did.

Observed from the failing payload:

- monster materialization succeeded (`blocked_count=0`, authored monsters resolved)
- schema validation was green (`62 passed`, `0 failed`)
- semantic authority had no blocking findings
- semantic probes were only degraded by `handoff_probe_fixture_missing`
- the actual failing gate was gameplay because structurally-authored monsters lacked module-local base media

This surfaced two concrete conclusions.

### 1. Finisher failure semantics are currently wrong for toolkit media debt

When the core module build is otherwise successful, missing module monster/NPC media should not produce an overall failed finisher result.

The desired UX is:

1. finish the module build successfully
2. report that module media is still missing
3. direct the user to `Module Builder -> Module Media Generator`

This is the authoritative product decision.

### 2. Toolkit information architecture should reflect the author workflow

The toolkit should read as two conceptual sections:

1. `Module Builder`
   - `Generate Module`
   - `Generate Module Media`
2. `Graphic Pack Manager`
   - graphic pack import/create
   - monster manager
   - NPC manager

That means module-builder tabs/sub-tabs (`Import`, `Media`) should come first, followed by graphic-pack tooling.

### 3. Small deterministic reporting fix remains required

`scripts/audit_module_readiness.py` is currently reading gameplay output as if fields are top-level, even though `scripts/audit_module_gameplay.py` emits them under `target`.

Result:

- gameplay still fails correctly by exit code
- but readiness/publishability lose structured `monster_media_findings`
- `toolkit_media_policy.structural_media_debt_count` can incorrectly report `0`

This is a separate deterministic bug and should be fixed alongside the UX contract update.

### Updated recommendation

The next bounded work should split into five small slices before broader LLM builder assistance:

1. finisher media-handoff semantics
2. toolkit UI/tab ordering around `Module Builder` vs `Graphic Pack Manager`
3. gameplay/readiness payload normalization
4. mixed-failure publishability classification
5. builder semantic remediation sequencing

After those deterministic Python/UX fixes land, continue with the planned LLM builder help at appropriate finishing/handoff points for genuine ambiguity and edge cases.

### 4. Mixed-failure classification still needs an explicit boundary

`The_Ancients_Lab` proved the uploader can land in a mixed state:

- gameplay/readiness carries real missing-media debt
- semantic publishability still has true blockers like unresolved destination phrases (`crucible hall`)
- finisher policy therefore must not reinterpret that module as a success-with-media-handoff case

This is a separate deterministic classification slice.

Required contract:

- pure media-only debt -> build succeeds with explicit media handoff
- mixed media + semantic/content blockers -> build remains failed
- semantic/content blockers without media debt -> build remains failed

This boundary should be codified after payload normalization so the finisher and publishability layers are reading corrected readiness data before status policy is tightened.

### 5. Builder semantic remediation needs its own bounded sequence

Once deterministic reporting is correct, the remaining unresolved destination alias debt is no longer a reporting bug. It is builder-quality semantic debt.

That means the next builder-facing slice should define:

- where unresolved destination alias defects surface in the GUI flow
- how the uploader hands those blockers back to the builder without pretending Python can auto-fix authoring intent
- what bounded remediation sequence should happen before broader Phase 2 ambiguity assistance

This keeps Phase 2 LLM work anchored to explicit semantic defects rather than mixed together with payload-shape or finisher-status bugs.

## What Success Looks Like

### Short-term success

- toolkit finisher no longer fails monster materialization on import context
- toolkit builds no longer fail sidecar gate by default
- evocative prose stops generating false travel blockers
- visible NPCs stop failing hidden-NPC probes
- existing modules can be re-run with fewer false failures

### Medium-term success

- illusion-heavy modules build without constant manual cleanup
- scene-only entities remain narratively rich without being forced into combat schemas
- real combatants still fail closed if not fully authored/materialized/media-complete

### Long-term success

- GUI uploader becomes a reviewable authoring pipeline rather than a brittle mechanical converter
- ambiguous narrative intent is surfaced and classified early
- Python remains authoritative while LLMs add clarity at bounded classification points

## Recommended Implementation Order

1. Replace finisher and ingest materialization subprocess calls with in-process calls.
2. Add build-source-aware readiness/publishability contracts and conditional sidecar behavior.
3. Tighten deterministic destination extraction.
4. Relax hidden-NPC probe rules for visible NPCs.
5. Re-run existing modules to establish new baseline.
6. Fix same-run toolkit provenance ordering and warning-only semantic publishability policy.
7. Add deterministic readiness convergence hardening for schema-era blocker classes.
8. Re-run `The_Hidden_City_of_Numillian` as the readiness convergence canary.
9. Close residual convergence gaps revealed by the canary.
10. Re-run `The_Hidden_City_of_Numillian` as the residual-closure canary.
11. Reconcile the remaining live Numillian validator/repair mismatches.
12. Re-run `The_Hidden_City_of_Numillian` as the blocker-reconciliation canary.
13. Re-run `The_Hidden_City_of_Numillian` as the post-reingest gate canary.
14. Complete `gui-builder-media-handoff-semantics` for pure media-only handoff policy.
15. Complete `gui-builder-module-workflow-ui-ordering` so `Module Builder -> Module Media Generator` is visually first.
16. Complete `gui-builder-gameplay-readiness-payload-normalization` so readiness/publishability consume gameplay payloads correctly.
17. Add a deterministic mixed-failure classification slice so media-only handoff is never applied to modules that still have semantic blockers.
18. Add a builder semantic remediation sequencing slice for unresolved destination-alias and similar authoring defects.
19. Add Phase 2 LLM entity triage.
20. Add Phase 2 destination and NPC classification.
21. Add reviewable remediation proposals.

## Open Questions

These are now mostly resolved, but kept here for implementation clarity:

- exact field name for build-source contract (`source`, `build_source`, or equivalent)
- whether toolkit provenance should remain only `toolkit_build_report.json` or also emit a sidecar-compatible artifact for audit interoperability
- whether Phase 2 classifications should be mandatory for ambiguous content or advisory-only in the first rollout

## Recommendation

Treat Phase 1 as substantially complete, but with a final deterministic toolkit UX/handoff cleanup chain before Phase 2.

The immediate next step is still not broader pipeline work. It is to finish the post-build deterministic chain in this order:

1. `gui-builder-media-handoff-semantics`
2. `gui-builder-module-workflow-ui-ordering`
3. `gui-builder-gameplay-readiness-payload-normalization`
4. mixed-failure publishability classification
5. builder semantic remediation sequencing

Only after those slices land should Phase 2 begin, because that keeps media-only handoff, mixed-failure policy, UI guidance, and semantic authoring defects separate and explicit.

Then add Phase 2 LLM classification specifically for ambiguity boundaries:

- illusion vs combatant
- travel alias vs evocative prose
- visible NPC vs hidden/reveal NPC

That is the cleanest way to preserve the current Python realism contract while giving the uploader a smarter interpretation layer for narrative-heavy modules.
