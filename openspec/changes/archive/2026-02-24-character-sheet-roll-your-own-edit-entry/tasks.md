## 1. OpenSpec scaffold and contract

- [x] 1.1 Add proposal/design/spec/tasks artifacts for this change with explicit MUST and SHOULD sections.
- [x] 1.2 Validate artifact language is testable and aligned to merge-safe plugin rules.

## 2. Character sheet UI entry

- [x] 2.1 Update character sheet action row in `web/templates/game_interface.html` to render `Edit` before `Download PDF` in one line.
- [x] 2.2 Wire `Edit` click handler to open Manage Party modal and activate Roll Your Own tab.
- [x] 2.3 Ensure button styling is consistent with existing character sheet controls.

## 3. Roll Your Own edit mode frontend

- [x] 3.1 Add quick-create form mode state (`create`/`edit`) in `web/static/js/tabletop_mode.js`.
- [x] 3.2 Implement prefill mapping from active character data into Roll Your Own fields.
- [x] 3.3 In edit mode, submit to edit endpoint and keep create endpoint for create mode.
- [x] 3.4 Set name field read-only during edit mode for MVP safety.
- [x] 3.5 Keep existing create behavior unchanged when launched from Manage Party.

## 4. Backend deterministic edit endpoint

- [x] 4.1 Add edit route in `web/routes/tabletop_party_routes.py` (for example `/api/party/update_manual`).
- [x] 4.2 Load existing character payload, merge mapped form fields, preserve untouched fields.
- [x] 4.3 Run `audit_character_creation(...)` on merged payload before write.
- [x] 4.4 Save with `safe_write_json`; return structured errors on audit/write failure.
- [x] 4.5 Ensure edit route does not mutate `party_tracker.json` membership or enqueue create-intro prompts.
- [x] 4.6 Keep implementation deterministic; do not call `updateCharacterInfo`.

## 5. Tests and verification

- [x] 5.1 Add or update targeted tests for UI source contracts and edit route behavior.
- [x] 5.2 Add assertions for button order and edit mode prefill hooks.
- [x] 5.3 Add assertions for audit-failure no-write behavior.
- [x] 5.4 Verify create-mode non-regression.
- [x] 5.5 Run compile checks and targeted tests; capture pass/fail summary.

## 6. Builder handoff

- [x] 6.1 Keep `executor_prompts.md` aligned with task sequencing and verification gates.
