# Progress Status

## Project: NeverEndingQuest - Tabletop Interface & Core Engine

## 🟢 Current Status
Active development of Tabletop Mode features, focusing on party management and UI improvements.

### Documentation Maintenance
- 2026-02-04: Memory Bank reviewed/updated on request (documentation-only pass; no code changes).

## 🚀 Recent Achievements

- **Load Dialog Unified Archive/Save Timeline (COMPLETED - 2026-02-17):**
  - **OpenSpec Change:** `load-dialog-unified-archive-save-timeline` fully implemented, validated, archived, and spec-synced
  - **Objective:** Present save folders and archive zips in one merged recency-ordered timeline with type filters
  - **Key Implementation:**
    - Unified entry normalization in `web/templates/game_interface.html` with `normalizeLoadEntries()`, `parseSaveTimestamp()`, `parseArchiveTimestamp()`
    - Newest-first sorting via `compareUnifiedEntries()` with deterministic tie-break (timestamp desc -> type_order -> display_name)
    - Filter chips (`all`, `save_folders`, `archive_zips`) with default `all`, active state styling via CSS
    - Selection safety: automatic clear when selected entry filtered out, button state updates
    - Preserved action routing: `restoreGame` for save folders, `restoreArchiveZip` for archives
    - Delete restriction maintained: only enabled for save-folder selections
  - **Files Modified:** `web/templates/game_interface.html` (unified model, filter UI, merged render, CSS)
  - **Verification:** Compile PASS, JS syntax PASS, `openspec validate` PASS, all invariant checks PASS
  - **Archived:** `openspec/changes/archive/2026-02-17-load-dialog-unified-archive-save-timeline/`
  - **Main Specs Updated:** `load-dialog-action-compatibility/`, `load-dialog-entry-filters/`, `load-dialog-unified-timeline/`

- **Exit/Enter GUI Button Implementation Phase 1 (COMPLETED - 2026-02-17):**
  - **OpenSpec Change:** `exit-only-gui-shutdown` fully implemented, validated, and archived
  - **Objective:** Enable graceful server shutdown from GUI Exit button without requiring terminal Ctrl+C
  - **Server Handler** (`web/web_interface.py`): Upgraded `handle_user_exit()` to emit `exit_acknowledged`, attempt graceful `socketio.stop()`, and force exit with code `91` (fail-closed on exceptions)
  - **Launcher Contract** (`run_web.py`): Added explicit `elif result.returncode == 91` branch to print shutdown message and break loop without restart
  - **GUI Flow** (`web/templates/game_interface.html`): Immediate "Shutting Down..." overlay on Exit confirm, input controls disabled, `user_exit` event emission
  - **Ack Handler** (`web/templates/game_interface.html`): `exit_acknowledged` listener updates overlay text, no restart/reload logic
  - **Key Behaviors:**
    - Exit code `91` = intentional GUI shutdown (no restart)
    - Exit code `0` = restart path preserved for reset/restore flows
    - ASCII-only terminal output (`[Py]`, `[SHUTDOWN]`, `[ERROR]`)
    - All changes marked with `# TABLETOP MODE:` comments
  - **Verification:**
    - Compile checks passed (`python3 -m py_compile web/web_interface.py run_web.py`)
    - Smoke test passed (GUI Exit -> code 91 -> shutdown message -> no restart)
    - Regression passed (reset/restore code `0` restart unchanged)
    - Ctrl+C fallback works cleanly
  - **Files Modified:** `web/web_interface.py`, `run_web.py`, `web/templates/game_interface.html`
  - **Archived:** `openspec/changes/archive/2026-02-17-exit-only-gui-shutdown/`

- **PC Image Create and Allied NPC Auto-Generation Planning (PLANNED - 2026-02-16):**
  - Created comprehensive UX enhancement plan at `/plans/pc-image-create.md` for Character Sheet portrait `Upload / Create` actions
  - **Auto-Generation Policy:** Automatic generation enabled for allied NPC companions only; disabled for non-allied NPCs and monsters in MVP
  - **Appearance Fields:** Added optional character schema fields (`age`, `height`, `weight`, `eyes`, `skin`, `hair`) for portrait prompt enrichment
  - **Missing Media Warning Throttle:** Per-key warning throttling to reduce repeated log spam
  - **Promotion Continuity:** NPC -> PC promotion preserves image linkage by name identity
  - **OpenSpec Scaffolding:** Created change `pc-image-create-and-allied-npc-autogen` with complete artifact set:
    - `proposal.md`, `design.md`, `tasks.md`, `executor_prompts.md`
    - Four capability specs: `pc-sheet-upload-create-portrait`, `allied-npc-missing-media-autogen`, `missing-media-warning-throttle`, `appearance-fields-for-portrait-prompts`
  - **New Modules Planned:**
    - `core/toolkit/portrait_service.py` - prompt composition, generation calls, canonical file outputs
    - `web/extensions/missing_media_autogen.py` - async worker with dedupe/cooldown, allied-only policy enforcement
  - **Integration Points:**
    - Character Sheet portrait controls in `web/templates/game_interface.html`
    - Create endpoint `POST /api/portrait/create` in `web/web_interface.py`
    - Missing media enqueue hook in `/media/<media_type>/<filename>` serving path
  - **Step 1.1 Completed:** Added optional appearance fields to `schemas/char_schema.json` with backward compatibility preserved
  - **Time Estimate:** 2-3 days for full implementation
  - **Status:** Plan complete, OpenSpec validated, Step 1.1 complete, ready for builder execution

- **PR3 Root Archive Export + Zip Import Restore (COMPLETED - 2026-02-17):**
  - **OpenSpec Change:** `archive-root-export-and-zip-import-restore` fully implemented, validated, and ready for archival
  - **Objective:** Enable repo-root archive exports for USB copy workflows and direct zip restore without manual unzip/staging
  - **Implementation Summary:**
    - **Step 1 Root Export Foundation:** `ARCHIVE_EXPORTS_DIR = "archive_exports"` constant, `_get_archive_exports_directory()` helper, deterministic naming `archive_<module>_<timestamp>_<save_folder>.zip`
    - **Step 2 Payload + Archive Catalog:** Full-save payload includes archive metadata, essential save unchanged, `list_archive_exports()` for catalog discovery
    - **Step 3 Zip Preflight Validation:** `_validate_archive_zip_preflight()` checks metadata, envelope, source module; rejects traversal, absolute paths, invalid entries
    - **Step 4 Secure Extraction + Staging:** `_extract_archive_save_to_temp()` secure temp extraction with cleanup, `_stage_archive_save_folder()` canonical staging
    - **Step 5 Zip Restore Pipeline:** `restore_save_game_archive()` validates -> extracts -> stages -> delegates to `restore_save_game_global()`
    - **Step 6 Web + Load Dialog Integration:**
      - Web actions: `listArchiveZips`, `restoreArchiveZip` with same emit semantics as existing restore
      - Load dialog: renders both save folders and archive zips, archive rows show name/size/modified
      - Delete disabled for archive entries, restore routes to appropriate handler based on selection
    - **Step 7 Validation:**
      - Compile gate: PASS (`updates/save_game_manager.py`, `web/web_interface.py`, `utils/reset_campaign.py`)
      - Positive smoke: full save -> zip in `archive_exports/` -> restore delegation confirmed
      - Negative smoke: traversal zip, missing metadata, unknown module -> all fail-closed
      - Regression: essential save unchanged, folder restore unchanged
      - New regression suite: `scripts/test_archive_zip_restore.py` (10 tests, all PASS)
  - **Key Behaviors:**
    - Archives export to repo-root `archive_exports/` for USB portability
    - Zip restore uses validate -> stage -> delegate pattern (preserves proven restore semantics)
    - Fail-closed: malformed archives rejected with explicit errors, no partial state mutation
    - Security: traversal/absolute path rejection, canonical save folder enforcement, module validation
    - ASCII-only: all user-facing messages use ASCII characters only
    - Backward compatible: essential save and folder restore paths unchanged
  - **Files Modified:**
    - `updates/save_game_manager.py` (+~340 lines): archive helpers, validation, extraction, staging, restore entrypoint
    - `web/web_interface.py` (+~40 lines): `listArchiveZips`, `restoreArchiveZip` socket handlers
    - `web/templates/game_interface.html` (+~120 lines): dual list rendering, archive row display, selection routing
    - `scripts/test_archive_zip_restore.py` (new, 10 regression tests)
  - **Status:** COMPLETED, all 7.x tasks checked, regression suite passing, ready for archival

- **PC Leave/Return World Memory (COMPLETED - 2026-02-17):**
  - **OpenSpec Change:** `pc-leave-return-world-memory` fully implemented, validated, and archived
  - **Objective:** Add explicit retire/rejoin lifecycle with world-memory continuity writes in `data/memory.db`
  - **Phase 1 - Transition Memory Service Foundation:**
    - `core/memory/party_transition_memory.py` created with `record_pc_retirement()`, `record_pc_return()`, and `build_return_memory_pack()` helpers
    - Exports added to `core/memory/__init__.py`
  - **Phase 2 - Retirement Flow Integration:**
    - `web/routes/tabletop_party_routes.py` `remove_party_character` accepts optional `departure_text`
    - Runtime guards block retirement during active combat and when retiring final party member
    - Fail-open memory persistence with structured logging (`MEMORY_TRANSITION ... status=degraded ... fallback=enabled`)
    - Retirement narration enqueued with explicit farewell vs mysterious departure fallback
    - `_tabletop_role_history` lifecycle metadata appended via `pc_manager.append_role_history_event()`
  - **Phase 3 - Return Flow Integration:**
    - `web/routes/tabletop_party_routes.py` `add_party_character` persists return transition memory on rejoin
    - Return narration context built from `build_return_memory_pack()` with bounded continuity snippets (max 12)
    - Canonical identity preserved via `pc_manager.ensure_stable_character_id()`
  - **Phase 4 - UI and Prompt Assets:**
    - `web/static/js/tabletop_mode.js` `retireCharacter` collects optional farewell text via `prompt()`
    - `prompts/tabletop/retirement_narration.txt` and `prompts/tabletop/return_narration.txt` created with narration-only instructions
  - **Phase 5 - Resilience and Verification:**
    - `scripts/test_party_retirement_memory.py` created with 4 test functions covering persistence, no-purge guarantees, continuity retrieval, and graceful degradation
    - All tests PASS, temp DB isolation verified
  - **Key Behaviors:** Canonical entity identity preserved, `role_transition` events with `importance=95`, actor/witness linking, bounded continuity, non-destructive guarantees, ASCII-only logs
  - **Verification:** Python compile PASS, JS syntax PASS, regression tests PASS, lifecycle tests PASS
  - **Status:** COMPLETED, validated, archived to `openspec/changes/archive/2026-02-17-pc-leave-return-world-memory/`

