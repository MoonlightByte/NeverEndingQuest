## ADDED Requirements

### Requirement: Combat validation SHALL reject explicit miss narration that falsely describes successful impact
Combat validation SHALL reject a combat response when authoritative attack math shows a miss against known AC and the same response explicitly narrates that attack as landing with damaging or destructive impact.

#### Scenario: Miss narrated as bone-splintering hit
- **WHEN** a combat response explicitly states or implies that an attack total is lower than the target AC
- **AND** the same response narrates that attack as biting deep, splintering bone, drawing blood, or landing solidly
- **THEN** deterministic combat validation SHALL reject the response before probabilistic validation

#### Scenario: Miss narrated as harmless deflection
- **WHEN** a combat response explicitly states or implies that an attack total is lower than the target AC
- **AND** the same response narrates a clang, dodge, scrape, or near miss without harmful impact
- **THEN** deterministic combat validation SHALL NOT reject the response on narration-consistency grounds

### Requirement: Combat validation SHALL reject explicit hit narration that falsely describes a harmless miss
Combat validation SHALL reject a combat response when authoritative attack math shows a hit against known AC and the same response explicitly narrates the attack as harmlessly missing or striking only the environment.

#### Scenario: Hit narrated as wall strike
- **WHEN** a combat response explicitly states or implies that an attack total meets or exceeds the target AC
- **AND** the same response narrates the projectile or blow as going wide, hitting only the wall, floor, or empty air, or otherwise missing harmlessly
- **THEN** deterministic combat validation SHALL reject the response before probabilistic validation

#### Scenario: Hit narrated without gore but with contact
- **WHEN** a combat response explicitly states or implies that an attack total meets or exceeds the target AC
- **AND** the same response narrates contact or injury without vivid gore
- **THEN** deterministic combat validation SHALL NOT reject the response solely for low-intensity narration

### Requirement: Hit-miss narration guards SHALL fail open on ambiguity
Deterministic narration-consistency guards SHALL defer to existing validation flow when narration or attack math is too ambiguous to prove contradiction safely.

#### Scenario: Atmospheric narration without explicit contact claim
- **WHEN** attack math is present but narration remains atmospheric and does not clearly claim impact or harmless miss
- **THEN** deterministic combat validation SHALL defer to the existing validation path

#### Scenario: Missing authoritative attack outcome
- **WHEN** attack total, attack bonus, or target AC is unavailable or not confidently parseable
- **THEN** deterministic combat validation SHALL NOT reject solely from inferred narration mismatch
