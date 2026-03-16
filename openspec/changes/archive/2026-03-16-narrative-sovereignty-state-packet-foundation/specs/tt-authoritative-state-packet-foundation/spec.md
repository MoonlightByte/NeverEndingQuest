## ADDED Requirements

### Requirement: Runtime SHALL build a canonical authoritative state packet for touched narrator domains
The runtime SHALL build a machine-readable authoritative state packet before packet-enabled narrator validation or DM Note rendering paths execute. The packet SHALL provide a single canonical truth surface for the touched domains in this change: current module, current area, current location, current party roster, current party NPC roster, and reachable topology context.

#### Scenario: Packet contains current world and roster truth
- **WHEN** the runtime prepares packet-enabled narrator validation or DM Note assembly
- **THEN** it SHALL build one authoritative state packet for the turn
- **AND** that packet SHALL include current module, area, and location truth
- **AND** that packet SHALL include current party roster and current party NPC roster
- **AND** that packet SHALL include reachable topology context needed by the touched consumers

### Requirement: Packet foundation SHALL preserve existing explicit action compatibility
The authoritative state packet foundation SHALL NOT replace the existing JSON/action schema or explicit action execution flow in this slice.

#### Scenario: Explicit action flow remains valid
- **WHEN** a response already includes valid explicit state actions under the existing action schema
- **THEN** packet construction SHALL NOT invalidate or replace that action flow
- **AND** runtime SHALL continue to support the existing explicit action contract unchanged in this slice

### Requirement: Packet foundation SHALL preserve single-player and tabletop compatibility
The authoritative state packet foundation SHALL operate for both single-player and tabletop modes without requiring mode-specific protocol forks.

#### Scenario: Shared packet contract across SP and tabletop
- **WHEN** the runtime builds the authoritative state packet in single-player mode or tabletop mode
- **THEN** it SHALL use the same packet contract for overlapping fields
- **AND** mode-specific fields MAY be additive only when they do not break shared consumers
