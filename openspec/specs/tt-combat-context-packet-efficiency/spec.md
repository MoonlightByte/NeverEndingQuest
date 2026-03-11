# tt-combat-context-packet-efficiency Specification

## Purpose
TBD - created by archiving change combat-runtime-authority-and-efficiency. Update Purpose after archive.
## Requirements
### Requirement: Combat runtime SHALL use a slimmer authoritative state packet
The combat runtime SHALL reduce duplicated or overlapping injected combat-state sections while preserving the current authoritative phase, actor, and accounting information required for legal turn resolution.

#### Scenario: Duplicate dynamic state is reduced without losing phase authority
- **WHEN** a combat prompt payload is assembled for a live turn
- **THEN** it SHALL preserve authoritative initiative, phase, active-actor, and touched-state information
- **AND** it SHALL avoid duplicating the same dynamic combat fact across multiple injected state blocks without explicit need

#### Scenario: Context trimming does not remove legal-actor fidelity
- **WHEN** combat runtime trims prompt payload sections for efficiency
- **THEN** the payload SHALL still identify the legal actor set for the current phase
- **AND** it SHALL still preserve the current round, active actor, and stop-boundary information needed to avoid turn desync

### Requirement: Combat packet slimming SHALL preserve tactical usefulness
Prompt payload reduction SHALL NOT intentionally collapse combat into a sterile mechanics summary.

#### Scenario: Enemy tactical context remains available
- **WHEN** combat prompt payloads are slimmed for efficiency
- **THEN** enough battlefield and creature-state context SHALL remain for the LLM to choose legal plausible enemy tactics
- **AND** the change SHALL NOT require enemies to behave simplistically to satisfy the slimmer packet

