## Builder Execution Prompts - character-sheet-roll-your-own-edit-entry

Use task order strictly. Do not implement outside current prompt scope.

---

## Execution Contract

MUST:
- MUST keep changes scoped to this task group only.
- MUST preserve existing create flow behavior.
- MUST keep edit flow deterministic and audit-gated.
- MUST NOT use `updateCharacterInfo` for Roll Your Own form edits.
- MUST keep Python-visible output ASCII-only.

SHOULD:
- SHOULD keep host edits minimal and marked with `# TABLETOP MODE:` where relevant.
- SHOULD add focused tests instead of broad test refactors.

---

## Prompt 1 - Character Sheet Edit Entry + Frontend Mode Scaffolding

Implement tasks 2.x and 3.1-3.2.

Scope:
- `web/templates/game_interface.html`
- `web/static/js/tabletop_mode.js`

Required:
- Add `Edit` button before `Download PDF` in the character sheet action row (one line).
- Wire `Edit` to open Manage Party modal and switch to Roll Your Own tab.
- Add quick-create mode state (`create`/`edit`) and prefill helpers for Roll Your Own fields.
- Do not change create submission endpoint behavior in this prompt.

Verify:
- Manual smoke:
  1. Open character sheet.
  2. Confirm action row order is `Edit` then `Download PDF`.
  3. Click `Edit` and confirm Roll Your Own opens with prefilled values.
- If adding JS helpers, include a concise note of function names and call path.

Report:
- List changed functions/elements.
- Include evidence for button order and prefill behavior.

---

## Prompt 2 - Frontend Submit Branch + Backend Edit Route

Implement tasks 3.3-3.5 and 4.x.

Scope:
- `web/static/js/tabletop_mode.js`
- `web/routes/tabletop_party_routes.py`

Required:
- In edit mode, submit to edit endpoint; in create mode keep `/api/party/create_manual`.
- Add deterministic edit endpoint (for example `/api/party/update_manual`).
- Load existing character, apply mapped updates, preserve untouched fields.
- Run `audit_character_creation` and fail closed on audit/write errors.
- Keep party membership and intro prompt behavior unchanged for edit path.
- Do not call `updateCharacterInfo`.

Verify:
- `python3 -m py_compile web/routes/tabletop_party_routes.py`
- Manual smoke for successful edit save and audit-failure no-write.

Report:
- Endpoint contract, success/error payload shape, and preservation behavior summary.

---

## Prompt 3 - Tests and Final Verification

Implement tasks 5.x and 6.1.

Scope:
- `scripts/test_pc_image_create_mvp.py` (or focused new test file)
- any touched files from prior prompts for small fixes only

Required:
- Add tests for:
  - button order contract (`Edit` before `Download PDF`),
  - prefill hook presence/usage,
  - successful edit persistence,
  - audit-failure no-write,
  - create-mode non-regression.

Verify:
- compile checks for modified Python files
- targeted test run(s)

Report:
- PASS/FAIL per test group and concise evidence lines.
- final changed-file list.
