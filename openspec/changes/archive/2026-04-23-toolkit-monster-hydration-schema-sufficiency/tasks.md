# Tasks: toolkit-monster-hydration-schema-sufficiency

## 1. Shared Sufficiency Contract
- [x] 1.1 Define the minimum monster-schema sufficiency boundary for hydration acceptance in the shared helper path.
- [x] 1.2 Define the failure semantics for schema-incomplete `existing`, `reuse`, and `bestiary` candidates.
- [x] 1.3 Confirm the boundary preserves backward compatibility for valid existing monster files.

## 2. Shared Hydration Precedence Hardening
- [x] 2.1 Implement a reusable schema-sufficiency helper in `utils/module_monster_authority.py`.
- [x] 2.2 Update `materialize_authorized_monster_file()` so schema-incomplete local existing files do not short-circuit hydration success.
- [x] 2.3 Update reusable cross-module file handling so schema-incomplete reuse candidates are skipped.
- [x] 2.4 Update compendium-backed raw copy handling so schema-incomplete bestiary entries fall through to controlled generation when available.
- [x] 2.5 Ensure generation-disabled paths fail closed with structured blocker output when no schema-sufficient deterministic source exists.

## 3. Toolkit Convergence Alignment
- [x] 3.1 Preserve the existing readiness repair path as a secondary safety net rather than the primary fix for malformed hydration success.
- [x] 3.2 Verify toolkit materialization/reporting still distinguishes `existing`, `reuse`, `bestiary`, and `generated` outcomes after sufficiency gating.
- [x] 3.3 Confirm the canary failure mode for `Murder_at_the_Drowning_Lass` no longer depends on accepting malformed `restless_spirit.json` as hydrated success.

## 4. Regression Coverage
- [x] 4.1 Add a regression where a schema-incomplete local existing file falls through instead of returning `source="existing"`.
- [x] 4.2 Add a regression where a schema-incomplete reusable file is skipped instead of being copied.
- [x] 4.3 Add a regression where a schema-incomplete compendium entry does not count as successful `bestiary` hydration.
- [x] 4.4 Add a regression covering the exact edge case: local file exists, compendium hit exists, but both are schema-incomplete.
- [x] 4.5 Add or update one shared-helper/runtime-oriented regression proving valid existing monster files still remain authoritative.

## 5. Verification
- [x] 5.1 Run targeted hydration regression tests.
- [x] 5.2 Run targeted toolkit readiness regression tests.
- [x] 5.3 Run targeted shared-helper/runtime regression tests if touched.
- [x] 5.4 Run a compile pass on all touched Python files.
