# toolkit-numillian-residual-blocker-resolution Specification

## Purpose
TBD - created by archiving change gui-builder-numillian-residual-blocker-resolution. Update Purpose after archive.
## Requirements
### Requirement: Numillian residual blocker resolution SHALL target the live remaining blocker set

The residual blocker resolution workflow SHALL operate against the live validator blocker set for `The_Hidden_City_of_Numillian` and SHALL report whether each blocker was resolved, remained a repair-engine gap, or was reclassified as authored debt.

#### Scenario: Live blocker report distinguishes resolved vs residual outcomes

- **WHEN** the blocker-resolution canary runs for `The_Hidden_City_of_Numillian`
- **THEN** the persisted artifact SHALL identify the previous and current live validator failure counts
- **AND** SHALL expose whether blocker-resolution materially advanced the canary
- **AND** SHALL classify remaining failures into repair-engine gaps vs author/content debt

