# Archiving and Restore Plan

## JSON Leakage Status

The JSON leakage came from the earlier streaming execution experiment, where draft/token-level output could surface before canonical narration finalized. That path was reverted in the streaming UX rollback, and only the foundation flags/helpers remain dormant.

Current status:

- Streaming execution paths that caused draft leakage are removed.
- Canonical output is back to the stable single-path behavior.
- Manual smoke validation recorded no JSON leakage during intro, non-combat, and combat flows.

If JSON leakage appears again, treat it as regression and first verify streaming flags are still disabled (`ENABLE_CHAT_STREAMING=False` and browser stream sync off).

## Safe Workflow (No Code Changes)

1. Preflight backup (recommended)
   - Copy repo or at minimum: `modules/`, `characters/`, `party_tracker.json`, `data/memory.db`.
   - This is an operator rollback layer in addition to in-app save/restore.

2. Archive current campaign A
   - In GUI, open Save dialog.
   - Use `Archive Edition` (`full`) for max historical coverage.
   - Confirm save folder exists under `modules/<module>/saved_games/save_<timestamp>/`.

3. Initialize campaign B
   - Use GUI reset (`nuclearReset`) for a clean worldline start.
   - Start and play campaign B.

4. Archive campaign B
   - Save again from GUI (same as step 2).

5. Restore campaign A
   - If A and B are in the same module save directory, restore directly in GUI.
   - If A is in a different module save directory, use a module-targeted restore until global index is implemented.

6. Verify memory parity on restored save
   - New-format saves should include `memory_db_package/` with DB artifact + manifest.
   - Restore should report memory package import (or legacy fallback for old saves).

## Phase 1 Gap List and PR Plan

### Scope

Phase 1 automates cross-campaign archive/save/zip/restore in GUI while preserving memory DB parity.

### PR 1 - Global Save Index + Cross-Module Restore + Memory Indicator

Goal: eliminate module-scoped save visibility and make restore module-agnostic in UI.

Backend work:

- Add save discovery across `modules/*/saved_games/save_*`.
- Include source module in each listed save item.
- Add restore API path that accepts both `save_folder` and owning `module` (or absolute validated save path).
- Keep current module-local list mode for backward compatibility, but make GUI default to global scope.

Frontend work:

- Load dialog shows all saves across modules.
- Add module badge/column and sort by timestamp descending globally.
- Add memory parity indicator per save:
  - `memory package: present`
  - `memory package: legacy`

Acceptance criteria:

- Can save in module A, switch/init module B, and restore A from GUI without manual terminal steps.
- Restore uses managed memory package import when package exists.
- Legacy saves remain restorable with deterministic fallback.

Primary files:

- `updates/save_game_manager.py`
- `web/web_interface.py`
- `web/templates/game_interface.html`

### PR 2 - Auto Archive Zip + Memory Coverage in Reset Backup

Goal: every GUI `Archive Edition` save produces a portable zip automatically (no new UI controls) and backup parity is strengthened for reset workflow.

Backend work:

- On existing GUI save action, when `save_mode == full` (`Archive Edition`), auto-generate zip in backend with no extra button path.
- Zip output naming: deterministic and tied to save folder (example: `<save_folder>.zip`).
- Zip content target: full campaign recovery for all played modules, not just current module snapshot.
- Include complete archive snapshot content and `memory_db_package/` when present.
- If archive zip generation fails, fail the archive save operation explicitly (portable backup is a hard requirement for patron data continuity).

Reset backup hardening:

- Extend `utils/reset_campaign.py` backup phase to capture memory state explicitly:
  - include `data/memory.db` when present, or
  - export memory package into backup directory.

Frontend work:

- No new buttons.
- Reuse existing Save dialog and existing `Archive Edition` mode.
- Show save result message including zip artifact path/status.

Acceptance criteria:

- Triggering `Archive Edition` from current Save dialog always produces a portable zip artifact.
- Archive zip contains campaign state recoverable for all played modules and includes memory parity artifacts.
- Archive save fails clearly if portable zip creation fails.
- Reset backup includes memory state artifact.

Primary files:

- `updates/save_game_manager.py`
- `web/web_interface.py`
- `utils/reset_campaign.py`
- `core/memory/memory_portability.py` (reuse existing helpers; extend only if needed)

## Validation Plan

- Unit/integration tests for save discovery and cross-module restore routing.
- Auto-zip archive tests on `save_mode=full`, including failure-path enforcement.
- Memory package parity checks on save, restore, auto-zip archive, and reset backup.
- Manual smoke:
  - A save -> B save -> restore A from GUI.
  - Archive Edition save -> verify zip artifact -> copy to external media path.
