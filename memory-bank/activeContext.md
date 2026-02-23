## Current Work Focus

- **Multi-Currency Debug Tab Cost Conversion (COMPLETED - 2026-02-24):**
  - **Status:** Live exchange rate fetching with multi-currency support implemented and tested.
  - **Config:** `EXCHANGE_RATE_TARGET_CURRENCY` supports any ISO 4217 3-letter code (NZD, AUD, CAD, EUR, GBP, JPY).
  - **Validation:** Currency codes validated as 3-letter alphabetic; invalid codes fall back to USD (1.0).
  - **Fallback Chain:** Live API → static NZD rate → USD (1.0) for non-NZD targets.
  - **Frontend:** Debug tab currency labels are dynamic based on `exchange_effective_currency` from backend.
  - **Testing:** 23/23 regression tests PASS, including end-to-end config validation test.
  - **Files:** `config_template.py`, `config.py`, `utils/llm_usage_tracker.py`, `web/web_interface.py`, `web/templates/game_interface.html`, `scripts/test_usage_rollups_debug_tab.py`.

- **World-Narrative Ingestion Foundation + Meta Assignment Planning (IN PROGRESS - 2026-02-22):**
  - **OpenSpec Change:** `world-narrative-seed-bootstrap-and-toolkit-ingestion` (new, valid)
  - **Copyright Firewall:** Hard cutover path is now `/user_uploads/text/` only (legacy `/user_uploads/` paths are rejected in route/test contracts).
  - **Ingestion Tooling Basis:** Local PDF chunk extractor + source-anonymous atom builder scripts are staged for one-book-at-a-time seed compilation.
  - **Bootstrap + Schema:** Runtime seed bootstrap contract and world-narrative additive tables are wired in memory foundation planning/implementation.
  - **Meta Governance:** Added `meta_source_rubric.md` and `profile_assignment_list.md` to OpenSpec for layered priors (strategy/cosmology/horror -> fantasy specifics).
  - **Verification:** `openspec validate world-narrative-seed-bootstrap-and-toolkit-ingestion` PASS; route/bootstrap verification scripts pass in `.venv`.

- **PDF Export Portrait and Typography Improvements (COMPLETED - 2026-02-19):**
  - **OpenSpec Change:** PDF export enhancements for character sheet downloads
  - **Portrait Embedding:** PC portrait now appears in page 2 Character Appearance box
    - Helper: `_resolve_character_portrait_path()` - multi-tier lookup (static portraits, module portraits, NPC media)
    - Helper: `_get_character_image_rect()` - reads PDF template widget rectangle
    - Helper: `_embed_character_portrait()` - stamps image into specified rectangle using pypdf/Pillow
  - **Font Size Override:** 8pt font for text-heavy fields to prevent clipping
    - Constant: `PDF_EXPORT_TEXT_FONT_SIZE = 8`
    - Target list: 20 fields including personality, attacks/spellcasting (with weapon rows), equipment, features, backstory, treasure
    - Helper: `_set_pdf_widget_font_size()` - sets widget `/DA` to `/Helvetica 8 Tf 0 g`
  - **Physical Traits:** Age, Height, Weight, Eyes, Skin, Hair now populate on page 2
  - **Debug Headers:** `X-Debug-Portrait-Source` and `X-Debug-Portrait-Status` in dev mode
  - **File Modified:** `web/routes/character_sheet_routes.py`
  - **Verification:** Compile PASS, font override applies to 20 widgets, portrait embeds correctly

- **DALL-E 3 Image Cost Rollup for Debug Tab (COMPLETED - 2026-02-19):
  - **OpenSpec Change:** `dalle3-image-cost-rollup-debug-tab` (archived to `openspec/changes/archive/2026-02-19-dalle3-image-cost-rollup-debug-tab/`)
  - **Pricing Foundation:** Added `DALLE3_PRICING_USD` config table in `model_config.py` with explicit per-image pricing for all size/quality combinations.
  - **Tracker Foundation:** Implemented `track_image_cost()` helper in `utils/llm_usage_tracker.py` that updates session/week USD/NZD rollups while preserving token counters (cost-only events).
  - **Compatibility:** New helpers re-exported via `utils/openai_usage_tracker.py` to maintain existing import path stability.
  - **Callsite Instrumentation:**
    - `core/toolkit/portrait_service.py` - tracks after successful character portrait save
    - `core/toolkit/npc_generator.py` - tracks after successful NPC portrait generation (fail-open with None check)
    - `core/toolkit/monster_generator.py` - tracks after successful monster portrait generation (fail-open with None check)
    - `web/web_interface.py` - tracks after successful `generate_image` socket generation (post-retry block to ensure single-count)
  - **Context Metadata:** All calls include structured context (endpoint, purpose, model, size, quality, n) for telemetry clarity.
  - **Regression Tests:** Extended `scripts/test_usage_rollups_debug_tab.py` with comprehensive Test 7.x series:
    - Test 7.1: DALL-E 3 cost lookup validation
    - Test 7.2: Image cost-only event (cost increases, tokens unchanged)
    - Test 7.3: Mixed session token + image aggregation
    - Test 7.4: Fail-open behavior (zero/negative/None cost handling)
    - Test 7.5: Telemetry entry structure with image_metadata
    - Test 7.6: Multiple image events aggregation
  - **Testing:** All 16 regression tests PASS, compile checks PASS, OpenSpec validation VALID.
  - **Architecture:** Fail-open design ensures image generation never blocked by telemetry failures. Zero token inflation guarantee for image-only events. Compatibility maintained via re-export shim.

- **Developer Documentation Packaging (COMPLETED - 2026-02-19):
  - Plans and OpenSpec developer docs are being bundled into the tester-facing commit stream.
  - Committed docs pass includes `plans/` and `openspec/changes/debug-usage-session-week-nzd-rollup/`.
  - Prior docs pass already committed `openspec/changes/toolkit-module-builder-rebuild-phase1-npc-alignment/` and memory-bank updates.
  - `.opencode` commit guardrail confirmed: stage only curated skills/command docs when needed; do not force-add dependency/package artifacts.

- **Background Feature UX Clarity (COMPLETED - 2026-02-19):**
  - **OpenSpec Change:** `background-feature-ux-clarity` (archived to `openspec/changes/archive/2026-02-19-background-feature-ux-clarity/`)
  - **Shared Placeholder Contract:** Added helper functions `is_generic_background_feature_name()` and `is_generic_background_feature_description()` to `utils/character_creation_audit.py` for deterministic placeholder detection. Extended completeness audit to flag generic placeholders as `completeness_error`.
  - **Guided Entry UX:** Updated portrait profile modal and manual character creation form labels/placeholders with concrete examples ("Criminal Contact, Researcher, Military Rank") and "1-3 sentences" guidance for descriptions.
  - **Backend Prefill:** Implemented `get_known_background_feature_suggestion()` and `apply_background_feature_suggestion_if_generic()` helpers. Integrated into portrait create flow (`web/web_interface.py`) and manual create flow (`web/routes/tabletop_party_routes.py`).
  - **Readiness and Repair Alignment:** Extended `getCharacterReadinessWarnings()` in Character Sheet to detect generic placeholders. Added `backgroundFeature.name` to `READINESS_REPAIR_WRITABLE_FIELDS` and fallback text. Updated warning banner to "Character sheet incomplete: fields missing or need meaningful values".
  - **Legacy Remediation Tooling:** Created `scripts/remediate_background_feature_placeholders.py` with `--dry-run` and `--apply` modes. Fail-open per-file error handling with read/analysis/write categorization. Atomic writes via `safe_write_json()`. Created comprehensive test suite `scripts/test_remediate_background_feature_placeholders.py` (5 tests, all PASS).
  - **Spec Sync:** Created new capability specs `background-feature-guided-entry-ux` and `background-feature-placeholder-remediation`. Updated existing specs `character-sheet-completeness-audit` and `tt-character-readiness-repair` with background feature placeholder scenarios.
  - **Testing:** All tests PASS - `test_character_creation_audit.py` (7 groups), `test_remediate_background_feature_placeholders.py` (5 functions). Dry-run on 19 production characters shows 0 changes needed (all already have proper values).

