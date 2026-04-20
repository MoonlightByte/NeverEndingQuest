## ADDED Requirements

### Requirement: Canary reporting SHALL distinguish reconciliation advancement from unchanged residual debt

Module canary reporting SHALL show whether live blocker reconciliation materially reduced validator failures and which remaining failures are still repair-engine mismatches versus authored debt.

#### Scenario: Reconciliation report shows no advancement

- **WHEN** a blocker-reconciliation canary rerun still reports the same total failure count and residual classes
- **THEN** the persisted report SHALL state that advancement did not occur
- **AND** SHALL preserve per-blocker classification for repair-engine gaps and author/content debt
