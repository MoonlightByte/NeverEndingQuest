## ADDED Requirements

### Requirement: Packet-enabled validation handoff SHALL consume authoritative packet truth
For domains enabled by this foundation slice, narrator validation assembly SHALL use authoritative state packet fields as the canonical truth handoff instead of reconstructing those truths independently from multiple ad hoc sources.

#### Scenario: Packet-enabled validation uses shared state surface
- **WHEN** narrator validation assembles current location, party roster, party NPC roster, or touched topology context for a packet-enabled turn
- **THEN** the assembly path SHALL consume those truths from the authoritative state packet
- **AND** it SHALL avoid rebuilding different values for the same overlapping truths from separate ad hoc sources

### Requirement: Packet handoff SHALL remain additive during migration
The packet-enabled validation handoff SHALL remain additive during this migration slice and SHALL NOT require immediate replacement of every legacy validation context source.

#### Scenario: Legacy context remains available outside packet-enabled domains
- **WHEN** validation still requires non-packet legacy context outside the domains covered by this change
- **THEN** runtime MAY include that additional context
- **AND** packet-enabled overlapping truths SHALL still come from the authoritative state packet