- **Portrait Prompt Visual Brief Hardening (COMPLETED - 2026-02-19):**
  - Reworked PC/allied portrait prompt assembly in `core/toolkit/portrait_service.py` to use structured-to-prose visual brief synthesis instead of label-like stat formatting.
  - Added defensive parsing helpers for numeric extraction and age descriptor mapping to prevent prompt build failures on non-numeric values.
  - Removed passport wording and reinforced anti-overlay exclusions to reduce character-sheet/card render artifacts.
  - Added connector normalization for personality clauses to avoid awkward phrasing patterns (`guided by believes`, `deeply connected to loyal to`, repeated "sometimes").
  - Added punctuation guard to prevent four-dot artifacts from bounded truncation.
  - Expanded regression coverage in `scripts/test_pc_image_create_mvp.py` (prompt format, anti-document exclusions, non-numeric safety, connector normalization).
  - Verification: `python3 -m py_compile core/toolkit/portrait_service.py` PASS, prompt test class PASS (19 tests).

- **Debug Sidebar Density + Cost Table Alignment (COMPLETED - 2026-02-19):**
  - Implemented compact density tuning in `web/templates/game_interface.html` for narrow debug sidebar readability and long narration sessions.
  - Finalized always-on compact spacing while removing LED font leak from sidebar tabs and narration chat.
  - Reworked Session/Week rollup markup into structured value tokens to eliminate spacing artifacts around currency and NZD parentheses.
  - Added right-aligned label column behavior (`Session:`, `Week:`) with grid-based row structure for stable table-like alignment.
  - Kept LED-style monospace emphasis only on debug telemetry surfaces where it improves scanability.

- **Portrait Create/Upload UX Locking (COMPLETED - 2026-02-19):**
  - **Objective:** Prevent duplicate portrait generation/upload requests and provide clear UX feedback during async operations
  - **Problem:** Clicking Create or Upload multiple times could trigger duplicate requests; no visual indication of processing state
  - **Solution:** Implemented shared portrait operation lock with centralized UI state synchronization
  - **Implementation:**
    - **Shared State Variables:** `portraitOperationInFlight` (boolean lock), `portraitOperationMessage` (progress text), `backendIsProcessing`/`backendStatusMessage` (backend coordination)
    - **Helper Functions:**
      - `setPortraitButtonsDisabled(disabled)` - Disables/enables all `.portrait-action-btn` elements
      - `syncInputAndPortraitUiState()` - Central coordinator managing input/send button states and placeholder text based on all processing conditions
    - **Status Handlers:** Modified `socket.on('status_update')` and `socket.on('status_response')` to store backend state and call centralized sync function
    - **Upload Flow:** Early return if lock active, set lock + message before fetch, clear in `.finally()`, re-sync UI state
    - **Create Flow:** Same lock pattern for profile submission, guards both submitPortraitProfile and createPortrait entry points
    - **Character Sheet Re-render:** Reapplies button disabled state after DOM refresh to maintain lock during periodic updates
    - **CSS:** Added `.portrait-action-btn:disabled` and `:disabled:hover` styles with reduced opacity and `not-allowed` cursor
  - **Lock Coordination Logic:**
    - Input/send disabled when: `!connected || !gameStarted || backendIsProcessing || portraitOperationInFlight`
    - Placeholder priority: portrait message → backend message → default prompt
    - Portrait buttons disabled only during portrait operations (not backend processing)
  - **Cleanup:** Removed redundant `createPortraitInFlight` variable (now uses shared `portraitOperationInFlight`)
  - **File Modified:** `web/templates/game_interface.html` (~75 lines changed: CSS, state vars, helpers, status handlers, upload/create flows, re-render hook)
  - **Verification:** All 16 implementation checks passed (variables, functions, CSS, lock patterns, cleanup)

- **Portrait Cache Coherence - Section 10 (COMPLETED - 2026-02-19):**
  - **OpenSpec Change:** `pc-image-create-and-allied-npc-autogen` Section 10 extension
  - **Objective:** Eliminate stale/reverting portrait behavior after upload/create mutations
  - **Backend Metadata Helpers:** `_normalize_character_slug()`, `_get_image_candidate_paths()`, `_compute_image_version_from_paths()`, `_build_image_metadata()` in `tabletop_socket_handlers.py`
  - **Payload Emission:** `image_slug` + `image_version` in initiative/party payloads; `_portrait_slug` + `_portrait_version` in stats payload
  - **Frontend Helpers:** `normalizePortraitSlug()` + `withAssetVersion()` in `game_interface.html`; updated Character Sheet, initiative, party strip surfaces
  - **Cache Invalidation:** `invalidateImageCachesForSlug()` removes targeted entries from `missingImageCache` and `existingImageCache` after mutations
  - **Ordering Fix:** Captures `preservedSlug` before `closePortraitProfileModal()` clears state; uses preserved identity for refresh
  - **Immediate Refresh:** Upload/create success paths call `loadCharacterStats()`, `requestInitiativeData()`, `requestPartyData()` without polling wait
  - **Regression Tests:** 8 new tests added (`TestPortraitMetadataPayloadContracts`, `TestFrontendCacheInvalidationContracts`), all PASS
  - **Files Modified:** `web/extensions/tabletop_socket_handlers.py` (+115 lines), `web/web_interface.py` (+14 lines), `web/templates/game_interface.html` (+102 lines), `scripts/test_pc_image_create_mvp.py` (+128 lines, 8 new tests)


