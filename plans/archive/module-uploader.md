# Public Homebrew Module Uploader Plan

## Status

- Lifecycle state: Completed (ready to archive)
- Product objective: Complete the public-facing Homebrew adventure upload path in Toolkit Module Builder
- Strategic path: `1 -> 2 -> 3`
- Meaning of path:
- `1` = upstream LLM-first Module Builder from narrative description
- `2` = OpenCode developer ingest workflow that interprets source material first, then seeds, validates, enriches, and publishes
- `3` = public GUI upload flow that must now inherit the strengths of both `1` and `2`
- Review model: mandatory human review before registry integration
- Artifact model: normalized source packet and intermediate build artifacts are persisted for audit, retry, and rebuild
- Roadmap role: final pre-v2 module-import slice for interactive reviewed import
- V2 import reference: `plans/version-2/module-import.md`
- World-narrative reference: `plans/version-2/world-narrative.md`
- Titan reference: `plans/version-2/titan-integration.md`
- Current implementation checkpoint:
- Phase 0 complete: normalized packet/workspace/job-state contract is established in the upload path.
- Phase 1 complete: preflight routes readable but ambiguous uploads into normalization rather than failing too early.
- Phase 2 complete: LLM normalization backend emits persisted packet/report artifacts.
- Phase 3 complete: async upload job orchestration persists artifacts and stops cleanly at `awaiting_review`.
- Phase 4 complete: mandatory review UI and approval snapshot flow are active.
- Phase 5 complete: approved uploads build from persisted normalized packets.
- Phase 5A complete for current uploader boundary: uploads now pass through structural readiness/repair and can land in `ready_for_finishing`.
- Phase 6 complete: `ready_for_finishing` upload jobs now attach to the shared finisher/publication pipeline and resolve into `completed`, `not_publishable`, or `finishing_failed`.
- Phase 7 complete: artifact manifest visibility, retry-from-packet, retry-from-finishing, and cleanup controls are now implemented and validated.
- Rebuild support complete: repeated uploads now require explicit confirmation and use backup + clean rebuild before re-entering build/readiness.
- Verified corpus checkpoint: `A_Pottsfield_Burial` demonstrates clean ingest/build/readiness success; `The_Ancients_Lab` demonstrates artifact generation and monster closure are working, with remaining issues isolated to post-build semantic/content quality rather than upload ingestion failure.
- Phase 8 complete: corpus-based quality gate and parity acceptance suite implemented and archived in OpenSpec.
- Logical successor plan: `plans/module-uploader-2.md` (GUI Builder stabilization + narrative classification).

## Goal

Deliver a fully functional public upload GUI for player-created adventures where a user can upload a Homebrewery markdown adventure and have NEQ:

1. read and interpret the source with LLM assistance,
2. infer missing metadata and module structure,
3. present a reviewable normalized adventure packet,
4. build a rich NEQ module using the upstream LLM builder strengths,
5. run the hardened Python validation, continuity, semantic, and publication pipeline built over the last three months,
6. register the module only after successful review and finishing.

This plan intentionally avoids treating regex preflight as the primary parser. Python remains the validator and publication authority. LLM becomes the first-pass source interpreter.

## Position In The Roadmap

This uploader plan is the intended end of the first pre-v2 phase of module import.

Its role is:

1. complete the public interactive upload path,
2. prove the raw prose -> normalized packet -> reviewed build -> validated module loop,
3. establish the markdown normalization contract that v2 import can later scale,
4. establish artifact persistence, review, and rebuild semantics,
5. hand a stronger foundation to `plans/version-2/module-import.md`.

After this plan completes:

1. `plans/version-2/module-import.md` should build on these contracts for bulk and canonical import operations,
2. `plans/version-2/world-narrative.md` should later build a separate source-anonymous narrative web from copyrighted literature under `user_uploads/text/`,
3. `plans/version-2/titan-integration.md` should later consume that interpreted narrative web and continuity-qualified module signals as proposal-only world pressure input.

Short version:

- uploader = end of pre-v2 interactive import
- module-import = scaled v2 canonical import
- world-narrative = separate source-anonymous narrative web
- Titan = later interpreted-state consumer, not uploader replacement

## Why This Is The Right Final Builder Slice

The current public upload path is blocked because it inherited the deterministic ingest pipeline too early in the flow.

Current reality:

1. The upstream Module Builder is already LLM-first and good at turning narrative intent into playable module structure.
2. The OpenCode-led ingest workflow proved that ambiguous Homebrew source can be interpreted, normalized, enriched, seeded, and validated successfully when an LLM is used before hard validation.
3. The public GUI upload route currently reaches the deterministic gate before source interpretation has happened.

That means the current error is a symptom, not the disease.

The disease is architectural:

1. upload is asking Python heuristics to decide whether the source is already a module,
2. instead of asking the system whether the source can be understood well enough to become one.

## Product Direction

The completed uploader should be a hybrid of the existing systems.

