# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

# OpenSpec Design: tt-narrator-prompt-validation-refactor

## Architecture Boundaries

### Deterministic Validator (MUST)
- **Responsibility**: Hard checks for off-location NPC arrival state sync
- **Source of truth**: NPC presence state vs. narrative mentions
- **Output**: Pass/Fail with explicit required action (if fail)
- **Files**: `utils/npc_arrival_validator.py`

### LLM Validator (MUST)
- **Responsibility**: Narrative quality, action semantics, combat routing
- **Constraint**: SHALL NOT re-litigate deterministic pass/fail outcomes
- **Input**: Deterministic validator result (pass/fail/ambiguous) as metadata
- **Files**: `main.py` (validation context assembly)

### Action Handler (MUST)
- **Responsibility**: Execute state-changing actions
- **Constraint**: NPC movement uses strict location hint first, then canonical fallback
- **Safety**: Fail-closed on ambiguous matches
- **Files**: `core/ai/action_handler.py`

## Validation Flow Redesign

### Current Flow (Problematic)
```
Narrator Output
    -> Deterministic Validator (arrival check)
    -> LLM Validator (full validation)
    -> Retry Loop (if either fails)
    -> Correction notes appended as user turns
```

### Target Flow (Clean)
```
Narrator Output
    -> Deterministic Validator (arrival check)
    -> LLM Validator (quality check, respects deterministic result)
    -> Retry Loop (validation-local metadata only)
    -> Correction notes isolated from conversation history
```

## Retry-Loop Hygiene

MUST:
- Correction instructions stored as validation-local metadata
- Not appended as persistent user conversation turns
- Available to retry attempt without polluting main conversation

SHOULD:
- Correction notes expire after successful validation
- Audit trail maintained in separate log channel

## NPC Movement Lookup Strategy

MUST:
1. Attempt strict `currentLocation` hint match first
2. If miss, attempt canonical identity fallback
3. Only apply fallback if unambiguous (exactly one match)
4. Fail-closed if ambiguous or no match

SHOULD:
- Log fallback usage for monitoring
- Consider hint staleness in future iterations

## Prompt Contract Cleanup

### Compressed vs Uncompressed Parity

MUST:
- Same arrival-sync rules in both variants
- Same name canonicalization examples
- No contradictory guidance

Files affected:
- `prompts/system_prompt_compressed.txt`
- `prompts/system_prompt.txt`
- `prompts/validation/validation_prompt_compressed.txt`
- `prompts/validation/validation_prompt.txt`

### Dynamic Context Cleanup

MUST:
- Remove "do not flag missing presence" text when off-location arrival sync applies
- Context reinforces deterministic contract, never contradicts

Files affected:
- `core/ai/build_npc_context.py`

## Thread Safety

- Deterministic validator is stateless (safe for concurrent calls)
- Action handler uses existing atomic file operations
- No shared mutable state introduced

## Observability

SHOULD:
- Log deterministic validator decisions (pass/fail/ambiguous)
- Log NPC movement fallback usage
- Log retry-loop iteration counts
- Maintain audit trail of correction notes

## Migration Sequencing

1. Scaffold artifacts (Step 1.1) - COMPLETE
2. Capture fixtures (Step 1.2)
3. Add regression tests (Step 2.1, 2.2)
4. Split validation ownership (Step 3.1)
5. Fix retry pollution (Step 3.2)
6. Harden NPC move lookup (Step 3.3)
7. Clean prompts (Step 4.1, 4.2)
8. Full regression run (Step 5.1)
9. OpenSpec verification (Step 5.2)

## Rollback Strategy

Each step is independently revertible:
- Steps 1-2: Documentation/test only (no runtime impact)
- Steps 3.1-3.3: Functional changes with feature flags or revertible logic
- Steps 4.1-4.2: Prompt text changes (revert to previous file version)
