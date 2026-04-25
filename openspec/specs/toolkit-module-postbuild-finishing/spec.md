# toolkit-module-postbuild-finishing Specification

## Purpose
TBD - created by archiving change toolkit-module-build-publication-parity. Update Purpose after archive.
## Requirements
### Requirement: Toolkit builds run a shared post-build finishing pass
Toolkit-generated module directories MUST run a shared post-build finishing pass after raw generation succeeds so they do not bypass the quality stages already used by the ingest workflow.

#### Scenario: Successful raw build enters finishing pass
- **WHEN** `ModuleBuilder.build_module(...)` completes successfully for a toolkit build
- **THEN** the toolkit MUST run a post-build finishing pass before declaring the build fully complete

#### Scenario: Finishing pass reuses existing quality stages
- **WHEN** the toolkit runs its post-build finishing pass
- **THEN** the pass MUST include continuity normalization, semantic authority enrichment, registry verification, monster materialization, and publication evaluation or their shared wrappers
- **AND** MUST NOT require a duplicate reimplementation of those stages inside the toolkit transport layer

#### Scenario: Monster materialization stage reports direct helper outcome
- **WHEN** the finishing pass executes monster materialization
- **THEN** the stage result MUST come from direct helper execution outcome
- **AND** MUST NOT depend on parsing subprocess stderr/stdout to infer success or failure

### Requirement: Finishing parity stops short of full semantic publication compliance
The first builder parity slice MUST improve publication readiness without claiming full semantic publication compliance.

#### Scenario: Full publication semantics remain out of scope
- **WHEN** a toolkit build completes its parity finishing pass
- **THEN** the result MUST NOT imply that probe-based semantic publication checks, spatial grounding, or tactical-grid generation have been completed unless a later change explicitly adds them.

### Requirement: Toolkit builder workflow SHALL sequence semantic remediation after deterministic post-build classification
When toolkit post-build reporting has been stabilized for media handoff, workflow ordering, payload normalization, and mixed-failure classification, remaining semantic publishability blockers SHALL be treated as an explicit builder remediation stage rather than collapsed into media handoff or hidden inside unrelated reporting defects.

#### Scenario: Unresolved destination alias enters semantic remediation lane
- **GIVEN** toolkit finishing reports an unresolved destination alias or similar semantic blocker after deterministic reporting boundaries are already correct
- **WHEN** the builder workflow determines the next remediation step
- **THEN** it SHALL treat that blocker as a semantic remediation task
- **AND** SHALL NOT present media-only handoff as sufficient remediation
- **AND** SHALL preserve reviewable builder guidance for the later repair slice

### Requirement: Toolkit finisher SHALL preserve failed semantics for mixed publishability blockers
When post-build reporting contains missing media debt together with true semantic or content blockers, toolkit finishing SHALL preserve failed semantics and SHALL NOT reinterpret the run as a successful media-only handoff.

#### Scenario: Mixed media and semantic blockers remain failed
- **GIVEN** toolkit finishing detects missing module media debt
- **AND** publishability reporting also contains a non-media semantic or content blocker
- **WHEN** the finisher emits its result payload and report
- **THEN** the overall outcome SHALL remain failed
- **AND** SHALL preserve visibility into the media debt details
- **AND** SHALL NOT emit success-with-media-handoff semantics

#### Scenario: Pure semantic blockers remain failed without media handoff
- **GIVEN** toolkit finishing detects semantic or content blockers without a media-only handoff case
- **WHEN** the finisher emits its result payload and report
- **THEN** the overall outcome SHALL remain failed
- **AND** SHALL NOT direct the operator to media handoff as if it were sufficient remediation

### Requirement: Toolkit finisher SHALL distinguish media-only debt from build failure
Toolkit finishing SHALL not report an overall failed build when structural build stages are green and the only remaining issue is missing module monster or NPC media that must be generated manually.

#### Scenario: Toolkit build completes with explicit media handoff
- **GIVEN** a toolkit finishing run has completed structural stages successfully
- **AND** required module-local monster or NPC media is still missing
- **AND** manual media generation remains the intended workflow
- **WHEN** the finisher emits its result payload and report
- **THEN** it SHALL report a successful build outcome with explicit post-build media handoff semantics
- **AND** SHALL preserve the missing media debt details
- **AND** SHALL direct the operator to `Module Builder -> Module Media Generator`