1. From upstream builder (`1`):

- keep rich LLM-driven adventure synthesis,
- keep builder orchestration,
- keep playable output quality as the primary UX target.

2. From developer ingest (`2`):

- keep explicit staging,
- keep artifact persistence,
- keep deterministic validation,
- keep continuity and semantic enrichment,
- keep fail-closed publication logic,
- keep sidecar/result visibility,
- keep replayable and inspectable steps.

3. For the public uploader (`3`):

- make source normalization a first-class stage,
- require human review before registry integration,
- preserve prepared artifacts so the user or developer can inspect and retry,
- reuse as much of the current finisher and publication pipeline as possible.

4. For v2 continuity:

- the uploader's normalized packet should become the precursor contract for markdown import in `plans/version-2/module-import.md`,
- but the uploader must not collapse into the separate copyright-firewalled world-narrative ingestion lane.

## Core Principle

The new upload architecture should follow this rule:

1. LLM interprets the adventure source.
2. Python validates and constrains what the interpretation is allowed to become.
3. Human review approves publication-facing commits into the game world.

Short version:

- LLM for understanding and richness.
- Python for structure, safety, and publication authority.
- Human for the final release boundary.

## Current Baseline

### Existing Public Upload Path

Current upload route:

- `web/routes/toolkit_homebrew_routes.py`

Current orchestrator:

- `scripts/homebrew_ingest_dev.py`

Current hard stop:

- `scripts/homebrew_preflight.py`

Current problem:

1. preflight is acting as a parser and a publication gate at the same time,
2. structural ambiguity is treated as fatal before interpretation,
3. missing `author` or `description` is surfaced as a hard error even though these are fields the system can infer or request,
4. deterministic import assumes room-based shape too early,
5. GUI upload cannot take advantage of the richer upstream builder path.

### Existing Builder Path Worth Reusing

Current upstream-style builder execution path:

- `web/templates/module_toolkit.html`
- `web/web_interface.py` socket `start_build`
- `core/generators/module_builder.py`

Strengths already present:

1. narrative prompt input,
2. multi-stage builder progress model,
3. LLM-first module generation,
4. existing post-build finishing hook,
5. existing toolkit UI patterns for async progress and completion.

### Existing Post-Build and Publication Work Worth Reusing

Already implemented and should remain authoritative:

1. continuity normalization and enrichment,
2. semantic authority enrichment,
3. monster materialization,
4. schema validation,
5. registry verification,
6. media extraction and handles,
7. portrait prewarm,
8. sidecar audit/reporting,
9. publication/readiness reporting surfaces.

## End-State User Flow

The final public upload experience should work like this.

1. User opens Toolkit Module Builder.
2. User uploads a Homebrewery `.md` adventure.
3. System stores the raw upload.
4. System runs light source sanity checks only.
5. System runs LLM normalization to interpret the uploaded adventure into a structured packet.
6. System persists the normalized packet and supporting notes.
7. System shows a review UI with:

- inferred title,
- inferred author,
- inferred description,
- inferred level range,
- locations/scenes,
- encounter seeds,
- NPC seeds,
- monster references,
- warnings and assumptions.

8. User confirms the normalized packet.
9. System builds the module using the normalized packet as structured builder input.
10. System runs post-build finishing and publication checks.
11. System shows final report:

- success,
- degraded,
- quarantined,
- or failed,
- with reviewable artifacts.

12. Only successful reviewed modules are added to the world registry.

## Non-Negotiable Requirements

1. Review before registry integration is mandatory.
2. Normalized packet and intermediate artifacts must be saved.
3. Upload may fail closed only on true unreadable or unsafe source conditions, not because source structure is ambiguous.
4. Existing validation and publication tooling stays authoritative.
5. Public upload must become resumable and inspectable.
6. The system must support rebuild from normalized packet without requiring the original LLM parse every time.
7. The final module must be at least as safe as the current deterministic pipeline and materially richer in playability.

## Rights And Provenance Classification

This uploader must classify source provenance explicitly so later v2 plans remain coherent.

Recommended classes:

1. `user_authored`

   - player-created or project-owned adventure content,
   - eligible for source-preserving normalized packet storage,
   - eligible for reviewed module publication flow.
2. `licensed_or_project_owned`

   - rights-cleared content that may still be imported through this module lane,
   - policy may still require review before registry integration.
3. `third_party_copyright_restricted`

   - source that may be readable locally but should not be assumed to be valid for ordinary source-preserving module publication,
   - belongs more naturally to the future source-anonymous world-narrative lane unless explicitly cleared.

Architectural rule:

1. This uploader primarily serves `user_authored` and approved `licensed_or_project_owned` module sources.
2. It may share workflow ideas with world-narrative ingestion, but it is not the same copyright model.
3. The literary corpus under `user_uploads/text/` is a later `world-narrative.md` concern whose derived committable outputs must remain source-anonymous.

