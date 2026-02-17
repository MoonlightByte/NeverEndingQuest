# PC Image Create and Allied NPC Autogen - Implementation Notes

Date: 2026-02-17
Scope: OpenSpec change `pc-image-create-and-allied-npc-autogen`

## Host Hook Markers and Minimality (7.1)

Verified host-file hooks are additive and marked with `# TABLETOP MODE:` in Python host files.

Key hook locations:
- `web/web_interface.py`
  - Missing media warning throttle state and helper
  - Missing media worker startup with allied-only policy callback
  - NPC miss enqueue hook in `serve_module_media(...)`
  - Portrait create endpoint integration (`/api/portrait/create`)
- Existing upload endpoint path retained (`/upload-portrait`), with normalization alignment only.

No broad host refactor was introduced for this change.

## ASCII Compliance (7.2)

Performed non-ASCII scan on changed Python files:
- `core/toolkit/portrait_service.py`
- `web/extensions/missing_media_autogen.py`
- `web/web_interface.py`
- `scripts/test_pc_image_create_mvp.py`

Result: no non-ASCII matches in these changed files.

Note: `model_config.py` has pre-existing non-ASCII arrow comments outside this change block; new added throttle settings are ASCII-only.

## Verification Evidence (7.3)

### Compile checks
Command:
- `python3 -m py_compile core/toolkit/portrait_service.py web/extensions/missing_media_autogen.py web/web_interface.py web/routes/tabletop_party_routes.py utils/character_creation_audit.py`

Result:
- PASS

### Schema validation
Command:
- `python3 core/validation/validate_module_files.py`

Result:
- Dependency block in system environment: `ModuleNotFoundError: No module named 'jsonschema'`

Fallback command:
- `.venv/bin/python core/validation/validate_module_files.py`

Result:
- Script runs in venv; validation report indicates schema-file availability issues in current module context (not caused by this change).

### MVP test script (Step 6.1)
Command:
- `.venv/bin/python scripts/test_pc_image_create_mvp.py`

Result:
- PASS (11 tests, OK)
- Covers:
  - portrait create endpoint behavior (existence, required input, 404 path)
  - allied policy task typing and media type gating expectations
  - warning throttle behavior (first/suppress/re-emit/independent keys)
  - queue dedupe/cooldown behavior

## Notes

- Missing media auto-generation remains non-blocking and fail-open in request path.
- Allied-only gating enforced at worker startup policy callback and at NPC miss pre-check in host path.
- Warning throttle preserves first warning signal and suppresses repeated spam per key/window.
