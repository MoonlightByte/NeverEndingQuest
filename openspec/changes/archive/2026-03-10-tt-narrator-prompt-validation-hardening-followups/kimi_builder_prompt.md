# Kimi Builder Prompt: Narrator-Validation Hardening Follow-ups
# Session Type: New builder session (Kimi K2.5)
# Context: Full variant for Step 1.2+ execution after spec sync

## OVERVIEW

You are implementing mission-critical hardening follow-ups for the narrator prompt/validation system in NeverEndingQuest. This is a BUILDER session - execute tasks, write code, validate with tests.

The prior change `tt-narrator-prompt-validation-refactor` was archived successfully but used `--skip-specs`, leaving main specs unsynced. Step 1.1 (spec sync) is now complete. Your job is Steps 1.2 through 4.

## CRITICAL ARCHITECTURAL CONTEXT

**The Python/LLM Handoff Philosophy:**
- Tier 1a (MUST): Python hard-gates enforce reality (HP, conditions, inventory)
- Tier 1b (SHOULD): Prompts guide LLM toward correct behavior
- Tier 2 (SHOULD): LLM self-correction via validation retry
- Tier 3 (MUST): Deterministic validators are sole source of truth for arrival sync

**Fail-Closed Principle:**
- Arrival sync: Deterministic validator must pass before LLM validator runs
- Ambiguity: Fail-open (ambiguous NPC mentions pass without action)
- Contradictions: Deterministic validator authority takes precedence

## OPENSPEC ARTIFACTS (READ THESE FIRST)

1. Main specs (now synced):
   - openspec/specs/tt-narrator-validation-contract/spec.md
   - openspec/specs/tt-validation-retry-hygiene/spec.md
   - openspec/specs/tt-npc-move-hint-fallback/spec.md

2. Follow-up change directory:
   - openspec/changes/tt-narrator-prompt-validation-hardening-followups/
   - Read: proposal.md, design.md, tasks.md
   - Read: executor_prompts.md (has task-by-task breakdown)

3. Archived reference (for context only):
   - openspec/changes/archive/2026-03-10-tt-narrator-prompt-validation-refactor/

## YOUR TASKS (EXECUTE IN ORDER)

### Task 1.2: Audit Main Spec Compliance Gaps

**Goal:** Identify where runtime code deviates from the three synced specs.

**Files to audit:**
- main.py (travel-intent detection, validation orchestration)
- core/ai/action_handler.py (moveBackgroundNPC implementation)
- core/ai/build_npc_context.py (NPC context building)
- utils/npc_arrival_validator.py (deterministic arrival validator)
- prompts/system_prompt_compressed.txt
- prompts/validation/validation_prompt_compressed.txt

**Deliverable:** Gap report in openspec/changes/tt-narrator-prompt-validation-hardening-followups/audit_report.md listing:
1. Areas where spec MUST requirements are not enforced
2. Areas where SHOULD guidance is missing
3. Contradictions between spec and implementation

**Success criteria:**
- All three specs cross-referenced against runtime
- Each gap includes file:line reference
- Gaps categorized: CRITICAL (blocks gameplay), HIGH (causes retry loops), MEDIUM (cosmetic)

---

### Task 2: Tighten Travel-Intent Detection (Broad -> Specific)

**Problem:** Current travel-intent detection in main.py is too broad, catching phrases like "I wonder about the forest" as travel intent.

**Spec reference:** tt-narrator-validation-contract Requirement "No Contradictory Rule Blocks"

**Implementation:**
1. In main.py, refine travel-intent regex/patterns:
   - REQUIRED: Directional keywords (go, travel, head, move, walk, run)
   - REQUIRED: Destination reference (location name, direction, "there")
   - EXCLUDED: Wondering, thinking, asking questions without movement

2. Examples of correct classification:
   - "I go to the forest" -> TRAVEL
   - "We head north" -> TRAVEL
   - "What do I know about the forest?" -> NOT TRAVEL
   - "I wonder if the forest is safe" -> NOT TRAVEL

3. Preserve existing behavior for actual travel commands.

**Testing:**
- Add test cases to scripts/test_narrator_prompt_validation_refactor.py
- Cover: true positives, true negatives, edge cases

---

### Task 3: Canonical Identity-Aware NPC Fallback

