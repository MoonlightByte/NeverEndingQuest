## Why

`modules/Night_of_the_Restless_Dead` is currently a linear combat crawl with thin motivations and low replay value. We need a post-ingest narrative expansion that adds meaningful player choice, preserves module validator compatibility, and ties lightly into the current worldline without creating hard dependencies.

## What Changes

- Add a morally gray horror storyline where the cathedral cult are both perpetrators and victims of a wider curse.
- Expand module flow from single-path to branch-capable progression while preserving the canonical PP001->PP007 backbone.
- Add additive investigation hooks and choice-driven outcomes in `areas/NIG001.json` and `module_plot.json`.
- Add additive NPC/cult context in `module_context.json` and `npcs_seed.json` with no destructive key rewrites.
- Introduce a contained ring thread (this module + one future module TBC), not a world-spanning hard dependency.
- Add minor cross-module references to Pumpkin King and Thornwood arcs as optional flavor only.
- Add verification gates aligned to homebrew ingest audit and module validation tooling.

## Capabilities

### New Capabilities
- `restless-dead-branching-investigation`: The module supports investigation-first and confrontation-first traversal with additive branch metadata.
- `restless-dead-moral-gray-faction-resolution`: The climax supports morally gray faction outcomes (help, oppose, or negotiate) with distinct consequences.
- `restless-dead-standalone-minor-world-links`: Cross-module references remain optional and do not gate progression.
- `restless-dead-ingest-validation-gates`: Expansion workflow enforces ingest-audit and module-validator pre/post checks with explicit degraded handling.

### Modified Capabilities
- None.

## Impact

- **Content files**: `modules/Night_of_the_Restless_Dead/module_plot.json`, `modules/Night_of_the_Restless_Dead/module_context.json`, `modules/Night_of_the_Restless_Dead/areas/NIG001.json`, `modules/Night_of_the_Restless_Dead/npcs_seed.json`.
- **Optional content additions**: New additive seed/support files under `modules/Night_of_the_Restless_Dead/`.
- **Tooling/verification**: `scripts/homebrew_sidecar_audit.py`, `core/validation/validate_module_files.py` execution contracts documented in tasks.
- **Compatibility**: No API break, no schema contract removals, no upstream host-file rewrite.

## Contract Layer (MUST)

- MUST keep edits additive in module JSON (no key removals/renames of existing ingest output contracts).
- MUST preserve standalone playability and keep cross-module links optional.
- MUST keep undead roster class stable (zombie/skeleton/spider baseline) unless explicitly approved later.
- MUST run ingest-audit and module-validation gates (or explicit degraded fallback when environment lacks dependencies).

## Guidance Layer (SHOULD)

- SHOULD keep narrative tone implication-first horror with restrained occult detail.
- SHOULD place branch hooks in existing structures rather than introducing large new structural schemas.
- SHOULD keep branch consequences legible through in-world evidence rather than hidden meta logic.
