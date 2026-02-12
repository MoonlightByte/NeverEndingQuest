## Implementation Notes - tt-character-readiness-repair

### What Was Implemented

- Added backend endpoints:
  - `POST /api/character_sheet/readiness_repair/preview`
  - `POST /api/character_sheet/readiness_repair/apply`
- Added narrative-only repair whitelist and sanitizer:
  - `personality_traits`
  - `ideals`
  - `bonds`
  - `flaws`
  - `backgroundFeature.description`
- Added cooldown and structured logging for preview/apply actions.
- Added bounded repair proposal helper in `utils/character_creation_audit.py`:
  - LLM-first proposal generation
  - Deterministic fallback if LLM path is unavailable
  - Fenced/raw JSON parsing with strict patch sanitization
- Added apply-time safety gates:
  - Mechanical snapshot comparison before/after patch
  - Post-patch audit gate (`audit_character_creation(..., enable_enrichment=False)`)
  - Save blocked when post-patch audit fails
- Added stats-panel `Repair` button and preview modal in `web/templates/game_interface.html`.
- Wired modal preview/apply actions through API calls only (no chat injection).

### Compile Checks (Task 5.1)

Command executed:

```bash
python3 -m py_compile "utils/character_creation_audit.py" "web/routes/character_sheet_routes.py" "web/web_interface.py"
```

Result:
- PASS (no syntax errors)

### Operator Usage

- Use `Repair` when the character sheet warning banner shows missing narrative fields.
- Flow is always `Preview -> Confirm`; no write occurs at preview time.
- If preview/apply is called repeatedly on the same character inside cooldown window, API returns a rate-limited response with `retry_after_seconds`.
- If LLM proposal generation is unavailable, deterministic fallback text is used so preview still works.
- If patch validation fails (mechanical drift or failed post-patch audit), apply is blocked and original file is preserved.
- For mechanical/stat fixes, use normal character edit/update workflows (Repair is narrative-only by design).

### Known Limits

- This change does not enable inline manual editing inside the preview modal (confirm/cancel only).
- Cooldown is per-character, per-action (`preview` and `apply` tracked separately).
- Manual GUI smoke verification still required on a running web session.