## Relationship To V2 Plans

### Relationship To `plans/version-2/module-import.md`

This uploader is the interactive reviewed import mode that should complete before v2 import expands into:

1. bulk inventory scanning,
2. incremental reprocessing,
3. canonical world-scale batch import,
4. progression ladder operations,
5. scheduled/high-volume workflows.

The uploader should therefore define the first practical version of:

1. the markdown normalization contract,
2. the review/quarantine model,
3. the rebuild-from-artifacts model,
4. the reviewed build -> validation -> registry sequence.

### Relationship To `plans/version-2/world-narrative.md`

This uploader should not replace the world-narrative plan.

World-narrative has a different mission:

1. ingest the copyrighted fantasy and horror novel corpus stored under `user_uploads/text/`,
2. analyze it for relations, motifs, narrative possibilities, and worldbuilding structures,
3. anonymize and copyright-sanitize those outputs,
4. persist them into relational narrative state,
5. later provide bounded narrative flavor and world-pressure inputs for runtime narration and module building.

The uploader can prepare for that future by establishing:

1. good artifact discipline,
2. provenance handling,
3. approval-gated interpretation,
4. builder-ready normalized structures,
5. continuity-qualified module outputs.

But it must remain a source-preserving module-import lane for approved adventure inputs, not the source-anonymous literary ingestion lane.

### Relationship To `plans/version-2/titan-integration.md`

Titan should consume interpreted narrative structures later, not own upload/import.

The uploader helps Titan indirectly by:

1. producing better continuity-qualified modules,
2. preserving provenance-safe build artifacts,
3. improving the quality of module seeds that later world-narrative and Titan systems can reference.

Titan remains proposal-only interpreted state, never mechanical truth, and never a substitute for the uploader's review/build pipeline.

## Proposed Architecture

## Layer 1: Source Intake

Purpose:

- accept raw user uploads,
- store them safely,
- perform minimal sanity checks,
- create upload job state.

Responsibilities:

1. extension and size checks,
2. UTF-8 readability check,
3. duplicate hash capture,
4. upload job state initialization,
5. artifact workspace creation.

Must not do:

1. full structure judgment,
2. publication eligibility decisions,
3. deterministic-only rejection for ambiguous adventures.

Primary touchpoints:

- `web/routes/toolkit_homebrew_routes.py`

## Layer 2: Normalization

Purpose:

- interpret raw Homebrew markdown into a structured, reviewable adventure packet.

This is the missing public equivalent of the developer ingest skill's early interpretation work.

Responsibilities:

1. infer missing metadata,
2. identify acts, scenes, and key locations,
3. infer rough connectivity and travel transitions,
4. identify key NPCs, monsters, and plot beats,
5. capture assumptions and confidence notes,
6. emit a canonical normalized source packet,
7. emit a builder-ready narrative summary derived from the packet,
8. keep provenance from raw source to inferred structure.

Must not do:

1. register modules,
2. directly modify world registry,
3. skip review,
4. bypass later validation.

## Layer 3: Build

Purpose:

- turn the normalized packet into NEQ module artifacts using LLM-rich generation with deterministic post-processing.

Responsibilities:

1. choose build mode,
2. produce module artifacts,
3. preserve normalized packet provenance,
4. emit build-stage artifact report.

Supported build modes:

1. `builder_hybrid`

- default for most public uploads,
- use normalized packet to drive `ModuleBuilder` or a packet-aware builder facade,
- preferred for richer playability.

2. `deterministic_emit`

- fallback or fast-path for already highly-structured normalized packets,
- may reuse deterministic importer/emitter when appropriate.

## Layer 4: Finishing, Validation, and Publication

Purpose:

- apply the existing hardening work as the authoritative safety and publication pipeline.

Responsibilities:

1. continuity contract normalization and enrichment,
2. semantic authority enrichment,
3. monster materialization,
4. schema validation,
5. registry verification,
6. media extraction and handle generation,
7. portrait prewarm,
8. publishability and readiness reporting,
9. sidecar persistence,
10. final reviewed registry integration.

This layer remains Python-owned and fail-closed.

## Canonical New Artifact Contract

Create a persisted normalized source packet for uploaded adventures.

Proposed location:

- `user_uploads/toolkit/homebrew_md/<job_id>/`

Suggested files:

1. `source_original.md`
2. `source_preflight.json`
3. `normalized_packet.json`
4. `normalization_report.json`
5. `builder_input.json`
6. `builder_narrative.txt`
7. `build_result.json`
8. `finishing_report.json`
9. `ui_review_snapshot.json`

### Normalized Packet Fields

Minimum contract:

1. `source_path`
2. `source_hash`
3. `title`
4. `author`
5. `description`
6. `estimated_level_min`
7. `estimated_level_max`
8. `adventure_summary`
9. `module_tone`
10. `acts`
11. `locations`
12. `connectivity_hints`
13. `encounter_seeds`
14. `npc_seeds`
15. `monster_refs`
16. `plot_progression`
17. `continuity_hints`
18. `media_hints`
19. `assumptions`
20. `warnings`
21. `confidence_notes`
22. `provenance`
23. `source_rights_class`
24. `review_policy`
25. `v2_alignment`

