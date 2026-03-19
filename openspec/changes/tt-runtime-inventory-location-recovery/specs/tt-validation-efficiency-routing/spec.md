## ADDED Requirements

### Requirement: Narration-only skip SHALL occur only after deterministic recovery opportunities are exhausted

The validation-efficiency routing path SHALL NOT finalize a turn as low-risk narration-only until deterministic inventory and location recovery hooks have had an opportunity to reconcile uniquely resolvable state drift.

#### Scenario: Candidate response is narration-only but transfer/location recovery is still possible
- **GIVEN** the candidate response has `actions: []`
- **AND** the triggering turn or recent transcript contains uniquely resolvable inventory-transfer or scene-location recovery evidence
- **WHEN** validation routing evaluates whether to skip the LLM validator as `narration_only`
- **THEN** deterministic recovery SHALL run first
- **AND** the low-risk skip decision SHALL occur only after that recovery path reports no remaining applicable reconciliation

#### Scenario: Pure narration-only turn with no recoverable state drift still skips normally
- **GIVEN** the candidate response has `actions: []`
- **AND** deterministic recovery finds no uniquely resolvable inventory or location repair opportunity
- **WHEN** validation routing evaluates the turn
- **THEN** runtime MAY still skip the LLM validator as low-risk narration-only
