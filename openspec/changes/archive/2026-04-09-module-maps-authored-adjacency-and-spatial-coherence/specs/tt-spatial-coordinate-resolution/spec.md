## MODIFIED Requirements

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