- **PR1 Archive Global Save Index and Restore Routing (COMPLETED - 2026-02-16):**
  - OpenSpec change `archive-global-save-index-and-restore-routing` fully implemented and validated
  - **Step 1 Global Catalog:** `list_save_games_global()` scans all modules (`modules/*/saved_games/save_*`), deterministic sort by `save_timestamp` descending, additive metadata fields (`source_module`, `memory_package_present`)
  - **Step 2 Restore Routing:** Validator rejects invalid/non-canonical paths (path traversal, malformed), module-aware entrypoint `restore_save_game_global()` delegates to shared `_execute_restore_core()`, legacy `saveFolder`-only path preserved
  - **Step 3 Web Integration:** `listSaves` returns global entries, `restoreGame` accepts module-aware payload with fallback routing, load dialog shows source module label + memory parity `[M]` indicator + module-aware payload on load
  - **Step 4 Validation:** All 12 completion items PASS (compile, import, positive smoke, negative smoke)
  - **Files Modified:** `updates/save_game_manager.py`, `web/web_interface.py`, `web/templates/game_interface.html`
  - **PR2 Handoff Ready:** Archive zip portability work can begin (scaffolded in `/archiving.md`)

- **Journal Diary MVP Phase 1 Planning (PLANNED - 2026-02-16):
  - Created comprehensive MVP plan at `/plans/journal.md` for transparent diary system with dual-checkpoint model
  - **Dual-Checkpoint Architecture:** Start Game triggers draft refresh (unsaved session summary), Save triggers confirmed checkpoint (save-bound canonical entry)
  - **Key Design Decisions:**
    - Draft entries excluded from "Story So Far" PDF export (confirmed-only canon)
    - Failure isolation: diary generation never blocks Start Game or Save operations
    - World-time ordering using normalized `world_sort_key` from `party_tracker.json`
    - Third-person anonymous narration style for all diary entries
  - **OpenSpec Scaffolding:** Created change `journal-diary-mvp-phase1` with complete artifact set:
    - `proposal.md`, `design.md`, `tasks.md`, `executor_prompts.md`
    - Three capability specs: `journal-diary-dual-checkpoint`, `journal-diary-tabbed-ui`, `campaign-journal-story-pdf`
  - **Data Model:** Additive migration for `session_diary_entries`, `session_diary_state`, `story_so_far_cache`
  - **New Modules Planned:**
    - `core/memory/session_diary.py` - draft/confirmed logic, world-time normalization, checkpoint management
    - `core/memory/story_so_far_compiler.py` - confirmed-only story compilation, PDF generation, caching
  - **Integration Points:**
    - Save pipeline hook in `updates/save_game_manager.py:create_save_game()`
    - Start Game hook in `web/web_interface.py:handle_start_game()`
    - Journal UI tabs in `web/templates/game_interface.html`
    - API endpoints: `/api/journal/diary`, `/api/journal/story-so-far/pdf`
  - **Time Estimate:** 4-6 days for MVP Phase 1
  - **Status:** Plan complete, OpenSpec artifacts scaffolded, ready for Kimi Builder execution

- **Exit/Enter GUI Button Implementation Plan (PLANNED - 2026-02-15):**
  - Created detailed plan at `/plans/exit-enter.md` with two phases
  - **Phase 1 (Exit Only - Recommended):**
    - GUI Exit button gracefully stops ALL Python processes
    - Uses exit code 91 so launcher knows intentional shutdown
    - Terminal prints "Shutting down NeverEndingQuest Web Interface..." without Ctrl+C
    - User must manually restart with `python run_web.py`
    - No watcher process required
  - **Phase 2 (Full Exit/Enter - Future):**
    - Requires persistent supervisor/controller process
    - Allows Enter button to restart server without manual terminal command
    - Deferred due to complexity/maintenance concerns
  - **Technical approach:** Modify `handle_user_exit()` in web_interface.py for graceful shutdown, update run_web.py to detect exit code 91, update GUI button to show waiting message
  - **Files to modify:** `web/web_interface.py`, `run_web.py`, `web/templates/game_interface.html`

- **TTS Text Sync Browser-First Implementation (COMPLETED - 2026-02-15):**
  - Implemented word-by-word text reveal synchronized with Browser TTS speech.
  - Features:
    - "Word Sync" toggle in DM Voice settings (browser-only visibility, localStorage persisted)
    - Real boundary sync for Edge/MS TTS using `SpeechSynthesisUtterance.onboundary`
    - Faux sync fallback (3x slowed) for browsers without boundary events
    - Auto-scroll chat as reveal text grows
    - Manual replay uses audio-only (no text reveal rerun)
  - Architecture:
    - Per-item `syncStrategy` metadata in queue (`browser_boundary`, `none`, `estimated_timeline`)
    - Lazy-init reveal mode (preserves normal block text until sync actually starts)
    - Explicit queue completion signaling for Browser TTS (`notifyTTSPlaybackEnded`)
  - Files: `model_config.py` (+7), `web/web_interface.py` (+6), `web/templates/game_interface.html` (+~300), `web/static/js/tts_queue_manager.js` (+~80)
  - Verification: Python compile PASS, Edge real sync confirmed, Chrome faux fallback confirmed, stop/replay behaviors correct.

- **Combat State Init and Batching Hardening (C1-C5) (COMPLETED - 2026-02-15):**
  - Completed OpenSpec change `combat-state-init-and-batching-hardening` across C1-C5.
  - C1-C3 shipped fail-closed combat entry, deterministic non-combat command guards, and Phase 1 initiative normalization/mirror sync.
  - C4 shipped deterministic enemy/NPC batch actor filtering and integrity acceptance for legal non-active PC targets.
  - C5 added focused regression suite `scripts/c5_regression_combat.py` and completed manual smoke checklist M1-M5.
  - Validation:
    - `python3 -m py_compile main.py core/ai/action_handler.py core/managers/combat_manager.py core/managers/multi_pc_combat.py` -> PASS
    - `python3 scripts/test_multi_pc_combat.py` -> PASS (43 tests)
    - `python3 scripts/c5_regression_combat.py` -> PASS (9 tests)
    - `openspec validate combat-state-init-and-batching-hardening` -> valid
  - Commits:
    - `56ec86c` - `fix(combat): harden enemy-phase batching and PC target validation`
    - `48ac4aa` - `fix(combat): fail closed entry and add C5 regressions`
  - Status: implementation complete and validated; archive deferred until full gameplay testing.

- **Streaming UX Reversion to Foundation-Only (COMPLETED - 2026-02-15):**
  - Reverted runtime streaming execution paths to restore canonical block narration UX.
  - Kept future-facing foundation stubs:
    - `web/extensions/streaming_events.py` (dormant backend lifecycle helper)
    - `model_config.py` streaming flags (defaults OFF)
    - minimal transport/template wiring in `web/web_interface.py`
  - Explicitly removed stream-execution coupling from `WebOutputCapture` (no canonical suppression hooks in rollback mode).
  - Reversion OpenSpec artifacts updated to match selective keep/revert strategy:
    - `openspec/changes/streaming-ux-dual-pipeline/`
    - `openspec/changes/streaming-ux-stabilization/`
    - `openspec/changes/archive/2026-02-15-streaming-ux-reversion/`
  - Synced main specs:
    - `openspec/specs/canonical-output-single-path/spec.md`
    - `openspec/specs/streaming-disabled-stable-output/spec.md`
    - `openspec/specs/tts-block-narration-only/spec.md`
  - Validation:
    - `python3 -m py_compile main.py core/managers/combat_manager.py web/web_interface.py web/extensions/streaming_events.py` -> PASS
    - `python3 scripts/test_multi_pc_combat.py` -> PASS (40 tests)
    - Dormant sanity check (`ENABLE_CHAT_STREAMING=False`): stream start emits no events -> PASS
  - Manual smoke complete: intro + one non-combat turn + one combat round passed with no stream events and no JSON token leakage.
  - OpenSpec verify/archive complete; only follow-up warning is to align `scripts/test_streaming_ux_stabilization.py` with rollback expectations.

- **Memory Backfill Source Selection + DB Portability Tools (COMPLETED - 2026-02-13):**
  - Added `--sources` selector to `scripts/backfill_memory_db.py` with strict allowed values: `journal`, `conversation`, `combat`.
  - Added portability module `core/memory/memory_portability.py` with:
    - `export_memory_db_package()`
    - `validate_memory_package()`
    - `import_memory_db_package()`
  - Export now creates DB package + manifest (schema version, row counts, migrations, campaign metadata, SHA-256 hash).
  - Import defaults are non-destructive (requires explicit `--overwrite` to replace existing target DB).
  - Import supports `--dry-run` validation-only mode.
  - Added test suite `scripts/test_memory_backfill_portability.py` and passed validation checks.
  - OpenSpec change `memory-backfill-portability-tools` completed and archived.