- **Load Dialog Unified Archive/Save Timeline (COMPLETED - 2026-02-17):
  - **OpenSpec Change:** `load-dialog-unified-archive-save-timeline` fully implemented, validated, and archived
  - **Objective:** Merge save folders and archive zips into one recency-ordered timeline with entry-type filters
  - **Implementation Complete:**
    - **Unified Entry Model:** Client-side normalization helper `normalizeLoadEntries()` maps both `save_list_response` and `archive_zip_list_response` into shared structure with `entry_type` (`save_folder` or `archive_zip`), `display_name`, and `sort_timestamp`
    - **Unified Sort and Render:** Merged render pipeline using `compareUnifiedEntries()` comparator for newest-first ordering with deterministic tie-break (timestamp -> type -> name)
    - **Timestamp Parsing:** `parseSaveTimestamp()` with fallback chain (parsed date -> folder name YYYYMMDD_HHMMSS extraction -> 0), `parseArchiveTimestamp()` for ISO strings
    - **Filter Controls:** Three chips (`all`, `save_folders`, `archive_zips`) with default `all`, visual `.active` state via `updateFilterChipVisuals()`
    - **Selection Safety:** `isEntryVisibleUnderFilter()` checks visibility, `clearLoadDialogSelection()` resets state when filtered out, `updateLoadButtons()` reflects current availability
    - **Filter Application:** `getFilteredUnifiedEntries()` applies active filter before render, per-filter empty messages ("No save folders found", "No archive zips found")
  - **Action Compatibility Preserved:**
    - `save_folder` selection -> `restoreGame` with `saveFolder` + optional `sourceModule`
    - `archive_zip` selection -> `restoreArchiveZip` with `zipName`
    - Delete disabled for archive entries (`entry_type !== 'archive_zip'` check in `updateLoadButtons()` and `deleteSelectedSave()`)
  - **Verification:**
    - Compile gate: PASS (`python3 -m py_compile web/web_interface.py`)
    - JS syntax gate: PASS (load dialog block validated)
    - `openspec validate`: PASS (Change is valid)
    - Invariant checks: All 7 pass (unified model/sort, filters, selection safety, restore routing, delete restrictions)
  - **Files Modified:** `web/templates/game_interface.html` (+364/-65 lines) - unified helpers, filter UI/CSS, merged render, preserved action routing
  - **Archived:** `openspec/changes/archive/2026-02-17-load-dialog-unified-archive-save-timeline/`
  - **Specs Updated:** `openspec/specs/load-dialog-action-compatibility/`, `openspec/specs/load-dialog-entry-filters/`, `openspec/specs/load-dialog-unified-timeline/`

- **PR2 Archive Zip Portability and Memory Backup Parity (COMPLETED - 2026-02-16):**
  - **OpenSpec Change:** `archive-zip-portability-and-memory-backup-parity` fully implemented and validated (Steps 1.1-4.3 complete)
  - **Section 1 - Archive Auto-Zip Backend:**
    - Step 1.1: Added `_generate_archive_zip()` helper in `updates/save_game_manager.py` with deterministic zip naming and structured result contract
    - Step 1.2: Implemented `_get_archive_additional_paths()` with campaign-wide inclusion policy (campaign_archives/, campaign_summaries/, global files)
    - Step 1.3: Added `memory_db_package/` inclusion and fail-closed behavior (memory entries sorted, critical write failures fail archive)
  - **Section 2 - Existing Save Flow Integration:**
    - Step 2.1: Integrated auto-zip trigger in `web/web_interface.py` for `save_mode=full` only
    - Step 2.2: Archive artifact status/path returned in success payload (archive.status, zip_path, zip_name, bytes)
    - Step 2.3: Preserved essential save behavior with legacy content-only payload
  - **Section 3 - Reset Backup Memory Parity:**
    - Step 3.1: Added memory state artifact capture to `utils/reset_campaign.py` (data/memory.db -> backup_dir/data/memory.db)
    - Step 3.2: Non-fatal absence reporting ("[INFO] Memory state artifact not present; continuing backup")
    - Step 3.3: Layout verification helper (`_verify_backup_layout_compatibility()`) with [OK]/[WARNING]/[INFO] status markers
  - **Section 4 - Validation:**
    - Step 4.1: Compile gate passed (all 3 files compile successfully)
    - Step 4.2: Smoke test passed (full save creates zip, path in message, ~26MB archive size)
    - Step 4.3: Negative tests passed (forced archive failure causes full save fail, essential save unaffected)
  - **Files Modified:** `updates/save_game_manager.py`, `web/web_interface.py`, `utils/reset_campaign.py`
  - **Evidence:** Archive zip generated at `modules/Keep_of_Doom/saved_games/archive_20260216_172143.zip` (26,499,753 bytes)
  - **Status:** All Steps 1.1-4.3 COMPLETE, validated, ready for PR3

- **PR3 Root Archive Export + Zip Import Restore (COMPLETED - 2026-02-17):**
  - **OpenSpec Change:** `archive-root-export-and-zip-import-restore` fully implemented, validated, and ready for archival
  - **Objective:** Enable repo-root archive exports for USB copy workflows and direct zip restore without manual unzip/staging
  - **Implementation Complete:**
    - **Root Export Foundation:** `ARCHIVE_EXPORTS_DIR`, `_get_archive_exports_directory()`, deterministic naming
    - **Archive Catalog:** `list_archive_exports()` for `archive_exports/*.zip` discovery
    - **Zip Preflight:** `_validate_archive_zip_preflight()` rejects traversal, absolute paths, missing metadata, unknown modules
    - **Secure Extraction:** `_extract_archive_save_to_temp()` with temp cleanup, defense-in-depth path validation
    - **Canonical Staging:** `_stage_archive_save_folder()` into `modules/<module>/saved_games/`
    - **Restore Pipeline:** `restore_save_game_archive()` validates -> extracts -> stages -> delegates to `restore_save_game_global()`
    - **Web Integration:** `listArchiveZips` and `restoreArchiveZip` socket handlers with existing emit semantics
    - **Load Dialog:** Dual rendering for save folders and archive zips, archive rows show name/size/modified, delete disabled for archives
  - **Regression Suite:** `scripts/test_archive_zip_restore.py` (10 tests: traversal, absolute path, missing metadata, unknown module, preflight, resolve, extraction, staging, delegation, catalog sorting) - all PASS
  - **Verification:** Compile gate PASS, positive smoke PASS, negative smoke PASS (all fail-closed), regression PASS (essential save and folder restore unchanged)
  - **Files Modified:** `updates/save_game_manager.py` (+~340 lines), `web/web_interface.py` (+~40 lines), `web/templates/game_interface.html` (+~120 lines), `scripts/test_archive_zip_restore.py` (new)
  - **Status:** COMPLETED, all 7.x tasks done, ready for archival

- **PC Leave/Return World Memory (COMPLETED - 2026-02-17):** OpenSpec change `pc-leave-return-world-memory` fully implemented, validated, and archived. **Phase 1:** `core/memory/party_transition_memory.py` created with `record_pc_retirement()`, `record_pc_return()`, `build_return_memory_pack()` - uses canonical entity IDs, `role_transition` events with `importance=95`, fail-safe returns. **Phase 2:** Retirement flow in `web/routes/tabletop_party_routes.py:remove_party_character` - accepts `departure_text`, guards for active combat/final member, fail-open memory persistence, retirement narration with farewell/mysterious fallback, `_tabletop_role_history` append. **Phase 3:** Return flow in `web/routes/tabletop_party_routes.py:add_party_character` - true rejoin detection, return memory persistence, continuity pack for narration (bounded: max 3 snippets per source, max 12 combined), canonical identity preservation via `ensure_stable_character_id()`. **Phase 4:** UI flow `web/static/js/tabletop_mode.js:retireCharacter` collects optional farewell text, prompt templates created at `prompts/tabletop/retirement_narration.txt` and `prompts/tabletop/return_narration.txt` with narration-only instructions and required placeholders. **Phase 5:** Test suite `scripts/test_party_retirement_memory.py` created with 4 test functions (20+ assertions) covering persistence, no-purge guarantees, continuity retrieval, graceful degradation - all PASS with temp DB isolation. Structured degraded-mode logging implemented: `MEMORY_TRANSITION event=retirement|return character=<name> status=success|degraded ... fallback=enabled`. All verification commands PASS: Python compile, JS syntax, regression tests, lifecycle tests. **Status:** COMPLETE, archived to `openspec/changes/archive/2026-02-17-pc-leave-return-world-memory/`.

