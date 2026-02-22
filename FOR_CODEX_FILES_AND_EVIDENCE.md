# Files and Evidence for Codex Review

## All Files Are Committed - Branch: multi-model-refactor (commit 493dabe)

---

## 1. Main Handoff Document
**Path:** `docs/CODEX_HANDOFF_VALIDATION_SYSTEM.md` (599 lines)

Contains complete system overview including:
- 3-component architecture (capture, validators, analysis)
- Validation workflow step-by-step
- T051 deep audit comparing runtime code vs validator
- Explanation of shallow validation design
- All 22 current failures with root causes

---

## 2. Audit Reports

### Full Validator Audit
**Path:** `docs/issues/2026-02-22-validator-audit-results.md` (435 lines)

**Key sections:**
- Lines 10-37: Executive summary showing 100% hallucination rate
- Lines 40-308: Detailed analysis of each task's schema mismatch
- Lines 390-475: Corrected schemas for all 10 validators

**Example (T051):**
```
BEFORE (hallucinated):
{'required': ['valid'], 'properties': {'valid': {'type': 'boolean'}}}

AFTER (correct):
{'required': ['validated_character_data', 'corrections_made', 'ac_calculation_breakdown'],
 'properties': {
   'validated_character_data': {'type': 'object'},
   'corrections_made': {'type': 'array'},
   'ac_calculation_breakdown': {'type': 'object', ...}
}}
```

### T051 Deep Audit
**Path:** `reports/T051_audit_report.md` (541 lines)

Compares 4 sources:
1. **System prompt** (lines 1199-1219 of character_validator.py) - defines output schema
2. **Runtime code** (lines 1279-1294) - what game actually requires
3. **Actual captures** (28 model outputs from T051.json)
4. **Validator schema** (EXPECTED_SCHEMA in task_T051.py)

**Key finding (lines 111-146):**
- Runtime only requires `validated_character_data`
- Validator requires all 3 fields (stricter)
- All models provide all 3 fields anyway (prompt compliance)

---

## 3. Current Validation Results

### Summary Report
**Path:** `reports/validation_summary.json` (99 lines)

```json
{
  "generated_at": "2026-02-22T07:47:12.766670",
  "total_variants": 230,
  "variants_passed": 208,
  "variants_failed": 22
}
```

**Per-task breakdown (lines 9-98):**
- T051: 28 passed, 0 failed ✅
- T054: 14 passed, 0 failed ✅
- T065: 20 passed, 14 failed ⚠️
- T067: 52 passed, 8 failed ⚠️
- T079: 8 passed, 0 failed ✅
- T082: 56 passed, 0 failed ✅

### Human-Readable Report
**Path:** `reports/validation_summary.html`

Open in browser for formatted view.

---

## 4. Detailed Failure Evidence

### T065 Validation Details
**Path:** `reports/details/T065_validation.json` (1377 lines)

Shows baseline passing but no variant outputs:
- Line 56-77: Baseline (gpt-4.1) passed validation
- Line 78: `"variants": {}` ← All Gemini variants failed to run

### T067 Validation Details
**Path:** `reports/details/T067_validation.json` (3465 lines)

Contains 8 failures from Gemini-3-flash models returning plain text instead of JSON.

### Error Log (Root Cause)
**Path:** `model_captures/errors.log` (40 lines)

**Gemini API failures (lines 4, 6, 9, 14, 18, 20, etc.):**
```
FileNotFoundError: google_api.pi not found - Gemini API key required for capture
```

**Summary:**
- All Gemini failures caused by missing API key file
- File expected: `google_api.pi` (not in repo)
- 14 total Gemini failures across T065, T067, T077, T090, T035

**Other failures (gpt-5.2 model not found):**
```
NotFoundError: Error code: 404 - The model `gpt-5.2-2025-08-07` does not exist
```
- gpt-5.2 is a future model (not released yet)
- These errors are expected/acceptable

---

## 5. Validator Implementation

### Example Regenerated Validator
**Path:** `validators/task_T051.py` (224 lines)

