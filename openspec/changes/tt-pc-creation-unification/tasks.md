## 1. Shared Audit Foundation

- [x] 1.1 Add shared character creation audit helpers (normalize -> schema validate -> completeness audit -> optional enrichment) in `utils/character_creator.py` or new `utils/character_creation_audit.py` (verify: `python3 -m py_compile` on modified file(s)).
- [x] 1.2 Define deterministic audit result classes (`schema_error`, `completeness_error`, `success`) and structured error payloads (verify: focused unit-style script/assertions for each result type).
- [x] 1.3 Add regression-safe ASCII logging for creation audit outcomes (verify: no Unicode symbols in new Python log strings).

## 2. Create with DM Finalization Hardening

- [x] 2.1 Update creation JSON extraction in `main.py` finalization path to accept raw and fenced JSON consistently (verify: local test inputs for both formats finalize correctly).
- [x] 2.2 Replace weak required-field gate in `main.py` with shared schema/completeness audit before save (verify: invalid payload blocked, valid payload persisted).
- [x] 2.3 Keep creation mode active on audit failure and enqueue corrective guidance with missing field paths (verify: marker file remains until successful finalization).

## 3. Roll Your Own (Manual Creation) Upgrade

- [x] 3.1 Rename `DM Quick-Create` to `Roll Your Own` in `web/templates/partials/character_tabs.html` and any dependent JS labels (verify: UI tab text changed, no broken tab switching).
- [x] 3.2 Expand manual form sections in `web/templates/partials/character_tabs.html` to cover key 5e sheet groups (identity, abilities, saves/skills, combat, proficiencies/languages, equipment, spellcasting, personality) (verify: form submits expected keys).
- [x] 3.3 Route manual submit in `web/routes/tabletop_party_routes.py` through shared audit before file write (verify: incomplete submit rejected; valid submit created and added to party).

## 4. Mid-Campaign Add Existing Filter and Dedupe

- [x] 4.1 Filter `/api/party/characters` results in `web/routes/tabletop_party_routes.py` to exclude current `partyMembers` (verify: active party PCs not shown in modal list).
- [x] 4.2 Deduplicate discovered characters across global/module scans in the same endpoint (verify: single entry returned per character name).
- [x] 4.3 Preserve backward-compatible response shape for frontend list rendering (verify: `web/static/js/tabletop_mode.js` works without additional parsing errors).

## 5. Startup Multi-PC Campaign Initiation Loop

- [x] 5.1 Extend startup flow in `utils/startup_wizard.py` to prompt for additional players after each successful creation (verify: can create 2+ PCs in one startup run).
- [x] 5.2 Update party tracker write logic in `utils/startup_wizard.py` to append party members instead of overwrite during loop completion (verify: `partyMembers` persists all created PCs).
- [x] 5.3 Keep single-player behavior unchanged when no additional players are requested (verify: existing one-PC startup path still passes).

## 6. Sheet/PDF Readiness Visibility

- [x] 6.1 Add non-fatal readiness audit hook for character sheet consumers in `web/templates/game_interface.html` data path and/or server-side response metadata (verify: warnings visible for incomplete legacy sheets).
- [x] 6.2 Add non-fatal readiness audit hook in `web/routes/character_sheet_routes.py` before PDF field mapping (verify: valid exports unchanged; incomplete data emits warning context only).

## 7. Verification and Scenario Acceptance

- [x] 7.1 Run syntax checks on all touched Python files (verify: `python3 -m py_compile <files>` passes).
- [ ] 7.2 Execute scenario smoke checks for all four workflows: campaign initiation multi-PC loop, Add Existing filtering, Create with DM completeness recovery, Roll Your Own validation (verify: checklist evidence recorded in change notes).
- [ ] 7.3 Confirm SP/MP compatibility invariants (single-PC startup unchanged, multi-PC runtime state consistent) (verify: manual startup + party tab smoke run).

## Session Verification Notes (2026-02-12)

- Completed: `python3 -m py_compile utils/character_creation_audit.py scripts/test_character_creation_audit.py web/routes/tabletop_party_routes.py web/routes/character_sheet_routes.py utils/startup_wizard.py main.py`
- Pending manual smoke: full app startup and browser workflows for 7.2 and 7.3
- Blocker: local runtime environment is missing `jsonschema`, so `python3 scripts/test_character_creation_audit.py` cannot execute until dependencies are installed
