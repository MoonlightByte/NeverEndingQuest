## ADDED Requirements

### Requirement: Toolkit SHALL attach the shared finisher/publication pipeline after upload readiness
The toolkit MUST allow Homebrew upload jobs that have already reached `ready_for_finishing` to enter the shared finisher/publication stack, and it MUST prevent earlier upload states from entering that path.

#### Scenario: Only readiness-cleared upload enters finisher
- **WHEN** a Homebrew upload job is `ready_for_finishing`
- **THEN** the toolkit MUST allow finisher/publication execution for that job
- **AND** it MUST use the shared finisher/publication stack rather than an upload-only implementation.

#### Scenario: Pre-readiness upload cannot enter finisher
- **WHEN** a Homebrew upload job has not reached `ready_for_finishing`
- **THEN** the toolkit MUST reject finisher/publication start
- **AND** it MUST surface an actionable state error.

### Requirement: Toolkit SHALL gate upload completion on publishability
The toolkit MUST distinguish structural readiness from final publishability, and it MUST only report upload completion when the shared finisher/publication result remains publishable.

#### Scenario: Publishable upload reaches completed
- **WHEN** the shared finisher/publication result returns `ready_status=pass` and `publishable_status=pass`
- **THEN** the toolkit MUST move the upload job to `completed`
- **AND** it MUST preserve final finisher/publication artifacts for that job.

#### Scenario: Non-publishable upload is blocked from completion
- **WHEN** the shared finisher/publication result returns `ready_status=pass` but `publishable_status` is not pass
- **THEN** the toolkit MUST move the upload job to `not_publishable`
- **AND** it MUST NOT silently report final completion or registry integration success.

### Requirement: Toolkit SHALL fail closed on finisher/runtime defects
The toolkit MUST classify shared finisher/runtime defects as uploader system failures rather than masking them as publishability blockers or silent success.

#### Scenario: Finisher exception becomes finishing_failed
- **WHEN** shared finisher/publication execution raises a hard exception or returns a hard system failure
- **THEN** the toolkit MUST move the upload job to `finishing_failed`
- **AND** it MUST preserve the failure context in upload-facing reports/artifacts.
