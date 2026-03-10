# tt-ammo-legality-guard Specification

## Purpose
TBD - created by archiving change prompt-validator-expanded-deterministic-guards. Update Purpose after archive.
## Requirements
### Requirement: Explicit ammunition-use contradictions SHALL fail closed
Deterministic precheck SHALL reject explicit ammunition spend/use contradictions when tracked ammunition state is known.

#### Scenario: Fired ammunition not possessed in sufficient quantity
- **WHEN** `updateCharacterInfo.changes` explicitly states that arrows, bolts, bullets, or similar tracked ammunition were fired, spent, or used
- **AND** known canonical inventory shows insufficient quantity
- **THEN** deterministic precheck SHALL fail before LLM validation with a deterministic reason

#### Scenario: Unmatched ammo type remains fail open
- **WHEN** explicit ammunition language cannot be matched deterministically to tracked ammunition state
- **THEN** deterministic precheck SHALL pass and defer to the existing validation flow

