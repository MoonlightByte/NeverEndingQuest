# module-plot-progression-path-validation Specification

## Purpose
TBD - created by archiving change module-runtime-progression-validation. Update Purpose after archive.
## Requirements
### Requirement: Module validator SHALL enforce graph-valid plot progression locations
The module validator SHALL verify that the module starting location, `plotPoints[*].location`, and explicit branch metadata paths are reachable under the authored runtime room graph.

#### Scenario: Plot point location is unreachable from module start
- **WHEN** a plot point declares a `location`
- **AND** the module starting location exists
- **AND** the plot point location is unreachable from the module start under the runtime room graph
- **THEN** validation SHALL fail with the plot point ID and unreachable location ID

#### Scenario: Explicit branch path contains a broken step
- **WHEN** branch metadata declares an explicit `path` array or `bypass` array of room IDs
- **AND** one or more consecutive steps in that path are not connected under the authored runtime room graph
- **THEN** validation SHALL fail with the branch identifier and the broken step pair

#### Scenario: Reachable plot progression passes
- **WHEN** plot point locations and explicit branch paths are reachable under the authored runtime room graph
- **THEN** plot progression path validation SHALL pass

### Requirement: Finale or conclusion progression SHALL remain gated by explicit upstream progression state
The module validator SHALL fail when a finale or conclusion beat is graph-valid but lacks explicit prerequisite or progression gating where the authored plot sequence otherwise indicates a downstream dependency.

#### Scenario: Conclusion beat lacks explicit prerequisite gate
- **WHEN** a module plot declares a downstream finale or conclusion plot point
- **AND** upstream plot points define a progression chain leading into that finale
- **AND** the finale lacks an explicit prerequisite or equivalent gating field linking it to its upstream dependency
- **THEN** validation SHALL fail with the finale plot point ID and the missing-gate reason

### Requirement: Deterministic plot repair SHALL target validator-identified failing conclusion edges

When validation identifies a missing prerequisite gate for a specific conclusion or finale plot point, deterministic repair SHALL target that failing edge directly.

#### Scenario: Validator identifies non-terminal conclusion node

- **WHEN** validation reports that `PP018` is missing an explicit prerequisite on `PP017`
- **AND** the numeric terminal node is a different plot point (for example `PP019`)
- **THEN** deterministic repair SHALL add the prerequisite to `PP018`
- **AND** SHALL NOT retarget the repair to the numerically last plot point

### Requirement: Deterministic finale prerequisite repair SHALL clear live plot progression failures when uniquely provable

When a finale or conclusion beat is missing an explicit upstream gate and the immediate predecessor is uniquely provable from the authored sequence, remediation SHALL apply that prerequisite against the live module plot shape and verify that the validator no longer reports the same failure.

#### Scenario: Live list-shaped plot data accepts prerequisite repair

- **WHEN** `module_plot.json` stores `plotPoints` as a list of objects with `id` fields
- **AND** finale `PP018` has no prerequisites
- **AND** `PP017` is the uniquely provable immediate predecessor
- **THEN** remediation SHALL write `prerequisites: ["PP017"]` to the live finale node
- **AND** post-repair validation SHALL no longer emit the same missing-gate failure

#### Scenario: Ambiguous prerequisite remains fail-closed

- **WHEN** no unique upstream predecessor can be proven for a finale or conclusion beat
- **THEN** remediation SHALL NOT invent a prerequisite
- **AND** the residual result SHALL classify the blocker as ambiguous plot debt

### Requirement: Finale prerequisite repair SHALL align with live module plot payload shapes

Residual plot-gate repair SHALL operate against the actual `module_plot.json` structures emitted by current toolkit modules rather than assuming a legacy-only shape.

#### Scenario: Live-shape finale receives uniquely provable prerequisite

- **WHEN** a live toolkit-emitted `module_plot.json` contains a finale or conclusion beat lacking explicit prerequisites
- **AND** a unique immediate upstream predecessor is provable from the authored plot sequence
- **THEN** residual repair SHALL add the explicit prerequisite gate to that finale beat

#### Scenario: Plot shape is present but predecessor is ambiguous

- **WHEN** the live plot payload shape is parseable
- **AND** no unique predecessor can be proven safely
- **THEN** residual repair SHALL classify the result as ambiguous plot-gating debt
- **AND** SHALL NOT insert a guessed prerequisite

### Requirement: Deterministic remediation SHALL repair uniquely provable finale prerequisites

When a finale or conclusion beat lacks explicit prerequisite gating but the upstream dependency chain is uniquely provable, remediation SHALL insert the missing prerequisite deterministically.

#### Scenario: Finale prerequisite is uniquely provable
- **GIVEN** validation reports a finale or conclusion beat missing an explicit prerequisite gate
- **AND** one upstream dependency is uniquely implied by the authored progression chain
- **WHEN** deterministic remediation runs
- **THEN** the missing prerequisite SHALL be added
- **AND** revalidation SHALL evaluate the repaired plot graph

#### Scenario: Finale prerequisite remains ambiguous
- **GIVEN** validation reports a missing finale prerequisite gate
- **AND** multiple upstream dependencies could satisfy the authored intent
- **WHEN** deterministic remediation runs
- **THEN** it SHALL NOT guess a prerequisite
- **AND** the result SHALL be classified as residual plot-gating debt