#### Scenario: Structural failures still fail
- **GIVEN** a toolkit finishing run has a real structural or finishing failure unrelated to media-only handoff debt
- **WHEN** the finisher emits its result payload and report
- **THEN** it SHALL preserve failed build semantics
- **AND** SHALL NOT reinterpret that outcome as success-with-handoff

### Requirement: Toolkit finishing SHALL report explicit monster-media policy outcome
Toolkit finishing SHALL expose the monster-media outcome for combat-valid structured monsters in a way that distinguishes reuse, generation, provider-disabled non-generation, and attempted-but-unresolved media debt.

#### Scenario: Toolkit run reports provider-disabled missing monster media explicitly
- **GIVEN** a toolkit finisher run evaluates a module with combat-valid structured monsters
- **AND** required module-local monster base media is absent
- **AND** provider-backed monster generation is disabled for that run
- **WHEN** the finisher emits its stage/report payload
- **THEN** the report SHALL identify the monster-media outcome as provider-disabled unresolved media debt or equivalent explicit policy-aware state
- **AND** SHALL NOT imply that provider generation already ran successfully in that same toolkit path
- **AND** SHALL point to the existing toolkit monster-image generation workflow as the manual remediation path

### Requirement: Toolkit finishing SHALL surface semantic remediation as a distinct post-build lane
When toolkit finishing ends with semantic publishability blockers, the builder workflow SHALL surface those blockers as a distinct semantic remediation lane rather than relying on raw JSON output or generic failure text alone.

#### Scenario: Semantic-only blockers render semantic remediation guidance
- **GIVEN** toolkit finishing reports semantic publishability blockers without media-only handoff eligibility
- **WHEN** the builder workflow renders the post-build result
- **THEN** it SHALL present a semantic remediation section
- **AND** SHALL include structured blocker detail when available
- **AND** SHALL keep the overall outcome failed.

#### Scenario: Mixed media and semantic blockers render distinct remediation lanes
- **GIVEN** toolkit finishing reports both structured media debt and semantic publishability blockers
- **WHEN** the builder workflow renders the post-build result
- **THEN** it SHALL preserve failed semantics
- **AND** SHALL distinguish media debt from semantic remediation detail
- **AND** SHALL NOT reinterpret the result as media-only handoff.

### Requirement: Toolkit finishing SHALL declare source-aware readiness and publishability outcomes
Toolkit finishing MUST pass toolkit source identity into readiness and publishability evaluation so final reports reflect the correct provenance contract.

#### Scenario: Toolkit finisher evaluates publishability as toolkit source
- **WHEN** the toolkit finisher invokes readiness or publishability evaluation
- **THEN** it MUST declare the module source as toolkit
- **AND** the final report MUST preserve stage outcomes using toolkit-source semantics

### Requirement: Toolkit finisher SHALL allow media handoff after deterministic short-form semantic normalization
When toolkit finishing receives semantic publishability output where short-form destination phrases have been deterministically normalized through already-resolved authored aliases, the finisher SHALL treat those phrases as cleared semantic debt while preserving the existing mixed-failure contract for truly unresolved blockers.

#### Scenario: Normalized short-form alias no longer forces mixed failure
- **GIVEN** toolkit finishing evaluates a module with manual media debt
- **AND** the module previously carried unresolved short-form destination phrases that were deterministically normalized before finisher classification
- **AND** no other true semantic blockers remain
- **WHEN** the finisher emits its result payload and report
- **THEN** it SHALL NOT preserve mixed-failure semantics solely because of the normalized short-form phrases
- **AND** MAY emit the existing success-with-media-handoff outcome if the remaining debt is media-only.

#### Scenario: True semantic blockers still keep mixed failure intact
- **GIVEN** toolkit finishing evaluates a module with media debt
- **AND** publishability output still contains true unresolved semantic blockers after deterministic short-form normalization has run
- **WHEN** the finisher emits its result payload and report
- **THEN** the overall outcome SHALL remain failed
- **AND** SHALL preserve the distinct media and semantic remediation lanes.

