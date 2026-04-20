# toolkit-module-postbuild-finishing Specification Delta

## ADDED Requirements

### Requirement: Toolkit finisher SHALL preserve failed semantics for mixed publishability blockers
When post-build reporting contains missing media debt together with true semantic or content blockers, toolkit finishing SHALL preserve failed semantics and SHALL NOT reinterpret the run as a successful media-only handoff.

#### Scenario: Mixed media and semantic blockers remain failed
- **GIVEN** toolkit finishing detects missing module media debt
- **AND** publishability reporting also contains a non-media semantic or content blocker
- **WHEN** the finisher emits its result payload and report
- **THEN** the overall outcome SHALL remain failed
- **AND** SHALL preserve visibility into the media debt details
- **AND** SHALL NOT emit success-with-media-handoff semantics

#### Scenario: Pure semantic blockers remain failed without media handoff
- **GIVEN** toolkit finishing detects semantic or content blockers without a media-only handoff case
- **WHEN** the finisher emits its result payload and report
- **THEN** the overall outcome SHALL remain failed
- **AND** SHALL NOT direct the operator to media handoff as if it were sufficient remediation
