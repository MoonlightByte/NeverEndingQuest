## Context

Roll Your Own already exists for manual character creation and is wired through:
- `web/templates/partials/character_tabs.html`
- `web/static/js/tabletop_mode.js` (`submitQuickCreate()`)
- `web/routes/tabletop_party_routes.py` (`/api/party/create_manual`)

Character sheet actions currently include `Download PDF` only. We will add an in-sheet edit entry that reuses Roll Your Own.

## Goals / Non-Goals

**Goals:**
- Provide direct in-sheet edit entry (`Edit`) adjacent to `Download PDF`.
- Reuse Roll Your Own modal and field contract.
- Add deterministic edit persistence path for existing PCs.
- Enforce shared audit before save.

**Non-Goals:**
- Introduce LLM/NLP edit parsing.
- Add character rename workflow.
- Replace readiness repair flow.

## Decisions

### 1) Reuse existing Roll Your Own modal (MUST)
Decision: `Edit` opens Manage Party modal, activates `quick-create` tab, and preloads current PC values.

Rationale:
- Prevents duplicated forms and drift.
- Keeps maintenance small and merge-safe.

### 2) Explicit edit mode in frontend state (MUST)
Decision: Add mode state (`create` or `edit`) in `tabletop_mode.js` for the quick-create form.

Rationale:
- Keeps one submit handler with deterministic branching.
- Enables simple UI differences (button label, name read-only).

### 3) Deterministic backend edit route (MUST)
Decision: Add a dedicated route (for example `/api/party/update_manual`) in `tabletop_party_routes.py`.

Rationale:
- Existing `/api/party/create_manual` is create-only and writes new files + party insertion.
- Edit route must load existing character and preserve party state.

### 4) No `updateCharacterInfo` for this flow (MUST)
Decision: Do not call `updates.update_character_info.update_character_info()`.

Rationale:
- That path is LLM-driven and optimized for narrative/runtime updates.
- Form edits must be deterministic and auditable.

### 5) Data preservation policy (MUST)
Decision: Apply only mapped form fields onto existing character payload; preserve untouched fields.

Rationale:
- Avoids accidental loss of nested structures not represented by form inputs.

### 6) Validation gate and fail-closed save (MUST)
Decision: Run `audit_character_creation(...)` after merge and before save.
- On audit failure: return structured error, no write.
- On write failure: return 500, no party mutation.

## MUST / SHOULD Contract

MUST:
- MUST render `Edit` before `Download PDF` in one row.
- MUST open Roll Your Own with prefilled active-PC data.
- MUST save through deterministic route and atomic write.
- MUST preserve non-targeted state and party membership.
- MUST keep create path behavior unchanged.

SHOULD:
- SHOULD keep name read-only in edit mode (MVP).
- SHOULD provide clear success/error messaging in existing UI surfaces.
- SHOULD add source-level regression tests for button order and edit route contract.

## Risks / Trade-offs

- [Risk] Prefill misses some fields -> [Mitigation] map all existing Roll Your Own fields and add source-level tests.
- [Risk] Edit path accidentally behaves like create path -> [Mitigation] separate route and explicit mode flag.
- [Risk] Data loss in complex nested fields -> [Mitigation] merge-on-existing payload, not replace-whole-payload.

## Migration Plan

1. Add OpenSpec artifacts and verify change scaffold.
2. UI hook: button row update + edit mode modal open + prefill.
3. Backend route: deterministic edit save with audit gate.
4. Regression tests and compile checks.

Rollback:
- Remove `Edit` button and edit mode branch.
- Remove edit route.
- Keep existing create flow untouched.

## Verification Strategy

- Compile check: `python3 -m py_compile web/routes/tabletop_party_routes.py`
- Targeted tests for:
  - button order (`Edit`, then `Download PDF`),
  - edit mode prefill contract,
  - successful update writes existing file,
  - audit failure blocks write,
  - create flow remains unchanged.
- Manual smoke:
  - open character sheet -> Edit -> modify fields -> save -> sheet refresh reflects updates.
