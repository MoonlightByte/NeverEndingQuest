## ADDED Requirements

### Requirement: Runtime SHALL accept additive scene-authority metadata on locations
Runtime and schema validation SHALL accept optional `sceneAuthority.presentSceneAnchors` metadata on area locations so authors can identify present-scene anchors exclusive to that location.

#### Scenario: Annotated finale location declares exclusive anchors
- **GIVEN** a location includes `sceneAuthority.presentSceneAnchors`
- **THEN** each anchor SHALL declare an `anchorId`
- **AND** SHALL declare one or more `aliases`

#### Scenario: Unannotated location preserves legacy compatibility
- **WHEN** a location omits `sceneAuthority`
- **THEN** runtime and schema validation SHALL preserve legacy compatibility
- **AND** SHALL NOT require immediate remediation for that location

### Requirement: Initial metadata contract SHALL remain narrow
The first rollout of scene-authority metadata SHALL remain minimal and additive.

#### Scenario: Initial anchor contract stays bounded
- **THEN** the contract SHALL require only `anchorId` and `aliases`
- **AND** optional descriptive fields MAY exist without widening into a full semantic rule language

### Requirement: Runtime SHALL be able to index authored anchors by location
Runtime SHALL be able to build a module-local scene-authority index from authored location metadata.

#### Scenario: Metadata-driven anchor lookup
- **GIVEN** multiple locations in a module declare present-scene anchors
- **WHEN** runtime evaluates narrator output
- **THEN** it SHALL be able to determine which location owns a referenced anchor
