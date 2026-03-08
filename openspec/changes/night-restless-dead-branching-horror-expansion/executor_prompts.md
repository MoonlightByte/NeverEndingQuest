# Executor Prompts - night-restless-dead-branching-horror-expansion

## Prompt 1 - Preflight Gates and Safe Scaffolding

### Tier
Full (Builder default)

### MUST
- Work only in `modules/Night_of_the_Restless_Dead/` and `openspec/changes/night-restless-dead-branching-horror-expansion/`.
- Do not modify core engine/web/runtime Python for this prompt.
- Run ingest gate check:
  - `python3 scripts/homebrew_sidecar_audit.py --slug Night_of_the_Restless_Dead --require-success --json`
- Run module validation gate:
  - `python3 core/validation/validate_module_files.py --module Night_of_the_Restless_Dead --json`
- If strict validator cannot run (for example missing `jsonschema`), record degraded mode and execute JSON parse checks on planned target files.
- Produce a gate report with explicit status per gate (`PASS`, `DEGRADED`, `FAIL`) and blocking reasons.
- Add only scaffolding-safe narrative placeholders (no destructive rewrites):
  - Add empty or minimal branch metadata containers in `module_plot.json`.
  - Add empty or minimal faction/context containers in `module_context.json`.
  - Preserve all required schema fields and existing ingest metadata keys.

### SHOULD
- Keep placeholder field names short and self-explanatory.
- Keep branch containers close to existing plot points to ease later implementation.
- Keep notes ASCII-only and deterministic.

### Verification Gate
- `python3 -m py_compile scripts/homebrew_sidecar_audit.py core/validation/validate_module_files.py`
- Re-run:
  - `python3 scripts/homebrew_sidecar_audit.py --slug Night_of_the_Restless_Dead --require-success --json`
  - `python3 core/validation/validate_module_files.py --module Night_of_the_Restless_Dead --json`
- If degraded validation mode is active, run fallback parse checks:
  - `python3 -c "import json; json.load(open('modules/Night_of_the_Restless_Dead/module_plot.json')); json.load(open('modules/Night_of_the_Restless_Dead/module_context.json')); json.load(open('modules/Night_of_the_Restless_Dead/areas/NIG001.json')); json.load(open('modules/Night_of_the_Restless_Dead/npcs_seed.json')); print('JSON parse OK')"`

### Next Step
Proceed to Prompt 2 to populate branch choices, climax outcomes, and morally gray faction content.

---

## Prompt 2 - Branch and Faction Population (to run after Prompt 1)

Populate branch metadata, morally gray outcomes, and standalone cross-module references while keeping additive edits and validation safety.

---

## Prompt 3 - Final Verification and Closure (to run after Prompt 2)

Run full validation/audit checks, finalize OpenSpec task status, and produce implementation summary.
