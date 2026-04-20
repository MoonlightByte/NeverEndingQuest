# toolkit-module-postbuild-finishing Specification Delta

## ADDED Requirements

### Requirement: Toolkit finishing SHALL report explicit monster-media policy outcome
Toolkit finishing SHALL expose the monster-media outcome for combat-valid structured monsters in a way that distinguishes reuse, generation, provider-disabled non-generation, and attempted-but-unresolved media debt.

#### Scenario: Toolkit run reports provider-disabled missing monster media explicitly
- **GIVEN** a toolkit finisher run evaluates a module with combat-valid structured monsters
- **AND** required module-local monster base media is absent
- **AND** provider-backed monster generation is disabled for that run
- **WHEN** the finisher emits its stage/report payload
- **THEN** the report SHALL identify the monster-media outcome as provider-disabled unresolved media debt or equivalent explicit policy-aware state
- **AND** SHALL NOT imply that provider generation already ran successfully in that same toolkit path
- **AND** SHALL point to the existing toolkit monster-image generation workflow as the manual remediation path
