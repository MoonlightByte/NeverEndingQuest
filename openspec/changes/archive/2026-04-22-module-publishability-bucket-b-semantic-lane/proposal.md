## Why

`Keep_of_Doom`, `Night_of_the_Restless_Dead`, and `The_Hidden_City_of_Numillian` are the next publishability lane after the quick wins because their monster media coverage is already strong, but they remain blocked by semantic-authority or destination-alias debt.

- `Keep_of_Doom` fails on missing semantic-authority payload plus unresolved destination aliases.
- `Night_of_the_Restless_Dead` fails on missing semantic-authority payload plus unresolved destination aliases.
- `The_Hidden_City_of_Numillian` is the semantic ambiguity canary and also carries a provenance/sidecar gap in addition to the unresolved `paradox sanctuary` alias.

These modules should be planned together as a semantic lane rather than mixed with the heavier media/provenance WIP modules.

## What Changes

- Define a bounded semantic-authority remediation lane for `Keep_of_Doom`, `Night_of_the_Restless_Dead`, and `The_Hidden_City_of_Numillian`.
- Preserve explicit unresolved destination-alias handling instead of silently suppressing ambiguous phrases.
- Include Numillian's sidecar/provenance closure because semantic repair alone is not sufficient for it to pass.
- Exclude `Murder_at_the_Drowning_Lass` and `The_Ancients_Lab` from this lane.

## Capabilities

### New Capabilities
- `toolkit-keep-of-doom-semantic-closure`: Close `Keep_of_Doom` semantic-authority payload and named destination-alias debt.
- `toolkit-restless-dead-semantic-closure`: Close `Night_of_the_Restless_Dead` semantic-authority payload and named destination-alias debt.
- `toolkit-numillian-semantic-provenance-closure`: Close `The_Hidden_City_of_Numillian` semantic alias/provenance lane without broadening into unrelated remediation.

### Modified Capabilities
- `module-semantic-authority-enrichment`: Preserve reviewable, explicit semantic-authority output and ambiguity diagnostics while closing these lane-specific blockers.
- `module-publishable-gate`: Preserve explicit publishability blocker classification during semantic-lane remediation.

## Impact

- Affected modules:
  - `Keep_of_Doom`
  - `Night_of_the_Restless_Dead`
  - `The_Hidden_City_of_Numillian`
- Excluded modules:
  - `Murder_at_the_Drowning_Lass`
  - `The_Ancients_Lab`
- Affected systems:
  - semantic-authority payload emission
  - publication-time destination alias/probe handling
  - Numillian provenance/sidecar closure
