## ADDED Requirements

### Requirement: Rejected narrator turns SHALL be captured in a dedicated debug log

When narrator generation fails validation, the runtime SHALL record the rejected turn in a dedicated append-only debug log outside canonical conversation history.

#### Scenario: Validation rejects a narrator turn
- **WHEN** the narrator response fails deterministic or LLM validation
- **THEN** the runtime SHALL append a debug record containing timestamp, rejection reason, raw rejected response, and triggering player input
- **AND** the record SHALL be written to a dedicated debug channel rather than conversation history

### Requirement: Rejected-turn debug records SHALL include minimal scene context

Rejected-turn debug logging SHALL include enough context to reproduce the scene without requiring full prompt dumps in every record.

#### Scenario: Debug review after a soft fail
- **WHEN** a developer inspects a rejected-turn debug record
- **THEN** the record SHALL include current module and current location when available
- **AND** it SHALL include retry-attempt or exhaustion state when available

### Requirement: Rejected-turn logging SHALL fail open

If rejected-turn debug logging cannot write successfully, the runtime SHALL preserve gameplay control flow and SHALL NOT create a new hard failure class.

#### Scenario: Debug log write fails
- **WHEN** the runtime cannot append the rejected-turn debug record
- **THEN** the original validation/fail-closed path SHALL continue unchanged
- **AND** logging failure SHALL not block gameplay progression, retry handling, or system output