### Review Snapshot Fields

The UI must show a curated subset of the packet and capture explicit confirmation.

Suggested review payload:

1. normalized title,
2. normalized author,
3. short description,
4. detected module type,
5. level range,
6. location list,
7. major NPC list,
8. major monster list,
9. main plot beats,
10. open assumptions,
11. user approval metadata.

## Phased Implementation Plan

## Phase 0: Alignment and Scaffolding

Objective:

- establish the shared contract and workspace before touching the upload behavior.

Tasks:

1. Create this plan and use it as the implementation blueprint.
2. Create an OpenSpec change for the uploader if formal execution tracking is desired.
3. Define the normalized packet schema in code or JSON schema.
4. Define canonical artifact workspace layout under `user_uploads/toolkit/homebrew_md/`.
5. Define job state transitions for upload normalization and review.
6. Define provenance and rights-classification fields so later v2 importer and world-narrative lanes remain distinct.

Output:

1. approved packet contract,
2. approved workspace contract,
3. approved stage-state machine.

Suggested files:

- `plans/module-uploader.md`
- `openspec/changes/<new-change>/...`
- `schemas/toolkit_homebrew_normalized_packet.schema.json` or equivalent runtime contract module

Verification:

1. packet schema validated with example payloads,
2. state machine documented,
3. artifact paths verified to be safe and stable.

## Phase 1: Soften Preflight Into Routing

Objective:

- convert preflight from structure gate into routing and sanity gate.

Tasks:

1. Refactor `scripts/homebrew_preflight.py` so it distinguishes:

- `unreadable_or_invalid_source`,
- `deterministic_ready_source`,
- `llm_normalization_required_source`.

2. Stop treating missing `author` or `description` as fatal.
3. Stop treating non-room-based structure as fatal if the source is interpretable.
4. Preserve fail-closed behavior for:

- missing file,
- unreadable file,
- empty file,
- clearly malformed upload.

5. Return routing hints for downstream job orchestration.

Expected result:

- `The Garden of Demons.md` no longer hard-fails at preflight.

Suggested files:

- `scripts/homebrew_preflight.py`
- `scripts/test_homebrew_preflight.py`

Verification:

1. ambiguous but readable Homebrewery files route to normalization,
2. broken files still fail,
3. existing deterministic-ready room-based files still pass directly.

## Phase 2: Build The LLM Normalization Backend

Objective:

- create the shared source interpretation layer that public upload is currently missing.

Tasks:

1. Create a normalization service module.
2. Read raw markdown and strip presentation noise.
3. Ask the LLM to produce the normalized packet.
4. Ask the LLM to explicitly infer:

- author when missing,
- description when missing,
- location structure when implicit,
- likely adjacency/connectivity hints,
- main plot progression,
- encounter candidates,
- major NPCs and monsters.

5. Require the LLM to separate facts from assumptions.
6. Persist normalized packet and normalization report.
7. Emit a short builder narrative derived from the packet.
8. Persist provenance classification and review policy in the packet.

Implementation notes:

1. The normalization prompt should be source-faithful, not freeform worldbuilding.
2. It should preserve source intent and not invent new branches unless explicitly marked as assumptions.
3. It should be bounded and resumable.
4. It should prepare compatibility with the v2 module-import intermediate schema without trying to solve world-narrative anonymization in this phase.

Suggested files:

- `web/extensions/toolkit_homebrew_normalizer.py` or `utils/toolkit_homebrew_normalizer.py`
- prompt file under `prompts/` for upload normalization
- tests for packet generation fallback behavior

Verification:

1. packet emits for real corpus files,
2. missing metadata is auto-filled,
3. assumptions are separated from grounded source facts,
4. packet persistence works.

## Phase 3: Add Upload Job Orchestration For Normalization

Objective:

- make the GUI upload route drive normalization as an async job with persisted artifacts.

Tasks:

1. Extend `web/routes/toolkit_homebrew_routes.py` job model to include stages:

- `uploaded`,
- `preflight`,
- `normalizing`,
- `awaiting_review`,
- `approved_for_build`,
- `building`,
- `finishing`,
- `completed`,
- `quarantined`,
- `failed`.

2. Save artifacts under job workspace.
3. Return structured job progress to the frontend.
4. Ensure jobs can resume from normalized packet if build has not yet started.
5. Keep a single-active-job safety policy unless or until concurrency is deliberately expanded.

Suggested files:

- `web/routes/toolkit_homebrew_routes.py`
- route tests in `scripts/test_toolkit_homebrew_md_upload_routes.py`

Verification:

1. upload creates workspace,
2. normalization stage can finish without build starting,
3. job status reflects `awaiting_review` cleanly.

