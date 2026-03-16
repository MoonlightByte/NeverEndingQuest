# tt-dm-note-state-packet-parity Specification

## Purpose
TBD - created by archiving change narrative-sovereignty-state-packet-foundation. Update Purpose after archive.
## Requirements
### Requirement: DM Note rendering SHALL consume authoritative packet truth for overlapping fields
Touched DM Note rendering paths SHALL use authoritative state packet fields as the source of truth for overlapping world and roster fields rather than independently reconstructing those same truths.

#### Scenario: DM Note location and roster parity
- **WHEN** DM Note output includes current module, area, location, party members, or party NPCs
- **THEN** the touched rendering path SHALL derive those overlapping fields from the authoritative state packet
- **AND** those rendered truths SHALL match the packet values for the same turn

### Requirement: DM Note parity SHALL NOT regress non-targeted narration support
State-packet parity work SHALL preserve existing DM Note support for non-targeted gameplay domains in this slice.

#### Scenario: Unrelated DM Note content remains stable
- **WHEN** a turn does not depend on new packet-enabled travel or NPC-reconciliation groundwork
- **THEN** DM Note rendering SHALL remain functionally compatible with existing behavior
- **AND** no unrelated gameplay domain SHALL require new packet fields before this slice is considered valid

