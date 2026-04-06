## ADDED Requirements

### Requirement: Non-narration tasks SHALL remain on the existing provider path during the pilot
Enabling the Bonsai narration pilot SHALL NOT reroute validation, combat, builder, or other non-allowlisted tasks to Bonsai.

#### Scenario: validation remains unchanged
- **WHEN** the Bonsai narration pilot is enabled
- **AND** runtime prepares a validation task
- **THEN** that task SHALL continue using the existing provider path
- **AND** it SHALL NOT be routed to Bonsai solely because the pilot is enabled

#### Scenario: combat remains unchanged
- **WHEN** the Bonsai narration pilot is enabled
- **AND** runtime prepares a combat task
- **THEN** that task SHALL continue using the existing provider path
- **AND** it SHALL NOT be routed to Bonsai solely because the pilot is enabled

### Requirement: The Bonsai pilot SHALL remain additive and easy to disable
The Bonsai narration pilot SHALL be configuration-gated and SHALL preserve the ability to return fully to the current provider behavior by disabling the pilot.

#### Scenario: disabling the pilot restores current behavior
- **WHEN** the Bonsai narration pilot is disabled after having been enabled previously
- **THEN** narration SHALL return to the existing provider path
- **AND** no broader provider migration steps SHALL be required for that rollback