- **Memory Foundation Retrieval + Backfill (COMPLETED - 2026-02-13):**
  - Added canonical memory package in `core/memory/`:
    - `memory_db.py` (idempotent SQLite migrations + additive readiness tables)
    - `memory_retrieval.py` (deterministic retrieval for timeline/context/retirement-return)
    - `memory_ingest.py` (idempotent ingest + history backfill)
    - `__init__.py` exports
  - Added read-only API route: `GET /api/memory/entity/<entity_id>?limit=25` via `web/routes/memory_routes.py` and registration in `web/web_interface.py`.
  - Added startup-safe memory init hook in `web/web_interface.py` (non-blocking fallback).
  - Added backfill tool: `scripts/backfill_memory_db.py` with:
    - `--dry-run` (temp DB copy, no persistent writes)
    - `--include-system` (include role=system history messages)
  - Backfill run result (default):
    - journal=40, conversation=48, combat=23
    - events_created=111, links_created=478
  - Dry-run include-system result:
    - conversation=65, combat=34
    - events_created=139, links_created=534
  - Validation:
    - `python3 -m py_compile core/memory/memory_db.py core/memory/memory_retrieval.py core/memory/memory_ingest.py core/memory/__init__.py web/routes/memory_routes.py` -> PASS
    - `python3 scripts/test_memory_retrieval_plan.py` -> PASS
    - `.venv/bin/python scripts/test_memory_foundation.py` -> PASS

- **NPC -> PC Role Lifecycle Promotion (COMPLETED - 2026-02-12):**
  - Added Add Existing source modes (`players`, `npc_companions`, `all`) and promote action flow.
  - Added promotion preview/apply endpoints with explicit confirmation and no chat side effects.
  - Added identity/lifecycle helpers in `utils/pc_manager.py`:
    - `ensure_stable_character_id()`
    - `append_role_history_event()`
    - `normalize_character_role_fields()`
  - Promotion now preserves active character (no auto-switch), updates role markers in place, and records `_tabletop_role_history`.
  - Added schema support for `character_id` and `_tabletop_role_history` in `schemas/char_schema.json`.
  - Validation:
    - `python3 -m py_compile utils/pc_manager.py web/routes/tabletop_party_routes.py` -> PASS
    - API smoke: preview/apply PASS; membership move PASS; active-character unchanged PASS.

- **Saving Throw Normalization and GUI/PDF Consistency (COMPLETED - 2026-02-12):**
  - Added shared helper `utils/saving_throw_utils.py` for case-insensitive save normalization and class fallback (includes `thief -> rogue` alias).
  - GUI now always renders six Saving Throws and uses normalized/fallback proficiency logic.
  - PDF saving throw checkboxes/bonuses now use the same normalized/fallback source.
  - Added optional backfill utility `scripts/backfill_saving_throws.py` (dry-run default, explicit `--apply`).
  - Validation:
    - `python3 -m py_compile utils/saving_throw_utils.py scripts/backfill_saving_throws.py web/routes/character_sheet_routes.py` -> PASS
    - Dry-run and apply runs completed; Cyrius/Tester/Xerxes now consistent in GUI/PDF.

- **Character Readiness Repair Workflow (COMPLETED - 2026-02-12):**
  - Added in-sheet `Repair` action with preview -> confirm flow in `web/templates/game_interface.html`.
  - Added backend endpoints:
    - `POST /api/character_sheet/readiness_repair/preview`
    - `POST /api/character_sheet/readiness_repair/apply`
  - Repair pipeline is non-chat, cooldown-protected, whitelist-restricted to narrative fields, and audit-gated.
  - Verified real recovery on `tester` and `xerxes` (readiness warnings cleared, PDF export preserved).

- **PC Creation Workflow Unification (COMPLETED - 2026-02-12):**
  - Added shared creation audit pipeline in `utils/character_creation_audit.py` with deterministic result types:
    - `schema_error`, `completeness_error`, `success`
  - Hardened Create with DM finalization in `main.py` (raw/fenced JSON extraction + correction loop).
  - Expanded Roll Your Own form and backend validation path.
  - Added Add Existing filter/dedupe to exclude current party members.
  - Extended startup to support iterative multi-PC creation loop while preserving SP behavior.
  - Full smoke suite (API + compile + script tests) passed on 2026-02-12.

- **Initiative Phase 1 Two-Group Start Gate (COMPLETED - 2026-02-12):**
  - **Objective:** Add deterministic combat opening phase (`dmGroup` vs `pcGroup`) while preserving existing `/end` enemy-batch flow.
  - **Implementation:**
    - `core/ai/action_handler.py`: Encounter startup now persists Phase 1 initiative state (`initiativeMode`, `initiativeRolls`, `initiativeWinner`, `roundStartsWith`, `awaitingPcGroupRoll`) with DM pre-roll in Python.
    - `core/managers/combat_manager.py`: Added `/init <1-20>` gate, strict blocking until valid roll, tie rule (`dmGroup` wins), and immediate enemy-phase trigger when DM starts.
    - Dynamic prompt context includes `=== INITIATIVE STATE ===` for runtime phase authority.
    - New-round phase opener now follows persisted `roundStartsWith` deterministically.
    - Prompt alignment updates in compressed sim/validation prompts to allow initiative-driven ENEMY_PHASE start alongside `/end` flow.
  - **Validation:**
    - `python3 -m py_compile core/ai/action_handler.py core/managers/combat_manager.py` -> PASS
    - `python3 scripts/test_multi_pc_combat.py` -> PASS (40 tests, 0 failures, 0 errors)
  - **Files:** `core/ai/action_handler.py`, `core/managers/combat_manager.py`, `prompts/combat/combat_sim_prompt_multipc_compressed.txt`, `prompts/combat/combat_validation_prompt_multipc_compressed.txt`.

- **Web Interface TT Merge Refactor Completion (COMPLETED - 2026-02-12):**
  - **Objective:** Reduce divergence from upstream `web/web_interface.py` by extracting TABLETOP MODE logic into extension/route modules while preserving behavior and thin host hooks.
  - **Increments Completed:**
    - Increment 7: Extracted `request_plot_data` + `request_storage_data` socket handler implementations to `web/extensions/tabletop_socket_handlers.py`.
    - Increment 8: Deduped WebOutputCapture debug-line filtering with shared helper/marker list in `web/web_interface.py`.
    - Increment 9: Hardened live chat monitor wrapper lifecycle in `web/extensions/live_chat_monitor.py` with idempotent setup + optional teardown.
  - **Validation:** `python3 -m py_compile` passed for changed files; grep checks verified thin host wrappers and extension-owned wrapper lifecycle.
  - **Commit:** `094a938` - `refactor(web): reduce TT divergence via extension hooks`.
  - **Files:** `web/web_interface.py`, `web/output_markers.py`, `web/extensions/*`, `web/routes/*`.

- **Phase 0 Cleanup: Factory Routing Alignment (COMPLETED - 2026-02-12):**
  - **Objective:** Align core files to OpenRouter factory routing baseline before GitHub push
  - **Work Completed:**
    - `core/ai/transition_validator.py`: Factory client + provider model selection + fallback handling
    - `main.py`: `generate_module_summary()` uses factory routing with fallback error handling
    - `core/managers/combat_manager.py`: Global client initialization uses factory
    - `AGENTS.md`: Updated migration status, removed duplicate transition_validator entries, renumbered lists
  - **Technical Implementation:**
    - Replaced `from openai import OpenAI` with `from utils.ai_client_factory import create_chat_client, get_chat_model_name, handle_provider_error`
    - Removed direct `client = OpenAI(api_key=...)` initialization
    - Implemented fallback pattern: primary call → `handle_provider_error()` classification → `create_chat_client(use_fallback=True)` retry
    - Used `actual_model_used` variable for accurate telemetry logging
    - Avoided Fix 4 scoping trap by using distinct variable names in local scopes (`summary_client`, `fallback_client`)
  - **Quality Assurance:**
    - Zero prompt/content changes (temperature, messages preserved)
    - All existing fallback behavior maintained (non-AI summary on failure)
    - Syntax verification: `python3 -m py_compile` passes for all 3 Python files
    - Git status: 4 files modified, +72/-41 lines
  - **Next Steps:** Smoke testing (startup → transition validation → combat entry)

- **OpenSpec Initialization for Project Management (COMPLETED - 2026-02-12):
  - **Objective:** Initialize OpenSpec spec-driven development framework for structured planning
  - **Work Completed:**
    - Ran `openspec init --tools opencode` generating local command/workflow skills
    - Created project guardrails in `openspec/config.yaml` aligned with AGENTS.md
    - Split OpenRouter router plan into two changes: `openrouter-llm-router-facade` and `openrouter-llm-callsite-migration`
    - Fast-forwarded all planning artifacts (proposal, design, specs, tasks) for both changes
    - Created global OpenSpec workflow skill at `~/.config/opencode/skills/openspec-workflow/SKILL.md`
  - **Result:** Clean scaffolding for OpenRouter phases; structured planning capability; zero codebase impact
  - **Files:** `openspec/config.yaml`, `openspec/changes/*` (9 artifacts), global skill

