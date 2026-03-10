# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

# OpenSpec Tasks: tt-narrator-prompt-validation-refactor

## Step 1.1 - Scaffold OpenSpec change artifacts (contract-first) [DONE]

- [x] Create `openspec/changes/tt-narrator-prompt-validation-refactor/proposal.md`
  - [x] Problem statement (Kira, Bex, validation noise)
  - [x] Objective and non-goals
  - [x] Risk analysis and fallback strategy
  - [x] Merge-safety and compatibility impact
  - [x] Acceptance criteria (MUST/SHOULD)

- [x] Create `openspec/changes/tt-narrator-prompt-validation-refactor/design.md`
  - [x] Architecture boundaries (deterministic/LLM/action handler)
  - [x] Validation flow redesign
  - [x] Retry-loop hygiene design
  - [x] NPC movement lookup strategy
  - [x] Prompt contract cleanup plan
  - [x] Migration sequencing

- [x] Create `openspec/changes/tt-narrator-prompt-validation-refactor/tasks.md` (this file)
  - [x] Step-by-step task breakdown
  - [x] Verification commands per step

- [x] Create spec directories
  - [x] `specs/tt-narrator-validation-contract/`
  - [x] `specs/tt-validation-retry-hygiene/`
  - [x] `specs/tt-npc-move-hint-fallback/`

**Verification:**
```bash
ls openspec/changes/tt-narrator-prompt-validation-refactor/
# Expected: proposal.md, design.md, tasks.md, specs/
```

## Step 1.2 - Capture known-failure replay fixtures [DONE]

- [x] Create `scripts/fixtures/narrator_validation/` directory
- [x] Create `kira_onboarding_failure.json`
  - [x] Input: Narrator output mentioning Scout Kira + Maelo off-location
  - [x] Expected: Deterministic pass (Kira present/added), no retry
  - [x] Actual (buggy): Deterministic fail due to Maelo mention, blocks Kira add

- [x] Create `bex_hint_mismatch.json`
  - [x] Input: `moveBackgroundNPC` with `currentLocation: TW03` (stale)
  - [x] Canonical: Bex in `RO03`
  - [x] Expected: Fallback to identity match succeeds
  - [x] Actual (buggy): Strict hint fails, "NPC not found"

- [x] Create `retry_pollution_chain.json`
  - [x] Input: 3-attempt retry sequence
  - [x] Expected: Correction notes isolated from conversation
  - [x] Actual (buggy): Correction notes persist as user turns

**Verification:**
```bash
python3 -c "import json; [json.load(open(f)) for f in ['scripts/fixtures/narrator_validation/kira_onboarding_failure.json', 'scripts/fixtures/narrator_validation/bex_hint_mismatch.json', 'scripts/fixtures/narrator_validation/retry_pollution_chain.json']]"
```

## Step 1.3 - Create capability specs

- [ ] Write `specs/tt-narrator-validation-contract/spec.md`
  - [ ] MUST: Deterministic validator is source of truth for arrival sync
  - [ ] MUST: LLM validator respects deterministic pass/fail
  - [ ] MUST: Contradictory rule blocks not emitted in same payload
  - [ ] MUST: Party-member exemptions preserved
  - [ ] MUST: Fail-open ambiguity policy preserved

- [ ] Write `specs/tt-validation-retry-hygiene/spec.md`
  - [ ] MUST: Correction instructions not persisted as user turns
  - [ ] MUST: Validation-local metadata isolated from conversation history
  - [ ] SHOULD: Correction notes expire after successful validation
  - [ ] SHOULD: Audit trail in separate log channel

- [ ] Write `specs/tt-npc-move-hint-fallback/spec.md`
  - [ ] MUST: Strict `currentLocation` hint match attempted first
  - [ ] MUST: Canonical identity fallback only if unambiguous
  - [ ] MUST: Fail-closed on ambiguous matches
  - [ ] SHOULD: Log fallback usage for monitoring

**Verification:**
```bash
openspec validate tt-narrator-prompt-validation-refactor
```

## Step 2.1 - Add regression tests before runtime edits [DONE]

- [x] Create `scripts/test_narrator_prompt_validation_refactor.py`
  - [x] Test: Kira onboarding (narrative acceptance + valid add action results in party state)
  - [x] Test: Maelo off-location mention does not block unrelated Kira onboarding in subsequent clean response
  - [x] Test: Bex movement with stale hint resolves via fallback
  - [x] Test: Correction note contamination guard

- [x] Append to `scripts/test_npc_arrival_state_sync.py`
  - [x] Test: Alias resolution works with short names in narration
  - [x] Test: Full canonical names in actions matched correctly

- [x] Append to `scripts/test_npc_arrival_party_exemption.py`
  - [x] Test: Party member short name remains exempt
  - [x] Test: Ambiguous mention fail-open under alias policy

