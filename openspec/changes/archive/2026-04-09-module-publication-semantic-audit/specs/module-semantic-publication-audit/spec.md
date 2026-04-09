## ADDED Requirements

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