- **EGO + RATIO Concept Plan Revision (COMPLETED - 2026-02-12):**
  - **Objective:** Tighten cybernetic control architecture based on RSO framework
  - **Key Architecture:** EGO (fast reflex controller) + RATIO (slow optimizer); Python=P2 ground truth, LLM=P1 narrative
  - **Decision Relay:** END (drift) → log; ADJUST (distortion) → Tier 1a tweak; ESCALATE (hallucination) → correction + RATIO queue
  - **Human DM Role:** Exogenous control signal enabling implicit RLHF via "silence = approval"
  - **Write Tiers:** 1a (EGO+RATIO), 1b (RATIO only), 2 (RATIO+checks), 3 (immutable)
  - **Future OpenSpec Changes:** `ego-foundation-passive-observer`, `ego-bounded-adjustments`, `ratio-reviewed-evolution`
  - **Prerequisite:** OpenRouter router facade completion
  - **Status:** Conceptual review complete; ready for implementation post-tester release
  - **Files:** `plans/EGO.md` (rewritten, 353 lines)

- **Hallucinated Monster Defense - Three-Layer Safety System (COMPLETED - 2026-02-10):**
  - **Problem:** Narrator LLM hallucinating creature names (e.g., "spectral servants") led to auto-created stat blocks via monster_builder.py, creating data integrity issues with fabricated monsters
  - **Root Cause:** `load_or_create_monster()` auto-spawns monster_builder.py when monster file not found; LLM unconstrained in `monsters` array content
  - **Solution:** Implemented three independent defense layers:
    - **Layer 1 (Bestiary Gate):** `core/generators/combat_builder.py:147-161` - Blocks auto-creation in tabletop mode (MULTIPLAYER_MODE check), preserves upstream SP behavior
    - **Layer 2 (Validation):** `core/ai/action_handler.py:798-838` - Validates encounter has ≥1 enemy before combat starts, catches edge cases (SP mode, malformed entries), deletes invalid files, returns gracefully
    - **Layer 3 (Prompt):** `prompts/system_prompt_compressed.txt:59` - Added `monsterSource` rule to @COMBAT directive, guides LLM to use existing bestiary creatures or explicitly described location monsters
  - **Defense-in-Depth:** Independent layers provide multiple failure points; Layer 3 reduces frequency, Layers 1-2 provide deterministic safety net
  - **Failure Cascade:** Hallucinated name → file not found → Layer 1 blocks → no encounter file → combat never starts → error logged → DM can retry with valid creatures
  - **Backward Compatibility:** SP mode preserves auto-creation; TT mode protected; zero breaking changes
  - **Files:** 3 files modified, +56 lines total (~35 tokens for prompt)

- **Expandable Chat Input Textarea (COMPLETED - 2026-02-09):**
  - **Objective:** Replace single-line input with auto-expanding textarea for long prompts and detailed action descriptions
  - **Requirements Met:** 5-line max, push-up effect (chat shrinks, header bars fixed), Enter to send, Shift+Enter for newlines
  - **Implementation:** CSS (`resize: none`, `overflow: hidden`, `min/max-height`), HTML (`<textarea>`), JavaScript (`autoResizeTextarea()`, `handleKeyDown()`)
  - **Layout:** Existing flexbox handles push-up - header bars fixed, only chat transcript shrinks upward
  - **Result:** ~50-line change, zero breaking changes, works for SP and MP modes
  - **File:** `web/templates/game_interface.html`

- **Combat API Timeout Protection & StatusTimer Infrastructure (COMPLETED - 2026-02-09):
  - **Problem:** Combat validation hung indefinitely on 2026-02-09 (10:57:42) with no timeout on API calls; OpenAI SDK default is 600s (10 minutes), unacceptable for interactive gameplay
  - **Solution:** Added timeout infrastructure and StatusTimer context manager for future UX improvements
  - **Constants Added (model_config.py:50-51):**
    - `COMBAT_API_TIMEOUT_SECONDS = 120` - Per-call timeout (generous for complex prompts)
    - `COMBAT_CONNECT_TIMEOUT_SECONDS = 10` - TCP connection timeout
  - **StatusTimer Class (status_manager.py:143-206):**
    - Context manager for escalating status messages during blocking operations
    - Escalation schedule: 10s → 30s → 60s with live elapsed counter ({elapsed}s)
    - Daemon thread auto-cancels on context exit; uses threading.Event for responsive shutdown
    - DEFAULT_SCHEDULE is class-level constant for easy customization per-call-site
    - Ready for future OpenRouter build integration
  - **Timeout Protection Applied (combat_manager.py):**
    - Line 852: `validate_combat_response()` - Validation LLM (highest risk for hanging)
    - Line 2576: Initial scene generation - Combat start narration
    - Line 3619: Main combat loop GPT-4.1 - Primary generation path (CRITICAL)
  - **Implementation Notes:**
    - All 3 high-traffic combat paths now protected; 6 secondary calls remain unprotected (acceptable risk)
    - Timeout exceptions caught by existing retry loops (up to 5 attempts)
    - StatusTimer not yet wired up (deferred for Section 4); timeout infrastructure complete
    - Zero code restructuring; all additive single-line changes with # TABLETOP MODE: comments
  - **Result:** Combat API calls timeout after 120s instead of 600s SDK default; prevents indefinite hangs
  - **Files Modified:** `model_config.py` (2 lines), `core/managers/status_manager.py` (66 lines), `core/managers/combat_manager.py` (3 timeout additions)

- **MultiPCCombatManager Bug Fixes & Code Quality Improvements (COMPLETED - 2026-02-09):
  - **10 Synchronization Bugs Fixed:** Based on comprehensive audit report of facade/sub-manager interactions
    - Bug 1: Added `current_round` property getter/setter to prevent shadow attribute creation (lines 775-783)
    - Bug 2: Fixed orphan attribute writes to `_turns.enemy_phase_complete` (lines 1229, 1365)
    - Bug 3-4: Refactored `complete_pc_turn()` and `force_end_pc_phase()` to delegate to sub-managers (lines 1068-1103)
    - Bug 5: Removed dead `CombatStateManager.get_combat_state_summary()` method (-28 lines)
    - Bug 6: Converted 4 facade methods to delegation pattern (-40 lines duplicated logic)
    - Bug 7: Windows Unicode compatibility fix - replaced emoji with ASCII tags ([WAIT], [DONE], [DOWN], [DEAD], [STBL])
    - Bug 8: Removed 3 dead methods from `TurnQueueManager` (-74 lines)
    - Bug 9: Fixed double-increment bug in round rollover by returning tuple from `advance_turn()` (lines 429-461, 778-815)
    - Bug 10: Removed dead `first_round` field from facade (-2 lines)
  - **5 Code Quality Improvements:**
    - Removed Unicode emoji (⛔⚠️) from prompt boxes - ASCII tags ([BLOCKED], [WARNING])
    - Removed stale comments and unused imports (Union, re)
    - Updated facade to use properties instead of direct `_state` access
  - **Test Fix:** Updated test at line 258 to unpack tuple from `advance_turn()`
  - **Architecture Principle Established:** Facade methods delegate OR coordinate; never reimplement
  - **Result:** All state synchronization bugs resolved, Windows compatibility restored, -187 lines total
  - **Files Modified:** `core/managers/multi_pc_combat.py` (~200 lines), `scripts/test_multi_pc_combat.py` (1 line)

- **OpenRouter LLM Router Architecture Plan (COMPLETED - 2026-02-07):**
  - **Strategic Architecture Decision:** Path A - Gradual Hardening with dual-mode support
    - Keep MULTIPLAYER_MODE toggle for upstream merge potential (TTS feature valuable)
    - Gradually harden toward TT-only over 6-12 months
    - Maintain insurance policy while focusing all development on TT mode
    - Plugin architecture enables clean extraction to TT-only fork when ready
  - **Technical Solution:** Centralize 89 LLM calls through single router interface
    - `llm.call(role="narrate", messages=...)` - Single interface for all LLM calls
    - Capability-based routing: creative (Trinity), mechanics (Flash Lite), structured (Flash Lite JSON)
    - GPT-4.1 universal fallback with user notification to update config
  - **Model Selection:**
    - **Creative/Narration:** Trinity Large Preview (free) → GPT-4.1 fallback
    - **Mechanics/Structured:** Gemini 2.5 Flash Lite (1.05M context) → GPT-4.1 fallback
  - **Implementation Plan:**
    - **Phase 1 (3-4 days):** Create `utils/llm_router.py`, update `model_config.py`, integration tests
    - **Phase 2 (5-7 days):** Migrate all 39 files with LLM calls
    - **Phase 3 (2-3 days):** Cleanup, usage reporting, documentation
  - **Plan Document:** `/plans/openrouter_llm_router_architecture.md` (700 lines comprehensive)
  - **Status:** PLANNING PHASE - Not yet implemented, under review

- **TTS Auto-Play Fix & Queue Management (COMPLETED - 2026-02-06):**
  - **Problem:** Cacophony on page reload (all cached messages played simultaneously), no queue management (audio overlap), mechanical messages (/att, /dmg, /help) were spoken breaking immersion
  - **Solution:** Queue manager plugin, skipAutoplay parameter for cached messages, system content filters, [skipTTS] tag system
  - **Key Components:**
    - `web/static/js/tts_queue_manager.js` - **NEW** Plugin with sequential playback, max 3 queue, skip when playing
    - `web/templates/game_interface.html` - skipAutoplay param, system filters (removes [SYSTEM], ---, /commands from TTS)
    - `core/managers/multi_pc_combat.py` - [skipTTS] prefix on 6 combat outputs (Hit, Miss, damage confirmations)
    - `main.py` - [skipTTS] prefix on /help command output
    - `web/web_interface.py` - Tag detection/stripping in write() and flush() methods, sets skipTTS flag
  - **Behavior:** Only DM narration auto-plays TTS, mechanical messages display but don't speak, queue not blocked
  - **Result:** No cacophony on reload, immersive storytelling, smooth audio queue flow
  - **Files:** 5 files modified, 1 new plugin, all changes marked with # TABLETOP MODE: comments

