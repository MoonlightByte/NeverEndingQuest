# Design: toolkit-monster-hydration-schema-sufficiency

## Context

The shared monster hydration helper currently resolves authorized monsters with this precedence:

1. existing local file
2. reusable file from another module
3. raw compendium copy
4. controlled generation

That precedence is structurally correct, but it lacks a schema-sufficiency boundary. The helper currently treats presence as success, not usability as success.

`Murder_at_the_Drowning_Lass` shows the failure clearly:

- `restless_spirit.json` already exists locally
- the local file is schema-incomplete
- hydration returns `source="existing"`
- readiness repair later attempts compendium backfill
- the compendium entry is also description-only
- convergence halts on `monster_schema_completion_gap`

## Goals

- Add a shared, deterministic schema-sufficiency boundary to monster hydration precedence.
- Ensure malformed local/reused/bestiary artifacts do not short-circuit better recovery paths.
- Preserve backward compatibility for valid existing monster files.
- Keep readiness repair as a secondary safety net rather than the only defense.

## Non-Goals

- Synthesizing missing monster fields from prose or LLM reasoning.
- Redesigning monster authorization or canonical-name resolution.
- Broadly restructuring toolkit readiness convergence.

## Decisions

### Decision: Hydration success SHALL require schema sufficiency, not mere presence
The shared helper SHALL only accept `existing`, `reuse`, or `bestiary` as successful hydration outcomes when the candidate payload contains the minimum required structured fields used by downstream validator/combat paths.

### Decision: Schema-incomplete deterministic sources SHALL fall through in precedence order
If a local existing file is schema-incomplete, the helper SHALL continue to check reusable files, then compendium-backed copy, then controlled generation. Likewise, schema-incomplete reusable or bestiary sources SHALL be skipped rather than accepted.

### Decision: Readiness repair remains additive and secondary
The readiness repair path SHALL remain in place for safe backfill of existing files when authoritative source data is available, but it SHALL no longer be expected to recover from malformed artifacts that were incorrectly accepted earlier as hydrated success.

### Decision: Shared helper behavior SHALL stay aligned across toolkit and runtime
Because `materialize_authorized_monster_file()` is shared by toolkit materialization and runtime hydration flows, the sufficiency boundary SHALL be implemented once in the shared helper and verified from both angles through focused regression coverage.

## Architecture

1. Add a narrow helper in `utils/module_monster_authority.py` that evaluates whether a monster payload is schema-sufficient for hydration acceptance.
2. Apply that helper at each precedence point in `materialize_authorized_monster_file()`:
   - local existing file
   - reusable cross-module file
   - compendium entry before raw write
3. Preserve current precedence order, but treat schema-incomplete candidates as skips rather than successful exits.
4. When generation is unavailable and all deterministic candidates are insufficient, return a structured failure instead of a false-success hydration result.
5. Keep readiness repair logic intact, but update regression coverage so malformed acceptance no longer masks the true remaining work.

## Risks / Trade-offs

- Narrow sufficiency checks reduce false success, but may expose residual content debt more explicitly in some existing modules.
- Shared-helper gating is the smallest correct fix, but it increases responsibility in one central path and therefore needs tight regression coverage.
- Using only the minimal required field set avoids overreach, but may still leave richer-schema debt for later steps; this change is intentionally focused on the blocker boundary.

## Migration Plan

1. Define the shared sufficiency boundary in spec deltas.
2. Implement the helper and thread it through shared precedence checks.
3. Add regression coverage for incomplete `existing`, `reuse`, and `bestiary` candidates.
4. Add a canary/regression proving `Murder_at_the_Drowning_Lass` no longer stalls because malformed `restless_spirit.json` was accepted as hydrated.
5. Verify no regression for valid existing monster files.

## Verification Plan

- Run `python3 -m py_compile` on the shared helper and touched test files.
- Run targeted hydration regressions in `scripts/test_homebrew_materialize_monsters.py`.
- Run targeted readiness regressions in `scripts/test_toolkit_homebrew_readiness_gate.py`.
- Run a shared-helper/runtime-oriented regression in `scripts/test_module_authorized_monster_hydration.py` if that file is touched.
- Confirm the canary behavior for `Murder_at_the_Drowning_Lass` is no longer blocked by false `existing` hydration acceptance.
