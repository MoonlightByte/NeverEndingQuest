# tt-rest-duration-precheck Specification

## Purpose
TBD - created by archiving change prompt-validator-expanded-deterministic-guards. Update Purpose after archive.
## Requirements
### Requirement: Explicit invalid rest durations SHALL fail closed
Deterministic precheck SHALL reject explicit short-rest and long-rest declarations that violate minimum duration rules when the duration is parseable.

#### Scenario: Explicit short rest below minimum rejected
- **WHEN** the response explicitly declares a short rest of less than 60 minutes
- **THEN** deterministic precheck SHALL fail before LLM validation with a deterministic reason

#### Scenario: Explicit long rest below minimum rejected
- **WHEN** the response explicitly declares a long rest of less than 8 hours
- **THEN** deterministic precheck SHALL fail before LLM validation with a deterministic reason

#### Scenario: Ambiguous natural-language rest duration remains fail open
- **WHEN** a rest declaration does not include a deterministically parseable duration
- **THEN** deterministic precheck SHALL pass and defer to the existing validation flow

