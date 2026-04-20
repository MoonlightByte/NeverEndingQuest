## ADDED Requirements

### Requirement: Blocker-resolution reporting SHALL expose measurable canary advancement

Residual blocker resolution reporting SHALL expose whether the latest canary materially improved the live validator state relative to the previous canary artifact.

#### Scenario: Canary comparison shows no advancement

- **WHEN** previous and current canary runs have the same live validator failure count and no residual classes were removed
- **THEN** reporting SHALL mark that blocker-resolution did not advance beyond the previous canary
- **AND** SHALL preserve added or reclassified residual classes separately from resolved classes

#### Scenario: Canary comparison shows advancement

- **WHEN** the current canary removes one or more prior residual classes or reduces total live validator failures
- **THEN** reporting SHALL mark blocker-resolution as advanced
- **AND** SHALL expose the removed classes and failure-count delta explicitly