- **Module Builder Rebuild - Phase 1 NPC Alignment (SCAFFOLDED - 2026-02-19):**
  - Created phased rebuild roadmap at `plans/module-builder-enhancements.md`
  - Created initial OpenSpec scaffold at `openspec/changes/toolkit-module-builder-rebuild-phase1-npc-alignment/`
  - **Scope:** Align module-authored NPC intent with runtime NPC materialization and promotion readiness
  - **Core Deliverables:**
    - Per-module NPC profile seed artifact (`npc_profile_seeds.json`)
    - Seed-aware NPC builder with deterministic postprocessing
    - Runtime callsite alignment (enlist/combat paths)
    - Hardened Add Existing candidate classification
  - **Non-Goals:** No full toolkit UI rebuild, no async workers, no eager generation of all NPC sheets
  - **Status:** Planning complete, ready for future implementation. Current gameplay (NPC recruit/promote) remains functional without this work.

- **PC Image Create and Allied NPC Auto-Generation Planning (PLANNED - 2026-02-16):** Completed comprehensive UX enhancement plan at `/plans/pc-image-create.md` for Character Sheet portrait `Upload / Create` actions. **Auto-Generation Policy:** Allied NPC companions only in MVP; non-allied NPCs and monsters disabled by default. **Appearance Fields:** Optional schema fields (`age`, `height`, `weight`, `eyes`, `skin`, `hair`) for portrait prompt enrichment, backward compatible. **Warning Throttle:** Per-key missing media log throttling to reduce spam. **Promotion Invariant:** NPC -> PC promotion preserves image linkage by name identity. **OpenSpec Scaffolding:** Created change `pc-image-create-and-allied-npc-autogen` with validated artifacts - `proposal.md`, `design.md`, `tasks.md`, `executor_prompts.md`, and four capability specs. **Step 1.1 Complete:** Schema updated in `schemas/char_schema.json`. **Next:** Builder execution for Steps 1.2-7 via executor prompts.

- **PR1 Archive Global Save Index and Restore Routing (COMPLETED - 2026-02-16):** OpenSpec change `archive-global-save-index-and-restore-routing` is fully implemented and validated. **Global Save Catalog:** `list_save_games_global()` scans all modules, deterministic timestamp sorting with tie-break, additive metadata fields (`source_module`, `memory_package_present`). **Cross-Module Restore Routing:** Target validator with path traversal rejection, module-aware entrypoint `restore_save_game_global()` that delegates to shared core pipeline, legacy `saveFolder`-only path preserved. **Web Integration:** `listSaves` action returns global entries, `restoreGame` accepts module-aware payload with fallback, load dialog shows source module + memory indicator `[M]`. **Files Modified:** `updates/save_game_manager.py`, `web/web_interface.py`, `web/templates/game_interface.html`. **All 12 completion items PASS.** Ready for PR2 zip portability work.

- **Journal Diary MVP Phase 1 (PLANNED - 2026-02-16):** Completed detailed MVP plan at `/plans/journal.md` and scaffolded OpenSpec change `journal-diary-mvp-phase1` with full artifacts. **Dual-Checkpoint Model:** Start Game refreshes draft diary entries when source history is stale; Save operations create confirmed canonical entries bound to `save_id`. **Journal UI:** Tabbed interface with preserved Quests behavior and new Diary tab showing draft card + confirmed timeline ordered by game-world time. **PDF Export:** "Download the story so far..." button generates fan-fiction style chronicle from confirmed entries only (draft excluded by design). **Failure Isolation:** Diary generation failures are non-blocking for both Start Game and Save flows. **Data Model:** Additive migration for `session_diary_entries`, `session_diary_state`, `story_so_far_cache` tables. **New Modules:** `core/memory/session_diary.py` (checkpoint logic), `core/memory/story_so_far_compiler.py` (PDF generation with caching). **Integration Points:** Save hook in `updates/save_game_manager.py`, Start Game hook in `web/web_interface.py`, Journal tabs in `web/templates/game_interface.html`, API endpoints `/api/journal/diary` and `/api/journal/story-so-far/pdf`. **Time Estimate:** 4-6 days. Status: Plan complete, ready for Kimi Builder execution.

- **Exit/Enter GUI Button Implementation Phase 1 (COMPLETED - 2026-02-17):**
  - **OpenSpec Change:** `exit-only-gui-shutdown` fully implemented, validated, and archived
  - **Phase 1 (Exit Only - COMPLETED):** Graceful server shutdown from GUI Exit button using exit code 91 contract
  - **Server Handler** (`web/web_interface.py:2717-2741`): Upgraded `handle_user_exit()` to emit `exit_acknowledged`, attempt graceful `socketio.stop()`, and force exit with code `91` (fail-closed on exceptions)
  - **Launcher Contract** (`run_web.py:119-122`): Added explicit `elif result.returncode == 91` branch to print "[SHUTDOWN] User initiated exit..." and break loop without restart
  - **GUI Flow** (`web/templates/game_interface.html:8501-8545`): Immediate "Shutting Down..." overlay on Exit confirm, input controls disabled (`user-input`, `send-button`), `user_exit` event emission
  - **Ack Handler** (`web/templates/game_interface.html:8459-8469`): `exit_acknowledged` listener updates overlay heading text, no restart/reload/connect logic
  - **Key Behaviors:**
    - Exit code `91` = intentional GUI shutdown (no restart)
    - Exit code `0` = restart path preserved for reset/restore flows
    - ASCII-only terminal output (`[Py]`, `[SHUTDOWN]`, `[ERROR]`)
    - All host edits marked with `# TABLETOP MODE:` comments
  - **Verification:**
    - Compile checks passed (`python3 -m py_compile web/web_interface.py run_web.py`)
    - Smoke test passed (GUI Exit -> code 91 -> shutdown message -> no restart)
    - Regression passed (reset/restore code `0` restart unchanged)
    - Ctrl+C fallback works cleanly
  - **Files Modified:** `web/web_interface.py`, `run_web.py`, `web/templates/game_interface.html`
  - **Status:** COMPLETED, validated, archived to `openspec/changes/archive/2026-02-17-exit-only-gui-shutdown/`
  - **Phase 2 (Full Exit/Enter - Future):** Deferred - requires persistent supervisor/watcher process

- **TTS Text Sync Browser-First Implementation (COMPLETED - 2026-02-15):** Implemented word-by-word text reveal synchronized with Browser TTS speech. **Features:** "Word Sync" toggle in DM Voice settings (browser-only, localStorage persisted), real boundary sync for Edge/MS TTS using `onboundary`, faux sync fallback (3x slowed) for browsers without boundaries, auto-scroll chat as text grows, manual replay audio-only. **Architecture:** Per-item `syncStrategy` in queue (`browser_boundary`, `none`, `estimated_timeline`), lazy-init reveal mode, explicit queue completion signaling. **Files:** `model_config.py`, `web/web_interface.py`, `web/templates/game_interface.html`, `web/static/js/tts_queue_manager.js`. **Verification:** Python compile PASS, Edge real sync works, Chrome faux fallback triggers correctly.

- **Combat State Init and Batching Hardening (C1-C5) (COMPLETED - 2026-02-15):** OpenSpec change `combat-state-init-and-batching-hardening` is implemented and validated (C1-C5 complete, M1-M5 smoke complete). Immediate focus is full gameplay test pass before archive.