**Verification:**
```bash
python3 scripts/test_narrator_prompt_validation_refactor.py
python3 scripts/test_npc_arrival_state_sync.py
python3 scripts/test_npc_arrival_party_exemption.py
```

## Step 2.2 - Add validation payload hygiene tests [DONE]

- [x] Create `scripts/test_validation_payload_hygiene.py`
  - [x] Test: No contradictory "do not flag presence" + arrival-sync blocks
  - [x] Test: No duplicate rule text
  - [x] Test: Payload size bounded (<5k tokens)
  - [x] Test: Deterministic result included as metadata (not re-judged)

**Verification:**
```bash
python3 scripts/test_validation_payload_hygiene.py
```

## Step 3.1 - Split validation ownership cleanly [DONE]

- [x] Modify `main.py`
  - [x] Call deterministic validator first
  - [x] Pass deterministic result to LLM validator context
  - [x] LLM validator context includes flag: `deterministic_passed: true/false`
  - [x] LLM validator prompt excludes arrival-sync re-judgment when `deterministic_passed: true`

- [x] Modify `utils/npc_arrival_validator.py` (if needed)
  - [x] Ensure consistent failure reason taxonomy
  - [x] Export result structure compatible with LLM validator context

**Verification:**
```bash
python3 -m py_compile main.py utils/npc_arrival_validator.py
python3 scripts/test_npc_arrival_state_sync.py
```

## Step 3.2 - Fix retry/correction message pollution [DONE]

- [x] Modify `main.py`
  - [x] Store correction instructions in validation-local metadata
  - [x] Do not append as user conversation turns
  - [x] Make available to retry attempt via validation context only

**Verification:**
```bash
python3 -m py_compile main.py
python3 scripts/test_narrator_prompt_validation_refactor.py::TestRetryPollution
```

## Step 3.3 - Harden NPC move lookup with strict-then-fallback [DONE]

- [x] Modify `core/ai/action_handler.py`
  - [x] Implement `find_npc_in_areas` with strict-then-fallback strategy
  - [x] Strict: `currentLocation` hint match
  - [x] Fallback: canonical identity match (unambiguous only)
  - [x] Fail-closed: return error if ambiguous

**Verification:**
```bash
python3 -m py_compile core/ai/action_handler.py
python3 scripts/test_narrator_prompt_validation_refactor.py::TestBexHintFallback
```

## Step 4.1 - Prompt contract cleanup [DONE]

- [x] Modify `prompts/system_prompt_compressed.txt`
  - [x] Remove contradictory arrival-sync wording
  - [x] Align name canonicalization examples

- [x] Modify `prompts/system_prompt.txt`
  - [x] Mirror changes from compressed version

- [x] Modify `prompts/validation/validation_prompt_compressed.txt`
  - [x] Remove arrival-sync re-judgment when deterministic passed
  - [x] Remove contradictory "do not flag presence" text

- [x] Modify `prompts/validation/validation_prompt.txt`
  - [x] Mirror changes from compressed version

**Verification:**
```bash
diff prompts/system_prompt_compressed.txt prompts/system_prompt.txt | wc -l
diff prompts/validation/validation_prompt_compressed.txt prompts/validation/validation_prompt.txt | wc -l
```

## Step 4.2 - Dynamic NPC context cleanup [DONE]

- [x] Modify `core/ai/build_npc_context.py`
  - [x] Remove/adjust conflicting "do not flag presence" text
  - [x] Ensure context reinforces deterministic contract

**Verification:**
```bash
python3 -m py_compile core/ai/build_npc_context.py
python3 scripts/test_validation_payload_hygiene.py
```

## Step 5.1 - Full regression run [DONE]

- [x] Run all modified Python files through syntax check
- [x] Run all test suites
- [x] Replay fixture-based regression tests

**Verification:**
```bash
python3 -m py_compile main.py utils/npc_arrival_validator.py core/ai/action_handler.py core/ai/build_npc_context.py
python3 scripts/test_npc_arrival_state_sync.py
python3 scripts/test_npc_arrival_party_exemption.py
python3 scripts/test_narrator_prompt_validation_refactor.py
python3 scripts/test_validation_payload_hygiene.py
```

## Step 5.2 - OpenSpec verification + archive readiness [DONE]

- [x] Update `tasks.md` with completion status
- [x] Run OpenSpec validation
- [x] Prepare archive-ready artifact set

**Verification:**
```bash
openspec validate tt-narrator-prompt-validation-refactor
# Expected: VALID
```

## Status Summary

| Step | Status |
|------|--------|
| 1.1 | DONE |
| 1.2 | DONE |
| 1.3 | DEFERRED (optional spec docs) |
| 2.1 | DONE |
| 2.2 | DONE |
| 3.1 | DONE |
| 3.2 | DONE |
| 3.3 | DONE |
| 4.1 | DONE |
| 4.2 | DONE |
| 5.1 | DONE |
| 5.2 | DONE |
