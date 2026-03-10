## ADDED Requirements

### Requirement: Compressed narrator prompt SHALL present hard rules before flavor guidance
The compressed narrator prompt SHALL prioritize output contract, truth hierarchy, and action grammar before narrative style guidance.

#### Scenario: Hard-rules-first order
- **WHEN** the compressed narrator prompt is read top-to-bottom
- **THEN** hard runtime/contract rules SHALL appear before flavor and style guidance

### Requirement: Compressed narrator prompt SHALL include a resolution ladder
The compressed narrator prompt SHALL include a compact decision ladder for turn resolution.

#### Scenario: Resolution ladder present
- **WHEN** the compressed narrator prompt is loaded
- **THEN** it SHALL contain an `@RESOLUTION_LADDER` block
- **AND** that block SHALL cover narration-only, player-roll, narrator-resolved, structured-action, and combat-commitment cases