- **OpenRouter Integration - Phase 1 Core Chat/LLM (COMPLETED - 2026-02-06):**
  - **Objective:** Enable multi-provider AI support with transparent fallback from OpenRouter to OpenAI for all chat/LLM operations.
  - **Factory Pattern Implementation:** Created centralized AI client factory in `utils/ai_client_factory.py` (312 lines)
    - `create_chat_client(use_fallback=False)` - Creates OpenAI or OpenRouter client based on config
    - `get_chat_model_name()` - Returns appropriate model (Kimi K2.5 or GPT-4.1) based on provider
    - `handle_provider_error()` - Detects retryable errors (rate limits, 503s, etc.) and triggers fallback
    - `get_fallback_notification()` - Returns user-friendly GUI message when fallback occurs
  - **Configuration:** Added OpenRouter settings to `model_config.py` (lines 68-101)
    - `LLM_PROVIDER = "openai"` (options: "openai", "openrouter")
    - `OPENROUTER_CHAT_MODEL = "moonshotai/kimi-k2.5"`
    - `ENABLE_PROVIDER_FALLBACK = True`
  - **Files Updated (9 total):**
    1. `utils/ai_client_factory.py` - **NEW** Factory implementation (312 lines)
    2. `updates/update_character_info.py` - Factory pattern + transparent fallback
    3. `utils/startup_wizard.py` - Factory pattern for character creation
    4. `core/ai/transition_validator.py` - Factory pattern + fallback for transitions
    5. `core/ai/combat_compression_engine.py` - Factory pattern for combat compression
    6. `core/ai/incremental_compression.py` - Factory pattern for location compression
    7. `core/ai/cumulative_summary.py` - Factory pattern for adventure summaries
    8. `core/ai/adv_summary.py` - Factory pattern for validation summaries
    9. `web/web_interface.py` - Factory pattern for chat endpoints (skipped image/TTS for Phase 2)
  - **Fallback Behavior:** Transparent auto-retry when OpenRouter fails
    - Detects rate limits, timeouts, 503/504 errors
    - Automatically switches to OpenAI without user intervention
  - **Validation:** All 9 files compile successfully
  - **Backward Compatibility:** Zero breaking changes
  - **Quick Start:** Set `OPENROUTER_API_KEY` in config.py, change `LLM_PROVIDER = "openrouter"` in model_config.py
  - **Status:** Phase 1 complete, ready for testing. Phase 2 (image/TTS) and Phase 3 (video) stubbed.

- **Combat Round Synchronization & Allied NPC Fix (COMPLETED - 2026-02-09):**
  - **Problem:** Combat stuck at Round 2 forever; allied NPCs not attacking during enemy phase batch
  - **Root Cause:** Manager round state (default 1) never synced from encounter file (round 2); `get_remaining_enemies_for_round()` only returned enemies, not allied NPCs
  - **Solution:**
    - Added `sync_round_from_encounter()` method to sync manager state from encounter file on combat start/resume (multi_pc_combat.py:1148)
    - Call sync after `initialize_turn_queue()` at single convergence point (combat_manager.py:2007-2011)
    - Include `CombatantType.NPC` alongside `CombatantType.ENEMY` in pending actors list (multi_pc_combat.py:537)
  - **Reverted Broken Fix:** Removed `clean_old_dm_notes` modification that deleted system messages prematurely
  - **Result:** Combat advances rounds correctly, allied NPCs participate in enemy phase, round state synchronized
  - **Files:** `core/managers/multi_pc_combat.py` (+21 lines), `core/managers/combat_manager.py` (+5 lines)

- **Combat Validation & Character Update Fixes (COMPLETED - 2026-02-09):**
  - **Validation Prompt Fixes (1a-d):** Clarified consolidation rules to prevent validator from rejecting valid PC damage during enemy batch phase
    - `combat_validation_prompt_multipc_compressed.txt`: 4 edits (consolidation_rule, batch_enemy_phase routing, violation clarification, positive example)
    - `combat_validation_prompt_multipc.txt`: 2 edits (mirrored for human review)
  - **Simulation Prompt Fix (2a):** Fixed ambiguous plan_note (line 97) to clarify PC damage routing
    - `combat_sim_prompt_multipc_compressed.txt`: 1 edit
  - **UnboundLocalError Fix:** Added `global client` to `update_character_info()` (line 1259)
    - **Bug:** OpenRouter fallback assignment at line 2110 caused Python scoping issue, breaking all character updates during combat
    - **File:** `updates/update_character_info.py` (+1 line)
  - **Result:** Batch enemy phase validation passes, character updates work, damage applies correctly

- **OpenRouter Migration - Phase 1B Model Reference Updates (COMPLETED - 2026-02-06):**
  - **Objective:** Migrate all hardcoded model references to use 3-tier OpenRouter configuration via `get_model_config()`
  - **Migration Script:** Created `scripts/migrate_to_openrouter.py` - AST-based surgical migration tool
    - Features: Surgical line replacement, temperature preservation, duplicate prevention
    - Safety: Automatic backups, syntax validation, dry-run mode, unit tests
    - Fixed bugs: Multi-line import handling, false positive detection
  - **Successfully Migrated (5 files):**
    1. `updates/plot_update.py` - 1 usage, now uses `create_chat_client()` ✅
    2. `updates/update_encounter.py` - 1 usage, now uses `create_chat_client()` ✅
    3. `web/web_interface.py` - 1 usage (image prompt generation) ✅
    4. `core/ai/adv_summary.py` - 2 usages, removed direct OpenAI client ✅
    5. `core/ai/cumulative_summary.py` - 2 usages, removed direct OpenAI client ✅
  - **Critical Bug Fixed:** `TypeError: unexpected keyword argument 'thinking'`
    - Root cause: Files used `OpenAI()` client but passed OpenRouter-specific `extra_body` params
    - Solution: Updated all migrated files to use `create_chat_client()` factory
    - Result: Client and params now match configured provider
  - **Task ID Mappings:** 9 upstream constants mapped to task IDs (dm_main, summaries, plot_update, etc.)
  - **Validation:** All migrated files compile successfully, unit tests pass
  - **Pending (3 complex files):** `core/ai/transition_validator.py`, `main.py`, `core/managers/combat_manager.py`

- **HP Persistence Bug Fix & Code Quality Cleanup (COMPLETED - 2026-02-06):**
  - **Critical Bug Fixed:** Every PC showing 10/10 HP regardless of actual values; defeated characters resurrecting mid-combat
  - **Root Cause:** `multi_pc_combat.py:initialize_from_party()` reading from non-existent `party_data["characters"][name]["hp"]` structure, defaulting to 10 when keys missing
  - **Solution:** Load character data directly from character JSON files using ModulePathManager
  - **File:** `core/managers/multi_pc_combat.py` (lines 276-305)
  
  **Code Quality Improvements:**
  1. **Removed Duplicate json Imports:** Removed 2 redundant inline imports (lines 299, 1111), using module-level import only
  2. **Fixed Silent Exception Swallowing:** Added debug logging for monster AC lookup failures with creature name and exception details
  3. **Consolidated Defensive Imports:** Removed 4 separate try/except ImportError blocks for internal modules; internal imports now fail fast
  4. **Refactored Large Method:** Split 130-line `format_initiative_tracker()` into 4 focused methods with better separation of concerns
  5. **Eliminated Magic Numbers:** Added constants `DEFAULT_AC = 10`, `INITIATIVE_DIE = 20`; replaced 6 hardcoded AC values and 4 random.randint calls
  6. **Planned Error Handling Standardization:** 6 print() statements identified for conversion to logger calls in next session
  
  **Lines Saved:** ~35 total across all improvements

- **MultiPCCombatManager Audit & Test Suite (COMPLETED - 2026-02-06):**
  - **Comprehensive Verification:** 40 unit tests created and all passing
  - **Audit Documentation:** Created detailed audit report covering all LLM prompt integration points and Python function integration points
  - **Test Categories (7 total):**
    - CombatStateManager tests (7): Initialization, HP updates, death saves
    - TurnQueueManager tests (5): Queue building, turn advancement, remaining enemies
    - Facade tests (7): Delegation verification, coordination methods
    - LLM Prompt tests (8): Head context, initiative tracker, required response prompts
    - Context Manager tests (3): Dependency injection for testing
    - Edge Case tests (7): Empty party, all incapacitated, invalid names
    - Integration tests (2): Full combat round, PC death scenarios
  - **Bugs Fixed During Testing:**
    - Line 1183: Fixed missing `enemy_phase_complete` attribute in `get_combat_state_summary()`
    - Lines 1741-1747: Fixed deprecated direct attribute access in `get_multi_pc_initiative_narrative()`
  - **Integration Points Verified:**
    - All 7 delegation methods working correctly
    - All 5 coordination methods properly updating both sub-managers
    - Context managers enable isolated testing without Flask app
    - Zero breaking changes confirmed
  - **Documentation Created:**
    - `docs/multi_pc_combat_audit.md` - Architecture and integration documentation
    - `scripts/test_multi_pc_combat.py` - 750-line comprehensive test suite
    - `docs/test_results_multi_pc_combat.md` - Test coverage analysis
  - **Files Modified:** `core/managers/multi_pc_combat.py` (2 bug fixes)