- **Streaming UX Reversion to Foundation-Only (COMPLETED - 2026-02-15):** Runtime streaming execution is now rolled back to stable block-output narration while preserving future-facing foundations (flags OFF, backend stream helper, minimal host transport wiring). Current focus shifts to post-reversion test alignment and normal feature work.

- **Memory Backfill Source Selection + DB Portability Tools (COMPLETED - 2026-02-13):** Follow-up tooling change is complete. Backfill now supports explicit source gating (`--sources journal,conversation,combat`) and memory DB portability workflows (export package, validate package, import package with safe non-destructive defaults). This establishes practical archive/restore groundwork while keeping runtime gameplay paths unchanged.

- **Memory Foundation Retrieval + Backfill (COMPLETED - 2026-02-13):** Stage 1 memory foundation is implemented and validated. SQLite memory DB (`data/memory.db`) now supports deterministic timeline retrieval, context-pack retrieval, retirement/return retrieval, idempotent journal ingest, and backfill from current campaign history files. Read-only inspection endpoint is live (`GET /api/memory/entity/<entity_id>`), startup init is guarded/non-blocking, and backfill utility now supports `--dry-run` plus `--include-system` for archive-readiness workflows.

- **Tabletop Character Lifecycle and Creation Hardening (COMPLETED - 2026-02-12):** PC creation and onboarding stack is now unified around shared validation/audit gates, with readiness repair and NPC -> PC promotion lifecycle in place. Immediate focus shifts to play-session validation and retirement workflow planning (future change).

- **Initiative Phase 1 Two-Group Start Gate (COMPLETED - 2026-02-12):** Implemented deterministic combat startup with facilitator `/init <1-20>` gating. Encounter files now persist Phase 1 initiative state (`initiativeMode`, `initiativeRolls`, `initiativeWinner`, `roundStartsWith`, `awaitingPcGroupRoll`), combat loop blocks until valid `/init`, ties resolve to `dmGroup`, and DM-start rounds trigger immediate enemy batch without changing `/end` semantics. Added dynamic `=== INITIATIVE STATE ===` prompt section and aligned compressed sim/validation prompt wording to accept initiative-driven ENEMY_PHASE entry.

- **Web Interface TT Merge Refactor Completion (COMPLETED - 2026-02-12):** Completed increments 7-9 from `plans/web_interface_tt_merge_refactor.md`. Host socket handlers in `web/web_interface.py` are now thin wrappers for plot/storage extraction, WebOutputCapture debug filtering is deduped with shared helper markers, and live chat monitor wrapper lifecycle is extension-owned with idempotent setup and optional teardown. Commit: `094a938`.

- **Phase 0 Cleanup: Factory Routing Alignment (COMPLETED - 2026-02-12):** Applied OpenRouter factory routing cleanup to core files before GitHub push. Aligned `transition_validator.py`, `main.py` (module summary), and `combat_manager.py` to use `create_chat_client()` instead of direct `OpenAI()` initialization. Added fallback error handling with `get_chat_model_name()` and `handle_provider_error()`. Updated AGENTS.md to reflect migration status. Zero breaking changes; preparation for OpenRouter rollout post-tester release.

- **OpenSpec Initialization (COMPLETED - 2026-02-12):** Initialized OpenSpec spec-driven development framework with OpenCode support. Created project guardrails, split OpenRouter plan into two scaffolded changes (`openrouter-llm-router-facade`, `openrouter-llm-callsite-migration`), and established global OpenSpec workflow skill. Ready for implementation post-tester release.

- **EGO + RATIO Concept Plan (COMPLETED - 2026-02-12):** Revised cybernetic control architecture based on RSO (Relative State Observer) framework. Defined EGO (fast bounded controller) and RATIO (slow optimizer) with strict write tiers, decision relay (END/ADJUST/ESCALATE), and human DM as external training signal. Conceptual review complete; implementation deferred until after OpenRouter router work and tester build stabilization.

- **OpenRouter LLM Router Architecture (PLANNING - 2026-02-07):** Comprehensive architecture plan to centralize all 89 LLM calls through a single router interface. Capability-based model routing with Trinity Large Preview (creative/narration) and Gemini 2.5 Flash Lite (mechanics/JSON). Strategic decision to maintain dual-mode support (MULTIPLAYER_MODE toggle) for upstream merge potential while gradually hardening toward TT-only. Plan document created at `/plans/openrouter_llm_router_architecture.md` (700 lines). OpenSpec scaffolding complete; implementation pending tester release.

- **TTS Auto-Play Fix & Queue Management (COMPLETED - 2026-02-06):** Implemented comprehensive TTS management system with queue control, message filtering, and [skipTTS] tagging. Fixed cacophony on page reload, parallel playback, and mechanical message narration. Only DM narration speaks now; combat results and system commands display but don't break immersion.

- **Multi-PC Conversation Compression (COMPLETED - 2026-02-04): Created `utils/compression/multi_pc_conversation_compressor.py` - Multi-PC aware compressor extending `ParallelConversationCompressor`. Implements message tagging with `active_pc` field for per-PC storyline continuity. Smart compression keeps recent 8 exchanges raw while preserving cross-PC events (location transitions, combat, plot). Modified `main.py` (~30 lines) for message tagging and conditional compressor selection. Zero upstream impact for single-PC mode.
- **Multi-PC DM Note Enhancement (COMPLETED - 2026-02-04):** Created `utils/multi_pc_dm_note.py` - a plugin-style DM Note builder for tabletop mode that implements `[>]` Active PC marker, section-based organization, notable items filtering, and HP truth enforcement. Refactored main.py to use conditional routing with minimal upstream changes (~10 lines). Added `@MULTI_PC` directive to compressed prompt (~80 tokens) with rest rules and HP truth guidance.
- **Developer Diary System (COMPLETED - 2026-02-03): Created `memory-bank/ONCNotes.md` (OpenCode Notes) - an ongoing conversational diary capturing "in-the-moment" observations from combat chat log analysis. Updated `read-combat-log` skill to automatically append entries with narrative summaries, combat analysis, and OCNote threading.
- **OpenCode Skill Infrastructure (COMPLETED - 2026-02-03):** Created `sync-project-memory` global skill to ensure AGENTS.md and Cline memory-bank are always updated together. Also created `read-combat-log` local skill for analyzing combat logs with OCNote threading and diary writing.
- **Split-Party Combat Enhancement (COMPLETED - 2026-02-03):** Added `@SPLIT_PARTY_GUIDANCE` to combat prompt for handling party members in different locations during combat. Minimal 20-line addition (~150 tokens) guides LLM to maintain dual narrative awareness for 3-5 turns before graceful degradation. Testing showed 8-10 turn capability before context compression requires human narrative bridge.
- **Real-Time Chat Monitoring (COMPLETED - 2026-02-03):** Implemented SocketIO middleware in `web_interface.py` to capture live gameplay events for AI assistant visibility. Created `utils/chat_monitor.py` utility for filtering, exporting, and real-time log following. Enables debugging, TTS feeds, and live audience streaming without polling.
- **Multi-PC Combat Rebuild Plan (COMPLETED):** Fully rebuilt multi-PC combat prompt using single-player foundation as the base. All tasks completed including validation, examples, protocols, and integration.
- **Job 1: Automated Initiative Handoff (STABILIZED):** Implemented "User Roll -> Python Logic -> LLM Narrative" loop for combat start.
- **Job 2: Turn Queue Automation:** Python driving turn order automatically via deterministic tracker.
- **Job 3: Combat Commands:** `/att` and `/dmg` commands implemented with proper validation.

