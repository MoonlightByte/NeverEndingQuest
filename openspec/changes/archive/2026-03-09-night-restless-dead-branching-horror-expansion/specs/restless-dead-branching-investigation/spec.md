# restless-dead-branching-investigation Specification

## Purpose
Define how `Night_of_the_Restless_Dead` expands from linear flow to branch-capable investigation while keeping existing progression compatibility.

## ADDED Requirements

### Requirement: Additive Branch Metadata on Canonical Backbone
The module SHALL support additive branch metadata while preserving the canonical PP001->PP007 progression path.

#### Scenario: Canonical chain remains valid
- **WHEN** branch metadata is added to `module_plot.json`
- **THEN** all existing plot points PP001-PP007 still exist with valid required fields
- **AND** canonical `nextPoints` chain remains traversable without using branch-only metadata

#### Scenario: Investigation and confrontation options coexist
- **WHEN** players enter the module via NIG01
- **THEN** at least one investigation-first route and one confrontation-first route are represented in additive narrative metadata
- **AND** neither route requires external module completion

### Requirement: Choice-Visible Clues
The module SHALL expose branch-driving clues in area content rather than hidden-only meta state.

#### Scenario: Clues are discoverable in-play
- **WHEN** a facilitator reads area content for NIG01-NIG06
- **THEN** narrative hooks include clear trigger conditions and outcomes for at least two major branch pivots
- **AND** hooks are additive and do not remove existing room text
