# Stub Validator Schema Hallucination Issue

**Date:** 2026-02-22
**Severity:** High
**Status:** Identified
**Affects:** All stub-generated validators (T035, T051, T054, T065, T067, T077, T078, T090)

---

## Problem Summary

The stub validator generation in `discover_validators.py` is inferring incorrect schemas for API outputs, causing false positive validation failures. This was discovered when T051 reported a 100% failure rate (0/28 variants passed) despite all model outputs being structurally correct and producing identical results.

## Root Cause

When `discover_validators.py` creates stub validators, it attempts to infer the expected output schema without analyzing:
1. The actual system prompt (which defines the required output format)
2. The callsite code (which shows how the response is parsed)
3. Existing validation logic (which defines acceptance criteria)

This results in hallucinated schemas that don't match reality.

## Example: T051 (Character Validator)

**Task:** `core/validation/character_validator.py:963`
**Purpose:** Validates character Armor Class calculations

**Actual Output Format** (from system prompt):
```json
{
  "validated_character_data": {
    "name": "Scout Kira",
    "armorClass": 16,
    ...
  },
  "corrections_made": [
    "Updated AC from 15 to 16..."
  ],
  "ac_calculation_breakdown": {
    "base_armor": "Studded Leather (12)",
    "dex_modifier": "+4",
    "shield_bonus": "0",
    "total_ac": "16"
  }
}
```

**Stub Validator's Inferred Schema** (incorrect):
```python
EXPECTED_SCHEMA = {
    "type": "object",
    "required": ["valid"],  # <-- This field doesn't exist!
    "properties": {
        "valid": {"type": "boolean"}
    }
}
```

**Result:**
- Validation error: `"Missing required field: valid"`
- All 28 variants (14 models × 2 captures) marked as FAILED
- Actual outputs: All correct and identical (AC = 16)

## Impact

**False Negative Rate:** Unknown (requires audit)

**Known Affected Tasks:**
- T051: 0/28 passed (100% false failures)
- T054: 0/14 passed (100% false failures)
- T065: 20/34 passed (41% false failures?)
- T067: 52/60 passed (13% false failures?)
- T078: 27/28 passed (4% false failures?)

**Tasks Requiring Audit:**
- T035, T051, T054, T065, T067, T077, T078, T090

## Evidence

### Validation Report Data
```
Total Captures Analyzed: 41
Total Variants Tested: 230
Passed: 165/230 (71.7%)
Failed: 65/230 (28.3%)
```

### T051 Detailed Errors
All variants show:
```json
{
  "valid": false,
  "errors": [
    "Output contains markdown code blocks",
    "Missing required field: valid"
  ]
}
```

### Actual T051 Outputs
Inspection of `model_captures/T051.json` shows:
- Baseline (gpt-4.1): AC = 16 ✓
- All GPT-5.2 variants: AC = 16 ✓
- All GPT-5-mini variants: AC = 16 ✓
- All Gemini variants: AC = 16 ✓

**All models produced correct, identical outputs.**

## Capture File Integrity

Verified capture timestamps:
```
Capture script finalized: Feb 19, 22:48
Recent captures: Feb 21, 23:44-23:46

✓ T051.json: Feb 21 23:46 (AFTER script finalized)
✓ T054.json: Feb 21 23:46 (AFTER script finalized)
✓ T065.json: Feb 21 23:46 (AFTER script finalized)
✓ T067.json: Feb 21 23:45 (AFTER script finalized)
✓ T078.json: Feb 21 23:46 (AFTER script finalized)
✓ T079.json: Feb 21 23:45 (AFTER script finalized)
✓ T082.json: Feb 21 23:44 (AFTER script finalized)
```

All critical captures were created with the finalized capture system. **Captures are valid.**

## Required Actions

### Immediate (Critical)
1. ✅ Document issue
2. ⏳ Audit all stub validators to identify schema mismatches
3. ⏳ Regenerate validators with correct schemas
4. ⏳ Re-run validation analysis with corrected validators

### Short-Term (Phase 2)
1. Implement agent-based validator generation per design doc
2. Each agent reads:
   - System prompt (extract actual schema)
   - Callsite code (understand usage)
   - Existing validators (extract rules)
3. Generate intelligent validators with real schemas

### Long-Term (Prevention)
1. Add schema extraction from system prompts to validator generation
2. Add validator self-test (run against known-good captures)
3. Add schema mismatch detection in analysis script
4. Consider JSON Schema validation library integration

## Design Reference

See: `docs/plans/2026-02-22-capture-validation-system-design.md`

**Quote from design (line 86-89):**
> For each task (e.g., T079), the agent reads:
> 1. **System prompt** from capture → Extract expected JSON schema/structure
> 2. **Callsite code** at `path:line` from inventory → Understand how response is parsed/used
> 3. **Existing validators** (if referenced) → Extract validation rules

**Current Implementation Status:** Stub validators skip steps 1-3, causing hallucinations.

## Workaround

For now, tasks with 100% failure rates (T051, T054) should be treated as "validator error, outputs likely correct." Manual inspection of capture files can confirm actual model outputs.

## Next Steps

1. Dispatch audit agents to validate schemas for all affected validators
2. Generate corrected validators based on audit findings
3. Re-run analysis with corrected validators
4. Update validation summary with accurate pass/fail rates

---

**Filed By:** Multi-Model Capture Validation System
**Priority:** High (blocks accurate model comparison)
**Related:** Design doc, implementation plan, T051-T090 validators
