# tt-spatial-coordinate-resolution Specification

## Purpose
TBD - created by archiving change tt-spatial-coordinate-grounding. Update Purpose after archive.
## Requirements
### Requirement: Build and ingest outputs SHALL emit a shared spatial contract
Newly produced toolkit-builder and homebrew-ingest module artifacts SHALL emit the same authored spatial contract shape for location and map data.

#### Scenario: Builder output includes spatial contract fields
- **GIVEN** toolkit builder emits area and map payloads
- **THEN** each location SHALL include valid `coordinates` using `X#Y#`
- **AND** each location SHALL include non-empty `aliases`
- **AND** each location SHALL include a 9-cell `tactical_grid`
- **AND** each map room SHALL include a `directions` object scoped to cardinal keys

#### Scenario: Ingest output includes matching spatial contract fields
- **GIVEN** homebrew importer emits area and map artifacts
- **THEN** emitted locations SHALL include `coordinates`, `aliases`, and `tactical_grid`
- **AND** emitted map rooms SHALL include cardinal `directions`
- **AND** spatial contract version markers SHALL be emitted for strict validation paths

### Requirement: Spatial coordinate resolution SHALL be shared and semantically grounded
Spatial coordinate planning SHALL be provided by a shared helper that can ground placement on room metadata and connectivity without duplicating caller logic.

#### Scenario: Shared helper supports builder, ingest, and remediation callers
- **GIVEN** builder, ingest, and remediation provide room records with ids and connectivity
- **WHEN** spatial planning runs through the shared helper
- **THEN** the helper SHALL return `coordinates`, `connectivity`, `directions`, and `layout`
- **AND** callers SHALL reuse this helper rather than implementing duplicate spatial planning logic

#### Scenario: Structured parser fails open
- **GIVEN** malformed or incomplete structured spatial output
- **WHEN** parser validation fails
- **THEN** the helper SHALL fail open to deterministic fallback planning
- **AND** runtime/module generation SHALL continue without hard failure

### Requirement: Spatial validation SHALL be strict for new outputs and warn-first for legacy modules
Spatial validation SHALL enforce strict field-presence and coherence checks for spatial-contract-marked modules while keeping legacy modules warn-first until remediated.

#### Scenario: Strict validation for marked modules
- **GIVEN** area/map artifacts with `spatialContractVersion`
- **WHEN** spatial validation runs
- **THEN** missing required spatial fields or incoherent cardinal directions SHALL fail validation

#### Scenario: Legacy warn-first behavior without runtime breakage
- **GIVEN** legacy modules without spatial contract markers
- **WHEN** spatial validation runs
- **THEN** missing spatial fields SHALL be reported as warnings
- **AND** gameplay/runtime behavior SHALL remain fail-open until remediation is applied

### Requirement: Remediation SHALL preserve authored connectivity while backfilling spatial fields
Legacy remediation tooling SHALL backfill spatial contract fields without mutating authored connectivity intent.

#### Scenario: Remediation updates spatial fields and retains authored edges
- **GIVEN** legacy area/map data with missing spatial fields
- **WHEN** remediation runs
- **THEN** missing `coordinates`, `aliases`, `tactical_grid`, `directions`, and layout parity SHALL be backfilled
- **AND** pre-authored `connectivity` arrays SHALL remain unchanged except for safe normalization of invalid values

#### Scenario: Remediation supports non-destructive preview and apply
- **GIVEN** remediation CLI execution
- **WHEN** invoked with `--dry-run`
- **THEN** no files SHALL be modified
- **WHEN** invoked with `--apply`
- **THEN** remediated artifacts SHALL be written atomically

