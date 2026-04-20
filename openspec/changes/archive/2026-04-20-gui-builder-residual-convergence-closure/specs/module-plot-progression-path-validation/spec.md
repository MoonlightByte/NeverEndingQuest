## ADDED Requirements

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
