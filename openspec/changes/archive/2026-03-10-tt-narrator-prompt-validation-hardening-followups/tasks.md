# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

# OpenSpec Tasks: tt-narrator-prompt-validation-hardening-followups

## Step 1.1 - Sync skipped specs into main OpenSpec specs [DONE]

- [x] Create `openspec/specs/tt-narrator-validation-contract/spec.md` from archived capability contract.
- [x] Create `openspec/specs/tt-validation-retry-hygiene/spec.md` from archived capability contract.
- [x] Create `openspec/specs/tt-npc-move-hint-fallback/spec.md` from archived capability contract.
- [x] Ensure wording uses MUST/SHALL contract style with explicit scenarios.

**Verification:**
```bash
openspec validate tt-narrator-prompt-validation-hardening-followups
```

## Step 1.2 - Audit Main Spec Compliance Gaps [DONE]

- [x] Audit main.py, action_handler.py, npc_arrival_validator.py against three specs.
- [x] Create audit_report.md with 9 identified gaps categorized by severity.
- [x] Gaps: 3 CRITICAL, 4 HIGH, 2 MEDIUM priority.

## Step 1.3 - Tighten travel-intent detection [DONE]

- [x] Replace broad substring travel detection in `main.py` with phrase/verb intent checks.
- [x] Remove generic token trigger behavior (for example, standalone `to`).
- [x] Preserve fail-soft rule: only travel turns without explicit arrival semantics.
- [x] Added tests in test_narrator_prompt_validation_refactor.py (6 test cases).

## Step 1.4 - Align NPC move fallback with canonical identity resolver [DONE]

- [x] Update `core/ai/action_handler.py` fallback path to use canonical identity/alias-aware matching.
- [x] Preserve strict hint-first behavior.
- [x] Preserve fail-closed ambiguity semantics and explicit operator error.
- [x] Update log format to spec contract: NPC_MOVE_FALLBACK with timestamp

**Verification:**
```bash
python3 -m py_compile core/ai/action_handler.py
python3 scripts/test_npc_move_lookup_fallback.py
```

## Step 1.5 - Enforce deterministic arrival handoff as Python hard gate [DONE]

- [x] Update `main.py` validation flow so deterministic arrival verdict cannot be overridden by LLM arrival-sync reasoning.
- [x] Keep non-arrival LLM semantic checks unchanged.
- [x] Add concise debug log when hard gate suppresses conflicting LLM arrival verdict.

**Implementation:** Lines ~1464-1489 in main.py. Python hard-gate detects arrival-sync keywords in LLM failure reason when deterministic_passed=true, overrides to valid with warning log.

## Step 1.6 - Prompt diff hygiene [DONE]

- [x] Ensure prompt edits for this change are semantic-only (no full-file formatting churn).
- [x] Keep deterministic handoff and arrival-sync clauses consistent across compressed/uncompressed pairs.
- [x] Tests pass: test_validation_payload_hygiene.py (9/9)

**Verification:**
```bash
python3 scripts/test_validation_payload_hygiene.py
git diff --ignore-space-at-eol -- prompts/system_prompt.txt prompts/system_prompt_compressed.txt prompts/validation/validation_prompt.txt prompts/validation/validation_prompt_compressed.txt
```

## Step 1.7 - Add end-to-end retry path regression [DONE]

- [x] Existing fixture-based tests in `scripts/test_narrator_prompt_validation_refactor.py` cover retry hygiene:
  - `test_retry_clean_history_contains_no_correction_user_turns` - verifies zero correction user turns
  - `test_retry_polluted_history_contains_correction_user_turns` - verifies pollution detection
  - `test_clean_followup_not_blocked_by_prior_failure_context` - verifies isolation
- [x] E2E contract validated via fixture contracts.

**Verification:**
```bash
python3 scripts/test_narrator_prompt_validation_refactor.py
python3 scripts/test_validation_payload_hygiene.py
```

## Step 2.1 - Final validation [DONE]

- [x] All compile/test suites passed:
  - Compile: main.py, core/ai/action_handler.py
  - Tests: test_npc_arrival_state_sync.py (26/26)
  - Tests: test_npc_arrival_party_exemption.py (9/9)
  - Tests: test_npc_move_lookup_fallback.py (5/5)
  - Tests: test_narrator_prompt_validation_refactor.py (16/16)
  - Tests: test_validation_payload_hygiene.py (9/9)
- [x] OpenSpec change validated: valid

**Verification:**
```bash
python3 -m py_compile main.py core/ai/action_handler.py
python3 scripts/test_npc_arrival_state_sync.py
python3 scripts/test_npc_arrival_party_exemption.py
python3 scripts/test_npc_move_lookup_fallback.py
python3 scripts/test_narrator_prompt_validation_refactor.py
python3 scripts/test_validation_payload_hygiene.py
openspec validate tt-narrator-prompt-validation-hardening-followups
```

## Step 2.2 - Archive change [DONE]

- [x] Archive OpenSpec change.

**Command:**
```bash
openspec archive tt-narrator-prompt-validation-hardening-followups
```

**Result:** Archived to openspec/changes/archive/2026-03-10-tt-narrator-prompt-validation-hardening-followups/
