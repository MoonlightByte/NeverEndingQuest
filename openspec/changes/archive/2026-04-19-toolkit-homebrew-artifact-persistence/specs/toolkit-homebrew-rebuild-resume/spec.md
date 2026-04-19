## Purpose

Provide explicit retry routes so operators can re-run build from an existing normalized packet (skipping normalization) or re-run finishing from existing build artifacts (skipping build), without manual filesystem inspection or orchestration.

## ADDED Requirements

### Requirement: Retry-From-Packet Route Handler

A route handler `POST /api/homebrew/retry-from-packet` MUST validate that the `normalized_packet` artifact exists, use the existing rebuild guard to check for concurrent active jobs, skip the normalization stage, and begin at build-from-packet.

#### Scenario: Retry-from-packet succeeds with existing normalized packet
- **WHEN** `POST /api/homebrew/retry-from-packet` is called with a valid job ID
- **AND** `normalized_packet` artifact is present on disk
- **AND** no other job is in an active non-terminal state
- **THEN** build starts immediately using the existing normalized packet
- **AND** the normalization stage is skipped
- **AND** the response has the same structure as the normal build route response

#### Scenario: Retry-from-packet fails when packet missing
- **WHEN** `POST /api/homebrew/retry-from-packet` is called
- **AND** `normalized_packet` artifact is absent
- **THEN** response is `{"status": "error", "reason": "missing_artifacts", "missing": ["normalized_packet"]}`

#### Scenario: Retry-from-packet blocked by concurrent active job
- **WHEN** `POST /api/homebrew/retry-from-packet` is called
- **AND** another job is in an active non-terminal state
- **THEN** response is `{"status": "error", "reason": "job_already_active"}`

### Requirement: Retry-From-Finishing Route Handler

A route handler `POST /api/homebrew/retry-from-finishing` MUST validate that `builder_input` and `build_result` artifacts exist, use the existing rebuild guard, skip the build stage, and begin at finishing.

#### Scenario: Retry-from-finishing succeeds with existing build artifacts
- **WHEN** `POST /api/homebrew/retry-from-finishing` is called with a valid job ID
- **AND** `builder_input` and `build_result` artifacts are present
- **AND** no other job is in an active non-terminal state
- **THEN** finishing starts immediately using existing build artifacts
- **AND** the build stage is skipped
- **AND** the response has the same structure as the normal finishing route response

#### Scenario: Retry-from-finishing fails when build artifacts missing
- **WHEN** `POST /api/homebrew/retry-from-finishing` is called
- **AND** `builder_input` or `build_result` artifact is absent
- **THEN** response is `{"status": "error", "reason": "missing_artifacts", "missing": ["builder_input"]}` or equivalent

#### Scenario: Retry-from-finishing blocked by concurrent active job
- **WHEN** `POST /api/homebrew/retry-from-finishing` is called
- **AND** another job is in an active non-terminal state
- **THEN** response is `{"status": "error", "reason": "job_already_active"}`

### Requirement: Retry Routes Preserve Validation Gates

Both retry routes MUST preserve all existing validation gates: readiness must still pass before finishing, publishability must still gate registry integration.

#### Scenario: Retry-from-finishing still enforces readiness gate
- **WHEN** `POST /api/homebrew/retry-from-finishing` is called
- **AND** build artifacts are present
- **THEN** finishing proceeds but readiness gate is enforced before registry integration

### Requirement: Cleanup Route Handler

A route handler `POST /api/homebrew/cleanup` MUST remove the upload workspace directory and all artifacts for a given job when the job is in a terminal state, or when `force=true` is passed.

#### Scenario: Cleanup removes workspace for terminal job
- **WHEN** `POST /api/homebrew/cleanup` is called with a job ID in a terminal state
- **THEN** the workspace directory and all artifacts are removed from disk
- **AND** response confirms removal with the removed path

#### Scenario: Cleanup blocked for non-terminal job without force
- **WHEN** `POST /api/homebrew/cleanup` is called without `force=true`
- **AND** the job is in a non-terminal state
- **THEN** response is `{"status": "error", "reason": "non_terminal_job"}`

#### Scenario: Cleanup succeeds on non-terminal with force flag
- **WHEN** `POST /api/homebrew/cleanup` is called with `force=true`
- **AND** the job is in any state
- **THEN** the workspace directory and all artifacts are removed
