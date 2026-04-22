# toolkit-module-postbuild-finishing Specification Delta

## ADDED Requirements

### Requirement: Toolkit finishing SHALL surface semantic remediation as a distinct post-build lane
When toolkit finishing ends with semantic publishability blockers, the builder workflow SHALL surface those blockers as a distinct semantic remediation lane rather than relying on raw JSON output or generic failure text alone.

#### Scenario: Semantic-only blockers render semantic remediation guidance
- **GIVEN** toolkit finishing reports semantic publishability blockers without media-only handoff eligibility
- **WHEN** the builder workflow renders the post-build result
- **THEN** it SHALL present a semantic remediation section
- **AND** SHALL include structured blocker detail when available
- **AND** SHALL keep the overall outcome failed.

#### Scenario: Mixed media and semantic blockers render distinct remediation lanes
- **GIVEN** toolkit finishing reports both structured media debt and semantic publishability blockers
- **WHEN** the builder workflow renders the post-build result
- **THEN** it SHALL preserve failed semantics
- **AND** SHALL distinguish media debt from semantic remediation detail
- **AND** SHALL NOT reinterpret the result as media-only handoff.

## SHOULD Guidance

- SHOULD prefer `blocking_findings` over plain error strings when both are present.
- SHOULD preserve access to the raw payload after the formatted remediation summary for debugging.
