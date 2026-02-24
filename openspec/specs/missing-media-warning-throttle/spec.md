## Purpose

Define deterministic throttling behavior for repeated missing-media warnings so logs preserve diagnostics without warning spam.

## Requirements

### Requirement: Missing-media warnings MUST be throttled per unique missing key

The media serving layer MUST avoid repeated warning spam for the same missing key within a throttle window.

#### Scenario: First miss for key
- **WHEN** a unique media key is missing for the first time in a throttle window
- **THEN** system emits a warning log for that key

#### Scenario: Repeated misses for same key
- **WHEN** repeated requests for the same missing key occur within throttle window
- **THEN** system suppresses repeated warning spam for that key

### Requirement: Throttle behavior SHALL preserve diagnostics

Throttle logic SHALL preserve useful diagnostics while reducing volume.

#### Scenario: Miss after throttle window expires
- **WHEN** the throttle window for a missing key has elapsed and key is still missing
- **THEN** system may emit a renewed warning signal for that key
