# module-publishability-reporting Specification

## Purpose
TBD - created by archiving change module-publication-publishable-gate. Update Purpose after archive.
## Requirements
### Requirement: CLI and toolkit reporting SHALL expose ready vs publishable clearly
Publication-facing reporting SHALL show both structural readiness and semantic publishability explicitly.

#### Scenario: CLI output includes both statuses
- **GIVEN** a publishability audit result
- **WHEN** CLI JSON or text output is emitted
- **THEN** it SHALL include explicit `ready_status` and `publishable_status` fields or equivalents

#### Scenario: Toolkit finisher report includes both statuses
- **GIVEN** a toolkit module finishing run
- **WHEN** the post-build report is written
- **THEN** the report SHALL expose whether the module is structurally ready and whether it is publishable

#### Scenario: Reporting does not collapse publishability into readiness
- **GIVEN** a module is ready but not publishable
- **WHEN** report surfaces are rendered
- **THEN** they SHALL NOT report a single ambiguous success state
- **AND** SHALL preserve the distinction clearly

### Requirement: Readiness and publishability reporting SHALL consume normalized gameplay findings
When gameplay audit output provides structured findings under a nested payload shape, readiness and publishability reporting SHALL consume those findings accurately so structural media debt summaries remain correct.

#### Scenario: Nested gameplay findings produce correct toolkit media policy summary
- **GIVEN** gameplay audit output includes structured monster-media findings under a nested `target` object
- **WHEN** readiness reporting computes toolkit media policy summary fields
- **THEN** `structural_media_debt_count` and related slug lists SHALL reflect the actual structured findings
- **AND** SHALL NOT incorrectly report zero when structural findings are present

#### Scenario: Publishability receives corrected readiness media debt metadata
- **GIVEN** readiness reporting has normalized gameplay findings correctly
- **WHEN** publishability output is emitted
- **THEN** the publishability payload SHALL preserve the corrected toolkit media policy metadata
- **AND** SHALL remain consistent with the gameplay findings that produced it

### Requirement: Toolkit reporting SHALL preserve successful build plus media handoff distinction
Publication-facing toolkit reporting SHALL distinguish a successful toolkit build that still requires manual media generation from a true build failure.

#### Scenario: Toolkit report shows build success and media handoff
- **GIVEN** a toolkit module build succeeded structurally
- **AND** manual module media generation remains outstanding
- **WHEN** toolkit reporting is emitted
- **THEN** it SHALL preserve the successful build outcome
- **AND** SHALL expose the outstanding media debt explicitly
- **AND** SHALL name `Module Builder -> Module Media Generator` as the next step

### Requirement: Canary reporting SHALL distinguish reconciliation advancement from unchanged residual debt

Module canary reporting SHALL show whether live blocker reconciliation materially reduced validator failures and which remaining failures are still repair-engine mismatches versus authored debt.

#### Scenario: Reconciliation report shows no advancement

- **WHEN** a blocker-reconciliation canary rerun still reports the same total failure count and residual classes
- **THEN** the persisted report SHALL state that advancement did not occur
- **AND** SHALL preserve per-blocker classification for repair-engine gaps and author/content debt

### Requirement: Blocker-resolution reporting SHALL expose measurable canary advancement

Residual blocker resolution reporting SHALL expose whether the latest canary materially improved the live validator state relative to the previous canary artifact.

#### Scenario: Canary comparison shows no advancement

- **WHEN** previous and current canary runs have the same live validator failure count and no residual classes were removed
- **THEN** reporting SHALL mark that blocker-resolution did not advance beyond the previous canary
- **AND** SHALL preserve added or reclassified residual classes separately from resolved classes

#### Scenario: Canary comparison shows advancement

- **WHEN** the current canary removes one or more prior residual classes or reduces total live validator failures
- **THEN** reporting SHALL mark blocker-resolution as advanced
- **AND** SHALL expose the removed classes and failure-count delta explicitly

### Requirement: Reporting SHALL distinguish convergence instrumentation from residual closure progress

