## ADDED Requirements

### Requirement: Monster media handles SHALL include video assets

Media handle generation SHALL include monster video assets so ingest modules can expose deterministic references for `_video.mp4` files.

#### Scenario: Monster video present

- **WHEN** `media/monsters/<name>_video.mp4` exists for a module
- **THEN** media handles generation SHALL emit a handle for that video asset
- **AND** handle ordering and dedupe rules SHALL remain deterministic

#### Scenario: Images and video coexist

- **WHEN** both image and video assets exist for the same monster
- **THEN** handles generation SHALL include both without collisions
- **AND** existing image handle behavior SHALL remain unchanged
