## ADDED Requirements

### Requirement: Player-facing phrase collision blockers SHALL be deterministic and bounded
Semantic publication blockers for phrase collisions SHALL target player-facing natural-language drift risk rather than every possible alias overlap.

#### Scenario: Player-facing phrase collision blocks audit
- **GIVEN** a phrase that a player would plausibly use to travel or refer to a destination is associated with multiple valid locations
- **AND** authored semantics do not resolve the phrase to one canonical target
- **WHEN** the semantic publication audit runs
- **THEN** the audit SHALL fail
- **AND** SHALL report the colliding phrase and candidate targets as a blocking finding

#### Scenario: Non-player-facing substrate duplication stays warning-only
- **GIVEN** substrate metadata contains a duplicated or weak alias that is not observed in authored destination semantics and is not treated as a likely player-facing phrase
- **WHEN** the semantic publication audit runs
- **THEN** the audit SHALL NOT fail on that duplication alone
- **AND** MAY report it as a warning or diagnostic instead

#### Scenario: Structured output separates blocker classes from warnings
- **GIVEN** the semantic publication audit returns both publication blockers and weaker diagnostics
- **WHEN** structured output is emitted
- **THEN** blocker findings SHALL be represented in explicit blocking output fields
- **AND** weaker diagnostics SHALL remain in non-blocking warning fields
