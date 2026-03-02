# homebrew_media_handles.py

## ADDED Requirements

### Requirement: Deterministic Handle Manifest
The tool SHALL emit a deterministic media handle manifest for each module.

#### Scenario: Manifest generation
Given extracted media references for a module
When handle generation runs
Then it SHALL write `modules/<slug>/media/media_handles.json`
And each entry SHALL include stable `handle_id`, `kind`, `source_ref`, and `storage_relpath`

### Requirement: Failed media references preserved
The tool SHALL preserve unresolved references in the manifest.

#### Scenario: Download failure
Given a detected image URL that could not be downloaded
When handle generation runs
Then the manifest SHALL still include an entry for that source_ref
And set `download_status` to `failed` or `missing`

### Requirement: Future use flags
The tool SHALL mark future consumer hints in each handle.

#### Scenario: Title handle future flag
Given a handle classified as title image
When manifest is emitted
Then `future_use.chat_title_candidate` SHALL be true

#### Scenario: Map handle future flag
Given a handle classified as map image
When manifest is emitted
Then `future_use.map_tab_candidate` SHALL be true

## ADDED Interface

### CLI
```bash
python scripts/homebrew_media_handles.py \
  --slug <module_slug> \
  [--json]
```