## Recent Changes
- **Portrait Create/Upload UX Locking (COMPLETED - 2026-02-19):**
  - **Objective:** Prevent duplicate portrait generation/upload requests and provide clear UX feedback during async operations
  - **Implementation:** Shared `portraitOperationInFlight` lock state with `syncInputAndPortraitUiState()` coordinator function, backend processing coordination via `backendIsProcessing`, early return guards in Upload/Create flows, CSS disabled states for portrait buttons, and re-apply on character sheet re-render
  - **Lock Behavior:** Input/send disabled during portrait operations; placeholder shows `Generating AI portrait for {name}...` or `Uploading portrait for {name}...`; portrait buttons disabled to prevent duplicate clicks
  - **Backend Coordination:** Portrait lock takes precedence over backend status for UX, input stays disabled until BOTH portrait operation AND backend processing complete
  - **Cleanup:** Removed redundant `createPortraitInFlight` variable
  - **File Modified:** `web/templates/game_interface.html`
  - **Verification:** All 16 implementation checks passed

- **PC Image Create and Allied NPC Auto-Generation (COMPLETED - 2026-02-17):
  - **OpenSpec Change:** `pc-image-create-and-allied-npc-autogen` fully implemented and verified (tasks 1.1-7.3)
  - **Appearance Fields:** Added optional schema fields (`age`, `height`, `weight`, `eyes`, `skin`, `hair`) with safe defaults and UI wiring
  - **Portrait Service:** New `core/toolkit/portrait_service.py` for prompt composition, image generation, and canonical file outputs
  - **Create Endpoint:** `POST /api/portrait/create` with safe error handling and cache-busted refresh
  - **Character Sheet UX:** Dual `Upload` + `Create` buttons with client-side create integration
  - **Warning Throttle:** Per-key throttle (`MISSING_MEDIA_WARNING_THROTTLE_ENABLED/SECONDS`) to suppress repeated miss spam
  - **Allied Auto-Gen:** New `web/extensions/missing_media_autogen.py` worker with dedupe, cooldown, and allied-only policy enforcement
  - **Policy Gating:** NPC miss enqueue hook with `is_allied_companion_check()` blocks non-allied NPCs and monsters
  - **Tests:** `scripts/test_pc_image_create_mvp.py` with 11 tests covering API, policy, throttle, and queue behavior
  - **Verification:** Compile PASS, tests PASS (11 OK), ASCII-only verified
  - **Files Created:** `core/toolkit/portrait_service.py`, `web/extensions/missing_media_autogen.py`, `scripts/test_pc_image_create_mvp.py`, `implementation_notes.md`
  - **Files Modified:** `schemas/char_schema.json`, `utils/character_creation_audit.py`, `web/routes/tabletop_party_routes.py`, `web/templates/partials/character_tabs.html`, `web/templates/game_interface.html`, `web/web_interface.py`, `model_config.py`

- **Exit/Enter GUI Button Implementation Phase 1 (COMPLETED - 2026-02-17):**
  - **OpenSpec Change:** `exit-only-gui-shutdown` fully implemented and archived
  - **Implementation:** Server handler emits `exit_acknowledged` then graceful stop + force exit with code `91`; launcher handles code `91` as intentional shutdown (no restart); GUI shows immediate "Shutting Down..." state with disabled inputs
  - **Verification:** Compile checks passed, smoke test confirmed server exits with code 91 and launcher prints "[SHUTDOWN] User initiated exit..." without restart, reset/restore restart regression passed, Ctrl+C fallback works
  - **Files Modified:** `web/web_interface.py`, `run_web.py`, `web/templates/game_interface.html`
  - **Archived:** `openspec/changes/archive/2026-02-17-exit-only-gui-shutdown/`

- **PR2 Archive Zip Portability and Memory Backup Parity (COMPLETED - 2026-02-16):**
  - **OpenSpec Change:** `archive-zip-portability-and-memory-backup-parity` fully implemented
  - **Section 1:** Archive helper scaffolding (`_generate_archive_zip`, `_get_archive_additional_paths`) with campaign-wide inclusion and memory package support
  - **Section 2:** Save flow integration with trigger wiring, archive payload, essential preservation
  - **Section 3:** Reset backup memory parity with artifact capture, absence reporting, layout verification
  - **Section 4:** All validation gates passed (compile, smoke, negative tests)
  - **Evidence:** Archive zip created at `modules/Keep_of_Doom/saved_games/archive_20260216_172143.zip` (26.5 MB)
  - **Files Modified:** `updates/save_game_manager.py`, `web/web_interface.py`, `utils/reset_campaign.py`
  - **Test Artifacts:** 12 test/report scripts created under `scripts/`

- **PR3 Root Archive Export Planning (COMPLETED - 2026-02-16):**
  - **OpenSpec Scaffolding:** Created `archive-root-export-and-zip-import-restore` with full artifact set
  - **Plan Location:** `archiving.md` (lines 125-244) and OpenSpec change directory
  - **Key Decisions:** Root export folder `archive_exports/`, deterministic naming, staged restore model
  - **Builder Ready:** Executor prompts staged for 6 execution phases

- **Journal Diary MVP Phase 1 Planning (COMPLETED - 2026-02-16):**
    - Created comprehensive MVP plan at `/plans/journal.md` establishing two-point diary model (Start Game draft + Save confirmed)
    - Scaffolded OpenSpec change `journal-diary-mvp-phase1` with complete artifact set:
      - `proposal.md` - Why, what changes, capabilities, impact, rollout risk
      - `design.md` - Dual-checkpoint state model, Start Game/Save integration decisions, confirmed-only PDF contract
      - `tasks.md` - 8 task groups (M1-M8) covering migration, diary service, integrations, routes, UI, tests
      - `executor_prompts.md` - 5 execution prompts for Kimi Builder with verification gates
      - Three capability specs:
        - `journal-diary-dual-checkpoint` - draft refresh, save confirmation, idempotency, failure isolation
        - `journal-diary-tabbed-ui` - Quests/Diary tabs, draft vs confirmed rendering, world-time ordering
        - `campaign-journal-story-pdf` - user-triggered export, confirmed-only source, cache reuse
    - **Key Architectural Decisions:**
      - Draft entries are "Current Session (Unsaved Draft)" visible in Diary but excluded from PDF
      - Confirmed entries are save-bound canon with `save_id` idempotency
      - World-time ordering via normalized `world_sort_key` from `party_tracker.json`
      - Third-person anonymous narration style
      - Failure isolation: diary generation never blocks Start Game or Save
    - **Data Model:** Additive migration for 3 tables with proper indexes
    - **New Modules:** `core/memory/session_diary.py`, `core/memory/story_so_far_compiler.py`
    - **Integration Points:** Save manager hook, Start Game socket handler, memory routes, Journal UI tabs
    - **Time Estimate:** 4-6 days for MVP Phase 1
    - **Status:** Plan complete and validated, ready for builder execution

