## 1. Scope Lock

- [x] 1.1 Confirm Bucket A is limited to `The_Pumpkin_Kings_Curse` and `A_Pottsfield_Burial`.
- [x] 1.2 Record explicit out-of-scope exclusion for `Murder_at_the_Drowning_Lass` and `The_Ancients_Lab`.

## 2. Pumpkin Quick Win

- [x] 2.1 Define the semantic-authority payload closure needed for `The_Pumpkin_Kings_Curse`.
  - Ran `enrich_module_semantic_authority()` which derived 52 location aliases, 52 destination phrases, 37 NPC scene authorities, 0 ambiguous destinations, 0 missing NPC authority from authored area/plot files.
  - Payload written to `modules/The_Pumpkin_Kings_Curse/module_context.json` under `semantic_authority` key.
- [x] 2.2 Define the verification pass that proves Pumpkin moves from `ready=pass, publishable=fail` toward publishable success.
  - `audit_module_publishability.py --module The_Pumpkin_Kings_Curse --json` confirms: `ready_status=pass`, `publishable_status=pass`, `blocking_errors=[]`, semantic_audit=pass, semantic_probes=18/18 pass.

## 3. Pottsfield Quick Win

- [x] 3.1 Define the structural closure for `modules/A_Pottsfield_Burial/monsters/crawling_claws.json`.
  - Created `crawling_claws.json` by copying `crawling_claws_2.json` content (Tiny Undead, AC12, HP2, CR0).
  - Schema validation now includes `crawling_claws.json` in monster pass list (13/13 monsters pass).
- [x] 3.2 Define the module-local monster media closure for `modules/A_Pottsfield_Burial/media/monsters/crawling_claws.jpg`.
  - Media already existed under `crawling_claws` slug (base=true, thumb=true). No additional media creation needed.
- [x] 3.3 Define the verification pass that proves no additional Pottsfield blocker remains hidden after this bounded closure.
  - `audit_module_publishability.py --module A_Pottsfield_Burial --json` confirms: `ready_status=pass`, `publishable_status=pass`, `blocking_errors=[]`, `json_missing=0`, `json_coverage_pct=100.0`, semantic_audit=pass, semantic_probes=15/15 pass.

## 4. Publishability Review

- [x] 4.1 Keep readiness and publishability outcomes explicit in the review/verification plan.
  - Both modules now report `ready_status=pass, publishable_status=pass` with zero blocking errors.
- [x] 4.2 Capture a short operator sequence for rerunning Bucket A audits after each closure lands.
  - Operator sequence:
    1. `.venv/bin/python scripts/audit_module_publishability.py --module The_Pumpkin_Kings_Curse --json`
    2. `.venv/bin/python scripts/audit_module_publishability.py --module A_Pottsfield_Burial --json`
    3. Verify `blocking_errors=[]` and `publishable_status=pass` for both modules.
