## ADDED Requirements

### Requirement: Toolkit SHALL build approved uploads from persisted normalized packets
The toolkit MUST provide a packet-driven build path for approved Homebrew upload workspaces so reviewed uploads can become module artifacts without rerunning normalization.

#### Scenario: Approved upload can start packet-driven build
- **WHEN** a Homebrew upload job is in `approved_for_build`
- **THEN** the toolkit MUST allow an explicit build-start action for that job
- **AND** it MUST use the persisted normalized packet as the authoritative build source.

#### Scenario: Unapproved upload cannot start packet-driven build
- **WHEN** a Homebrew upload job has not reached `approved_for_build`
- **THEN** the toolkit MUST reject packet-driven build start
- **AND** it MUST surface an actionable state error rather than silently building anyway.

### Requirement: Packet-driven build SHALL persist builder input and build result artifacts
The toolkit MUST persist the packet-to-builder transform and the build outcome for later inspection and resume workflows.

#### Scenario: Builder input is persisted before build execution
- **WHEN** a packet-driven build starts
- **THEN** the toolkit MUST write `builder_input.json`
- **AND** that artifact MUST preserve normalized packet identity or provenance fields.

#### Scenario: Build result is persisted on success or failure
- **WHEN** a packet-driven build finishes or errors
- **THEN** the toolkit MUST write `build_result.json`
- **AND** it MUST include the authoritative build outcome and packet-linked identity fields.

### Requirement: Packet-driven build completion SHALL remain pre-finishing
The toolkit MUST distinguish raw builder completion from later finisher/publication completion.

#### Scenario: Successful build enters build-complete state only
- **WHEN** a packet-driven build succeeds before the finisher is attached
- **THEN** the upload job MUST enter a distinct pre-finishing success state such as `build_completed`
- **AND** it MUST NOT be reported as final publication-ready completion.

#### Scenario: Concept builder remains unchanged
- **WHEN** the toolkit concept-builder is used directly with raw narrative input
- **THEN** it MUST continue to use its existing builder start path
- **AND** packet-driven upload build wiring MUST NOT replace that concept-builder contract.
