# toolkit-static-media-runtime-cache Specification

## Purpose
TBD - created by archiving change static-media-strict-cache-rebuild. Update Purpose after archive.
## Requirements
### Requirement: Shared static NPC and monster media SHALL be treated as rebuildable runtime cache

`web/static/media/npcs` and `web/static/media/monsters` MUST be treated as disposable runtime fallback populated from active packs, not as canonical long-lived media storage.

#### Scenario: Operator audits live static fallback
- **GIVEN** live static NPC and monster folders contain accumulated files
- **WHEN** the strict-cache audit runs in dry-run mode
- **THEN** it SHALL report which files come from active packs
- **AND** which files would be treated as orphaned or stale during rebuild

### Requirement: Strict-cache rebuild MUST clear live static NPC and monster folders before repopulation

Rebuild behavior MUST replace additive drift with clear-and-repopulate semantics for the NPC and monster fallback folders.

#### Scenario: Rebuild executes against active packs
- **GIVEN** one or more active graphic packs are present
- **WHEN** strict-cache rebuild executes
- **THEN** it SHALL clear `web/static/media/npcs` and `web/static/media/monsters`
- **AND** repopulate them only from active-pack assets

#### Scenario: Unrelated static media folders remain untouched
- **GIVEN** sibling folders such as `web/static/media/videos` or `web/static/media/environment` exist
- **WHEN** strict-cache rebuild executes
- **THEN** it SHALL NOT delete or rewrite those out-of-scope folders in this slice

### Requirement: Strict-cache rebuild MUST support reviewable backup and collision reporting

Destructive rebuild MUST be preceded by operator-reviewable diagnostics and a reversible backup path.

#### Scenario: Backup and collision report before rebuild
- **GIVEN** live static fallback contains files that overlap or conflict with active-pack inputs
- **WHEN** the operator requests strict-cache rebuild
- **THEN** the workflow SHALL provide a backup or snapshot path before deletion
- **AND** SHALL report filename collisions or overwrite candidates explicitly

### Requirement: Runtime fallback behavior SHALL remain compatible with module-first resolution

This change SHALL clean the shared fallback surface without changing the existing runtime preference for module-local media.

#### Scenario: Module-local media exists
- **GIVEN** a requested NPC or monster image exists in `modules/<module>/media`
- **WHEN** runtime media resolution occurs
- **THEN** the module-local asset SHALL remain preferred over shared static fallback