Toolkit and operations-facing report artifacts SHALL make it clear whether a run only classified residual blockers or actually reduced them.

#### Scenario: Residual closure canary persists advancement state

- **GIVEN** a residual-closure canary run for a module
- **WHEN** the canary report is written
- **THEN** it SHALL expose whether the module advanced beyond the previous residual blocker set
- **AND** SHALL include the current residual blocker classes and category counts

#### Scenario: Reporting distinguishes unresolved repair gap from author debt

- **WHEN** residual blockers remain after closure attempts
- **THEN** report surfaces SHALL distinguish between unresolved repair-engine coverage gaps and author/content debt where safe repair was not possible

### Requirement: Reporting SHALL surface remediation classes for non-publishable outcomes
CLI and toolkit reporting SHALL expose remediation classes so operators can see whether a failure is caused by provenance, semantic blocking contradictions, warning-only semantic degradation, tooling debt, or real content remediation.

#### Scenario: Toolkit report includes remediation categories
- **GIVEN** a toolkit finishing run completes with mixed outcomes
- **WHEN** the toolkit report is written
- **THEN** the report SHALL include enough structured detail to distinguish remediation categories
- **AND** SHALL keep warning-only semantic degradation visible without collapsing it into generic failure text.

### Requirement: Reporting SHALL expose readiness convergence outcomes distinctly

Readiness and publishability reports SHALL surface convergence outcomes separately from final ready/publishable status.

#### Scenario: Fixed-point non-convergence is reported distinctly
- **GIVEN** a readiness workflow stops because the blocker signature is unchanged across consecutive passes
- **WHEN** JSON reporting is emitted
- **THEN** the report SHALL include a distinct convergence outcome such as `fixed_point_non_convergence` or equivalent
- **AND** it SHALL NOT collapse that state into a generic readiness failure without classification

#### Scenario: Residual blocker classes are visible in report artifacts
- **GIVEN** a canary or toolkit readiness run ends with unresolved blockers
- **WHEN** the report artifact is written
- **THEN** the artifact SHALL include the residual blocker classes
- **AND** operators SHALL be able to distinguish repair-coverage gaps from content debt

### Requirement: Toolkit reporting SHALL expose structured semantic blocker detail for remediation
When publication-facing toolkit reporting includes semantic blocker findings, it SHALL expose enough structured detail for operators to identify the blocker class and authored source without reading raw JSON only.

#### Scenario: Structured blocking findings reach toolkit reporting
- **GIVEN** publishability reporting contains `blocking_findings` for semantic blockers
- **WHEN** toolkit reporting is emitted or rendered
- **THEN** it SHALL surface the blocker class and message
- **AND** SHALL preserve relevant context such as unresolved phrase, candidate location IDs, or authored source when that context is present.

#### Scenario: Structured findings absent falls back safely
- **GIVEN** publishability reporting contains semantic blockers but no structured `blocking_findings`
- **WHEN** toolkit reporting is emitted or rendered
- **THEN** it SHALL fall back to `blocking_errors`
- **AND** SHALL still present a semantic remediation path rather than raw JSON only.

### Requirement: Publishability reporting SHALL distinguish normalized short-form resolution from true semantic blockers
When semantic-authority enrichment deterministically resolves a short-form destination phrase through an already-resolved authored alias, publication-facing reporting SHALL not continue to classify that phrase as an unresolved semantic blocker.

#### Scenario: Normalized short-form does not remain a blocker
- **GIVEN** semantic-authority enrichment has deterministically normalized a short-form destination phrase to one canonical location
- **WHEN** publishability reporting is emitted
- **THEN** that phrase SHALL NOT remain in blocking semantic destination findings
- **AND** reporting SHOULD preserve structured normalization context when available.

#### Scenario: Ambiguous short-form remains a structured blocker
- **GIVEN** a short-form destination phrase still has multiple plausible canonical matches after deterministic normalization
- **WHEN** publishability reporting is emitted
- **THEN** the phrase SHALL remain a semantic publishability blocker
- **AND** reporting SHALL preserve blocker class, phrase, and relevant candidate context when available.

