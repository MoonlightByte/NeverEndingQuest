# toolkit-module-postbuild-finishing Specification Delta

## ADDED Requirements

### Requirement: Toolkit finisher SHALL allow media handoff after deterministic short-form semantic normalization
When toolkit finishing receives semantic publishability output where short-form destination phrases have been deterministically normalized through already-resolved authored aliases, the finisher SHALL treat those phrases as cleared semantic debt while preserving the existing mixed-failure contract for truly unresolved blockers.

#### Scenario: Normalized short-form alias no longer forces mixed failure
- **GIVEN** toolkit finishing evaluates a module with manual media debt
- **AND** the module previously carried unresolved short-form destination phrases that were deterministically normalized before finisher classification
- **AND** no other true semantic blockers remain
- **WHEN** the finisher emits its result payload and report
- **THEN** it SHALL NOT preserve mixed-failure semantics solely because of the normalized short-form phrases
- **AND** MAY emit the existing success-with-media-handoff outcome if the remaining debt is media-only.

#### Scenario: True semantic blockers still keep mixed failure intact
- **GIVEN** toolkit finishing evaluates a module with media debt
- **AND** publishability output still contains true unresolved semantic blockers after deterministic short-form normalization has run
- **WHEN** the finisher emits its result payload and report
- **THEN** the overall outcome SHALL remain failed
- **AND** SHALL preserve the distinct media and semantic remediation lanes.
