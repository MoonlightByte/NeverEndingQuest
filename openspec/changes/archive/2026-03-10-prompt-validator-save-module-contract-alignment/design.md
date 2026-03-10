## Context

This change is Phase 1B of the prompt/validator contract-alignment program. Phase 1A tightened `rest` parity and established the expectation that prompt text must match runtime behavior. Phase 1B applies the same approach to the next most visible auxiliary contracts: save-management actions and `createNewModule`.

The stack properties that MUST remain intact are unchanged:

- Python state and runtime execution remain ground truth.
- Validation retries remain transient and fail-closed.
- Single-player and tabletop mode share the same action contract surface.

This is still a narrow contract-alignment and regression-coverage pass, not a broader prompt/validator redesign.

## Goals / Non-Goals

**Goals:**
- Align covered save-management actions across narrator prompt, validator prompt, and runtime handling.
- Align `createNewModule` validator expectations with the current narrative-driven runtime contract.
- Add regression checks that cover both compressed and uncompressed prompt variants.
- Preserve existing runtime behavior unless an obvious bug or minimal compatibility need is discovered.
- Keep the covered action set explicit so implementation stays reviewable.

**Non-Goals:**
- Do not redesign the save system UX or save manager internals.
- Do not redesign module creation architecture or replace the narrative parser flow.
- Do not add deterministic prechecks for HP, slots, or inventory in this change.
- Do not broaden scope into combat, validation retry architecture, or structured `updateCharacterInfo` ops.
- Do not clean up unrelated prompt drift outside the covered action set.

## Decisions

### Decision 1: Treat runtime as the baseline for save-management contracts

**Decision:** For this slice, runtime behavior in `core/ai/action_handler.py` SHALL define the operational contract for `saveGame`, `restoreGame`, `listSaves`, and `deleteSave`.

**Rationale:** Runtime is already executing these actions. The main defect is stale prompt/validator text, not a missing save-system implementation.

**Operational baseline:**
- `saveGame`: `{"description": str_opt, "saveMode": "essential|full"_opt}`
- `restoreGame`: `{"saveFolder": str}`
- `listSaves`: `{}`
- `deleteSave`: `{"saveFolder": str}`

### Decision 2: `createNewModule` remains narrative-driven

**Decision:** `createNewModule` SHALL be documented and validated as a narrative-driven handoff action, not as a rigid two-field schema.

**Rationale:** Runtime currently passes a narrative payload to `ai_driven_module_creation()` and supports optional overrides. The compressed validator's rigid `moduleName` and `startingLocation` shape is stale and causes artificial drift.

**Canonical contract for this phase:**
- Required canonical payload: `{"narrative": str}`
- Optional runtime-supported overrides MAY remain accepted where already supported, such as `moduleName`, `module_name`, `levelRange`, `numberOfAreas`, `locationsPerArea`, `adventureType`, `plotThemes`, or `concept`
- Validator SHALL NOT require `moduleName` and `startingLocation` as the only valid shape

### Decision 3: Prompt parity must cover both variants in active use

**Decision:** This change SHALL enforce parity across both compressed and uncompressed system/validation prompt files.

**Rationale:** Runtime currently loads `prompts/system_prompt.txt`, while validation can use compressed or uncompressed prompt variants depending on configuration. Checking only one copy would leave real drift unguarded.

### Decision 4: Compatibility shims are optional and minimal

**Decision:** If prompt correction exposes a legacy caller or stale test assumption, the implementation MAY add the smallest compatibility shim needed, but only for the covered actions.

**Rationale:** The preferred fix is prompt/validator correction, but a small shim can make rollout safer if a stale side path is still active.

**Examples of acceptable shims:**
- aliasing `saveName` to `saveFolder` only if a live caller still depends on it
- clarifying comments or tiny input normalization around `createNewModule` payload parsing

**Rejected for this phase:**
- broad save-system API redesign
- module builder contract rewrite

## Risks / Trade-offs

- **[Risk] Prompt corrections may surface stale tests or hidden save-path assumptions** -> Mitigation: add focused parity tests first and keep shims minimal.
- **[Risk] `createNewModule` runtime supports more optional fields than prompts should canonize** -> Mitigation: define `narrative` as the canonical minimum while allowing existing runtime-supported overrides without documenting every internal detail as required.
- **[Risk] Builders may over-expand into module-builder refactors** -> Mitigation: tasks and execution prompts MUST forbid architecture rewrites.
- **[Trade-off] Prompt parity tests do not eliminate every source of duplication** -> Accepted because they provide immediate protection with low churn.

## Migration Plan

1. Audit runtime handling for the covered actions and lock the canonical Phase 1B contract.
2. Add parity regression coverage that fails on save/create-module drift across both prompt variants.
3. Align compressed prompt and compressed validator text to the runtime contract.
4. Align uncompressed prompt and uncompressed validator copies to the same contract.
5. Add a minimal compatibility shim only if targeted tests or active callers still require one.
6. Run targeted verification and stop.

Rollback strategy:
- Prompt edits are file-local and easy to revert.
- Any compatibility shim SHOULD be additive and easy to remove.
- Regression tests can remain even if wording is revised later.

## Deferred Follow-Ups

- A later phase SHOULD address deterministic prechecks for illegal HP/slot/inventory mutations before LLM validation.
- A later phase MAY decide whether to generate prompt contracts from a shared schema source rather than relying on parity tests.
- Any remaining action drift outside `saveGame`, `restoreGame`, `listSaves`, `deleteSave`, and `createNewModule` stays out of scope for this change.
