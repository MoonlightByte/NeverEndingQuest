# tt-authoritative-state-packet-foundation Specification

## Purpose
TBD - created by archiving change narrative-sovereignty-state-packet-foundation. Update Purpose after archive.
## Requirements
### Requirement: Runtime SHALL build a canonical authoritative state packet for touched narrator domains

The runtime SHALL build a machine-readable authoritative state packet before packet-enabled narrator validation or DM Note rendering paths execute. The packet SHALL provide a single canonical truth surface for the touched domains in this change: current module, current area, current location, current party roster, current party NPC roster, and reachable topology context.

#### Scenario: Packet topology includes module-level location catalog for safe arrival reconciliation
- **WHEN** the runtime prepares packet-enabled narrator validation or DM Note assembly
- **THEN** reachable topology context SHALL include the known current-area location set
- **AND** SHALL also include the minimal module-level location catalog required for narrated-location-arrival reconciliation
- **AND** that catalog SHALL expose enough location metadata to commit a resolved in-module destination safely

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

