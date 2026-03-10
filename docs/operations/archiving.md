# Archiving Plan

## Status Snapshot

### PR1 (Completed)
Change: `archive-global-save-index-and-restore-routing`

Completed and validated:
- Global save catalog discovery across modules
- Deterministic global ordering
- Additive global metadata (`source_module`, `memory_package_present`)
- Cross-module restore routing with validation
- Legacy `saveFolder` restore compatibility preserved
- Web action integration (`listSaves`, `restoreGame`)
- Load dialog integration (source module + memory indicator + module-aware payload)

### PR2 (Next)
Change: `archive-zip-portability-and-memory-backup-parity`

PR2 goals:
- Auto-generate portable zip on Archive Edition save (`save_mode=full`)
- Include memory parity artifacts when present
- Fail archive save if zip generation fails (fail-closed)
- Keep `save_mode=essential` behavior unchanged
- No new GUI zip buttons

Operational note for next build:
- Add a repo-root export folder for portable archives so library staff can easily find/copy zips to USB.
- Planned restore-from-zip flow should look in that repo-root archive folder by default.

---

## PR2 Staged Execution Plan

1. Archive Auto-Zip Backend (`updates/save_game_manager.py`)
   - Step 1.1: Add zip generation helper for full-save path
   - Step 1.2: Implement campaign-wide inclusion policy for played modules
   - Step 1.3: Include `memory_db_package/` when present + fail-closed behavior

2. Existing Save Flow Integration (`web/web_interface.py` and save response path)
   - Step 2.1: Trigger auto-zip only for `save_mode=full`
   - Step 2.2: Return zip status/path in existing save result flow
   - Step 2.3: Preserve essential save behavior unchanged

3. Reset Backup Memory Parity (`utils/reset_campaign.py`)
   - Step 3.1: Include memory artifact in reset backup when available
   - Step 3.2: Non-fatal handling if memory artifact missing
   - Step 3.3: Preserve existing backup layout compatibility

4. Validation
   - Step 4.1: `py_compile` gate
   - Step 4.2: Positive smoke (full save produces zip + path in result)
   - Step 4.3: Negative smoke (forced zip failure fails full save, essential still passes)

---

## Builder Scaffold - PR2 Step 1.1

Use this staged prompt format for implementation review.

### You are implementing PR2 Step 1.1 for NeverEndingQuest.

Goal
- Implement ONLY Step 1.1: add archive zip generation helper in `updates/save_game_manager.py` for `save_mode=full`.

Context
- OpenSpec change: `archive-zip-portability-and-memory-backup-parity`
- PR1 global save index/restore routing is complete.
- Step 1.1 is helper-only scaffolding; do not wire full trigger behavior yet.

Scope (Allowed)
- Edit only: `updates/save_game_manager.py`
- Add helper method(s) for deterministic zip generation and structured result.

Scope (Forbidden in this step)
- Do NOT wire zip trigger into `create_save_game(...)` flow yet (Step 2.x).
- Do NOT modify web/UI files.
- Do NOT modify reset backup behavior.
- Do NOT add PR2 Step 1.2/1.3 logic in this pass.

Required implementation
1) Add helper method (name may vary, suggested):
   - `_generate_archive_zip(self, save_path: str, metadata: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]`
2) Helper behavior:
   - Create deterministic zip artifact path/name from save metadata/timestamp-safe values.
   - Build zip from existing save folder envelope (no custom flattening).
   - Return structured result dict on success/failure.
3) Structured result contract (suggested):
   - Success: `{"status": "success", "zip_path": "...", "zip_name": "...", "bytes": <int>}`
   - Failure: `{"status": "error", "message": "..."}`
4) Safety behavior:
   - Validate input paths are usable before zipping.
   - Do not mutate save folder contents.

Coding constraints
- ASCII-only user-facing Python strings.
- Minimal, merge-safe changes.
- Mark host/core edits with `# TABLETOP MODE:` comments when applicable.

Verification (must run)
1) `python3 -m py_compile updates/save_game_manager.py`
2) Unit smoke (helper-level):
   - Call helper with a known valid save path -> success result with zip path and bytes > 0.
   - Call helper with invalid path -> clean failure result.
3) Artifact check:
   - Verify zip file exists at returned path.
   - Verify zip is readable via `zipfile.ZipFile(...).testzip()`.

Expected report format
- Changed files (exact list)
- Helper signature and result contract
- Verification outputs (pass/fail)
- Confirmation no trigger wiring or UI changes were made in Step 1.1

---

## PR2 Guardrails Reminder

- No new GUI zip buttons in PR2.
- Auto-generate portable zip only when Archive Edition (`save_mode=full`) runs.
- Fail archive save if zip generation fails.

---

## PR3 (Planned) - Root Archive Folder + Zip Import Restore

Change (planned): `archive-root-export-and-zip-import-restore`

### Why