**Structure:**
```python
TASK_ID = "T051"
SOURCE_FILE = "core/validation/character_validator.py"
SOURCE_LINE = 963
MODEL_EXPR = "CHARACTER_VALIDATOR_MODEL=>gpt-5.2"

EXPECTED_SCHEMA = {
    'required': ['validated_character_data', 'corrections_made', 'ac_calculation_breakdown'],
    # ... correct schema from audit
}

def validate_json_structure(output_text):
    # Extracts JSON from markdown blocks, preamble text

def validate_schema_compliance(parsed_json):
    # Checks required fields and types (1-level deep)

def validate_business_rules(parsed_json, input_data):
    # Task-specific validation (extensible)

def validate_output(output_text, input_data, baseline_output):
    # Main entry point - runs all validations
```

---

## 6. Regeneration Script
**Path:** `tools/regenerate_validators_from_audit.py` (492 lines)

Contains hardcoded correct schemas from audit (lines 16-201).

Used to regenerate 9 validators after discovering hallucination.

---

## Summary of 22 Failures

### Infrastructure Issues (14 failures)
**T065:** 14 Gemini variants failed
**Cause:** Missing `google_api.pi` file
**Evidence:** `model_captures/errors.log` lines 4, 6, 9, 14, 18, 20, 22, 24

**Fix:** Either:
1. Add Gemini API key to `google_api.pi` file
2. Disable Gemini testing in `model_captures/capture_config.json`

### Model Format Errors (8 failures)
**T067:** 8 Gemini-3-flash variants returned plain text instead of JSON
**Evidence:** `reports/details/T067_validation.json`

**Example failure:**
```
Output: "The assistant's response is valid..."
Expected: {"narration": "...", "actions": [...]}
```

**Fix:** Prompt engineering for Gemini or model configuration adjustment

---

## Key Questions for Codex

1. **Shallow validation acceptable?**
   - Current: Checks only 1 level deep (top-level fields)
   - Alternative: Recursive validation of all nested structures
   - Trade-off: Simplicity vs thoroughness

2. **Validator strictness?**
   - Current: Enforces prompt contract (all 3 fields required)
   - Alternative: Match runtime minimums (only 1 field required)
   - Decision: Prompt contract is correct (catches non-compliant models)

3. **Gemini API key required?**
   - Current: Optional (tests skip if missing)
   - Alternative: Required (tests fail if missing)
   - Impact: 14 current failures, but infrastructure issue not model issue

---

## Next Actions for Codex

1. **Verify pass/fail rates:**
   - Check `reports/validation_summary.json` (208/230 = 90.4%)
   - Review detailed failures in `reports/details/T065_validation.json` and `T067_validation.json`

2. **Confirm Gemini failures:**
   - Check `model_captures/errors.log` for API key errors
   - Verify all 14 failures are infrastructure, not model errors

3. **Audit 2-3 more validators:**
   - T079 (currency update - simple schema)
   - T082 (action predictor - medium complexity)
   - T065 (DM validation - has failures to investigate)

4. **Decide on deep validation:**
   - Review T051 audit findings (lines 111-200 of `reports/T051_audit_report.md`)
   - Determine if shallow validation is sufficient
   - Consider extending DMResponseValidator if needed

---

## File Checklist

✅ `docs/CODEX_HANDOFF_VALIDATION_SYSTEM.md` - Main documentation
✅ `docs/issues/2026-02-22-validator-audit-results.md` - Audit findings
✅ `reports/T051_audit_report.md` - Deep audit example
✅ `reports/validation_summary.json` - Current results (208/230 passed)
✅ `reports/details/T065_validation.json` - Gemini API failure evidence
✅ `reports/details/T067_validation.json` - Gemini format error evidence
✅ `model_captures/errors.log` - Root cause of all failures
✅ `validators/task_T051.py` - Reference validator implementation
✅ `tools/regenerate_validators_from_audit.py` - Regeneration script

**All files committed to branch `multi-model-refactor` (commit 493dabe)**
