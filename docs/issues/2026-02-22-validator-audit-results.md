# Validator Schema Audit Results

**Date:** 2026-02-22
**Audited Tasks:** T035, T051, T054, T065, T067, T077, T078, T079, T082, T090
**Method:** Parallel agent dispatch with capture file analysis

---

## Executive Summary

**Status: ALL 10 VALIDATORS HAVE HALLUCINATED SCHEMAS**

Every single stub validator (100%) contains a completely wrong schema that does not match actual API outputs. The validation system is currently non-functional for schema compliance checking.

### Overall Results

| Task | Schema Status | Pass Rate | True Status | Recommendation |
|------|---------------|-----------|-------------|----------------|
| T035 | Completely Wrong | N/A | False positive | Regenerate |
| T051 | Completely Wrong | 0% | All outputs correct | Regenerate |
| T054 | Completely Wrong | 0% | All outputs correct | Regenerate |
| T065 | Completely Wrong | 59% | 100% (excl. infra errors) | Regenerate |
| T067 | Completely Wrong | 87% | 89% (8 Gemini format errors) | Regenerate |
| T077 | Completely Wrong | 100% | False positive | Regenerate |
| T078 | Completely Wrong | 96% | 100% (1 false failure) | Regenerate |
| T079 | Completely Wrong | 100% | False positive | Regenerate |
| T082 | Completely Wrong | 100% | False positive | Regenerate |
| T090 | Completely Wrong | 100% | False positive | Regenerate |

### Key Findings

1. **100% Hallucination Rate**: All validators use generic placeholder schemas
2. **Most Common Hallucination**: `{"status": "string"}` or `{"valid": boolean, "errors": array}`
3. **False Positives**: 6 validators show 100% pass due to empty `required` fields
4. **False Negatives**: 2 validators show 0% pass due to schema mismatch (T051, T054)
5. **Real Failures Hidden**: Only 8 actual model errors (Gemini format issues) buried in false failures

---

## Detailed Task Analysis

### T035: NPC Builder (core/generators/npc_builder.py:126)

**Validator Expects:**
```json
{
  "content": "string",
  "metadata": "object"
}
```

**Actual Output:**
```json
{
  "character_role": "npc",
  "name": "Scout Kira",
  "race": "Wood Elf",
  "class": "Rogue",
  "abilities": {...},
  "equipment": [...],
  // 47 total top-level fields
}
```

**Issue:** Validator expects a simple wrapper object, actual output is full D&D 5e NPC schema with 47 fields.

**Impact:** No validation of NPC structure, would accept any JSON with "content" field.

---

### T051: Character AC Validator (core/validation/character_validator.py:963)

**Validator Expects:**
```json
{
  "valid": boolean,
  "errors": array
}
```

**Actual Output:**
```json
{
  "validated_character_data": {...},
  "corrections_made": [...],
  "ac_calculation_breakdown": {...}
}
```

**Issue:** Validator expects generic validation response, actual output is AC validation report with corrections.

**Impact:** 100% false failure rate (0/28 passed). All model outputs are correct and identical.

**Evidence:** Every variant (gpt-4.1, gpt-5.2, gpt-5-mini, Gemini) calculated AC = 16 correctly.

---

### T054: Inventory Consolidation (core/validation/character_validator.py:2026)

**Validator Expects:**
```json
{
  "valid": boolean,
  "errors": array
}
```

**Actual Output:**
```json
{
  "ammunition": [...],
  "equipment": [...],
  "consolidations_made": [...],
  "inventory": {...} // optional
}
```

**Issue:** Validator expects generic validation response, actual output is inventory consolidation report.

**Impact:** 100% false failure rate (0/14 passed). All outputs structurally correct.

---

### T065: DM Response Validation (main.py:1222)

**Validator Expects:**
```json
{
  "status": "string"
}
```

**Actual Output:**
```json
{
  "valid": boolean,
  "reason": "string"
}
```

**Issue:** Wrong field names (`status` vs `valid`/`reason`).

**Impact:**
- Reported: 59% pass (20/34)
- Actual: 67% pass (28/42 including Gemini API failures)
- True: 100% pass (28/28 when API failures excluded)

**Note:** 14 failures are Gemini API key missing (infrastructure), not model errors.

---

### T067: Main DM Response (main.py:2321)

**Validator Expects:**
```json
{
  "status": "string"
}
```

**Actual Output:**
```json
{
  "narration": "string",
  "actions": array
}
```

**Issue:** Completely wrong structure.

**Impact:**
- Reported: 87% pass (52/60)
- Actual: 89% pass (64/72)
- Real failures: 8 Gemini-3-flash outputs returned plain text instead of JSON

