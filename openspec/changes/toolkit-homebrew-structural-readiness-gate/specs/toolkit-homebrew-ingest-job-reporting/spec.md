## MODIFIED Requirements

### Requirement: Toolkit exposes structured ingest job outcomes
The toolkit MUST expose structured upload, build, validation, and repair outcomes using authoritative job state fields so users can distinguish raw build completion from readiness success and bounded failure states.

#### Scenario: Validation and repair stages are shown explicitly
- **WHEN** a toolkit-triggered Homebrew upload job is in post-build validation or repair
- **THEN** the toolkit MUST display explicit states such as `validating`, `repairing_deterministic`, or `repairing_semantic`
- **AND** it MUST preserve enough detail for the operator to understand which post-build stage is active.

#### Scenario: Readiness success is distinct from raw build success
- **WHEN** a packet-built upload job has not yet passed the structural readiness gate
- **THEN** the toolkit MUST display `build_completed` distinctly from `ready_for_finishing`
- **AND** it MUST NOT imply that the module is already eligible for finishing or publication.

#### Scenario: System-failure or budget-exhaustion result is shown distinctly
- **WHEN** a toolkit-triggered upload job stops because of a builder/runtime defect or bounded repair exhaustion
- **THEN** the toolkit MUST display a distinct failure state such as `build_system_failed` or `repair_budget_exhausted`
- **AND** it MUST preserve actionable grouped failure details for debugging or retry.
