# module-publishability-reporting Specification Delta

## ADDED Requirements

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
