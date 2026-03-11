# tt-combat-mechanics-contradiction-guards Specification

## Purpose
TBD - created by archiving change combat-expanded-deterministic-guards. Update Purpose after archive.
## Requirements
### Requirement: Combat deterministic guards SHALL reject explicit mechanics contradictions only when state-backed and unambiguous
Combat deterministic guards SHALL reject explicit mechanics contradictions only when the contradiction is supported by authoritative combat/runtime state and explicit mechanical text.

#### Scenario: Above-zero HP contradicts unconscious mechanical state
- **WHEN** a combat response explicitly sets or states a character above 0 HP
- **AND** the same response explicitly applies an unconscious-only mechanical state to that same character
- **THEN** deterministic combat validation SHALL reject the response before probabilistic validation

#### Scenario: Explicit ranged-ammo spend underflows tracked ammunition
- **WHEN** a combat response explicitly spends or fires tracked ranged ammunition
- **AND** authoritative inventory state shows insufficient ammunition
- **THEN** deterministic combat validation SHALL reject the response before probabilistic validation

#### Scenario: Explicit leveled combat cast underflows known slots
- **WHEN** a combat response explicitly spends a leveled spell slot during combat
- **AND** authoritative slot state shows the spend would underflow
- **THEN** deterministic combat validation SHALL reject the response before probabilistic validation

### Requirement: Combat deterministic mechanics guards SHALL fail open on ambiguity
Combat deterministic mechanics guards SHALL defer to the existing validation path when the text or state is ambiguous.

#### Scenario: Flavor-only wording does not trigger unconscious contradiction guard
- **WHEN** combat narration says a character is reeling, dazed, or barely standing without an explicit mechanical contradiction
- **THEN** deterministic combat validation SHALL NOT reject on that basis alone

#### Scenario: Unknown ammo source does not trigger underflow guard
- **WHEN** combat text implies ammo use but authoritative ammo matching is unavailable or ambiguous
- **THEN** deterministic combat validation SHALL defer to the existing validation path