**Problem:** NPC fallback lookup in moveBackgroundNPC doesn't use canonical alias resolution, causing misses when NPC has aliases.

**Spec reference:** tt-npc-move-hint-fallback Requirement "Canonical Identity Fallback"

**Implementation in core/ai/action_handler.py:**
1. After strict currentLocation hint fails:
   a. Load canonical identity map from module_context.json
   b. Resolve provided name to canonical form (handle aliases)
   c. Search all locations for canonical name
   d. If exactly one match found -> use it (log fallback)
   e. If zero or multiple matches -> fail-closed

2. Add logging per spec:
   - `NPC_MOVE_FALLBACK: name={name} stale_hint={hint} resolved_location={location}`

3. Preserve fail-closed behavior on ambiguity.

**Testing:**
- Add tests to scripts/test_npc_move_lookup_fallback.py
- Test: alias resolution, unambiguous fallback success, ambiguous failure, strict hint success (no fallback)

---

### Task 4: End-to-End Retry-Path Regression Test

**Goal:** One comprehensive test covering the full validation retry cycle.

**Spec reference:** tt-validation-retry-hygiene (all requirements)

**Test scenario:**
1. Narrator outputs response mentioning off-location NPC without action
2. Deterministic validator fails it
3. Correction instruction generated (isolated, not in conversation history)
4. Retry attempted with correction
5. Success on retry
6. Verify: conversation history contains zero correction messages
7. Verify: audit log contains correction record

**Implementation:**
- New test file: scripts/test_validation_retry_e2e.py
- Mock LLM responses for deterministic failure then success
- Verify conversation history state
- Verify audit log entries

**Success criteria:**
- Test passes deterministically
- No real LLM calls (mocked)
- Covers full cycle: fail -> correct -> retry -> pass

---

### Task 5: Update OpenSpec Tasks and Validate

1. Update openspec/changes/tt-narrator-prompt-validation-hardening-followups/tasks.md:
   - Mark completed tasks DONE
   - Add any discovered subtasks

2. Run validation:
   ```bash
   openspec validate tt-narrator-prompt-validation-hardening-followups
   ```

3. Archive when complete:
   ```bash
   openspec archive tt-narrator-prompt-validation-hardening-followups
   ```

---

## CONSTRAINTS (MUST FOLLOW)

1. **ASCII-only:** No Unicode in code, logs, or prompts
2. **Merge-safe:** Minimal changes, backward compatible
3. **Fail-closed:** Arrival sync, ambiguity handling must fail safely
4. **Two-layer contract:**
   - MUST = normative, testable, enforceable
   - SHOULD = guidance, never overrides MUST
5. **No prompt drift:** Keep prompts bounded; deterministic validators enforce hard constraints

## KEY FILES REFERENCE

**Runtime/Prompt:**
- main.py (travel detection, validation orchestration)
- core/ai/action_handler.py (moveBackgroundNPC, encounter creation)
- core/ai/build_npc_context.py (NPC context)
- utils/npc_arrival_validator.py (deterministic validator)
- prompts/system_prompt_compressed.txt
- prompts/validation/validation_prompt_compressed.txt

**Test Files:**
- scripts/test_narrator_prompt_validation_refactor.py
- scripts/test_validation_payload_hygiene.py
- scripts/test_npc_arrival_state_sync.py
- scripts/test_npc_arrival_party_exemption.py
- scripts/test_npc_move_lookup_fallback.py (extend this)

**OpenSpec:**
- openspec/specs/tt-narrator-validation-contract/spec.md
- openspec/specs/tt-validation-retry-hygiene/spec.md
- openspec/specs/tt-npc-move-hint-fallback/spec.md
- openspec/changes/tt-narrator-prompt-validation-hardening-followups/

---

## STARTING STATE

- All three specs are now synced to openspec/specs/
- Follow-up change exists with proposal/design/tasks/executor_prompts
- No code changes have been made yet in this session
- Prior archived change is reference only

## SUCCESS DEFINITION

1. Gap audit report exists and is accurate
2. Travel-intent detection tightened with tests
3. NPC fallback uses canonical identity with logging
4. E2E retry test passes
5. OpenSpec change validates and archives cleanly
6. All existing tests still pass

Begin with Task 1.2 (audit). Report progress after each task.