## Phase 4: Add Mandatory Review UI

Objective:

- create the review boundary before world-affecting build and registry stages.

Tasks:

1. Extend `web/templates/module_toolkit.html` to show a review panel for normalized upload jobs.
2. Display:

- title,
- author,
- description,
- level range,
- scene/location list,
- major NPCs,
- monster references,
- major warnings/assumptions.

3. Add explicit actions:

- `Approve and Build`
- `Reject`
- optional later `Edit Metadata`

4. Persist user approval snapshot.
5. Prevent registry integration or build start without approval.

Recommended first release scope:

1. review only,
2. approve or reject only,
3. no deep inline editing yet.

Suggested files:

- `web/templates/module_toolkit.html`
- corresponding JS in that template or extracted toolkit JS
- route handlers for review approval/rejection

Verification:

1. a job stops at `awaiting_review`,
2. approval is required to continue,
3. rejection keeps artifacts available for debugging.

## Phase 5: Build From Normalized Packet

Objective:

- connect normalization output to a richer module build path.

Tasks:

1. Add a builder facade for upload-driven builds.
2. Convert `normalized_packet.json` into `builder_input.json` and `builder_narrative.txt`.
3. Use the upstream builder path as the default rich-generation mode.
4. Ensure the builder gets:

- source-grounded narrative,
- location and plot constraints,
- source-derived NPC and monster hints,
- connectivity hints,
- publication intent.

5. Preserve provenance from normalized packet into generated module artifacts.
6. Keep deterministic emitter fallback available for edge cases if needed.

Architectural preference:

1. Add a dedicated upload-aware builder entrypoint rather than overloading raw `start_build` immediately.
2. Reuse `ModuleBuilder` internally wherever possible.

Suggested files:

- new builder facade module under `web/extensions/` or `core/generators/`
- `web/web_interface.py` integration if socket-based reuse is chosen
- tests for packet-to-builder transformation

Verification:

1. approved upload can start and complete a module build,
2. build stages are visible in toolkit,
3. output quality is richer than deterministic ingest alone.

V2 continuity note:

- This phase should produce the first reusable markdown build contract that `plans/version-2/module-import.md` can later use for scaled import operations.

## Phase 5A: Structural Readiness Gate And Repair Loop

Objective:

- ensure `build_completed` means raw artifacts exist,
- but only advance modules to finishing when they pass a structural readiness gate,
- and repair the most common post-build failures using bounded Python-first remediation with targeted LLM repair only where semantics are missing.

Why this phase exists:

The packet-driven builder can successfully emit a module directory while still leaving the module structurally unready for finishing/publication.

Observed failure classes include:

1. builder/runtime defects in generator code,
2. deterministic output defects that Python can repair safely,
3. semantic/content defects that require a bounded repair prompt against the generated files.

This phase introduces a formal distinction:

1. `build_completed` = raw artifacts were produced,
2. `ready_for_finishing` = the module passed structural validation and remediation,
3. `completed` = finishing + publishability gate passed.

### Proposed Post-Build State Model

Recommended uploader states after approval:

1. `approved_for_build`
2. `building`
3. `build_completed`
4. `validating`
5. `repairing_deterministic`
6. `repairing_semantic`
7. `ready_for_finishing`
8. `finishing`
9. `publishability_audit`
10. `completed`

Recommended fail states:

1. `build_system_failed`
2. `validation_failed_unrepairable`
3. `repair_budget_exhausted`
4. `finishing_failed`
5. `not_publishable`

### Structural Gate Sequence

Immediately after raw packet build:

1. run `core/validation/validate_module_files.py --module <slug>`
2. run `scripts/audit_module_readiness.py --module <slug>`
3. classify findings into repair domains
4. attempt bounded deterministic repair first
5. rerun validation
6. if needed, attempt bounded semantic repair
7. rerun validation
8. only mark `ready_for_finishing` if readiness passes

Architectural rule:

1. the uploader must not enter finisher/publication while readiness is red,
2. validator and readiness audit remain authoritative,
3. the repair loop is bounded and fail-closed.

### Failure Triage Model

All post-build failures should be grouped into three classes.

#### Class A: Builder / Runtime Defects

Definition:

- generator code bug,
- persistence bug,
- invalid helper wiring,
- exception path inside builder/runtime logic.

Examples:

1. undefined helper imports in builder methods,
2. bad `safe_write_json(...)` call shapes,
3. placeholder template strings emitted into final summary files,
4. any uncaught exception that indicates the build system itself is wrong rather than the generated content.

Handling:

1. classify as `build_system_failed`, not ordinary content validation failure,
2. stop remediation loops immediately,
3. surface the failing stack/context in the upload report,
4. require code fix before retry.

Rule:

- never ask an LLM repair loop to compensate for a builder code defect.

#### Class B: Deterministic Output Defects

Definition:

- generated content is structurally wrong,
- but the correction can be derived mechanically from authoritative existing artifacts.

