## MODIFIED Requirements

### Requirement: Low-risk deterministic-safe turns SHALL have an eligible skip path

The validation pipeline SHALL support skipping or narrowing LLM validation for conservative low-risk turns only after authoritative deterministic checks have run and only when no unresolved high-risk or contested-truth condition remains.

#### Scenario: Reconciled soft-state only turn
- **WHEN** the response contains only deterministic or reconciled travel or NPC soft-state actions
- **AND** no unreconciled high-risk action remains
- **THEN** the pipeline MAY skip or narrow the LLM validator path using deterministic routing rules

#### Scenario: Mixed reconciled and unreconciled turn still reviewed
- **WHEN** a response contains both reconciled soft-state updates and unrelated unreconciled high-risk actions
- **THEN** the pipeline SHALL continue to use the LLM validator for the unreconciled portion

#### Scenario: Possession contradiction turn does not qualify for narration-only skip
- **WHEN** the triggering turn explicitly questions or contradicts the possession of a tracked item
- **THEN** the pipeline SHALL run authoritative inventory checks before deciding whether the turn is eligible for low-risk narration-only skip

#### Scenario: Authoritative transition failure does not qualify for narration-only skip
- **WHEN** a turn includes a failed `transitionLocation` attempt or other authoritative movement failure
- **THEN** the pipeline SHALL NOT downgrade that turn into a low-risk narration-only outcome