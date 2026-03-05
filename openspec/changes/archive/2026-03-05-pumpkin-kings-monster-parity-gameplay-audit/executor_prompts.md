## Builder Execution Prompts - pumpkin-kings-monster-parity-gameplay-audit

### Prompt A - Populate missing monster JSON files

Implement missing monster registry files for `The_Pumpkin_Kings_Curse`.

Scope:
- `modules/The_Pumpkin_Kings_Curse/monsters/*.json`

Required:
- Create these files:
  - `animated_scarecrow.json`, `blight_tendril.json`, `bloodshadow.json`, `cornfield_shadow.json`, `grain_wraith.json`, `guardian_stone.json`, `harvest_shade.json`, `lantern_husk.json`, `nest_lurker.json`, `noose_wraith.json`, `protective_shadow.json`, `pumpkin_stalkers.json`, `rope_strangler.json`, `rune_scarred_vermin.json`, `scarecrow_sentinel.json`, `shadow_creeper.json`, `stirge_swarm.json`, `straw_blight.json`, `straw_husk.json`, `swarm_of_field_rats.json`, `the_pumpkin_king.json`.
- Ensure each satisfies `schemas/mon_schema.json` required keys.
- Keep stats consistent with module difficulty progression.

Forbidden:
- No changes to existing area IDs or plot flow.

Verify:
- JSON parse checks on all created files.

### Prompt B - Media slug parity aliases

Scope:
- `modules/The_Pumpkin_Kings_Curse/media/monsters/*`

Required:
- Add alias copies where normalized slugs and existing media slugs differ (example: rune_scarred_vermin).
- Do not remove or rename existing media files.

Verify:
- Audit reports no media lookup blockers for referenced monsters.

### Prompt C - Build gameplay audit script + skill

Scope:
- `scripts/audit_module_gameplay.py`
- `.opencode/skills/module-gameplay-audit/SKILL.md`

Required script behaviors:
- Accept `--module` and optional `--baseline`.
- Extract monster references from active area files.
- Normalize with runtime slug rules.
- Validate JSON existence + parse + required keys.
- Report in four sections: `blocking_errors`, `warnings`, `coverage_stats`, `fix_list`.
- Exit nonzero if blocking errors exist.

Required skill behaviors:
- Trigger phrases: `audit module gameplay`, `validate module gameplay`, `monster parity audit`.
- Run script and return concise summary.

### Prompt D - Final verification

Run:
- `python core/validation/validate_module_files.py`
- `python scripts/audit_module_gameplay.py --module The_Pumpkin_Kings_Curse`
- `python scripts/audit_module_gameplay.py --module The_Pumpkin_Kings_Curse --baseline The_Thornwood_Watch`

Acceptance:
- No blocking monster-resolution errors for Pumpkin King's Curse.
- Output includes unresolved warnings, if any, separately.

### Prompt E - Regression tests for gameplay audit stability

Scope:
- `scripts/test_audit_module_gameplay.py` (new)
- `scripts/audit_module_gameplay.py` (minimal fixes only if required)

Required:
- Add deterministic fixture-based regression tests for:
  - Structural extraction coverage (`locations[].monsters`, `randomEncounters[].monsters`, nested `createEncounter` payloads)
  - Heuristic extraction behavior and source attribution (`file`, `path`, `confidence`, `original`)
  - Strict-mode severity escalation (warnings in normal mode, blockers in strict mode)
  - Output contract stability (`blocking_errors`, `warnings`, `coverage_stats`, `fix_list`)
  - Exit behavior (0 with no blockers, 1 with blockers)

Verify:
- `python3 scripts/test_audit_module_gameplay.py`
- `python3 scripts/audit_module_gameplay.py --module The_Pumpkin_Kings_Curse`
- `python3 scripts/audit_module_gameplay.py --module The_Pumpkin_Kings_Curse --strict-instructions`

### Prompt F - Heuristic false-positive guardrails

Scope:
- `scripts/audit_module_gameplay.py`
- `scripts/test_audit_module_gameplay.py`

Required:
- Reduce heuristic false positives from prose/instruction text.
- Keep extraction for likely monster-entity names.
- Add regression proving generic clause text (for example, "but can be avoided with stealth") is not extracted.
- Preserve Prompt E contracts and strict-mode behavior.

Verify:
- `python3 scripts/test_audit_module_gameplay.py`
- `python3 scripts/audit_module_gameplay.py --module The_Pumpkin_Kings_Curse`
- `python3 scripts/audit_module_gameplay.py --module The_Pumpkin_Kings_Curse --strict-instructions`

### Prompt G - OpenSpec closure and archive readiness

Scope:
- `openspec/changes/pumpkin-kings-monster-parity-gameplay-audit/tasks.md`
- `openspec/changes/pumpkin-kings-monster-parity-gameplay-audit/executor_prompts.md`

Required:
- Mark completed tasks and capture Prompt E/F completion notes.
- Record verification outcomes:
  - tests: 20/20 PASS
  - normal mode: exit 0
  - strict mode: exit 0
  - baseline: JSON 55.6% -> 100.0%, media 100.0% -> 100.0%
- Keep CLI output contract unchanged (`blocking_errors`, `warnings`, `coverage_stats`, `fix_list`).

Verify:
- `openspec validate pumpkin-kings-monster-parity-gameplay-audit`
