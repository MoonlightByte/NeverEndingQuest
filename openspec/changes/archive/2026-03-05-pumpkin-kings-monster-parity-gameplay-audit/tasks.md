## 1. Build monster parity foundation

- [x] 1.1 Create missing monster JSON files for all 21 unresolved slugs in Pumpkin King's Curse.
- [x] 1.2 Ensure each new monster file passes `schemas/mon_schema.json` requirements.
- [x] 1.3 Validate slug naming parity using runtime normalization rules.

## 2. Align media parity

- [x] 2.1 Identify media slug mismatches for referenced monsters.
- [x] 2.2 Add additive alias media files (no removals) for mismatch cases.

## 3. Add gameplay audit tooling

- [x] 3.1 Create `scripts/audit_module_gameplay.py` with blocking/warning output groups.
- [x] 3.2 Add module/baseline comparison mode.
- [x] 3.3 Enforce nonzero exit code on blocking resolution failures.

## 4. Add skill contract

- [x] 4.1 Create `.opencode/skills/module-gameplay-audit/SKILL.md`.
- [x] 4.2 Include trigger phrases and output contract.

## 5. Verify and handoff

- [x] 5.1 Run module schema validation.
- [x] 5.2 Run gameplay audit for Pumpkin King's Curse.
- [x] 5.3 Confirm zero blocking monster-resolution errors.
- [x] 5.4 Document remaining warnings and follow-up tuning items.

## 6. Prompt E/F/G completion notes

- [x] 6.1 Prompt E completed: Added regression suite for structural extraction, strict-mode severity, output contract, and exit behavior.
- [x] 6.2 Prompt F completed: Added heuristic false-positive guardrails while preserving valid heuristic extraction and strict escalation contracts.
- [x] 6.3 Prompt G completed: OpenSpec docs updated and final verification re-run for handoff/archive readiness.
