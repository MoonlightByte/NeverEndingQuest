# toolkit-module-postbuild-finishing Specification

## Purpose
TBD - created by archiving change toolkit-module-build-publication-parity. Update Purpose after archive.
## Requirements
### Requirement: Toolkit builds run a shared post-build finishing pass
Toolkit-generated module directories MUST run a post-build finishing pass after raw generation succeeds so they do not bypass the quality stages already used by the ingest workflow.

#### Scenario: Same-run toolkit publishability can validate toolkit provenance
- **GIVEN** a toolkit finisher run is evaluating readiness or publishability with `source="toolkit"`
- **WHEN** toolkit provenance is required for that evaluation
- **THEN** the finisher MUST satisfy the provenance contract during the same run
- **AND** MUST NOT fail solely because the final toolkit report has not yet been written at the end of the run.

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

