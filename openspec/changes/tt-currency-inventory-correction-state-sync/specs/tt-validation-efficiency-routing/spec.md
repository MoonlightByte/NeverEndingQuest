## MODIFIED Requirements

### Requirement: Low-risk deterministic-safe turns SHALL have an eligible skip path

The validation pipeline SHALL support skipping or narrowing LLM validation for conservative low-risk turns only after authoritative deterministic checks have run and only when no unresolved high-risk, contested-truth, or explicit bookkeeping-correction condition remains.

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

#### Scenario: Explicit bookkeeping correction turn does not qualify for narration-only skip
- **WHEN** the triggering turn or candidate response explicitly claims that currency or inventory bookkeeping has already been corrected, reclassified, paid, refunded, gained, or removed
- **THEN** the pipeline SHALL NOT classify that turn as eligible for `narration_only` skip until matching state-mutation action coverage is present

#### Scenario: Authoritative transition failure does not qualify for narration-only skip
- **WHEN** a turn includes a failed `transitionLocation` attempt or other authoritative movement failure
- **THEN** the pipeline SHALL NOT downgrade that turn into a low-risk narration-only outcome

### Requirement: Narration-only skip SHALL occur only after deterministic recovery opportunities are exhausted

The validation-efficiency routing path SHALL NOT finalize a turn as low-risk narration-only until deterministic inventory and location recovery hooks have had an opportunity to reconcile uniquely resolvable state drift and until explicit bookkeeping-correction guards report no missing committed state mutation.

#### Scenario: Candidate response is narration-only but transfer/location recovery is still possible
- **GIVEN** the candidate response has `actions: []`
- **AND** the triggering turn or recent transcript contains uniquely resolvable inventory-transfer or scene-location recovery evidence
- **WHEN** validation routing evaluates whether to skip the LLM validator as `narration_only`
- **THEN** deterministic recovery SHALL run first
- **AND** the low-risk skip decision SHALL occur only after that recovery path reports no remaining applicable reconciliation

#### Scenario: Candidate response is narration-only but claims a committed bookkeeping correction
- **GIVEN** the candidate response has `actions: []`
- **AND** the triggering turn or candidate narration explicitly claims that a currency or inventory correction has already been applied
- **WHEN** validation routing evaluates the turn
- **THEN** runtime SHALL reject `narration_only` skip eligibility for that turn

#### Scenario: Pure narration-only turn with no recoverable state drift still skips normally
- **GIVEN** the candidate response has `actions: []`
- **AND** deterministic recovery finds no uniquely resolvable inventory or location repair opportunity
- **AND** no explicit bookkeeping correction claim is present
- **WHEN** validation routing evaluates the turn
- **THEN** runtime MAY still skip the LLM validator as low-risk narration-only
