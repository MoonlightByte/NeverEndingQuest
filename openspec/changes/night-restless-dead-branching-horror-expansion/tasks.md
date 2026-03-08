## 1. Preflight and Gate Verification

- [x] 1.1 Re-run ingest sidecar audit for `Night_of_the_Restless_Dead` and record whether sidecar exists.
- [x] 1.2 Establish validation mode:
  - strict mode when `jsonschema` is available,
  - degraded mode with explicit fallback checks when unavailable.
- [x] 1.3 Create a short gate report in change notes with PASS/DEGRADED/FAIL per gate.

## 2. Branching Backbone Expansion

- [x] 2.1 Update `modules/Night_of_the_Restless_Dead/module_plot.json` with additive branch metadata while preserving PP001->PP007 chain.
- [x] 2.2 Add explicit climax outcome matrix (aid cult, oppose cult, negotiate) with consequence notes.
- [x] 2.3 Keep all existing required plot fields valid (`status`, `location`, `nextPoints`, `plotImpact`).

## 3. Area and Context Narrative Enrichment

- [x] 3.1 Update `modules/Night_of_the_Restless_Dead/areas/NIG001.json` with additive investigation hooks and player-choice prompts.
- [x] 3.2 Update `modules/Night_of_the_Restless_Dead/module_context.json` with moral-gray faction context and contained ring-thread metadata.
- [x] 3.3 Update `modules/Night_of_the_Restless_Dead/npcs_seed.json` with additive NPC seed entries aligned to revised storyline.
- [x] 3.4 Preserve creature roster class stability (no new creature types).

## 4. Standalone and Cross-Module Constraints

- [x] 4.1 Add minor Pumpkin King and Thornwood references as optional flavor only.
- [x] 4.2 Verify no branch requires external module completion.
- [x] 4.3 Keep ring thread bounded to this module + one future module placeholder.

## 5. Verification and Closure

- [x] 5.1 Run strict validator (or degraded fallback) on modified module files and record results.
- [x] 5.2 Run JSON parse sanity checks for all changed JSON files.
- [x] 5.3 Run `openspec validate night-restless-dead-branching-horror-expansion` and resolve findings.
- [x] 5.4 Produce implementation summary with final gate status table.
