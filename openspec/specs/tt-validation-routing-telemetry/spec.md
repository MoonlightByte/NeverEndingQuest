# tt-validation-routing-telemetry Specification

## Purpose
TBD - created by archiving change prompt-validator-telemetry-and-truth-pack. Update Purpose after archive.
## Requirements
### Requirement: Validation routing SHALL expose deterministic telemetry

The validation pipeline SHALL expose deterministic telemetry for skip, compression, and authoritative-domain suppression outcomes.

#### Scenario: Authoritative-domain suppression telemetry emitted
- **WHEN** runtime suppresses an LLM validation failure because it targets authoritative-passed domains only
- **THEN** telemetry SHALL record `authoritative_domain_conflict = true`
- **AND** SHALL record the `suppressed_domains`

#### Scenario: Mixed-domain review telemetry emitted
- **WHEN** runtime preserves a failure because unreconciled domains remain
- **THEN** telemetry SHALL record `remaining_failure_domains`
- **AND** SHALL distinguish that path from full suppression

#### Scenario: Payload version telemetry emitted
- **WHEN** deterministic narrator handoff is assembled
- **THEN** telemetry SHALL record a deterministic payload version identifier