Examples:

1. enum normalization in `party_tracker.json`,
2. missing monster files for referenced monsters,
3. spatial coordinate / direction contradictions,
4. stale or incomplete `module_context.json` indexes,
5. summary fields derivable from existing module artifacts,
6. canonical slug / alias / field-shape cleanup.

Handling:

1. run Python repair helpers first,
2. patch generated module files directly,
3. rerun validation after the deterministic batch,
4. only escalate remaining failures.

Rule:

- every repeatable failure class should be promoted into deterministic repair once observed enough times.

#### Class C: Semantic / Content Defects

Definition:

- module structure exists,
- but the generated content is semantically incomplete or inconsistent in a way Python cannot infer safely.

Examples:

1. plot references NPCs that are not placed anywhere,
2. plot hooks need context-aware enrichment,
3. summary/objective prose contradicts the built module,
4. identity strings require semantic cleanup rather than pure normalization.

Handling:

1. issue a narrow repair prompt scoped to the failing files only,
2. require minimal patch payloads rather than full rebuilds,
3. apply the patch in Python,
4. rerun validation immediately.

Rule:

- semantic repair must be targeted, not a second full module build.

### Deterministic Repair Domains

The first implementation should support these Python-first repair loops.

#### Domain 1: Party / World Conditions Normalization

Repairs:

1. canonical month names,
2. season/weather enum normalization,
3. known-safe default repairs for missing world fields,
4. schema-shape normalization.

Inputs:

- `party_tracker.json`
- schema expectations from `party_schema.json`

Exit condition:

- party schema passes or emits an explicit non-repairable reason.

#### Domain 2: Monster Reference Materialization

Repairs:

1. scan all area monster references,
2. materialize required monster files into `monsters/`,
3. preserve deterministic slug expectations from validator output,
4. rerun monster reference integrity check.

Inputs:

- `areas/*.json`
- existing monster materialization/build helpers

Rule:

- upload-driven builds should not defer unresolved monster references all the way to finisher if the builder has already named the monsters.

#### Domain 3: Spatial Contract Repair

Repairs:

1. rebuild directions from authoritative connectivity and coordinates when possible,
2. rebuild coordinates from authoritative connectivity graph when current coordinates are contradictory,
3. patch map/area parity together,
4. rerun spatial validation.

Inputs:

- `areas/*.json`
- `map_*.json`
- `utils/spatial_contract.py` and validator rules

Escalation rule:

- only escalate when the graph itself is semantically contradictory or under-specified.

#### Domain 4: Context / Summary Regeneration

Repairs:

1. rebuild `module_context.json` from generated areas/plot,
2. rebuild `MODULE_SUMMARY.md` from authoritative generated artifacts,
3. remove literal template placeholders,
4. refresh validation/context counts.

Rule:

- derived artifacts should be regenerated, not semantically improvised.

### Semantic Repair Domains

The first LLM-assisted repair pass should be limited to the following.

#### Domain 5: Missing NPC Placement

Prompt contract:

1. consume validator/context findings,
2. place missing NPCs into existing locations only,
3. preserve plot references,
4. return minimal patch payload.

Validation:

1. NPC must exist in at least one location,
2. `module_context.json` must reconcile afterward,
3. rerun validator.

#### Domain 6: Plot Hook Repair / Enrichment

Prompt contract:

1. update only `plotHooks` fields,
2. reference known plot points or side quests only,
3. preserve area tone,
4. return patch payload only.

Validation:

1. file structure unchanged beyond targeted fields,
2. rerun validation and area integrity checks.

#### Domain 7: Narrative Summary Alignment

Prompt contract:

1. fix module summary/objective prose using authoritative built module data,
2. do not alter maps, areas, or plot structure,
3. rewrite only summary/report text surfaces.

### Repair Budget And Stop Conditions

The uploader should use bounded repair budgets.

Recommended initial limits:

1. deterministic repair passes: max 2
2. semantic repair passes per domain: max 2
3. total repair cycles per job: max 4

Stop immediately when:

1. a Class A builder/runtime defect is detected,
2. the same validation signature repeats without improvement,
3. a semantic repair patch would require broad uncontrolled rewrite,
4. readiness remains red after budget exhaustion.

If budget is exhausted:

1. job state becomes `repair_budget_exhausted`,
2. preserve all artifacts,
3. emit grouped fix guidance for operator/developer follow-up.

### UX And Reporting Requirements

The upload UI should make this pipeline visible.

Recommended UX additions:

1. stage-aware progress bar after build start,
2. explicit stage labels for `building`, `validating`, `repairing_deterministic`, `repairing_semantic`, `ready_for_finishing`,
3. review panel title changes after approval/build completion (for example `Approved`, `Building`, `Build Completed`) instead of lingering `Review Required`,
4. grouped repair report by domain,
5. clear distinction between `build_completed` and `ready_for_finishing`.

