## MODIFIED Requirements

### Requirement: Low-risk deterministic-safe turns SHALL have an eligible skip path

The validation pipeline SHALL support skipping or narrowing LLM validation for conservative low-risk turns when deterministic checks pass, including reconcile-first soft-state turns that contain no remaining unreconciled high-risk behavior.

#### Scenario: Reconciled soft-state only turn
- **WHEN** the response contains only deterministic/reconciled travel or NPC soft-state actions
- **AND** no unreconciled high-risk action remains
- **THEN** the pipeline MAY skip or narrow the LLM validator path using deterministic routing rules

#### Scenario: Mixed reconciled and unreconciled turn still reviewed
- **WHEN** a response contains both reconciled soft-state updates and unrelated unreconciled high-risk actions
- **THEN** the pipeline SHALL continue to use the LLM validator for the unreconciled portion
