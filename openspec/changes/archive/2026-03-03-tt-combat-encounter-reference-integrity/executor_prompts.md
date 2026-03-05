## Kimi Builder Execution Prompts - tt-combat-encounter-reference-integrity

Use this file as the plan-to-builder handoff for encounter reference integrity and combat failure surfacing hardening.

---

## Execution Contract

- MUST keep fail-closed tabletop monster behavior (do not re-enable monster auto-create in TT mode).
- MUST preserve single-player behavior and existing combat phase semantics.
- MUST mark host integration edits with `# TABLETOP MODE:` where applicable.
- MUST apply one anchored patch at a time and run compile/tests between prompts.
- MUST keep Python-visible text ASCII-only.
- SHOULD prefer additive validator checks and thin hooks over broad refactors.

---

## Prompt 1 - Add Monster Reference Integrity Validator

Implement tasks `1.1` to `1.4` from `tasks.md`.

Scope:
- `core/validation/validate_module_files.py`

Requirements:
- Add deterministic monster reference normalization helper aligned with combat lookup slugging.
- Add `validate_monster_references()` that scans `areas/*.json` references and verifies `monsters/<slug>.json` files exist.
- Record detailed failures in `results['reference_integrity']`.
- Wire into `run_all_validations()` and `print_report()` output ordering.

Verify before moving on:
- `python3 -m py_compile core/validation/validate_module_files.py`

---

## Prompt 2 - Enforce in Ingest and Activation Paths

Implement tasks `2.1` to `2.4`.

Scope:
- `core/importers/homebrewery_importer.py`
- `web/extensions/module_ingest_watch.py` (if needed for explicit status wiring)
- module activation/copy route(s) in `web/` where modules are registered/selected for campaign use

Requirements:
- Ensure strict ingest quarantines unresolved reference failures via existing validation pipeline.
- Ensure watcher path does not bypass strict validation failures.
- Add module activation/copy preflight validation gate and block on unresolved refs.
- Emit concise `[SYSTEM]` summary when blocked and preserve detailed error logging/sidecar.

Verify before moving on:
- `python3 -m py_compile core/importers/homebrewery_importer.py web/extensions/module_ingest_watch.py`

---

## Prompt 3 - Runtime Failure Messaging and Narration Gate

Implement tasks `3.1` to `3.4`.

Scope:
- `core/ai/action_handler.py`
- `main.py`

Requirements:
- Enrich failed `createEncounter` `error_message` with actionable missing monster/stat-file context when available.
- Preserve `[SYSTEM]` append behavior for action errors.
- Prevent combat narration emission when a turn includes failed `createEncounter`.
- Keep non-combat and successful-combat narration behavior unchanged.

Verify before moving on:
- `python3 -m py_compile core/ai/action_handler.py main.py`

---

## Prompt 4 - Tests and Final Verification

Implement tasks `4.1` to `5.4`.

Scope:
- `scripts/` regression tests for validator/ingest/runtime behavior
- validation only for final gate

Required commands:
- `python3 -m py_compile core/validation/validate_module_files.py core/importers/homebrewery_importer.py core/ai/action_handler.py main.py`
- Run targeted tests created/updated in this change.
- `python3 core/validation/validate_module_files.py` (or module-targeted invocation if added)
- `openspec validate tt-combat-encounter-reference-integrity`

Manual smoke checklist:
1. Module with unresolved area monster reference is blocked before gameplay.
2. Strict ingest returns quarantined status with clear validation errors.
3. Failed `createEncounter` produces actionable `[SYSTEM]` error.
4. No combat-flavored narration is shown for failed combat start.

---

## Stop Conditions

- Stop immediately if any patch weakens TT fail-closed monster policy.
- Stop and fix if single-player behavior changes.
- Stop and fix if validator false-positives valid module references.
- Do not expand scope into unrelated combat manager refactors.