Recommended artifact/report outputs:

1. `validation_report.json`
2. `readiness_report.json` or readiness payload snapshot
3. `repair_report.json`
4. semantic patch payloads when used
5. final state summary with grouped fix list

### Verification Targets For This Phase

1. a packet-built module with deterministic-only defects can self-heal to `ready_for_finishing`,
2. a packet-built module with semantic-only defects can self-heal with bounded repair prompts,
3. a packet-built module with builder/runtime defects fails as `build_system_failed`,
4. no job reaches finisher/publication while readiness is red,
5. repeated failures are surfaced with actionable grouped reports.

## Phase 6: Reattach The Existing Finisher and Publication Pipeline

Objective:

- ensure the new public upload path finishes with the same hardened publication stack as developer ingest,
- but only after Phase 5A has marked the module `ready_for_finishing`.

Tasks:

1. Route completed upload builds through the existing finisher.
2. Ensure upload builds execute:

- continuity normalization,
- continuity enrichment,
- semantic authority enrichment,
- monster materialization,
- schema validation,
- registry verification,
- media extraction,
- media handles,
- portrait prewarm,
- sidecar persistence,
- publication/readiness reporting.

3. Preserve fail-closed semantics on validation and registry stages.
4. Preserve fail-open degraded semantics for non-core media stages.
5. Preserve continuity-qualified outputs so later v2 world-narrative and Titan plans can consume module-level signals without this uploader owning those interpreted-state systems.
6. Treat `ready_status=pass` as the minimum gate for entering finishing.
7. Treat `publishable_status=pass` as the final gate for registry integration.

Suggested files:

- `web/extensions/toolkit_module_finisher.py`
- `scripts/homebrew_ingest_dev.py` refactor points if shared code extraction is needed
- sidecar audit tests

Verification:

1. upload-built modules produce the same finishing artifacts as developer ingest,
2. sidecar/report payloads remain consistent,
3. registry integration happens only after approval and successful finishing.
4. modules that fail readiness never enter the finisher.

## Phase 7: Persist and Expose Rebuildable Artifacts

Objective:

- make the upload path transparent, debuggable, and resumable.

Tasks:

1. Expose artifact links or summaries in the job UI.
2. Store normalized packet, review snapshot, build input, and final report permanently until explicit cleanup.
3. Add retry-from-packet capability:

- rerun build without rerunning normalization,
- rerun finisher without rerunning build when appropriate.

4. Add cleanup policy for abandoned failed uploads.

Suggested files:

- upload route layer,
- module toolkit frontend,
- optional cleanup helper script.

Verification:

1. build can resume from packet,
2. artifacts survive restarts,
3. failed uploads are inspectable.

## Phase 8: Corpus-Based Quality Gate

Objective:

- use the real Homebrewery corpus as the acceptance suite for this feature.

Fixture policy:

1. the canonical acceptance corpus must use tracked in-repo markdown fixtures,
2. fixture names may mirror representative Homebrewery adventures, but must not depend on private developer folders,
3. optional extended corpus runs may accept operator-supplied external paths, but no default external path may be hardcoded.

Tasks:

1. Add normalization snapshot tests using tracked representative sources.
2. Add end-to-end upload tests where feasible.
3. Add publication parity checks between developer ingest and public upload for representative modules.
4. Add a golden-path smoke script for manual QA.

Verification goals:

1. no hard preflight stop for readable Homebrewery adventure markdown,
2. review packet generated successfully,
3. build completes or quarantines with actionable report,
4. publish-ready modules can reach registry after approval.

## Detailed Workstreams

## Workstream A: Shared Contracts

Deliverables:

1. normalized packet contract,
2. review snapshot contract,
3. builder input contract,
4. job stage contract,
5. sidecar parity contract for upload builds.

Reason:

Without explicit contracts, the upload path will fragment again between builder logic, finisher logic, and UI state.

## Workstream B: Shared Services Extraction

Deliverables:

1. shared normalization service,
2. shared artifact workspace helper,
3. shared build-from-packet entrypoint,
4. shared finishing adapter.

Reason:

The public upload path should not duplicate the dev pipeline; it should compose it.

## Workstream C: UI Completion

Deliverables:

1. upload stage visualization,
2. review UI,
3. final build report UI,
4. artifact visibility,
5. retry/resume buttons where safe.
6. structural readiness / repair progress visualization.

Reason:

This is the first truly public-facing path for player-authored adventures. It must be understandable, not just functional.

## Workstream D: Publication Safety

Deliverables:

1. mandatory review enforcement,
2. registry integration guard after approval only,
3. quarantine reporting,
4. resumable debug path from persisted packet.
5. fail-closed separation between raw build success and readiness/publication success.

Reason:

Upload quality will vary wildly. Safety and visibility are mandatory.

## Suggested File Touchpoints

### Likely New Files

