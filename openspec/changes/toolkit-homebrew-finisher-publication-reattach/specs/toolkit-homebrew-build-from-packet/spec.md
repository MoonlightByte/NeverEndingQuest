## MODIFIED Requirements

### Requirement: Packet-driven upload build SHALL continue through shared finishing after readiness
Packet-driven upload builds that have already passed structural readiness MUST be able to continue through the shared finisher/publication stack without rerunning normalization or rebuilding from source.

#### Scenario: Ready upload proceeds to finisher without rebuild
- **WHEN** a packet-driven Homebrew upload job is already `ready_for_finishing`
- **THEN** the toolkit MUST allow it to enter shared finisher/publication execution
- **AND** it MUST reuse persisted build/readiness artifacts instead of forcing a new normalization/build cycle.

#### Scenario: Non-ready upload cannot skip into finisher
- **WHEN** a packet-driven upload has not reached `ready_for_finishing`
- **THEN** the toolkit MUST block attempts to continue directly to finishing/publication
- **AND** it MUST preserve the existing build/readiness boundary.
