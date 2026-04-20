# module-semantic-publication-audit Specification

## Purpose
TBD - created by archiving change module-publication-semantic-audit. Update Purpose after archive.
## Requirements
### Requirement: Semantic publication audit SHALL fail publication-unsafe destination and NPC contradictions
The standalone semantic publication audit SHALL classify publication-unsafe semantic contradictions as blocking failures while preserving weaker substrate issues as warnings.

#### Scenario: Unresolved authored destination phrase fails audit
- **GIVEN** a destination phrase appears in authored module semantics
- **AND** the phrase remains unresolved in the semantic-authority payload
- **WHEN** the semantic publication audit runs
- **THEN** the audit SHALL fail
- **AND** SHALL surface the phrase and provenance as a blocking finding

#### Scenario: Ambiguous authored destination phrase fails audit
- **GIVEN** a destination phrase appears in authored module semantics
- **AND** the phrase resolves to multiple candidate locations
- **WHEN** the semantic publication audit runs
- **THEN** the audit SHALL fail
- **AND** SHALL surface the candidate targets and provenance as a blocking finding

#### Scenario: Missing NPC authority fails audit for authored visible or revealable NPCs
- **GIVEN** an authored NPC is visible in-scene or revealable through module semantics
- **AND** the semantic-authority payload lacks a deterministic scene-authority path for that NPC
- **WHEN** the semantic publication audit runs
- **THEN** the audit SHALL fail
- **AND** SHALL surface the canonical NPC identity and provenance as a blocking finding

#### Scenario: Standalone audit remains separate from repo-wide publishable gating
- **GIVEN** the semantic publication audit returns blocking failures
- **WHEN** this change is implemented before the later publishable-gate slice
- **THEN** the audit SHALL remain a standalone report surface
- **AND** SHALL NOT by itself redefine repo-wide `ready` versus `publishable` release policy

### Requirement: Explicitly deferred semantic ambiguity SHALL be classified separately from structural contradiction
The semantic publication audit SHALL classify explicitly deferred Phase 2 ambiguity as a separate semantic debt class when deterministic closure is intentionally out of scope for the current structural slice.

#### Scenario: Bounded deferred ambiguity is reported as Phase 2 debt
- **GIVEN** a player-facing destination phrase remains unresolved
- **AND** canonical destination authority for the related location is otherwise present
- **AND** project policy explicitly defers that contraction or ambiguity to a later LLM-assisted phase
- **WHEN** the semantic publication audit emits its result
- **THEN** it SHALL classify the phrase as deferred ambiguity debt or equivalent explicit Phase 2 semantic debt
- **AND** SHALL NOT report the phrase only as an undifferentiated structural contradiction

### Requirement: Semantic audit SHALL distinguish blocking contradictions from warning-only or tooling-debt degradation
The semantic publication audit SHALL preserve a strict distinction between blocking semantic contradictions and degradation caused only by warnings or tooling fixture debt.

#### Scenario: Warning-only semantic degradation remains non-blocking to contradiction classification
- **GIVEN** the semantic audit produces warnings only
- **AND** no blocking semantic findings are present
- **WHEN** the audit result is emitted
- **THEN** it SHALL report a non-blocking degraded state
- **AND** SHALL NOT classify the module as having semantic blocking contradictions.

