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
