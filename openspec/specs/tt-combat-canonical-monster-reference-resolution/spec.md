# tt-combat-canonical-monster-reference-resolution Specification

## Purpose
TBD - created by archiving change combat-canonical-monster-reference-resolution. Update Purpose after archive.
## Requirements
### Requirement: Encounter monster labels SHALL resolve to canonical authored identities when deterministic
`createEncounter.monsters` references SHALL support deterministic canonicalization from flavored labels to authored canonical statblock identities.

#### Scenario: Exact authorized base identity
- **WHEN** a `createEncounter.monsters[]` entry exactly matches an authorized canonical monster identity
- **THEN** runtime SHALL use that same canonical identity
- **AND** authorization and hydration behavior SHALL remain unchanged from exact-match behavior

#### Scenario: Exact stronger authorized identity remains exact
- **WHEN** a `createEncounter.monsters[]` entry exactly matches an explicitly authored stronger canonical monster identity
- **THEN** runtime SHALL preserve that exact stronger canonical identity
- **AND** runtime SHALL NOT degrade it to a weaker base species

#### Scenario: Flavored label with one unique canonical base species
- **WHEN** a `createEncounter.monsters[]` entry includes non-canonical flavor or rank wording
- **AND** exactly one authored canonical monster identity is deterministically resolvable
- **THEN** runtime SHALL resolve to that canonical identity for authorization, hydration, and mechanics
- **AND** encounter runtime SHALL preserve the flavored label for display and targeting

#### Scenario: Ambiguous canonicalization candidates
- **WHEN** multiple authored canonical monster identities are equally plausible for a flavored `createEncounter.monsters[]` label
- **THEN** runtime SHALL reject encounter creation fail-closed
- **AND** hydration SHALL NOT run

#### Scenario: No canonical match
- **WHEN** no authored canonical monster identity can be resolved for a `createEncounter.monsters[]` label
- **THEN** runtime SHALL reject encounter creation fail-closed as unauthorized
- **AND** hydration SHALL NOT run

### Requirement: Encounter runtime identity split SHALL be preserved
Encounter enemy records SHALL preserve display identity and canonical mechanics identity as separate fields.

#### Scenario: Canonicalized flavored monster entry persisted to encounter
- **WHEN** a flavored monster label resolves successfully
- **THEN** encounter enemy `name` SHALL preserve the flavored display/target identity
- **AND** encounter enemy `monsterType` SHALL store the canonical statblock identity used by mechanics/template loaders

### Requirement: Canonicalization SHALL NOT widen monster authority beyond authored module content
Canonicalization SHALL remain inside the existing authored-content monster authority boundary.

#### Scenario: Runtime narration-only monster mention
- **WHEN** a monster reference is not resolvable from authored module monster authority sources
- **THEN** canonicalization SHALL NOT authorize that reference
- **AND** encounter creation SHALL fail closed