- **Combat State Init and Batching Hardening (C1-C5) (COMPLETED - 2026-02-15):**
    - C1-C3 completed and committed: fail-closed combat entry, deterministic combat-only command guards outside active combat, and Phase 1 startup normalization with compatibility mirror sync.
    - C4 completed and committed: deterministic living non-PC enemy-phase actor filtering plus integrity roster expansion so legal non-active PC targets are accepted while PCs remain forbidden as DM-controlled actors.
    - C5 completed: added focused regression file `scripts/c5_regression_combat.py`, expanded coverage in `main.py` helper pathways, and checked M1-M5 smoke gates.
    - Verification:
      - `python3 -m py_compile main.py core/ai/action_handler.py core/managers/combat_manager.py core/managers/multi_pc_combat.py` -> PASS
      - `python3 scripts/test_multi_pc_combat.py` -> PASS (43 tests)
      - `python3 scripts/c5_regression_combat.py` -> PASS (9 tests)
      - `openspec validate combat-state-init-and-batching-hardening` -> valid
    - Commits:
      - `56ec86c` - `fix(combat): harden enemy-phase batching and PC target validation`
      - `48ac4aa` - `fix(combat): fail closed entry and add C5 regressions`
    - OpenSpec status: complete and validated; archive intentionally deferred until full gameplay test confirmation.

- **Streaming UX Reversion to Foundation-Only (COMPLETED - 2026-02-15):**
    - Selective rollback applied:
      - Reverted execution integrations in `main.py`, `core/managers/combat_manager.py`, `web/templates/game_interface.html`, and `web/static/js/tts_queue_manager.js`.
      - Preserved foundation in `web/extensions/streaming_events.py`, `model_config.py` (flags OFF), and minimal host wiring in `web/web_interface.py`.
    - Removed stream-suppression coupling from `WebOutputCapture` so canonical narration emit path remains baseline.
    - Revised `openspec/changes/streaming-ux-reversion/*` to encode file-level keep/revert decisions and validation gates, then archived to `openspec/changes/archive/2026-02-15-streaming-ux-reversion/`.
    - Synced main specs:
      - `openspec/specs/canonical-output-single-path/spec.md`
      - `openspec/specs/streaming-disabled-stable-output/spec.md`
      - `openspec/specs/tts-block-narration-only/spec.md`
    - Verification complete for non-interactive checks:
      - `python3 -m py_compile main.py core/managers/combat_manager.py web/web_interface.py web/extensions/streaming_events.py` -> PASS
      - `python3 scripts/test_multi_pc_combat.py` -> PASS (40 tests)
      - Dormant stream sanity check with flags OFF -> PASS (no stream events emitted)
    - Manual smoke completed (intro + one non-combat turn + one combat round): no stream events, no JSON token leakage.
    - `/opsx-verify` and `/opsx-archive` completed; synced new main specs for canonical-output single path and block-only narration behavior.

- **Memory Backfill Source Selection + DB Portability Tools (COMPLETED - 2026-02-13):**
    - Added `--sources` CSV parsing and strict validation in `scripts/backfill_memory_db.py`.
    - Added source-gating support in `backfill_memory_db_from_histories(...)` (journal/conversation/combat channel selection).
    - Added new portability module `core/memory/memory_portability.py` with export/validate/import contracts.
    - Export writes package DB copy + manifest metadata and integrity hash.
    - Import validates manifest/schema/hash and defaults to non-destructive behavior unless `--overwrite` is explicitly provided.
    - Import supports `--dry-run` for compatibility/integrity checks with zero writes.
    - Added tests in `scripts/test_memory_backfill_portability.py`; all checks passed.
    - OpenSpec change `memory-backfill-portability-tools` was completed and archived.

- **Memory Foundation Retrieval + Backfill (COMPLETED - 2026-02-13):**
    - Added `core/memory/memory_db.py` with idempotent migrations and additive readiness tables (`memory_policy_profiles`, `memory_policy_assignments`, `retrieval_audit_log`, `controller_change_log`, `memory_event_provenance`).
    - Added deterministic retrieval module `core/memory/memory_retrieval.py` with:
      - `get_entity_timeline(...)`
      - `get_context_memories(...)`
      - `get_retirement_return_memories(...)`
      - retrieval guardrails and optional best-effort audit logging.
    - Added ingestion/backfill module `core/memory/memory_ingest.py` with:
      - `ingest_journal_entry(...)` (source/checksum dedupe)
      - `ingest_journal_file(...)` (malformed-entry tolerant)
      - `backfill_memory_db_from_histories(...)` (journal + narrative history + combat history).
    - Added route `web/routes/memory_routes.py` and route registration/startup DB init hook in `web/web_interface.py`.
    - Added CLI utility `scripts/backfill_memory_db.py` with `--dry-run` and `--include-system` flags.
    - Backfill metrics:
      - Default: journal=40, conversation=48, combat=23, events=111, links=478
      - Include-system dry-run: conversation=65, combat=34, events=139, links=534
    - Validation:
      - `python3 -m py_compile core/memory/memory_db.py core/memory/memory_retrieval.py core/memory/memory_ingest.py core/memory/__init__.py web/routes/memory_routes.py` -> PASS
      - `python3 scripts/test_memory_retrieval_plan.py` -> PASS
      - `.venv/bin/python scripts/test_memory_foundation.py` -> PASS

- **NPC -> PC Role Lifecycle Promotion (COMPLETED - 2026-02-12):**
    - Add Existing now supports `players`, `npc_companions`, and `all` source modes with explicit `Promote` action for NPC companions.
    - Added promotion endpoints in `web/routes/tabletop_party_routes.py`:
      - `POST /api/party/promotion/preview` (no writes)
      - `POST /api/party/promotion/apply` (confirm required)
    - Promotion is in-place (same character file), normalizes role markers to player, removes from `partyNPCs`, adds to `partyMembers`, and preserves `active_character`.
    - Added identity/lifecycle metadata support:
      - `character_id` (stable identity)
      - `_tabletop_role_history` (append-only transition events)
    - Added schema support for `character_id` and `_tabletop_role_history` in `schemas/char_schema.json`.

- **Saving Throws Consistency Fix (COMPLETED - 2026-02-12):**
    - Added shared normalization/fallback helper `utils/saving_throw_utils.py`.
    - Character sheet now always renders six saves and no longer hides panel when `savingThrows` is empty.
    - PDF export now uses same normalized/fallback proficiency source as GUI, preventing case-mismatch drift.
    - Added `scripts/backfill_saving_throws.py` for deterministic one-time data cleanup.

- **Readiness Repair Workflow (COMPLETED - 2026-02-12):**
    - Added `Repair` button in sheet readiness warning block.
    - Added preview/confirm APIs with cooldown, whitelist-only narrative patching, mechanical-field guard, and post-patch audit gate.
    - Successfully repaired incomplete characters (`tester`, `xerxes`) and confirmed warning clearance.

- **PC Creation Unification (COMPLETED - 2026-02-12):**
    - Added shared creation audit module (`utils/character_creation_audit.py`) used by startup, DM interview finalization, and Roll Your Own/manual create.
    - Startup now supports iterative multi-PC creation loop.
    - Add Existing candidate endpoint now filters out current party members and dedupes scan results.
    - End-to-end API smoke suite passed (creation validation, repair, promotion, PDF compatibility).

