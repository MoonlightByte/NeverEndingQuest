# toolkit-module-postbuild-finishing Specification Delta

## ADDED Requirements

### Requirement: Toolkit builder workflow SHALL sequence semantic remediation after deterministic post-build classification
When toolkit post-build reporting has been stabilized for media handoff, workflow ordering, payload normalization, and mixed-failure classification, remaining semantic publishability blockers SHALL be treated as an explicit builder remediation stage rather than collapsed into media handoff or hidden inside unrelated reporting defects.

#### Scenario: Unresolved destination alias enters semantic remediation lane
- **GIVEN** toolkit finishing reports an unresolved destination alias or similar semantic blocker after deterministic reporting boundaries are already correct
- **WHEN** the builder workflow determines the next remediation step
- **THEN** it SHALL treat that blocker as a semantic remediation task
- **AND** SHALL NOT present media-only handoff as sufficient remediation
- **AND** SHALL preserve reviewable builder guidance for the later repair slice
