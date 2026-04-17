## 1. Shared Hydration Contract

- [x] 1.1 Add a shared monster hydration helper surface that returns structured authorization, hydration mode, and blocker-class outcomes for toolkit and runtime workflows.
- [x] 1.2 Define deterministic hydration precedence in the shared helper: existing local file, trusted reusable source, bestiary-backed materialization, controlled AI generation, then blocking failure.
- [x] 1.3 Ensure shared helper writes module-local monster files atomically and treats pre-existing valid files as idempotent success.

## 2. Authored Reference Discovery Parity

- [x] 2.1 Extend monster hydration inputs so packet-built modules can discover authorized monsters from generated module assets when `monsters_seed.json` is absent or incomplete.
- [x] 2.2 Update `scripts/homebrew_materialize_monsters.py` to use authored reference fallback discovery rather than seed-only lookup.
- [x] 2.3 Preserve backward compatibility so existing ingest-built modules with valid seed artifacts continue to hydrate without behavior regression.

## 3. Controlled AI Generation For Authored Non-Bestiary Monsters

- [x] 3.1 Define the controlled AI generation entrypoint for authorized monsters that lack reusable deterministic or bestiary-backed sources.
- [x] 3.2 Scope generation inputs to authored monster context only, including module/location prose and difficulty metadata needed to create 5e SRD-compatible stats.
- [x] 3.3 Classify generation failures into stable blocking outcomes such as unauthorized reference, provider unavailability, and authorized hydration failure.

## 4. Readiness, Finisher, And Runtime Integration

- [x] 4.1 Replace readiness-gate monster repair in `web/extensions/toolkit_homebrew_readiness_gate.py` with the shared monster hydration contract.
- [x] 4.2 Update `web/extensions/toolkit_module_finisher.py` and `scripts/homebrew_materialize_monsters.py` to reuse the same shared hydration path and structured result model.
- [x] 4.3 Align runtime-authorized monster hydration helpers so encounter-time hydration follows the same precedence order and authorization semantics.

## 5. Reporting And Artifacts

- [x] 5.1 Extend toolkit workspace/build/finisher reporting to expose monster hydration mode, normalized monster identity, and blocker classes without parsing freeform stderr.
- [x] 5.2 Ensure readiness and finisher artifacts preserve hydration diagnostics when validation remains blocked.
- [x] 5.3 Update toolkit UI reporting surfaces to distinguish deterministic reuse, bestiary hydration, controlled generation, unauthorized references, and provider failure states.

## 6. Regression Coverage

- [x] 6.1 Add tests for packet-built modules that have authored monster refs but no `monsters_seed.json`, proving shared hydration still discovers authorized monsters.
- [x] 6.2 Add tests for deterministic precedence order: existing file, reuse-first, bestiary-backed materialization, then controlled AI generation.
- [x] 6.3 Add tests for authorized bespoke monsters that require controlled AI generation and for unauthorized monsters that must fail closed.
- [x] 6.4 Add tests proving readiness and finisher now share the same hydration result semantics and stop conditions.

## 7. Verification

- [x] 7.1 Run targeted syntax validation for the shared hydration helper, readiness gate, finisher, and materialization script changes.
- [x] 7.2 Run targeted regression tests for packet-builder parity, hydration precedence, authorized bespoke monster generation, and reporting semantics.
- [x] 7.3 Run a real or fixture-based toolkit smoke path that reproduces the packet-build missing-monster case and confirm it reaches readiness success or a precise structured blocker instead of opaque retry exhaustion.
- [x] 7.4 Run `openspec validate toolkit-homebrew-monster-hydration-convergence`.
