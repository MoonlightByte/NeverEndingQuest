## MODIFIED Requirements

### Requirement: Toolkit SHALL expose upload finisher/publication states distinctly
Toolkit job reporting MUST distinguish build/readiness success from finisher/publication progress and terminal publication outcomes.

#### Scenario: Finisher stages are visible after readiness
- **WHEN** a Homebrew upload job has entered the shared finisher/publication stack
- **THEN** the toolkit MUST expose states such as `finishing` and `publishability_audit`
- **AND** it MUST keep them distinct from `building`, `validating`, and `ready_for_finishing`.

#### Scenario: Publishability blocker is visible to operator
- **WHEN** a Homebrew upload job finishes structurally but fails final publishability
- **THEN** the toolkit MUST surface `not_publishable` or equivalent bounded state
- **AND** it MUST include artifact-backed detail rather than collapsing to generic failure.