**Note:** Schema is wrong but so permissive (no required fields) it passes most outputs.

---

### T077: Plot Update (updates/plot_update.py:149)

**Validator Expects:**
```json
{
  "status": "string"
}
```

**Actual Output:**
```json
{
  "PP001": {
    "status": "completed",
    "plotImpact": "Rusk revealed the location..."
  }
}
```

**Issue:** Validator expects flat object, actual output is nested by plot point ID.

**Impact:** 100% false positive (passes due to no required fields, doesn't actually validate structure).

---

### T078: Character Effects (updates/update_character_effects.py:199)

**Validator Expects:**
```json
{
  "status": "string"
}
```

**Actual Output:**
```json
{
  "should_track": boolean,
  "effect": {
    "stat": "string",
    "value": number,
    "source": "string",
    "duration_type": "string",
    "duration_value": number,
    "description": "string",
    "affects_max": boolean
  }
}
```

**Issue:** Wrong structure, plus validator can't extract JSON with preamble text.

**Impact:**
- Reported: 96% pass (27/28)
- Actual: 100% pass - the 1 failure is validator bug (can't parse preamble text)

---

### T079: Character Info Update (updates/update_character_info.py:1453)

**Validator Expects:**
```json
{
  "status": "string"
}
```

**Actual Output:**
```json
{
  "currency": {
    "gold": 11,
    "silver": 5,
    "copper": 15
  }
}
```

**Issue:** Wrong structure (expects status, actual is currency delta).

**Impact:** 100% false positive (passes due to no required fields).

---

### T082: Action Predictor (utils/action_predictor.py:152)

**Validator Expects:**
```json
{
  "status": "string"
}
```

**Actual Output:**
```json
{
  "requires_actions": boolean,
  "reason": "string"
}
```

**Issue:** Wrong field names.

**Impact:** 100% false positive (11 captures, 56 variants all structurally correct but validator doesn't check them).

---

### T090: Quest Formatter (utils/quest_player_formatter.py:83)

**Validator Expects:**
```json
{
  "status": "string"
}
```

**Actual Output:**
```json
{
  "PP001": "Reformatted quest description...",
  "PP002": "Another quest description..."
}
```

**Issue:** Validator expects static field, actual output has dynamic quest ID keys.

**Impact:** 100% false positive (passes due to no required fields).

---

## Root Cause Analysis

### How Did This Happen?

The stub validators in `discover_validators.py` were created with `create_stub_validator()` function that:

1. **Never reads the system prompt** (which defines the actual output schema)
2. **Never reads the callsite code** (which shows how response is parsed)
3. **Never reads existing validators** (which define validation rules)
4. **Uses generic templates** (`{"status": "string"}` or `{"valid": boolean}`)

**Quote from design doc:**
> For each task (e.g., T079), the agent reads:
> 1. **System prompt** from capture → Extract expected JSON schema/structure
> 2. **Callsite code** at `path:line` from inventory → Understand how response is parsed/used
> 3. **Existing validators** (if referenced) → Extract validation rules

**Current stub implementation:** Skips ALL 3 steps, resulting in hallucinations.

---

## Impact Assessment

### False Positives (Validators Pass Incorrectly)

**Tasks:** T035, T077, T079, T082, T090

**Cause:** Validators have empty `required` fields arrays, so they accept any valid JSON.

**Impact:** No actual validation happening. System reports "100% pass" but isn't checking schema compliance.

**Risk:** Could deploy broken model outputs that pass validation.

---

### False Negatives (Validators Fail Incorrectly)

**Tasks:** T051, T054

**Cause:** Validators expect wrong fields (e.g., `valid` field that doesn't exist).

**Impact:** All model outputs marked as failed despite being structurally correct and producing identical results.

**Risk:** Rejecting good model candidates due to validator bugs.

---

### Mixed Results (Partial Validation)

**Tasks:** T065, T067, T078

**Cause:** Some failures are real (Gemini format issues), others are validator bugs.

**Impact:** Can't distinguish between model errors and validator errors.

**Risk:** Wasting time investigating false failures instead of real issues.

---

## Real Model Issues Discovered

Despite broken validators, audit found **actual model failures:**

### 1. Gemini API Infrastructure (T065)
- **Issue:** 14 Gemini outputs failed due to missing `google_api.pi` file
- **Status:** Infrastructure issue, not model issue
- **Fix:** Configure Gemini API key

### 2. Gemini Format Compliance (T067)
- **Issue:** 8 Gemini-3-flash outputs returned plain text instead of JSON
- **Models:** gemini-3-flash|minimal, low, medium, high
- **Fix:** Prompt engineering or model configuration for Gemini

### 3. Preamble Text Handling (T078)
- **Issue:** 1 Gemini-3-pro output included preamble text before JSON
- **Example:** "Based on the analysis of the update, here is the JSON response: {...}"
- **Status:** Valid output, validator needs to handle preamble

---

## Corrected Schemas

For each validator, the audit identified the correct schema:

### T051 (Character AC Validator)
```python
EXPECTED_SCHEMA = {
    "type": "object",
    "required": ["validated_character_data", "corrections_made", "ac_calculation_breakdown"],
    "properties": {
        "validated_character_data": {"type": "object"},
        "corrections_made": {"type": "array", "items": {"type": "string"}},
        "ac_calculation_breakdown": {
            "type": "object",
            "required": ["base_armor", "dex_modifier", "shield_bonus", "fighting_style_bonus", "total_ac"],
            "properties": {
                "base_armor": {"type": "string"},
                "dex_modifier": {"type": "string"},
                "shield_bonus": {"type": "string"},
                "fighting_style_bonus": {"type": "string"},
                "total_ac": {"type": "integer"}
            }
        }
    }
}
```

### T065 (DM Validation)
```python
EXPECTED_SCHEMA = {
    "type": "object",
    "required": ["valid", "reason"],
    "properties": {
        "valid": {"type": "boolean"},
        "reason": {"type": "string"}
    }
}
```

### T067 (Main DM Response)
```python
EXPECTED_SCHEMA = {
    "type": "object",
    "required": ["narration", "actions"],
    "properties": {
        "narration": {"type": "string"},
        "actions": {
            "type": "array",
            "items": {"type": "string"}
        }
    }
}
```

### T079 (Character Currency Update)
```python
EXPECTED_SCHEMA = {
    "type": "object",
    "required": ["currency"],
    "properties": {
        "currency": {
            "type": "object",
            "required": ["gold", "silver", "copper"],
            "properties": {
                "gold": {"type": "integer"},
                "silver": {"type": "integer"},
                "copper": {"type": "integer"}
            }
        }
    }
}
```

### T082 (Action Predictor)
```python
EXPECTED_SCHEMA = {
    "type": "object",
    "required": ["requires_actions", "reason"],
    "properties": {
        "requires_actions": {"type": "boolean"},
        "reason": {"type": "string"}
    }
}
```

*(See individual audit reports for remaining tasks)*

---

## Recommended Actions

### Immediate (Critical)

1. **✅ COMPLETED:** Document all schema mismatches
2. **⏳ IN PROGRESS:** Regenerate all 10 validators with correct schemas
3. **⏳ TODO:** Re-run validation analysis with corrected validators
4. **⏳ TODO:** Update validation summary with accurate pass/fail rates

### Short-Term (Phase 2)

1. Implement agent-based validator generation per design doc
2. Each agent analyzes:
   - System prompt (extract actual schema)
   - Callsite code (understand usage)
   - Existing validators (extract business rules)
3. Generate intelligent validators with real schemas
4. Add self-test (validate against known-good captures)

### Long-Term (Prevention)

1. Add schema extraction from system prompts to discovery script
2. Add validator self-test before accepting generated validators
3. Add schema mismatch detection in analysis script
4. Consider JSON Schema library integration for robust validation
5. Add CI/CD check: capture validation must pass before merge

---

## Files to Regenerate

All 10 validators need regeneration:

```
validators/task_T035.py - NPC builder schema
validators/task_T051.py - Character AC validation schema
validators/task_T054.py - Inventory consolidation schema
validators/task_T065.py - DM validation schema
validators/task_T067.py - Main DM response schema
validators/task_T077.py - Plot update schema
validators/task_T078.py - Character effects schema
validators/task_T079.py - Character info update schema
validators/task_T082.py - Action predictor schema
validators/task_T090.py - Quest formatter schema
```

---

## Conclusion

The validator audit revealed **systematic schema hallucination** affecting 100% of stub validators. This explains the inconsistent validation results (0% to 100% pass rates) observed in initial analysis.

**Key Takeaway:** The capture system is working correctly and collecting valid data. The validation failures are due to broken validators, not broken models.

**Next Step:** Regenerate all validators with correct schemas extracted from actual capture data and system prompts.

---

**Audit Completed By:** 10 parallel auditor agents
**Audit Duration:** ~2 minutes (concurrent execution)
**Total Captures Analyzed:** 41 capture files, 230+ model outputs
**Issue Tracker:** docs/issues/2026-02-22-stub-validator-schema-hallucination.md