- **Tabletop Mode Debug Monitor Skill v2.3.0 (COMPLETED - 2026-02-06):**
  - **Three-Phase Complete Workflow:** Start → Check → Stop
    - **Phase 1:** `start debug` - Configure and enable debugging, prompt for restart
    - **Phase 2:** `check debug` - Enhanced error analysis with timestamped listings
    - **Phase 3:** `stop debug` - Revert configs, delete all debug logs, prompt for restart
  - **Enhanced Error Reporter:** Created `scripts/debug_error_reporter.py` with:
    - Automatic error classification (CRITICAL/ERROR/WARNING)
    - Timestamped chronological error listings
    - Smart error grouping by exception type
    - File location extraction (e.g., `core/managers/multi_pc_combat.py:867`)
    - Actionable fix suggestions based on error patterns
  - **Log Cleanup:** Deletes all debug log files on stop (game_debug.log*, game_errors.log*)
  - **KISS Principle:** Manual control only, no auto-disable, clean state between sessions
  - **Commands:** `start debug`, `check debug`, `stop debug`, `tabletop debug status`
  - **Script Features:** `--enable`, `--stop`, `--status`, `--warnings`, `--verbose`, `--lines N` flags
  - **Configuration:** Updates both `debug_config.py` (categories) and `config.py` (TABLETOP_DEBUG_VERBOSE flag)
  - **Instrumentation:** 8 debug points in `multi_pc_combat.py`, 2 in `combat_manager.py`
  - **Files:** `.opencode/skills/debug-monitor/SKILL.md` (v2.3.0), `scripts/check_debug_logs.py`, `scripts/debug_error_reporter.py` (NEW), `utils/tabletop_debug.py`

- **MultiPCCombatManager Structure Refactoring & Delegation (COMPLETED - 2026-02-06):**
  - **Phase 3 of Multi-PC Combat Rebuild:** Refactored monolithic MultiPCCombatManager into focused sub-managers
  - **Architecture:** Implemented Facade pattern with 2 sub-managers:
    - `CombatStateManager` (lines 142-327, ~185 lines): Manages PC combat states, HP tracking, round/initiative metadata
    - `TurnQueueManager` (lines 331-635, ~305 lines): Manages initiative order, turn advancement, phase tracking
  - **Delegation Pattern:** Converted 7 duplicate methods to thin delegation wrappers (1-3 lines each):
    - `initialize_from_party()` → `self._state.initialize_from_party()`
    - `initialize_turn_queue()` → `self._turns.initialize_turn_queue()`
    - `get_available_pcs()` → `self._state.get_available_pcs()`
    - `get_current_actor()` → `self._turns.get_current_actor()`
    - `advance_turn()` → `self._turns.advance_turn()`
    - `find_target()` → `self._turns.find_target()`
    - `get_remaining_enemies_for_round()` → `self._turns.get_remaining_enemies_for_round()`
  - **Coordination Methods Kept:** 5 methods remain in MultiPCCombatManager that coordinate between both sub-managers:
    - `update_pc_hp()` - Updates state and syncs to turn_queue
    - `complete_pc_turn()` - Marks acted + checks phase completion
    - `force_end_pc_phase()` - Marks all acted + sets phase flag
    - `start_new_round()` - Coordinates round increment + resets
    - `get_combat_state_summary()` - Aggregates data from both sub-managers
  - **Line Reduction:** 1,943 → 1,756 lines (-187 lines, ~10% reduction)
  - **Benefits:** Better separation of concerns, easier testing, clearer responsibilities
  - **Files Modified:** `core/managers/multi_pc_combat.py` (restructured, no breaking changes)

- **State Synchronization Fix & The Mechanics vs Narrative Philosophy (COMPLETED - 2026-02-05):**
  - **Problem:** LLM hallucinated exhaustion state for all PCs at Feb 5 session start despite full HP restoration (Acheron 21/21 HP narrated as "limp and drifting")
  - **Root Cause:** DM Note formatting didn't display `condition_affected` array; LLM relied on conversation history from Feb 3 ending
  - **Philosophical Resolution:** Established "Hierarchy of Truth" - Python = Objective Reality (HP/conditions), LLM = Subjective Interpretation (atmosphere/mood), Player = Bridge
  - **Implementation:**
    - Added `condition_affected` display to `format_pc_full_stats()` and `format_pc_condensed()` in `utils/multi_pc_dm_note.py`
    - Format: `Conditions: None` or `Conditions: Exhaustion L1, Prone` (full), `Cond: Exhaustion` (condensed)
    - Created @STATE_SYNC directive in `prompts/system_prompt_compressed.txt`:
      - `bookmark: "SESSION BOUNDARY - State below is current mechanical truth"`
      - `truth_source: "DM Note character stats are GROUND TRUTH"`
      - `override: "If narrative memory contradicts DM Note, DM Note WINS"`
      - `narrative_freedom: "You may narrate SUBJECTIVE experience... BUT mechanical state MUST match DM Note"`
      - `principle: "Python enforces reality; you interpret it"`
  - **Golden Rule:** "Python enforces reality; you interpret it"
  - **Token Cost:** ~15 tokens per character for conditions + ~80 tokens for @STATE_SYNC directive
  - **Why Only PCs:** NPCs don't have persistent JSON state tracking; PCs need mechanical consistency for player trust
  - **Key Insight:** The exhaustion bug wasn't rest automation failure—it was perception synchronization failure
  - **Documentation:** Full philosophical discussion in ONCNotes Entry 002
  - **Files Modified:** `utils/multi_pc_dm_note.py` (2 functions), `prompts/system_prompt_compressed.txt` (new @STATE_SYNC block)

- **Chat Log Skill Rename & Enhancement (COMPLETED - 2026-02-05):**
  - Renamed `read-combat-log` to `read-chat-log` to reflect both combat and non-combat content
  - Updated trigger phrases: "read chat log" / "update chat log" (incremental when bookmark exists)
  - Implemented "Fading Memory" OCNote architecture:
    - Ongoing summary persists across incremental reads (accumulates themes)
    - Latest 5 OCNotes shown individually with full detail
    - Threshold: After 8 total OCNotes, oldest collapse into ongoing summary
  - Token efficiency: Hard limits on all sections (narrative 3 sentences, combat 2, OCNotes 2 per)
  - No raw entry reproduction (user sees entries in web GUI)
  - Files: Deleted `.opencode/skills/read-combat-log/`, created `.opencode/skills/read-chat-log/SKILL.md`

- **5e Rest Automation Implementation (COMPLETED - 2026-02-05):
  - Implemented automatic resource restoration when rest action is processed
  - **Prompt Contract Fix:** Added "rest" to @ACTIONS, @PARAMS, @EXAMPLES in prompts/system_prompt_compressed.txt
  - **5e-Compliant Logic:**
    - Short rest (≥1 hour): Warlock spell slots + shortRest features only (no auto-heal)
    - Long rest (≥8 hours): Full HP, all spell slots, all features, exhaustion removal
    - Hit Dice: Players manually spend via updateCharacterInfo (not auto-tracked)
  - **Bug Fixes:**
    - Fixed character path resolution using find_character_file_fuzzy()
    - Fixed exhaustion detection (schema uses list[string], not list[dict])
    - Added parameter validation for rest_type ("short" or "long")
    - Added file existence safety checks
  - **Files Modified:**
    - core/ai/action_handler.py - _process_character_rest() function (~164 lines, lines ~1902-2065)
    - prompts/system_prompt_compressed.txt - Added rest to @ACTIONS (line 24), @PARAMS (line 228), @EXAMPLES (lines 292-295), @REST section (lines 109-116)
    - scripts/test_rest_action.py - **NEW** - Comprehensive test suite
  - **Testing:** Test script created as integration test specifications
  - **5e Compliance:** No reliance on LLM to remember rest rules; consistent rule application for both single-PC and multi-PC modes

- **Validation API Sanitization Patch (COMPLETED - 2026-02-05):**
  - Added merge-safe patch to strip `active_pc` metadata from validation API calls
  - **Problem:** The `active_pc` field used for multi-PC compression was being sent to OpenAI/validation APIs, causing 400 errors with some providers
  - **Solution:** Added sanitization loops in two locations immediately before API calls:
    - `main.py:validate_ai_response()` - Strips `active_pc` from `validation_messages_to_send` before export and API call
    - `core/managers/combat_manager.py` - Strips `active_pc` from `validation_conversation` before combat validation
  - **Pattern:** `for msg in messages: if isinstance(msg, dict) and "active_pc" in msg: del msg["active_pc"]`
  - **Merge-Safe:** 4 lines each, clearly marked with `# TABLETOP MODE:` comments
  - **Consistent:** Same pattern already used in `get_ai_response()` for main DM calls
  - **Testing:** Logic verified with unit tests; Python syntax validated
  - **Files Modified:** `main.py` (1 location), `core/managers/combat_manager.py` (1 location)