- **Initiative Phase 1 Two-Group Start Gate (COMPLETED - 2026-02-12):**
    - `core/ai/action_handler.py`: Added encounter startup initialization for Phase 1 initiative state with DM pre-roll (`random.randint(1, 20)`) and compatibility mirror in `party_tracker.json`.
    - `core/managers/combat_manager.py`: Added hard gate for `awaitingPcGroupRoll`; only `/init <1-20>` accepted before combat progression.
    - On valid `/init`, stores `pcGroup` roll, computes winner, sets `roundStartsWith`, clears waiting flag, and starts PC or enemy phase accordingly.
    - Tie behavior enforced: `dmGroup` wins ties.
    - Added `=== INITIATIVE STATE ===` dynamic block to combat prompt context and deterministic round opener logic based on persisted `roundStartsWith`.
    - Prompt updates:
      - `prompts/combat/combat_sim_prompt_multipc_compressed.txt`: ENEMY_PHASE can begin via `/end` or initiative-driven DM start.
      - `prompts/combat/combat_validation_prompt_multipc_compressed.txt`: Validation accepts initiative-driven ENEMY_PHASE start and routing.
    - Validation:
      - `python3 -m py_compile core/ai/action_handler.py core/managers/combat_manager.py` -> PASS
      - `python3 scripts/test_multi_pc_combat.py` -> PASS (40 tests, 0 failures, 0 errors)

- **Web Interface TT Merge Refactor Completion (COMPLETED - 2026-02-12):**
    - **Scope:** Increment 7 (plot/storage socket extraction), Increment 8 (WebOutputCapture filter dedupe), Increment 9 (emit wrapper lifecycle hardening)
    - **Architecture:** Preserved merge-safe host hooks; moved TABLETOP MODE implementation details into extension/route modules
    - **Validation:** `python3 -m py_compile` passed for changed files; grep checks confirmed thin wrappers and extension-owned wrapper lifecycle
    - **Commit:** `094a938` - `refactor(web): reduce TT divergence via extension hooks`
    - **Files:** `web/web_interface.py`, `web/output_markers.py`, `web/extensions/__init__.py`, `web/extensions/live_chat_monitor.py`, `web/extensions/tabletop_socket_handlers.py`, `web/routes/__init__.py`, `web/routes/browser_settings_routes.py`, `web/routes/character_sheet_routes.py`, `web/routes/tabletop_party_routes.py`

- **Phase 0 Cleanup: Factory Routing Alignment (COMPLETED - 2026-02-12):**
    - **Objective:** Align core files to OpenRouter factory routing baseline before GitHub push
    - **Files Modified:**
      - `core/ai/transition_validator.py` - Factory client + provider model selection + fallback handling
      - `main.py` - `generate_module_summary()` uses factory routing with fallback
      - `core/managers/combat_manager.py` - Global client uses factory
      - `AGENTS.md` - Updated migration status, removed duplicate entries
    - **Technical Changes:**
      - Removed `from openai import OpenAI` and direct `OPENAI_API_KEY` usage
      - Added `from utils.ai_client_factory import create_chat_client, get_chat_model_name, handle_provider_error`
      - Implemented fallback pattern: primary call → error classification → fallback retry
      - Used `actual_model_used` variable for accurate telemetry logging
      - Avoided `client` variable shadowing in local scopes (`summary_client`, `fallback_client`)
    - **Risk Mitigation:**
      - Zero prompt/content changes (temperature, system messages preserved)
      - All existing fallback behavior maintained (non-AI summary on failure in main.py)
      - No model selection logic changes
      - Syntax verification: `python3 -m py_compile` passes for all 3 Python files
    - **Lines Changed:** +72/-41 across 4 files
    - **Status:** Ready for smoke testing (startup → transition validation → combat entry)

- **OpenSpec Initialization for Project Management (COMPLETED - 2026-02-12):**
    - **Objective:** Initialize OpenSpec spec-driven development framework for structured planning
    - **Initialization:** `openspec init --tools opencode` generated local skills in `.opencode/command/` and `.opencode/skills/openspec-*/`
    - **Project Guardrails:** Created `openspec/config.yaml` with rules aligned to AGENTS.md conventions (merge-safe, SP/MP compatibility, atomic JSON, ASCII-only)
    - **OpenRouter Planning:** Split architecture plan into two changes:
      - `openrouter-llm-router-facade`: Router facade + model profile infrastructure
      - `openrouter-llm-callsite-migration`: Tiered migration of 89 LLM callsites
    - **Fast-Forward:** All planning artifacts created (proposal, design, specs, tasks) for both changes
    - **Global Skill:** Created `~/.config/opencode/skills/openspec-workflow/SKILL.md` for consistent OPSX workflows across projects
    - **Result:** Clean scaffolding for OpenRouter phases; structured planning capability; zero codebase impact
    - **Files:** `openspec/config.yaml`, `openspec/changes/*` (9 artifacts), global skill

- **EGO + RATIO Concept Plan Revision (COMPLETED - 2026-02-12):**
    - **Objective:** Tighten cybernetic control architecture based on RSO (Relative State Observer) framework
    - **Framework:** EGO (fast reflex controller) + RATIO (slow optimizer); Python=P2 ground truth, LLM=P1 narrative
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
    - **Objective:** UI enhancement for long prompts and detailed action descriptions in chat interface
    - **CSS Changes:** `.input-container` added `align-items: flex-end` (Send button at bottom); `.input-field` added `resize: none`, `overflow: hidden`, `min/max-height` (5-line cap)
    - **HTML Changes:** `<input type="text">` → `<textarea rows="1">` with `onkeydown` and `oninput` handlers
    - **JavaScript Functions:**
      - `handleKeyDown(event)`: Enter sends (no Shift), Shift+Enter inserts newline
      - `autoResizeTextarea(textarea)`: Grows to content, caps at 150px
      - `resetTextareaHeight()`: Returns to 40px after send
      - Paste event listener in `DOMContentLoaded` for immediate resize on paste
    - **Layout Architecture:** Leverages existing flexbox - header bars fixed, only chat transcript shrinks upward
    - **Result:** ~50-line change, zero breaking changes, works for SP and MP modes
    - **File:** `web/templates/game_interface.html`

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

- **Combat API Timeout Protection & StatusTimer Infrastructure (COMPLETED - 2026-02-09):**
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

- **MultiPCCombatManager Bug Fixes & Code Quality Improvements (COMPLETED - 2026-02-09):**
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
    - **Strategic Architecture Decision:** Path A - Gradual Hardening with MULTIPLAYER_MODE toggle maintained for upstream merge potential (TTS feature valuable)
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
    - **Root Cause:** `multi_pc_combat.py:initialize_from_party()` reading from non-existent `party_data["characters"][name]["hp"]` structure (defaults to 10)
    - **Solution:** Load character data directly from character JSON files using ModulePathManager
    - **File:** `core/managers/multi_pc_combat.py` (lines 276-305)
    
    **Code Quality Improvements:**
    1. **Removed Duplicate json Imports:** Eliminated 2 inline `import json` statements (lines 299, 1111), consolidated to module-level import only (line 29)
    2. **Fixed Silent Exception Swallowing:** Added `debug()` logging for monster AC lookup failures including creature name and exception details (line 381-383)
    3. **Consolidated Defensive Imports:** Removed 4 separate try/except ImportError blocks for internal modules; internal imports now fail fast with clear errors. Consolidated `multi_pc_dm_note.py` to use centralized `should_use_abstraction_layer()` from `pc_manager.py`
    4. **Refactored Large Method:** Split 130-line `format_initiative_tracker()` into 4 focused helper methods with single responsibilities:
       - `_get_combatant_marker()`: Determines state markers ([>], [X], [D], [ ])
       - `_build_initiative_lines()`: Constructs initiative and tracker line lists
