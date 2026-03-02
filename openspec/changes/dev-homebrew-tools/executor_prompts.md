# Developer Homebrew Ingest Tools - Executor Prompts

## Prompt 1: homebrew_preflight.py

**Task:** Build readiness assessment tool

**Scope:**
- Read source markdown
- Detect title hygiene issues
- Check metadata completeness
- Classify structure (room-based vs act/location)
- Determine if auto-transform is possible

**CLI Contract:**
```bash
python scripts/homebrew_preflight.py \
  --source <path> \
  [--json]
```

**Output JSON:**
```json
{
  "ready": true|false,
  "issues": [...],
  "structure_class": "room_based|act_location|unknown",
  "can_auto_transform": true|false
}
```

**Stop Conditions:**
- Cannot read source file
- Invalid JSON output when --json specified

**Verification:**
```bash
python -m py_compile scripts/homebrew_preflight.py
python scripts/homebrew_preflight.py --source Docs/modules/hombrew/Mangrove.md --json
```

## Prompt 2: homebrew_transform_to_deterministic.py

**Task:** Build structural conversion tool

**Scope:**
- Strip title prefixes ("CLONE - ADVENTURE:", etc.)
- Inject metadata block if missing
- Convert ACT/LOCATION format to ## Room N: blocks
- Infer exits from location descriptions
- Add encounter placeholders

**CLI Contract:**
```bash
python scripts/homebrew_transform_to_deterministic.py \
  --source <input_path> \
  --output <output_path>
```

**Stop Conditions:**
- Source file not found
- Output path not writable
- Structure too complex to auto-transform

**Verification:**
```bash
python -m py_compile scripts/homebrew_transform_to_deterministic.py
python scripts/homebrew_transform_to_deterministic.py \
  --source Docs/modules/hombrew/Mangrove.md \
  --output /tmp/test_transform.md
cat /tmp/test_transform.md | head -50
```

## Prompt 3: homebrew_ingest_dev.py

**Task:** Build orchestration pipeline

**Scope:**
- Run full pipeline: preflight → transform → dry-run → guard → ingest → audit → verify
- Stop on any failure
- Generate comprehensive report

**CLI Contract:**
```bash
python scripts/homebrew_ingest_dev.py \
  --source <path> \
  [--strict] \
  [--json]
```

**Output JSON on success:**
```json
{
  "status": "success",
  "module_slug": "...",
  "areas": 8,
  "encounters": 3,
  "registry_verified": true
}
```

**Stop Conditions:**
- Preflight fails and cannot auto-transform
- Dry-run validation fails
- Registry guard finds conflicts
- Ingest quarantined
- Registry verification fails

**Verification:**
```bash
python -m py_compile scripts/homebrew_ingest_dev.py
python scripts/homebrew_ingest_dev.py \
  --source Docs/modules/hombrew/Mangrove.md \
  --strict --json
```

## Prompt 4: homebrew_sidecar_audit.py

**Task:** Build result validation tool

**Scope:**
- Find latest sidecar for module slug
- Validate status and registration block
- Enforce --require-success contract

**CLI Contract:**
```bash
python scripts/homebrew_sidecar_audit.py \
  --slug <module_slug> \
  [--require-success] \
  [--json]
```

**Output JSON:**
```json
{
  "valid": true|false,
  "sidecar_found": true|false,
  "status": "success|quarantined|...",
  "registration": {
    "registration_attempted": true|false,
    "registration_success": true|false,
    "registry_module_present": true|false
  }
}
```

**Verification:**
```bash
python -m py_compile scripts/homebrew_sidecar_audit.py
python scripts/homebrew_sidecar_audit.py \
  --slug "Birble_Adventuring_Academy" \
  --require-success --json
```

## Prompt 5: homebrew_registry_guard.py

**Task:** Build duplicate prevention tool

**Scope:**
- --check-duplicate: Check for slug/title conflicts
- --verify-present: Confirm module in registry
- --remove: Safe removal with backup

**CLI Contract:**
```bash
python scripts/homebrew_registry_guard.py \
  [--slug <slug> --check-duplicate] \
  [--slug <slug> --verify-present] \
  [--slug <slug> --remove]
```

**Output JSON:**
```json
{
  "safe_to_proceed": true|false,
  "conflicts": [...],
  "present": true|false,
  "removed": true|false
}
```

**Verification:**
```bash
python -m py_compile scripts/homebrew_registry_guard.py
python scripts/homebrew_registry_guard.py \
  --slug "Birble_Adventuring_Academy" \
  --verify-present --json
```

## Prompt 6: Integration Test

**Task:** End-to-end verification

**Steps:**
1. Use Mangrove Keep as test subject
2. Run full pipeline via homebrew_ingest_dev.py
3. Verify:
   - Module slug registered
   - Sidecar shows success
   - Toolkit API lists module
4. Document example session

**Stop Conditions:**
- Any step fails
- Registry verification fails
- Unexpected quarantine

**Verification:**
```bash
# Full pipeline test
python scripts/homebrew_ingest_dev.py \
  --source Docs/modules/hombrew/The_Secrets_of_Mangrove_Keep.md \
  --strict --json

# Verify registry
curl http://localhost:8357/api/toolkit/modules | grep Mangrove
```
