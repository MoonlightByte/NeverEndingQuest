## ADDED Requirements

### Requirement: Scene-only illusion content SHALL stay outside structured combatant requirements
Builder, finisher, and publication flows MUST preserve the distinction between scene-only illusion content and combat-valid entities so scene-only illusions do not trigger monster hydration or media blockers unless they are explicitly authored as combat-valid.

#### Scenario: Scene-only illusion modeled as scene entity avoids monster-readiness blocking
- **WHEN** authored illusion or mindscape content is represented through `sceneEntity` metadata instead of structured monster fields
- **THEN** monster hydration and gameplay media gates MUST NOT require monster statblocks or monster media for that content

#### Scenario: Structured monster fields remain strict for combat-valid entities
- **WHEN** authored content appears in `locations[].monsters[]` or other combat-valid structured fields
- **THEN** build and publication flows MUST continue to require full combat-valid hydration and media support
- **AND** MUST NOT treat the content as scene-only by implication
