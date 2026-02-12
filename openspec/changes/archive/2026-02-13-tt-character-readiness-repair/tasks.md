## 1. Backend Repair API Foundation

- [x] 1.1 Add readiness repair preview/apply endpoints in `web/routes/character_sheet_routes.py` (verify: `python3 -m py_compile web/routes/character_sheet_routes.py`).
- [x] 1.2 Add strict repair whitelist and patch sanitizer for narrative-only fields (verify: test that extra/unapproved fields are ignored/rejected).
- [x] 1.3 Add per-character cooldown logic and structured ASCII-safe logging for preview/apply actions (verify: repeated call within window returns cooldown response).

## 2. Proposal Generation and Fallback

- [x] 2.1 Add bounded repair proposal helper (LLM-first, deterministic fallback) in `utils/character_creation_audit.py` or new helper module (verify: helper returns proposal even when LLM path is unavailable).
- [x] 2.2 Ensure proposal parsing tolerates fenced/raw JSON and maps only to whitelisted fields (verify: malformed proposal falls back cleanly).
- [x] 2.3 Reuse readiness/audit pipeline to identify missing fields and validate post-patch payload before save (verify: failed audit blocks apply and preserves original file).

## 3. UI Repair Preview and Confirm Flow

- [x] 3.1 Add `Repair` button in warning block of `web/templates/game_interface.html` visible only when warnings exist (verify: warning-present char shows button; ready char does not).
- [x] 3.2 Add preview modal with field-by-field proposed updates and explicit Confirm/Cancel controls (verify: preview renders expected before/after values).
- [x] 3.3 Wire modal actions to preview/apply endpoints without chat emission side effects (verify: no message inserted into game chat on preview/apply).

## 4. Safety and Compatibility Validation

- [x] 4.1 Add regression checks proving mechanical fields remain unchanged after apply (verify: pre/post mechanical field snapshot comparison).
- [x] 4.2 Verify readiness warning clears for repaired incomplete characters (for example Tester/Xerxes) after confirm apply (verify: `audit_character_readiness` returns ready).
- [x] 4.3 Verify PDF export behavior remains non-breaking and compatible with existing warning header behavior (verify: export endpoint still returns PDF and headers as expected).

## 5. Smoke and Documentation

- [x] 5.1 Run compile checks for modified Python files and capture outputs in change notes (verify: `python3 -m py_compile <files>` passes).
- [ ] 5.2 Run manual GUI smoke: Repair button visibility, preview, cancel, confirm, cooldown message (verify: checklist evidence captured).
- [x] 5.3 Document operator usage (when to Repair vs manual edit) in change notes or docs handoff file (verify: includes fallback behavior and known limits).

## Session Verification Notes (2026-02-12)

- Runtime API checks passed on local server (`http://localhost:8357`):
  - `POST /api/character_sheet/readiness_repair/preview` for `tester` returned proposed updates and `success=true`.
  - `POST /api/character_sheet/readiness_repair/apply` for `tester` and `xerxes` returned `success=true` and readiness `ready=true`.
  - Immediate repeated apply call returned cooldown response (`429` with `retry_after_seconds`).
- Readiness cleared verification passed:
  - `.venv/bin/python` audit script reported `tester {'ready': True}` and `xerxes {'ready': True}`.
- PDF compatibility verification passed:
  - `GET /api/character_sheet/pdf?character=tester` returned `HTTP/1.1 200 OK` and `Content-Type: application/pdf`.
- Remaining manual item:
  - 5.2 browser click-through (visual modal interactions) remains pending explicit GUI walkthrough evidence.
