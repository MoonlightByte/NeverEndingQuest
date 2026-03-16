## MODIFIED Requirements

### Requirement: Runtime SHALL build a canonical authoritative state packet for touched narrator domains

The runtime SHALL build a machine-readable authoritative state packet before packet-enabled narrator validation or DM Note rendering paths execute. The packet SHALL provide a single canonical truth surface for the touched domains in this change: current module, current area, current location, current party roster, current party NPC roster, and reachable topology context.

#### Scenario: Packet topology includes module-level location catalog for safe arrival reconciliation
- **WHEN** the runtime prepares packet-enabled narrator validation or DM Note assembly
- **THEN** reachable topology context SHALL include the known current-area location set
- **AND** SHALL also include the minimal module-level location catalog required for narrated-location-arrival reconciliation
- **AND** that catalog SHALL expose enough location metadata to commit a resolved in-module destination safely