1. `plans/module-uploader.md`
2. prompt file for Homebrew upload normalization
3. normalization service module
4. packet schema or contract module
5. upload artifact workspace helper
6. tests for normalized packet generation and review flow

### Likely Modified Files

1. `web/routes/toolkit_homebrew_routes.py`
2. `web/templates/module_toolkit.html`
3. `scripts/homebrew_preflight.py`
4. `scripts/homebrew_ingest_dev.py`
5. `web/extensions/toolkit_module_finisher.py`
6. `web/web_interface.py` or a new upload-build facade depending on execution design
7. route and pipeline tests in `scripts/`

## Risks

### Risk 1: LLM Normalization Hallucinates Structure

Mitigation:

1. normalization prompt must separate facts from assumptions,
2. review stage makes inferred structure visible,
3. Python validation remains authoritative,
4. packet retains provenance and warnings.

### Risk 2: Public Upload Becomes Too Slow

Mitigation:

1. asynchronous jobs only,
2. persisted artifacts allow resume,
3. reuse normalized packet for rebuild,
4. keep deterministic fast-path for already well-structured sources.

### Risk 3: Upload and Dev Pipelines Diverge Again

Mitigation:

1. extract shared services,
2. share finisher/reporting contracts,
3. add parity tests,
4. treat upload as a front-end orchestration layer over shared backend logic.

### Risk 4: Builder Overwrites Source Fidelity With Excessive Creativity

Mitigation:

1. normalize source packet first,
2. use packet as constraint context for builder,
3. preserve reviewable assumptions,
4. keep publication audit as final authority.

### Risk 5: Review UI Becomes Too Complex For First Release

Mitigation:

1. first release uses approve/reject only,
2. no deep editing in v1,
3. editable metadata can be a follow-up.

### Risk 6: Repair Loops Hide Real Builder Bugs

Mitigation:

1. classify builder/runtime defects separately from content defects,
2. stop immediately on generator code failures,
3. never use semantic repair to paper over Python/runtime bugs,
4. surface builder defects as uploader system failures with preserved artifacts.

### Risk 7: Unbounded Repair Loops Increase Latency Without Convergence

Mitigation:

1. use domain-grouped repair passes instead of one-error-at-a-time retries,
2. cap deterministic and semantic repair budgets,
3. stop when the validation signature repeats without improvement,
4. preserve grouped fix reports for manual follow-up.

## Acceptance Criteria

The uploader is complete when all of the following are true.

1. A readable Homebrewery markdown upload no longer fails only because it lacks `author`, `description`, or room-based headings.
2. Upload produces a persisted normalized packet.
3. Toolkit shows a mandatory review screen before build/publish.
4. Approved uploads can trigger a rich module build based on the normalized packet.
5. Raw build success is distinct from structural readiness and final completion.
6. Build output reaches `ready_for_finishing` only after post-build validation/remediation passes.
7. Only structurally ready modules go through the existing continuity, semantic, validation, and publication pipeline.
8. Registry integration occurs only after review, successful finishing, and publishability success.
9. Failed or quarantined uploads preserve artifacts for inspection and retry.
10. At least the following real files are usable as corpus fixtures:

- `The Pumpkin King.md`
- `The Garden of Demons.md`
- `A Pottsfield Burial.md`
- `Murder at the Drowning Lass.md`

11. Public upload path produces gameplay-ready modules with quality meaningfully closer to dev/OpenCode-led ingest than to the current regex-gated importer.
12. The uploader exposes enough stage/report detail that a facilitator or developer can distinguish raw build success, readiness failure, repair-in-progress, and publication failure without inspecting stdout.

## Recommended Execution Order

1. Phase 0: contracts and workspace
2. Phase 1: soften preflight into routing
3. Phase 2: implement normalization backend
4. Phase 3: wire upload job orchestration
5. Phase 4: add mandatory review UI
6. Phase 5: build from normalized packet
7. Phase 5A: structural readiness gate and repair loop
8. Phase 6: reattach finisher/publication pipeline
9. Phase 7: artifact persistence and rebuild support
10. Phase 8: corpus-based validation and rollout

## Final Position

This plan intentionally treats public upload as the convergence point of the last three months of work.

It does not replace the upstream builder.
It does not discard the deterministic ingest hardening.
It does not ask regex to do the LLM's job.

Instead it combines the strengths of all three paths:

1. upstream builder for rich, playable generation,
2. developer ingest workflow for staged interpretation and artifact discipline,
3. public upload GUI as the safe, reviewable, player-facing execution surface.

That is the correct final builder architecture for NEQ's public Homebrew upload path.

It is also the correct handoff point into v2:

1. this uploader completes the interactive reviewed import lane,
2. `plans/version-2/module-import.md` scales that lane into bulk canonical import,
3. `plans/version-2/world-narrative.md` later builds the source-anonymous narrative web from literary ingestion under `user_uploads/text/`,
4. `plans/version-2/titan-integration.md` later consumes those interpreted narrative structures as proposal-only world pressure.