- **Character Data Access Abstraction Layer (COMPLETED - 2026-02-06):**
  - Created centralized character data access abstraction in `utils/pc_manager.py` (~175 lines added)
  - Establishes consistent patterns for future database migration path
  - **Plugin Architecture:** All core logic contained in TABLETOP MODE file; zero breaking changes
  - **Dual-Check Activation:** Uses `config.MULTIPLAYER_MODE` + runtime `len(partyMembers) > 1` check
  - **9 Functions Added:**
    - `should_use_abstraction_layer()` - DUAL-CHECK activation
    - `get_character_state()` / `update_character_state()` - Main CRUD operations
    - `get_party_character_states()` - Bulk party loading
    - `get_character_field()` / `update_character_field()` - Single field access
    - `character_exists()` - Existence check
    - `_is_multiplayer_enabled()` - Cached config check
    - `_validate_character_name()` - Input validation
  - **Safety Features:**
    - Thread-safe statistics with `_stats_lock` for multi-threaded web server
    - Input validation rejects empty/None/invalid types
    - Config caching prevents repeated imports
    - Graceful fallback to direct file access on errors
  - **Upstream Integration (marked # TABLETOP MODE):**
    - `core/managers/combat_manager.py` - Combat character loading
    - `core/ai/action_handler.py` - Party filtering for encounters  
    - `utils/multi_pc_dm_note.py` - DM note character loading
  - **Verification:** Both combat LLM and narrator LLM paths verified working
  - **Performance:** Neutral (config caching slightly improves; <0.1% overhead vs LLM latency)
  - **Backward Compatibility:** Zero breaking changes; single-player mode unaffected
  - **Future Ready:** Database migration by updating `CHARACTER_STORAGE_BACKEND` constant
  - **Documentation:** `docs/functional_verification_report.md`, `docs/character_data_abstraction_implementation.md`
  - **Files Modified:** `utils/pc_manager.py` (~175 lines), `core/managers/combat_manager.py` (6 lines), `core/ai/action_handler.py` (5 lines), `utils/multi_pc_dm_note.py` (12 lines)

- **Multi-PC Conversation Compression (COMPLETED - 2026-02-04):**
  - Created `utils/compression/multi_pc_conversation_compressor.py` - Multi-PC aware compressor class (~350 lines)
  - Extends `ParallelConversationCompressor` via inheritance for clean merge boundaries
  - Implements message tagging with `active_pc` field for per-PC storyline tracking
  - Smart compression: Recent 8 exchanges kept raw, cross-PC events preserved
  - Groups messages by active PC to maintain narrative continuity during rotation
  - Dual-check activation: `MULTIPLAYER_MODE` config + runtime `active_pc` tag detection
  - Zero upstream impact: Standard compressor used for single-PC mode
  - Modified `main.py` with ~30 lines for message tagging and conditional selection
  - **Files:** `multi_pc_conversation_compressor.py` (new), `main.py` (2 locations modified)
  
- **Multi-PC DM Note Enhancement (COMPLETED - 2026-02-04):
  - Created `utils/multi_pc_dm_note.py` - Plugin-style DM Note builder for tabletop mode
  - Implements `[>]` Active PC marker (consistent with combat prompt syntax)
  - Section-based organization: WORLD STATE, ACTIVE PC, PARTY MEMBERS, PARTY NPCs, PLOT, LOCATION
  - Notable items filtering for non-Active PCs (quest/magic/consumable/>50gp only)
  - HP truth enforcement with `[SOURCE: DM Note]` tags to prevent hallucination
  - Third-person perspective guidance for all PCs
  - Full MULTIPLAYER_MODE integration (respects global toggle from config.py)
  - **Token Optimization:** ~80-token `@MULTI_PC` directive in compressed prompt
  - **Architecture:** Plugin-style with minimal main.py hooks (~10 lines modified)
  
- **ONCNotes Developer Diary System (COMPLETED - 2026-02-03):**
  - Created `memory-bank/ONCNotes.md` for ongoing conversational analysis
  - Captures "in-the-moment" developer observations from gameplay testing
  - Entry 001 documents split-party testing with OCNote analysis
  - Complements formal docs with informal testing diary format
  - Updated `read-combat-log` skill to automatically write diary entries
- **OpenCode Global Skill Creation (COMPLETED - 2026-02-03):
  - Created `sync-project-memory` skill at `~/.config/opencode/skills/sync-project-memory/SKILL.md`
  - Triggers on phrases: "update memory bank", "update memory", "sync memory", "sync docs and memory", "update agents and memory"
  - Automatically synchronizes AGENTS.md and Cline memory-bank when triggered
  - Ensures future AI assistants update BOTH documentation locations together
  - Follows exact-phrase matching (ignores partial matches like "memory" alone)
- **Real-Time Chat Monitoring System (COMPLETED - 2026-02-03):**
  - Added SocketIO middleware to `web/web_interface.py` to capture live chat events
  - Created `utils/chat_monitor.py` command-line utility for log analysis
  - Logs to `debug/logs/live_chat_monitor.json` with 100-entry rotating buffer
  - Enables AI assistant real-time gameplay monitoring without polling
  - Supports filtering by character, event type, and real-time follow mode
  - **Use Cases:** Live audience feeds, TTS narration, debugging, AI assistant visibility
- **Context Manager Pattern for Testability (COMPLETED - 2026-02-06):**
  - **Problem:** Global singleton pattern (`_active_combat_manager`, `_combat_callback`) makes unit testing difficult without running full Flask app
  - **Solution:** Implemented context manager pattern for clean dependency injection in tests
  - **Imports Added (lines 30-31):** `Generator` from `typing`, `contextmanager` from `contextlib`
  - **Context Managers (lines 1251-1290):**
    - `temporary_combat_manager(manager)` - Temporarily inject mock combat manager
    - `temporary_combat_callback(callback)` - Temporarily replace event callback
    - Both use `@contextmanager` decorator with automatic cleanup via `try/finally`
  - **Reset Helper (lines 1292-1302):** `reset_combat_state()` - Clears global state for test isolation
  - **Benefits:** Zero breaking changes, clean test syntax, composable (can nest), thread-safe, enables parallel test execution
  - **Test Scenarios Enabled:** Mock combat without Flask, test edge cases, verify persistence without file I/O, capture web events
  - **Files Modified:** `core/managers/multi_pc_combat.py` (3 imports + 3 functions, ~50 lines)

- **Multi-PC Combat Manager Error Handling Fix (COMPLETED - 2026-02-06):**
  - **Problem:** Inconsistent error handling with mix of `debug()`, `print()`, and silent pass statements across `core/managers/multi_pc_combat.py`
  - **Solution:** Standardized all logging to use `utils.enhanced_logger` with proper categories
  - **Import Update (line 45):** Added `info` and `error` to existing `debug` import
  - **6 print() Statements Replaced:**
    - 4x `error()` - for error conditions and exceptions (lines 849, 868, 871, 1274)
    - 2x `info()` - for success confirmation and lifecycle messages (lines 866, 1310-1314)
  - **Logger Categories:** `combat_persistence` (save/load ops), `combat_events` (callback errors), `combat_lifecycle` (session management)
  - **Result:** Zero `print()` statements remaining, consistent error handling following codebase standards
  - **Files Modified:** `core/managers/multi_pc_combat.py` - 6 lines changed, 1 import updated

- **Split-Party Combat Narrative Enhancement (COMPLETED - 2026-02-03):**
  - Added `@SPLIT_PARTY_GUIDANCE` to `prompts/combat/combat_sim_prompt_multipc_compressed.txt` (lines 146-154)
  - Guides combat LLM to handle party members in different locations from active combat
  - **Testing Results:** Successfully maintained dual narrative for 8-10 turns before natural context compression
  - **Human DM Role:** Player narrates rejoining ("we walk up the stairs") to recover frozen context
  - Minimal 20-line addition (~150 tokens) prevents "What does [wrong PC] do?" loop
- **Multi-PC Combat PC/NPC Type Classification Fix (COMPLETED):**
  - Fixed PCs being incorrectly classified as `type: "npc"` in combat encounters.
  - Root cause: AI was including party members in the `npcs` array when generating `createEncounter` actions.
  - Solution: Added filtering in `core/ai/action_handler.py` to remove party members from `npcs` before encounter generation.
  - Fixed `encounter_C05-E2.json` to have correct types for all PCs and removed erroneous `npcType` fields.
  - Prevents LLM confusion during batch enemy phase processing.
- **Multi-PC Combat Enemy Armor Class Fix (COMPLETED):**
  - Fixed enemy AC defaulting to 10 regardless of monster template values (e.g., Mimic AC 12).
  - Root cause: `core/generators/combat_builder.py` was not including `armorClass` when building enemy encounters.
  - Solution (Option A): Added `armorClass: monster_data.get("armorClass", 10)` to monster generation (line ~347) with `# TABLETOP MODE:` comment.
  - Solution (Option D): Enhanced `initialize_turn_queue()` in `multi_pc_combat.py` (lines ~326-352) to backfill missing AC from monster templates at runtime.
  - Impact: 19 existing encounters without AC will now resolve correct armor values; `/att` command hit/miss resolution fixed.
- **Multi-PC Initiative Tracking Fix (COMPLETED):
  - Fixed scrambled initiative order where AI asked PCs for actions after they already acted.
  - Root cause: AI tracker only recognized first PC with `type == "player"`, treating others as NPCs.
  - Solution: Bypassed AI tracker in multi-PC mode using deterministic `multi_pc_manager.format_initiative_tracker()`.
  - Modified `core/managers/multi_pc_combat.py` with new `format_initiative_tracker()` method.
  - Modified `core/managers/combat_manager.py` to use multi-PC tracker when available.
  - Maintains backward compatibility with AI tracker fallback for single-PC mode.
- **Multi-PC Combat Prompt Rebuild (Task 1 & 1.5):**
  - Created `prompts/combat/combat_sim_prompt_multipc.txt` based on the robust single-player foundation.
  - Hydrated `prompts/combat/combat_validation_prompt_multipc.txt` to align with the new prompt and enforce multi-PC rules.
  - Validated interaction between the new prompt and validator (Confirmed no conflicts).
- **Multi-PC Combat Enhancement Plan (NEW):** Created comprehensive implementation plan (`Docs/multi_pc_combat_enhancement_plan.md`) for 5 key enhancements:
  1. "Holding Pattern" Protocol - Handle out-of-turn PC declarations
  2. Comprehensive Examples - AoE spells, saving throws, complex rounds  
  3. NPC Ally Examples - Show NPC allies acting alongside enemies
  4. Standardize Preroll Format - Match single-player's clarity
  5. Initiative Visualization - Better turn markers
- **PDF Export Improvements**:
  - Replaced `html2pdf.js` with native `window.print()` to fix blank page rendering.
  - Initiated total rebuild of character sheet layout using CSS Grid to match official Wizards of the Coast 5E printable template.
- **Prompt Agency Enforcement**:
  - Renamed prompt labels to "Active Player Characters (User Controlled)" and "Accompanied by Party NPCs (DM Controlled)" in `main.py`.
  - Added strict agency rules to `prompts/system_prompt.txt` to prevent LLM autopilot for user-controlled characters.
- **Tabletop Party Management**:
  - Implemented "Manage Party" modal replacing the simple "+" button.
  - Added "Add Existing Character" functionality with character list.
  - Added "Retire Character" functionality with UI confirmation.
  - Fixed backend bug in `add_party_character` (ImportError).
- **Weapon Synchronization**:
  - Implemented automatic weapon-to-attack synchronization in Python.
  - Added a standard weapon database for auto-filling attack stats.
- **Multi-PC Combat Integration**:
  - Connected `MultiPCCombatManager` to the core `combat_manager.py` loop.
  - Implemented dynamic prompt injection for turn status and PC context.
  - Automated turn-tracking and round progression hooks.
  - Synchronized real-time character state (HP/Status) between files and UI.
- **Multi-PC Combat Cleanup (STABILIZED)**:
  - Implemented architectural cleanup for deterministic combat flow.
  - Replaced brittle turn-index slicing with state-based non-PC batch calculation (Option B).
  - Added authoritative `=== COMBAT PHASE STATE ===` block to LLM prompts to prevent turn amnesia.
  - Removed obsolete legacy browser overlay (`multi_pc_combat.js`) and associated SocketIO endpoints.
- **Bulletproof Phase Transition (COMPLETED)**:
  - Implemented `/end` command and prompt logic for deterministic PC-to-Enemy phase handoff.
  - Ensures enemy turns are triggered reliably when all PCs have acted.
  - Added explicit prompt instructions to stop PC prompts when enemy phase begins.
- **Multi-PC Validation Hydration (COMPLETED)**:
  - Rebuilt `prompts/combat/combat_validation_prompt_multipc.txt` to achieve full parity with the single-player validation prompt (~360 lines).
  - Restored critical validation logic for HP math, resource usage, and status integrity.
  - Added explicit Multi-PC rules: "Golden Rule" (Active PC check) and "Batch Enemy Phase".
  - Aligned the compressed validation prompt for consistent behavior.
- **Multi-PC Validation Layer (NEW)**:
  - Created specialized Multi-PC validation prompts to enforce batch processing and turn order.
  - Integrated dynamic validation prompt switching in `combat_manager.py`.
  - Added hard-wired Python guardrails against premature round advancement.
- **UI/UX Maintenance & Fixes**:
  - **Startup Synchronization**: Fixed issue where the active PC was not correctly synced to JS state on page load.
  - **404 Log Suppression**: Implemented client-side image caching (Set-based) to stop repetitive requests for missing character assets.
- **Core Engine**:
  - Stabilized LLM output formatting and JSON adherence.
  - Improved robustness of the game loop against API errors.
  - Added future-proofing for multi-PC combat metadata (position markers support).

## 📋 Todo List

### 5e Rest Automation (Option B - COMPLETED - 2026-02-05)
- [x] **PROMPT CONTRACT BUG:** Add "rest" to @ACTIONS, @PARAMS, @EXAMPLES in prompts/system_prompt_compressed.txt
  - Added to @ACTIONS (line 24): "rest"
  - Added to @PARAMS (line 228): rest parameters
  - Added @EXAMPLES (lines 292-295): {"action":"rest","parameters":{"type":"long","characters":["Acheron","Claris"]}}
  - Updated @REST section (lines 109-116) with 5e rest rules
- [x] **IMPLEMENTATION:** Create `_process_character_rest()` in core/ai/action_handler.py (lines ~1902-2065)
  - Short rest logic: Warlock spell slots + shortRest features only (no auto-heal)
  - Long rest logic: Full HP, all spell slots, all features, exhaustion removal
  - Parameter validation for rest_type ("short" or "long")
- [x] **BUG FIXES:**
  - [x] Fixed character path resolution using `find_character_file_fuzzy()`
  - [x] Fixed exhaustion detection (schema uses list[string], not list[dict])
  - [x] Added file existence safety checks
  - [x] Added logging with proper error handling
- [x] **TESTING:** Created scripts/test_rest_action.py as integration test specifications
- [x] **5e COMPLIANCE VERIFIED:**
  - Short rest: Only refreshes shortRest features + Warlock pact magic
  - Long rest: HP to max, all spell slots, all features, removes exhaustion
  - Hit Dice: Players manually spend via updateCharacterInfo (not auto-tracked)

### Multi-PC DM Note Enhancement (COMPLETED - 2026-02-04)
- [x] Create plugin file `utils/multi_pc_dm_note.py` (~250 lines, merge-safe)
- [x] Implement `[>]` Active PC marker consistent with combat prompt
- [x] Section-based DM Note organization (WORLD STATE, ACTIVE PC, PARTY MEMBERS, etc.)
- [x] Notable items filtering for non-Active PCs (quest/magic/consumable/>50gp)
- [x] Third-person perspective guidance for all PCs
- [x] HP truth enforcement with `[SOURCE: DM Note]` tags
- [x] MULTIPLAYER_MODE global toggle integration
- [x] Refactor main.py DM Note builder with conditional routing (~10 lines changed)
- [x] Add `@MULTI_PC` directive to compressed prompt (~80 tokens)
- [x] Document rest automation (Option B) in AGENTS.md for future implementation

### Multi-PC Combat Prompt Rebuild (COMPLETED)
- [x] Task 1: Foundation Migration with Active PC Integration (v2 prompt)
- [x] Task 1.5: Validation Logic Update (Hydrated Multi-PC validation prompts)
- [x] Task 2: Multi-PC Example Integration (COMPLETED - 12 examples including Death Saves)
- [x] Task 3: Protocol Adaptation for Multi-PC (COMPLETED - All protocols adapted with queue ordering enhancement)
- [x] Task 4: NPC Combat Interaction Guidelines Update (COMPLETED - All 5 objectives addressed including new Guideline 10)
- [x] Task 5: Preroll System Integration (COMPLETED - Preroll format documentation added)
- [x] Task 6: Final Integration and Validation - Codebase Update (COMPLETED)
- [x] **Task 7: Multi-PC Initiative Tracker Fix (COMPLETED)**
  - [x] Bypass AI initiative tracker which only supports single-PC mode
  - [x] Implement deterministic `format_initiative_tracker()` in `multi_pc_combat.py`
  - [x] Update `combat_manager.py` to use multi-PC tracker when available
  - [x] Maintain fallback to AI tracker for single-PC mode
- [x] **Task 8: Multi-PC Combat Enemy Armor Class Fix (COMPLETED)**
  - [x] Add `armorClass` to enemy generation in `combat_builder.py`
  - [x] Implement backfill logic in `multi_pc_combat.py` for existing encounters
  - [x] Verify fix with Mimic (AC 12) and other monster templates
- [x] **Task 9: Multi-PC Combat PC/NPC Type Classification Fix (COMPLETED)**
  - [x] Identify root cause: AI including party members in `npcs` array
  - [x] Implement filtering in `action_handler.py` to remove party members from `npcs`
  - [x] Fix existing encounter file `C05-E2.json` with correct types
  - [x] Clean up erroneous `npcType` fields from player entries
  - [x] Verify combat sync no longer loads PCs as NPCs
- [x] **Task 10: Real-Time Chat Monitoring (COMPLETED - 2026-02-03)**
  - [x] Add SocketIO middleware to `web_interface.py` for live event capture
  - [x] Create `utils/chat_monitor.py` utility with filtering and follow mode
  - [x] Document in AGENTS.md with usage examples
- [x] **Task 11: Split-Party Combat Enhancement (COMPLETED - 2026-02-03)**
  - [x] Add `@SPLIT_PARTY_GUIDANCE` to combat prompt (minimal 20-line edit)
  - [x] Test and verify 8-10 turn dual narrative capability
  - [x] Document in AGENTS.md with testing results

### Tabletop Mode
- [x] Create "Manage Party" modal UI.
- [x] Implement "Add Existing Character" logic.
- [x] Implement "Retire Character" logic.
- [x] Fix `ImportError` in `web_interface.py` for adding characters.
- [x] Implement Multi-PC Combat Mode (Turn tracking, Group Initiative, Death Saves).
- [x] Integrate Multi-PC Combat into core combat loop (Prompt injection, State sync).
- [x] Multi-PC Combat Overhaul (Automated Handoff & Phase Cleanup).
- [x] **MultiPCCombatManager Audit & Test Suite (COMPLETED - 2026-02-06):**
  - [x] Create comprehensive test suite with 40 unit tests
  - [x] Test all delegation methods (7 total)
  - [x] Test all coordination methods (5 total)
  - [x] Test LLM prompt integration points (5 formatting functions)
  - [x] Test context managers for isolated testing
  - [x] Test edge cases (empty party, all incapacitated, no enemies)
  - [x] Fix bugs discovered during testing (2 fixes)
  - [x] Document audit findings
- [ ] Test "Quick Create" character flow (manual form).
- [x] Implement "Create New Player" via LLM flow.
- [ ] Finish official 5E Character Sheet PDF rebuild.

### Core Engine
- [ ] Refactor `user_input_queue` to `shared_state.py` eventually for cleaner architecture (low priority).
- [x] Enhance character sheet parsing for more robust updates.

### UI/UX
- [ ] Polish styles for the new modal.
- [ ] Add tooltips for new management buttons.

## 🐛 Known Issues
- None critical at the moment.

## 📉 Backlog
- **Narrative Mode Head-JSON Optimization**: Refactor `conversation_utils.py` to use a consolidated JSON "Head" for the entire party (mirroring the combat architecture) to save tokens and improve multi-PC continuity.
- Advanced filtering for character list in "Add Existing".
- "dm_quick_create" improvements for more detailed character templates.
