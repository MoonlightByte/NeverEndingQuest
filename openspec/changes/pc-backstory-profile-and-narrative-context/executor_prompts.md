## Builder Execution Prompts - pc-backstory-profile-and-narrative-context

Use task order strictly. Do not implement outside current prompt scope.

## Execution Contract

- MUST keep `backgroundFeature` behavior intact while introducing `backstory`.
- MUST keep schema changes additive (no breaking required-list migration for legacy files).
- MUST replace portrait Create modal background-feature inputs with `backstory`.
- MUST keep mechanical state invariants unchanged in audit/repair paths.
- SHOULD bound backstory text when injected into prompts/contexts.
- SHOULD keep host-file edits minimal and marked with `# TABLETOP MODE:` where relevant.

---

## Prompt 1 - Schema and audit foundation (tasks 1.x)

Implement tasks 1.1-1.6.

Scope:
- `schemas/char_schema.json`
- `utils/character_creation_audit.py`
- `scripts/test_character_creation_audit.py`

Requirements:
- Add additive `backstory` schema property.
- Include `backstory` in canonical defaults and PC completeness/readiness checks.
- Add `backstory` to readiness repair writable/fallback paths.
- Preserve mechanical immutability checks.

Verify:
- `python3 -m py_compile utils/character_creation_audit.py`
- `python3 scripts/test_character_creation_audit.py`

---

## Prompt 2 - PC creation workflows (tasks 2.x)

Implement tasks 2.1-2.5.

Scope:
- `web/templates/partials/character_tabs.html`
- `web/routes/tabletop_party_routes.py`
- `prompts/character_creation/dm_interview_prompt.txt`
- `utils/startup_wizard.py`

Requirements:
- Add backstory capture in Roll Your Own and backend persistence.
- Require backstory in Create with DM prompt contract and fallback guidance.
- Ensure startup fallback includes backstory key.

Verify:
- `python3 -m py_compile web/routes/tabletop_party_routes.py utils/startup_wizard.py`
- Manual form payload inspection for `backstory` passthrough

---

## Prompt 3 - Portrait profile contract swap (tasks 3.x)

Implement tasks 3.1-3.5.

Scope:
- `web/templates/game_interface.html`
- `web/web_interface.py`
- `scripts/test_pc_image_create_mvp.py`

Requirements:
- Replace background-feature portrait modal fields with required backstory.
- Update frontend required list and API payload.
- Update server-side required profile fields and persistence mapping.
- Keep reasonable backward compatibility for old payload clients.

Verify:
- `python3 -m py_compile web/web_interface.py`
- targeted profile validation tests in `scripts/test_pc_image_create_mvp.py`

---

## Prompt 4 - Narrative influence integration (tasks 4.x)

Implement tasks 4.1-4.5.

Scope:
- `core/toolkit/portrait_service.py`
- `core/ai/conversation_utils.py`
- `core/managers/combat_manager.py`
- `utils/multi_pc_dm_note.py`
- `core/ai/character_sheet_compressor.py`

Requirements:
- Add bounded backstory context in portrait prompt and runtime context formatters.
- Keep additions concise and non-mechanical.

Verify:
- `python3 -m py_compile core/toolkit/portrait_service.py core/ai/conversation_utils.py core/managers/combat_manager.py utils/multi_pc_dm_note.py core/ai/character_sheet_compressor.py`

---

## Prompt 5 - Promotion + PDF alignment + final verification (tasks 5.x, 6.x, 7.x)

Implement tasks 5.1-5.4, 6.1-6.5, and 7.1.

Scope:
- `web/routes/tabletop_party_routes.py`
- `web/routes/character_sheet_routes.py`
- test files touched in prior prompts
- `openspec/changes/pc-backstory-profile-and-narrative-context/executor_prompts.md`

Requirements:
- Promotion warnings include backstory gaps without blocking apply.
- PDF `Backstory` field prefers authored backstory.
- Preserve `backgroundFeature` -> `Feat+Traits` mapping.
- Run compile and targeted tests, summarize results.

Verify:
- compile checks for all modified Python files
- `python3 scripts/test_character_creation_audit.py`
- targeted `python3 scripts/test_pc_image_create_mvp.py` suites
