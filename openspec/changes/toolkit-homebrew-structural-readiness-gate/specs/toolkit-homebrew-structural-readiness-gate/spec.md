## ADDED Requirements

### Requirement: Toolkit SHALL gate packet-built modules on structural readiness before finishing
The toolkit MUST treat successful packet-driven raw build completion as distinct from structural readiness and MUST require a post-build readiness gate before a module may enter the finisher/publication pipeline.

#### Scenario: Raw build completion is pre-readiness only
- **WHEN** a Homebrew upload job completes packet-driven raw build successfully
- **THEN** the toolkit MUST place the job in a pre-readiness state such as `build_completed`
- **AND** it MUST NOT treat that state as equivalent to finishing-eligible completion.

#### Scenario: Structurally ready module advances to finisher boundary
- **WHEN** the post-build readiness gate passes after validation and any bounded repair steps
- **THEN** the toolkit MUST place the job in `ready_for_finishing` or an equivalent finisher-entry state
- **AND** that state MUST be the earliest point at which the next uploader slice may attach finisher/publication stages.

### Requirement: Toolkit SHALL prefer deterministic repair before semantic repair
The toolkit MUST classify post-build failures into repair domains and MUST attempt deterministic repair first for structurally repairable defects before invoking any semantic repair workflow.

#### Scenario: Deterministic structural defect is repaired before semantic pass
- **WHEN** validation finds a repairable deterministic defect such as enum normalization, monster materialization, spatial contract repair, or derived context regeneration
- **THEN** the toolkit MUST attempt a deterministic repair pass first
- **AND** it MUST rerun validation before entering semantic repair.

#### Scenario: Semantic repair remains narrow and bounded
- **WHEN** deterministic repair does not resolve the remaining readiness failures
- **THEN** the toolkit MAY run a targeted semantic repair pass against the failing files only
- **AND** it MUST apply bounded repair budgets and immediate revalidation.

### Requirement: Toolkit SHALL fail closed on builder/runtime defects during readiness gating
The toolkit MUST distinguish build-system defects from content defects and MUST stop remediation loops immediately when builder/runtime failures are detected.

#### Scenario: Builder defect becomes system failure state
- **WHEN** post-build validation or repair processing detects a generator/runtime defect such as an undefined helper, broken persistence call, or equivalent builder-side exception
- **THEN** the toolkit MUST classify the job as `build_system_failed` or an equivalent system failure state
- **AND** it MUST preserve artifacts and actionable failure context without attempting semantic repair to mask the defect.

#### Scenario: Repair budget exhaustion remains inspectable
- **WHEN** bounded repair attempts do not converge to readiness
- **THEN** the toolkit MUST stop further automatic repair
- **AND** it MUST preserve grouped validation and repair artifacts for operator or developer review.
