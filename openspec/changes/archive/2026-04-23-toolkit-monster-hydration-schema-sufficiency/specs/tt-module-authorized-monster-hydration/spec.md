# tt-module-authorized-monster-hydration Specification Delta

## ADDED Requirements

### Requirement: Runtime-authoritative monster hydration SHALL only accept schema-sufficient local authority
Runtime-authoritative monster hydration SHALL preserve existing local monster files as authoritative only when those files remain schema-sufficient for shared hydration acceptance.

#### Scenario: Valid existing local monster file remains authoritative
- **GIVEN** a module-local monster file already exists
- **AND** it contains the minimum required structured fields for hydration acceptance
- **WHEN** runtime-authorized monster hydration evaluates the monster
- **THEN** the helper SHALL preserve the existing file as authoritative
- **AND** SHALL remain backward compatible with current runtime behavior.

#### Scenario: Schema-incomplete existing local file does not block shared recovery
- **GIVEN** a module-local monster file already exists for an authorized monster
- **AND** that file is schema-incomplete for shared hydration acceptance
- **WHEN** runtime-authorized monster hydration evaluates the monster
- **THEN** the helper SHALL NOT stop at the existing file solely because it is present
- **AND** SHALL continue to reusable, bestiary, or controlled generation recovery according to existing precedence rules.
