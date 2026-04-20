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
Spatial coordinate planning SHALL be provided by a shared helper that can ground placement on room metadata and authored connectivity without duplicating caller logic.

#### Scenario: Shared helper supports builder, ingest, and remediation callers
- **GIVEN** builder, ingest, and remediation provide room records with ids and connectivity
- **WHEN** spatial planning runs through the shared helper
- **THEN** the helper SHALL return `coordinates`, `connectivity`, `directions`, and `layout`
- **AND** callers SHALL reuse this helper rather than implementing duplicate spatial planning logic

#### Scenario: Ingest uses authored adjacency before fallback ordering
- **GIVEN** the homebrew importer has extracted multiple rooms from source text
- **AND** room descriptions or room labels contain deterministic authored adjacency signals stronger than source order alone
- **WHEN** ingest prepares room records for spatial planning
- **THEN** the importer SHALL build connectivity from those authored adjacency signals before invoking the shared spatial planner
- **AND** SHALL NOT rely on previous/next room ordering as the primary graph when authored adjacency is available

#### Scenario: Structured parser fails open
- **GIVEN** malformed or incomplete structured spatial output
- **WHEN** parser validation fails
- **THEN** the helper SHALL fail open to deterministic fallback planning
- **AND** runtime/module generation SHALL continue without hard failure

### Requirement: Spatial validation SHALL be strict for new outputs and warn-first for legacy modules
Spatial validation SHALL enforce strict field-presence and geometric coherence checks for spatial-contract-marked modules while keeping legacy modules warn-first until remediated.

#### Scenario: Strict validation for marked modules
- **GIVEN** area/map artifacts with `spatialContractVersion`
- **WHEN** spatial validation runs
- **THEN** missing required spatial fields or incoherent cardinal directions SHALL fail validation

#### Scenario: Strict validation rejects non-adjacent connected rooms
- **GIVEN** a strict spatial-contract-marked area and map pair
- **AND** two rooms are directly connected in authored connectivity
- **WHEN** their emitted coordinates are not cardinally adjacent under the module spatial contract
- **THEN** validation SHALL fail with both room ids and file context

#### Scenario: Strict validation rejects direction-coordinate contradictions
- **GIVEN** a strict spatial-contract-marked map room includes a cardinal direction target
- **WHEN** the target room coordinate delta does not match that cardinal direction
- **THEN** validation SHALL fail rather than accepting the direction entry as shape-only metadata

#### Scenario: Legacy warn-first behavior without runtime breakage
- **GIVEN** legacy modules without spatial contract markers
- **WHEN** spatial validation runs
- **THEN** missing spatial fields or geometric incoherence SHALL be reported as warnings
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

### Requirement: Spatial remediation SHALL synchronize paired map artifacts after area repair

When deterministic spatial repair changes an area room coordinate graph and the paired `map_*.json` file is directly mappable by room id, remediation SHALL synchronize the paired map artifact before classifying residual contradictions as debt.

#### Scenario: Area repair leaves stale map coordinates

- **WHEN** an area file has been repaired to cardinal adjacency
- **AND** the paired `map_*.json` file still contains the old non-cardinal coordinates for the same room ids
- **THEN** deterministic remediation SHALL synchronize the paired map coordinates and dependent direction data when that mapping is unambiguous
- **AND** only unchanged contradictions after parity sync attempt may escalate to residual structural debt

### Requirement: Residual spatial reporting SHALL distinguish unchanged authored contradictions from repair-engine gaps

Spatial residual reporting SHALL separate unchanged contradiction sets that survive deterministic remediation from contradictions that changed but still failed validation.

#### Scenario: Unchanged contradiction set becomes authored structural debt

- **WHEN** deterministic spatial remediation runs
- **AND** the post-repair `spatial_contract` contradiction set is identical to the pre-repair contradiction set
- **THEN** residual reporting SHALL classify the result as authored structural debt
- **AND** SHALL NOT report that outcome as blocker-resolution advancement

#### Scenario: Changed contradiction set remains repair-engine gap

- **WHEN** deterministic spatial remediation changes the contradiction set but validation still fails
- **THEN** residual reporting SHALL classify the outcome as an unresolved repair-engine gap
- **AND** SHALL preserve both pre-change and post-change contradiction context

### Requirement: Residual spatial contradictions SHALL either converge or escalate explicitly

When shared spatial remediation is re-run during residual closure, unchanged contradiction sets SHALL be escalated as author-required structural debt instead of being retried implicitly.

#### Scenario: Spatial remediation resolves contradiction set

- **WHEN** residual closure re-runs shared spatial remediation for a module with adjacency contradictions
- **AND** the contradiction set is reduced or eliminated
- **THEN** reporting SHALL record that spatial closure advanced

#### Scenario: Spatial contradiction set remains unchanged

- **WHEN** residual closure re-runs shared spatial remediation
- **AND** the contradiction set after remediation is unchanged
- **THEN** reporting SHALL classify the result as unresolved structural spatial debt
- **AND** the workflow SHALL stop rather than retrying equivalent remediation again

### Requirement: Spatial remediation SHALL classify fixed-point adjacency contradictions

Spatial remediation MUST stop and classify unresolved connected-room adjacency contradictions when repeated planning produces no further change.

#### Scenario: Connected rooms remain non-cardinal after remediation
- **GIVEN** strict spatial validation reports two directly connected rooms whose coordinates are not cardinally adjacent
- **AND** a subsequent remediation pass produces no coordinate or direction delta
- **WHEN** convergence evaluation runs
- **THEN** the workflow SHALL classify the result as residual spatial contradiction debt
- **AND** SHALL NOT continue retrying unchanged spatial blockers

### Requirement: Shared planner SHALL be reused for convergence repair

Spatial convergence repair SHALL reuse the shared planner rather than introducing a parallel coordinate fixer.

#### Scenario: Convergence repair reruns spatial planning
- **GIVEN** a module area/map pair with strict spatial contradictions
- **WHEN** deterministic convergence repair executes
- **THEN** it SHALL reuse the shared spatial planner and authored connectivity as the source of truth
- **AND** any rewritten coordinates and directions SHALL remain mutually consistent under strict validation

