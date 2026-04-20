# module-semantic-publication-audit Specification Delta

## ADDED Requirements

### Requirement: Explicitly deferred semantic ambiguity SHALL be classified separately from structural contradiction
The semantic publication audit SHALL classify explicitly deferred Phase 2 ambiguity as a separate semantic debt class when deterministic closure is intentionally out of scope for the current structural slice.

#### Scenario: Bounded deferred ambiguity is reported as Phase 2 debt
- **GIVEN** a player-facing destination phrase remains unresolved
- **AND** canonical destination authority for the related location is otherwise present
- **AND** project policy explicitly defers that contraction or ambiguity to a later LLM-assisted phase
- **WHEN** the semantic publication audit emits its result
- **THEN** it SHALL classify the phrase as deferred ambiguity debt or equivalent explicit Phase 2 semantic debt
- **AND** SHALL NOT report the phrase only as an undifferentiated structural contradiction
