# module-semantic-authority-enrichment Specification Delta

## ADDED Requirements

### Requirement: Semantic authority SHALL normalize uniquely anchored short-form destination phrases
When a player-facing destination phrase remains unresolved, semantic-authority enrichment SHALL collapse it to canonical destination authority only when one already-resolved authored alias in the same module provides a deterministic unique anchor.

#### Scenario: Short-form destination collapses to one resolved authored alias
- **GIVEN** semantic-authority enrichment has already resolved `silent oath chamber` to location `H03`
- **AND** the same module still contains unresolved player-facing phrase `oath chamber`
- **WHEN** short-form destination normalization runs
- **THEN** the phrase SHALL collapse to `H03`
- **AND** the payload SHALL preserve that the collapse was derived from the resolved authored alias rather than direct authored identity.

#### Scenario: Short-form destination remains unresolved when anchor is ambiguous
- **GIVEN** a module contains two already-resolved authored aliases that both plausibly match the same unresolved short-form phrase
- **WHEN** short-form destination normalization runs
- **THEN** the phrase SHALL remain unresolved
- **AND** SHALL preserve ambiguity diagnostics rather than forcing one canonical destination.

#### Scenario: Prose-only phrase without resolved anchor remains outside canonical authority
- **GIVEN** an unresolved player-facing phrase has no already-resolved authored alias that provides a deterministic anchor
- **WHEN** short-form destination normalization runs
- **THEN** enrichment SHALL NOT promote that phrase into canonical destination authority
- **AND** MAY preserve it as unresolved or diagnostic output according to existing enrichment rules.
