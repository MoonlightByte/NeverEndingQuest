## 1. Schema and audit foundation

- [ ] 1.1 Add `backstory` field to `schemas/char_schema.json` properties (additive, string).
- [ ] 1.2 Add `backstory` to `_canonical_character_defaults()` in `utils/character_creation_audit.py`.
- [ ] 1.3 Add `backstory` to completeness paths for PC creation audit.
- [ ] 1.4 Add `backstory` to profile readiness path checks.
- [ ] 1.5 Add `backstory` to `READINESS_REPAIR_WRITABLE_FIELDS` and fallback text map.
- [ ] 1.6 Preserve mechanical immutability guardrails and update tests accordingly.

## 2. PC creation workflows (Roll Your Own + Create with DM + startup)

- [ ] 2.1 Add `Backstory` input to Roll Your Own form in `web/templates/partials/character_tabs.html`.
- [ ] 2.2 Persist `backstory` from `/api/party/create_manual` in `web/routes/tabletop_party_routes.py`.
- [ ] 2.3 Update DM interview prompt contract (`prompts/character_creation/dm_interview_prompt.txt`) to collect and require `backstory` in final JSON.
- [ ] 2.4 Update Create with DM fallback guidance string in `web/routes/tabletop_party_routes.py` to include backstory.
- [ ] 2.5 Add `backstory` to startup fallback character path in `utils/startup_wizard.py`.

## 3. Portrait Create modal and API contract

- [ ] 3.1 Replace portrait modal background-feature fields with a required `Backstory` textarea in `web/templates/game_interface.html`.
- [ ] 3.2 Update frontend required-field list and payload construction to send `backstory`.
- [ ] 3.3 Update `_REQUIRED_PORTRAIT_PROFILE_FIELDS` in `web/web_interface.py` to require `backstory` instead of background-feature fields.
- [ ] 3.4 Update `_extract_profile_payload()` and `_build_profile_update_payload()` to parse/persist `backstory`.
- [ ] 3.5 Keep backward-compatible parsing behavior for old payload keys where reasonable.

## 4. Narrative influence and context injection

- [ ] 4.1 Add bounded backstory clause to portrait prompt builder in `core/toolkit/portrait_service.py`.
- [ ] 4.2 Inject bounded backstory into character context formatting in `core/ai/conversation_utils.py`.
- [ ] 4.3 Inject bounded backstory into combat character formatter in `core/managers/combat_manager.py`.
- [ ] 4.4 Add backstory visibility in multi-PC DM note summaries (`utils/multi_pc_dm_note.py`) using concise bounded format.
- [ ] 4.5 Add backstory output token in `core/ai/character_sheet_compressor.py`.

## 5. Promotion and PDF alignment

- [ ] 5.1 Ensure NPC->PC promotion profile readiness warnings include missing `backstory` (non-blocking) in `web/routes/tabletop_party_routes.py`.
- [ ] 5.2 Optionally seed empty `backstory` during promotion normalization if absent (additive).
- [ ] 5.3 Update PDF page 2 Backstory mapping in `web/routes/character_sheet_routes.py` to prefer authored `backstory` (with optional recent-adventures append).
- [ ] 5.4 Confirm `backgroundFeature` remains mapped to `Feat+Traits` and unchanged in semantics.

## 6. Tests and verification

- [ ] 6.1 Update `scripts/test_character_creation_audit.py` for backstory completeness/readiness/repair expectations.
- [ ] 6.2 Update `scripts/test_pc_image_create_mvp.py` profile validation suites to require backstory.
- [ ] 6.3 Add/adjust tests for promotion warnings including backstory missing path.
- [ ] 6.4 Run compile checks on modified Python files.
- [ ] 6.5 Run targeted test scripts and capture pass/fail summary.

## 7. Builder handoff

- [ ] 7.1 Keep `executor_prompts.md` aligned with completed task scope and verification gates.
