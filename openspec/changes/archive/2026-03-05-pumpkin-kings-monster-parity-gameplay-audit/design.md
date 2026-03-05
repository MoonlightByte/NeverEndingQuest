## Context

Current module state is schema-valid for many artifacts, but runtime monster resolution is not guaranteed. In tabletop mode, missing `monsters/<slug>.json` is a hard blocker for encounter materialization.

## Objectives

- Ensure every active monster reference resolves to a concrete monster JSON file.
- Ensure naming parity across reference text -> normalized slug -> monster file -> media file.
- Provide a deterministic gameplay audit command that reports blocking issues before session launch.

## Decision Rules

- MUST preserve existing area and plot structures.
- MUST keep edits additive and contract-safe.
- MUST use runtime slug normalization rules (`normalize_character_name`) for filenames.
- SHOULD source baseline stat patterns from existing module ecosystem (Thornwood / Keep templates) and tune for Pumpkin module level band.

## Implementation Plan

### Phase 1 - Monster JSON parity

Create all missing monster files in `modules/The_Pumpkin_Kings_Curse/monsters/` matching active area references.

Each file MUST satisfy `schemas/mon_schema.json` required keys.

### Phase 2 - Media slug parity

Add alias media files where punctuation mismatches can cause lookups to fail (for example `rune-scarred_vermin` vs `rune_scarred_vermin`).

### Phase 3 - Gameplay audit tooling

Create `scripts/audit_module_gameplay.py`:
- Extract monster refs from active area files (exclude `*_BU.json`)
- Normalize ref names to runtime slugs
- Check monster JSON existence and parseability
- Check required schema fields
- Check media parity
- Emit blocking/warning/fix-list report and nonzero exit on blockers

Create skill `.opencode/skills/module-gameplay-audit/SKILL.md` to standardize usage.

## Data Contracts

- Monster filenames MUST equal normalized slug for each referenced monster.
- No refactor of existing area `locations[].monsters` shape.
- New audit output contract:
  - `blocking_errors`
  - `warnings`
  - `coverage_stats`
  - `fix_list`

## Risks

- Stat tuning imbalance if all monsters are copied without CR adjustment.
  - Mitigation: targeted CR band tuning for 1-3 adventure flow.
- Hidden reference sources in freeform instructions.
  - Mitigation: audit should parse structural references and optionally scan instruction text heuristically.

## Verification

- `python core/validation/validate_module_files.py`
- `python scripts/audit_module_gameplay.py --module The_Pumpkin_Kings_Curse`
- Baseline comparison:
  - `python scripts/audit_module_gameplay.py --module The_Pumpkin_Kings_Curse --baseline The_Thornwood_Watch`