Library staff need a predictable, easy-to-find archive location at repo root for USB copy workflows. The next step is to make full-save zips land in a dedicated root folder and add restore-from-zip that reads from the same folder.

### Objectives

1. Export location UX:
   - Full-save zip artifacts written to a repo-root folder (proposed: `archive_exports/`).
   - Deterministic filenames, easy manual copy to external media.
2. Zip restore UX:
   - Restore flow can import zip archives from that root folder.
   - Reuse existing restore semantics after safe zip validation and staging.
3. Safety:
   - Strict zip validation and path traversal protection.
   - Fail closed on invalid zip restore requests.
4. Compatibility:
   - Keep existing folder-based restore working.
   - Keep `save_mode=essential` behavior unchanged.

### Architecture Decisions

1) Root export directory
- Introduce repo-root folder: `archive_exports/`.
- On full save, zip artifact is generated in `archive_exports/`.
- Optional compatibility duplicate in `saved_games/` is not required for MVP; prefer single canonical export location.

2) Deterministic archive naming
- Proposed format: `archive_<module>_<timestamp>_<save_folder>.zip`.
- ASCII-only, filesystem-safe, deterministic for supportability.

3) Zip import restore model
- Validate archive first (read-only): required metadata and expected save envelope.
- Extract to temporary staging directory.
- Stage extracted save folder into `modules/<source_module>/saved_games/`.
- Delegate actual restore to existing validated restore path (`restore_save_game_global`).
- Cleanup temp staging on success/failure.

4) Trust boundaries and validation
- Reject archives with path traversal entries (`..`, absolute paths).
- Reject missing `save_metadata.json` or missing/invalid module mapping.
- Reject malformed archive envelopes that cannot map to a canonical save folder.

### Detailed Implementation Plan

#### Phase A - Root archive export path
1. Add `ARCHIVE_EXPORTS_DIR = "archive_exports"` constant in save manager layer.
2. Ensure directory creation on full-save zip generation.
3. Switch full-save zip output path from module `saved_games/` sibling to root export folder.
4. Preserve success payload fields (`zip_path`, `zip_name`, `bytes`) and update path value accordingly.
5. Keep fail-closed full-save behavior intact.

#### Phase B - Archive catalog for zip restore
1. Add zip catalog discovery in save manager:
   - list `archive_exports/*.zip`
   - derive metadata summary (filename, size, mtime)
   - optional parsed metadata preview from archive `save_metadata.json`
2. Add API action path(s) in web layer for listing zip archives.
3. Keep existing `listSaves` and folder catalog unchanged.

#### Phase C - Zip preflight validation + staging
1. Add save manager helper for zip preflight:
   - open zip
   - validate entries and traversal safety
   - locate and parse `save_metadata.json`
   - resolve `source_module` and `save_folder`
2. Add extraction helper to temp staging dir with strict arcname checks.
3. Add staging helper to copy extracted save folder into canonical `modules/<module>/saved_games/<save_folder>`.

#### Phase D - Restore integration
1. Add web action `restoreArchiveZip` (or equivalent) to invoke zip restore pipeline.
2. On successful staging, call existing folder restore route logic.
3. Emit existing restore success/restart behavior.
4. On failure, emit explicit restore error with no partial success messaging.

#### Phase E - UI wiring (minimal)
1. Add archive-zip list in existing Load dialog flow (no new top-level button).
2. Provide clear operator labels: filename, size, modified time.
3. Route selection to zip restore action while preserving current folder-restore UX.

#### Phase F - Validation + operations
1. Compile checks for touched files.
2. Positive smoke: full save -> zip in `archive_exports/` -> reset -> restore from zip.
3. Negative smoke: invalid zip, missing metadata, path traversal attempts.
4. Regression smoke: essential save unchanged; folder restore unchanged.

### Acceptance Criteria

- Full save creates zip in `archive_exports/` with deterministic name.
- Save success payload includes archive path under `archive_exports/`.
- Zip restore from `archive_exports/` succeeds and reuses existing restore semantics.
- Invalid zips fail with explicit operator-facing errors.
- Essential save and folder-based restore remain backward-compatible.

### Operations Notes

- `archive_exports/` becomes the primary handoff folder for staff USB copy.
- Zip import restore should default to this folder for discoverability.

---

## Builder Scaffold - PR3 (Plan-to-Builder)

Use OpenSpec change `archive-root-export-and-zip-import-restore` with staged prompts:

1. Step 1.x: Root export directory and deterministic zip naming.
2. Step 2.x: Zip catalog listing and API wiring.
3. Step 3.x: Zip validation, secure extraction, and save-folder staging.
4. Step 4.x: Restore integration and UI load-dialog wiring.
5. Step 5.x: Compile/smoke/negative/regression validation gates.

Execution contract:
- MUST preserve existing folder-based restore behavior.
- MUST keep fail-closed semantics for invalid/failed zip restore.
- MUST keep essential save behavior unchanged.
- MUST keep host edits merge-safe and TABLETOP MODE marked.
