## Current Work Focus
- **PR1 Archive Global Save Index and Restore Routing (COMPLETED - 2026-02-16):** OpenSpec change `archive-global-save-index-and-restore-routing` is fully implemented and validated. **Global Save Catalog:** `list_save_games_global()` scans all modules, deterministic timestamp sorting with tie-break, additive metadata fields (`source_module`, `memory_package_present`). **Cross-Module Restore Routing:** Target validator with path traversal rejection, module-aware entrypoint `restore_save_game_global()` that delegates to shared core pipeline, legacy `saveFolder`-only path preserved. **Web Integration:** `listSaves` action returns global entries, `restoreGame` accepts module-aware payload with fallback, load dialog shows source module + memory indicator `[M]`. **Files Modified:** `updates/save_game_manager.py`, `web/web_interface.py`, `web/templates/game_interface.html`. **All 12 completion items PASS.** Ready for PR2 zip portability work.

- **Journal Diary MVP Phase 1 (PLANNING - 2026-02-16):** Completed detailed MVP plan at `/plans/journal.md` and scaffolded OpenSpec change `journal-diary-mvp-phase1` with full artifacts. **Dual-Checkpoint Model:** Start Game refreshes draft diary entries when source history is stale; Save operations create confirmed canonical entries bound to `save_id`. **Journal UI:** Tabbed interface with preserved Quests behavior and new Diary tab showing draft card + confirmed timeline ordered by game-world time. **PDF Export:** "Download the story so far..." button generates fan-fiction style chronicle from confirmed entries only (draft excluded by design). **Failure Isolation:** Diary generation failures are non-blocking for both Start Game and Save flows. **Data Model:** Additive migration for `session_diary_entries`, `session_diary_state`, `story_so_far_cache` tables. **New Modules:** `core/memory/session_diary.py` (checkpoint logic), `core/memory/story_so_far_compiler.py` (PDF generation with caching). **Integration Points:** Save hook in `updates/save_game_manager.py`, Start Game hook in `web/web_interface.py`, Journal tabs in `web/templates/game_interface.html`, API endpoints `/api/journal/diary` and `/api/journal/story-so-far/pdf`. **Time Estimate:** 4-6 days. Status: Plan complete, ready for Kimi Builder execution.

- **Exit/Enter GUI Button Plan (PLANNING - 2026-02-15):** Created detailed implementation plan at `/plans/exit-enter.md` for adding Exit/Enter functionality to GUI. **Phase 1 (Exit Only):** Gracefully stop all Python processes from browser button without Ctrl+C. Uses exit code 91 to signal intentional shutdown to launcher. User must manually restart with `python run_web.py`. **Phase 2 (Future):** Full Exit/Enter toggle requires persistent supervisor/watcher process - deferred due to complexity concerns. No watcher processes will be implemented in Phase 1.

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

## Recent Changes
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

- **NPC -> PC Role Lifecycle (COMPLETED - 2026-02-12):**
    - Add Existing now supports `players`, `npc_companions`, and `all` source modes with explicit `Promote` action for NPC companions.
    - Added promotion endpoints in `web/routes/tabletop_party_routes.py`:
      - `POST /api/party/promotion/preview` (no writes)
      - `POST /api/party/promotion/apply` (confirm required)
    - Promotion is in-place (same character file), normalizes role markers to player, removes from `partyNPCs`, adds to `partyMembers`, and preserves `active_character`.
    - Added identity/lifecycle metadata support:
      - `character_id` (stable identity)
      - `_tabletop_role_history` (append-only transition events)
    - Added schema support in `schemas/char_schema.json` so lifecycle metadata persists without validation failures.

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
    - **Validation:** `python3 -m py_compile` passed for changed files; grep checks confirmed thin wrappers and extension ownership
    - **Commit:** `094a938` - `refactor(web): reduce TT divergence via extension hooks`
    - **Files:** `web/web_interface.py`, `web/output_markers.py`, `web/extensions/__init__.py`, `web/extensions/live_chat_monitor.py`, `web/extensions/tabletop_socket_handlers.py`, `web/routes/__init__.py`, `web/routes/browser_settings_routes.py`, `web/routes/character_sheet_routes.py`, `web/routes/tabletop_party_routes.py`

- **OpenRouter LLM Router Architecture Plan (COMPLETED - 2026-02-07):**
    - **Objective:** Centralize 89 LLM call sites across 39 files through single router interface
    - **Capability-Based Routing:** Trinity Large Preview (free) for creative/narration, Gemini 2.5 Flash Lite for mechanics/JSON
    - **Fallback Strategy:** GPT-4.1 universal fallback with user notification to update config when models change
    - **Strategic Decision:** Path A - Gradual Hardening with MULTIPLAYER_MODE toggle maintained for upstream merge potential (TTS feature valuable)
    - **Dual-Mode Support:** MULTIPLAYER_MODE=False (OpenAI hardwired, upstream compatible), MULTIPLAYER_MODE=True (OpenRouter with capability routing)
    - **Error Handling:** Hard stop on quota/billing errors - game cannot continue without LLM
    - **Cost Tracking:** Total tokens + USD cost, by model, capability, and role
    - **Implementation Timeline:** 2-3 weeks (10-14 days) - Phase 1: Router Foundation, Phase 2: Full Migration, Phase 3: Cleanup
    - **Plan Location:** `/plans/openrouter_llm_router_architecture.md` (700 lines comprehensive plan)
    - **Extraction Strategy:** Plugin architecture enables future clean TT fork extraction when upstream declared legacy

- **TTS Auto-Play Fix & Queue Management (COMPLETED - 2026-02-06):**
    - **Queue Manager Plugin:** `web/static/js/tts_queue_manager.js` - Sequential playback, max 3 queue, skip when playing, cancelAll() emergency stop
    - **Cached Message Protection:** Added `skipAutoplay` parameter to `addMessage()` function, prevents TTS on page reload/reconnect
    - **Player Message Cleanup:** Removed TTS button from player input messages (DM-only feature)
    - **System Content Filter:** Filters [SYSTEM], ---, /command lines from TTS auto-play
    - **[skipTTS] Tag System:**
      - **Generation:** `core/managers/multi_pc_combat.py` - 6 combat outputs marked; `main.py` - /help command marked
      - **Processing:** `web/web_interface.py` - Tag detection/stripping in 3 locations (write() x2, flush())
      - **Frontend:** `web/templates/game_interface.html` - Checks message.skipTTS flag before auto-play
    - **Behavior:** DM narration → TTS plays; Combat results/system commands → No TTS; Cached messages → No auto-TTS
    - **Result:** No cacophony, immersive storytelling only, smooth queue flow

- **OpenRouter Integration - Phase 1 Complete (COMPLETED - 2026-02-06):** Multi-provider AI support with transparent fallback. Factory pattern implemented across 9 files. Ready for testing with Kimi K2.5 or GPT-4.1.

- **Tabletop Mode Debug Monitor Skill v2.3.0 (COMPLETED - 2026-02-06):** Implemented complete three-phase debug workflow (start → check → stop). **Phase 1:** `start debug` configures and enables debugging with restart prompt. **Phase 2:** `check debug` uses enhanced error reporter with timestamped listings, error classification, file location extraction, and actionable fix suggestions. **Phase 3:** `stop debug` reverts configs to debug=false and deletes all debug log files for clean state. Created `scripts/debug_error_reporter.py` for advanced error analysis with chronological reporting and smart grouping. KISS principle: manual control only, no auto-disable. Commands: "start debug", "check debug", "stop debug", "tabletop debug status". Script flags: `--enable`, `--stop`, `--status`, `--warnings`, `--verbose`.

- **State Synchronization Fix (COMPLETED - 2026-02-05):** Fixed LLM state hallucination bug where rested PCs were narrated as "unconscious" despite full HP. Root cause: DM Note formatting didn't display `condition_affected` array, so LLM relied on conversation history instead of mechanical truth. Added conditions display to `format_pc_full_stats()` and `format_pc_condensed()` in `utils/multi_pc_dm_note.py`. Created @STATE_SYNC directive in system prompt establishing "Python enforces reality; you interpret it" hierarchy. This is the philosophical resolution of mechanics vs narrative freedom debate.

- **Chat Log Skill Rename (COMPLETED - 2026-02-05):** Renamed `read-combat-log` to `read-chat-log` to reflect that the log contains both combat and non-combat entries. Updated trigger phrases from "read combat log" to "read chat log"/"update chat log". Implemented "fading memory" OCNote architecture: ongoing summary persists across reads, latest 5 OCNotes shown individually, threshold at 8 total. Optimized for token efficiency with hard limits on all output sections.

- **5e Rest Automation (COMPLETED - 2026-02-05):** Implemented automatic resource restoration in core/ai/action_handler.py with _process_character_rest() function. Fixed prompt contract by adding "rest" to @ACTIONS, @PARAMS, @EXAMPLES. Applied 5e-compliant logic: short rest refreshes shortRest features + Warlock pact magic (no auto-heal), long rest restores HP to max, all spell slots, all features, and removes exhaustion. Fixed character path resolution, exhaustion detection (list[string] schema), parameter validation, and file safety checks. Created test suite at scripts/test_rest_action.py. Zero upstream impact; works for both single-PC and multi-PC modes.

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
- **Phase 0 Cleanup: Factory Routing Alignment (COMPLETED - 2026-02-12):**
    - **Objective:** Align core files to OpenRouter factory routing baseline before GitHub push
    - **Files Modified:**
      - `core/ai/transition_validator.py` - Factory client + provider model selection + fallback handling
      - `main.py` - `generate_module_summary()` uses factory routing with fallback
      - `core/managers/combat_manager.py` - Global client uses factory
      - `AGENTS.md` - Updated migration status, removed duplicate entries
    - **Technical Changes:**
      - Removed `from openai import OpenAI` and direct client initialization
      - Added `create_chat_client()`, `get_chat_model_name()`, `handle_provider_error()` imports
      - Implemented fallback pattern: primary call → error classification → fallback retry
      - Used `actual_model_used` variable for accurate telemetry logging
      - Avoided `client` variable shadowing in local scopes (Fix 4 prevention)
    - **Risk Mitigation:**
      - Zero prompt/content changes
      - All temperature/prompt logic preserved
      - Existing fallback summary behavior maintained
      - Syntax verified: `python3 -m py_compile` passes all files
    - **Lines Changed:** +72/-41 across 4 files
    - **Status:** Ready for smoke testing (startup, transition validation, combat entry)

- **OpenSpec Initialization for Project Management (COMPLETED - 2026-02-12):
    - **Objective:** Initialize spec-driven development framework for structured OpenRouter and EGO planning
    - **Initialization:** `openspec init --tools opencode` generated local skills in `.opencode/command/` and `.opencode/skills/openspec-*/`
    - **Project Guardrails:** Created `openspec/config.yaml` with rules aligned to AGENTS.md conventions (merge-safe, SP/MP compatibility, atomic JSON, ASCII-only)
    - **OpenRouter Planning:** Split architecture plan into two changes:
      - `openrouter-llm-router-facade`: Router facade + model profile infrastructure
      - `openrouter-llm-callsite-migration`: Tiered migration of 89 LLM callsites
    - **Fast-Forward:** All planning artifacts created (proposal, design, specs, tasks) for both changes
    - **Global Skill:** Created `~/.config/opencode/skills/openspec-workflow/SKILL.md` for consistent OPSX workflows across projects
    - **Key Commands:** `/opsx explore`, `/opsx new`, `/opsx continue`, `/opsx ff`, `/opsx apply`, `/opsx verify`, `/opsx archive`
    - **Result:** Clean scaffolding ready for post-tester implementation; zero current codebase impact
    - **Files:** `openspec/config.yaml`, `openspec/changes/*` (9 artifacts), global skill

- **EGO + RATIO Concept Plan Revision (COMPLETED - 2026-02-12):**
    - **Framework:** RSO (Relative State Observer) cybernetic control theory mapping
      - EGO = State Observer reflex controller (System 1, fast, bounded)
      - RATIO = Neocortical learning layer (System 2, slow, reflective)
      - Python/P2 = Mechanical Reality (ground truth)
      - LLM/P1 = Narrative Reality (interpretation)
    - **Boundary Contract:** Python state authoritative; Tier 3 immutable; all edits logged/reversible
    - **Decision Relay:** END (drift) → log; ADJUST (distortion) → Tier 1a tweak; ESCALATE (hallucination) → correction + queue
    - **Human DM:** Exogenous control signal enabling implicit RLHF; "silence = approval" heuristic
    - **Write Tiers:** 1a (knobs), 1b (prose), 2 (behavioral), 3 (immutable contracts)
    - **Future OpenSpec Changes:** `ego-foundation-passive-observer`, `ego-bounded-adjustments`, `ratio-reviewed-evolution`
    - **Prerequisites:** OpenRouter router stable; baseline metrics; cost/time budgets defined
    - **Status:** Conceptual review complete; ready for implementation after tester release
    - **Files:** `plans/EGO.md` (353 lines), `plans/EGO-Comments_on_Cybernetic_Potentials.md`

- **Hallucinated Monster Defense - Three-Layer Safety System (COMPLETED - 2026-02-10):**
    - **Objective:** Prevent data integrity issues when narrator LLM hallucinates creature names that get auto-generated as real stat blocks
    - **Layer 1 (Bestiary-Only Gate):** Added TABLETOP MODE guard in `core/generators/combat_builder.py:147-161` - refuses auto-creation in multiplayer mode, preserves upstream SP behavior
    - **Layer 2 (Enemy Count Validation):** Added validation in `core/ai/action_handler.py:798-838` - checks encounter has ≥1 enemy before combat starts, deletes invalid files, returns gracefully without combat
    - **Layer 3 (Prompt Constraint):** Added `monsterSource` rule to @COMBAT directive in `prompts/system_prompt_compressed.txt:59` - guides LLM toward valid bestiary creatures, ~35 tokens
    - **Defense-in-Depth:** Independent layers provide multiple failure points; Layer 3 reduces frequency, Layers 1-2 provide deterministic safety net
    - **Backward Compatibility:** SP mode preserves auto-creation; TT mode protected; zero breaking changes
    - **Files Modified:** `core/generators/combat_builder.py` (+14 lines), `core/ai/action_handler.py` (+41 lines), `prompts/system_prompt_compressed.txt` (+1 line)

- **Expandable Chat Input Textarea (COMPLETED - 2026-02-09):**
    - **Objective:** UI enhancement for long prompts and detailed action descriptions in chat interface
    - **CSS Changes:** `.input-container` added `align-items: flex-end` (Send button at bottom); `.input-field` added `resize: none`, `overflow: hidden`, `min-height: 40px`, `max-height: 150px` (5-line cap)
    - **HTML Changes:** `<input type="text">` → `<textarea rows="1">` with `onkeydown` and `oninput` handlers
    - **JavaScript Functions:**
      - `handleKeyDown(event)`: Enter sends (no Shift), Shift+Enter inserts newline
      - `autoResizeTextarea(textarea)`: Grows to content, caps at 150px
      - `resetTextareaHeight()`: Returns to 40px after send
      - Paste event listener in `DOMContentLoaded` for immediate resize on paste
    - **Layout Architecture:** Leverages existing flexbox - `.panel-header` (fixed), `.panel-content#game-output` (`flex: 1`, shrinks), `.input-container` (bottom, expands upward)
    - **Result:** Clean 50-line implementation, header bars stay fixed, chat shrinks naturally, zero breaking changes
    - **File:** `web/templates/game_interface.html` (~50 lines)

- **Combat Round Synchronization & Allied NPC Fix (COMPLETED - 2026-02-09):
    - **Problem:** Combat stuck at Round 2, AI refused to increment round; allied NPCs (Scout Kira, liri, Festivus, etc.) not attacking during enemy phase
    - **Root Cause A (Round):** `MultiPCCombatManager.current_round` defaulted to 1 on construction, never synced from encounter file's `combat_round: 2`. Prompt showed Round 1 to AI, AI processed Round 1, returned `combat_round: 2`, but check `2 > 2` failed, skipping `start_new_round()`
    - **Root Cause B (NPCs):** `get_remaining_enemies_for_round()` only returned `CombatantType.ENEMY`, excluding allied `CombatantType.NPC` from batch processing
    - **Solution:**
      - **Round Sync (multi_pc_combat.py:1148):** Added `sync_round_from_encounter()` method to sync manager state from encounter file on combat start/resume
      - **Sync Call (combat_manager.py:2007-2011):** Call sync method after `initialize_turn_queue()` at single convergence point for all combat entry paths
      - **NPC Inclusion (multi_pc_combat.py:537):** Changed filter from `== CombatantType.ENEMY` to `in (CombatantType.ENEMY, CombatantType.NPC)`
      - **Docstring Updates (multi_pc_combat.py:524, 1109):** Updated to reflect "enemies and allied NPCs"
    - **Reverted Broken Fix:** Removed `clean_old_dm_notes()` modification that was deleting system messages before AI saw them; was causing `/end` command to fail entirely
    - **Result:** Combat now advances rounds correctly, allied NPCs participate in enemy phase batch, round state stays synchronized with encounter file
    - **Files:** `core/managers/multi_pc_combat.py` (+20 lines method, +1 line filter change), `core/managers/combat_manager.py` (+5 lines sync call)

- **Combat Validation & Character Update Fixes (COMPLETED - 2026-02-09):**
    - **Fix 1 (Validation Prompt):** Clarified consolidation rules to prevent AI validator from rejecting valid PC damage actions during enemy batch phase
      - `@ACTION_TYPES.consolidation_rule` (line 143): "enemy STATE changes" vs "ALL enemy changes"
      - `@ROUTING_RULES.batch_enemy_phase` (lines 152-155): Explicit guidance that multiple `updateCharacterInfo` is VALID during batch
      - `@CRITICAL_VIOLATIONS.multiple_update_encounter` (line 178): Added note that multiple `updateCharacterInfo` is not a violation
      - `@OUTPUT_EXAMPLE.batch_enemy_pc_damage` (lines 311-319): Positive example showing valid routing pattern
    - **Fix 2 (Simulation Prompt):** Fixed ambiguous plan_note at line 97 to remove "hits PC -> updateEncounter" confusion, now uses "attacks PC -> updateEncounter (housekeeping only)" format
    - **Fix 3 (Uncompressed Validation Prompt):** Mirrored compressed prompt changes to human-readable version for review
    - **Fix 4 (UnboundLocalError):** Added `global client` declaration to `update_character_info()` function (line 1259) to resolve Python scoping bug introduced during OpenRouter migration
      - **Bug:** Assignment `client = create_chat_client(use_fallback=True)` at line 2110 caused Python to treat `client` as local for entire function, making line 1643 fail with `UnboundLocalError`
      - **Impact:** All `updateCharacterInfo` actions were silently failing during combat since OpenRouter migration
    - **Result:** Validation now accepts correct action routing, character updates work during combat, batch enemy phase processes correctly
    - **Files:** `prompts/combat/combat_validation_prompt_multipc_compressed.txt` (+4 edits), `prompts/combat/combat_sim_prompt_multipc_compressed.txt` (+1 edit), `prompts/combat/combat_validation_prompt_multipc.txt` (+2 edits), `updates/update_character_info.py` (+1 line `global client`)

- **Combat API Timeout Protection & StatusTimer Infrastructure (COMPLETED - 2026-02-09):**
    - **Objective:** Prevent indefinite hangs during combat API calls (validation hung at 10:57:42 on 2026-02-09)
    - **StatusTimer Class:** Created in `core/managers/status_manager.py` (lines 143-206) - Context manager for escalating status messages
      - Escalation schedule: 10s ("Still processing...") → 30s ("Response taking longer than usual...") → 60s ("Waiting for AI provider ({elapsed}s)...")
      - Daemon thread with threading.Event for 1-second responsive shutdown; auto-cancels on context exit
      - DEFAULT_SCHEDULE class constant for per-call-site customization; ready for OpenRouter `llm_router.py` integration
    - **Timeout Constants (model_config.py:50-51):**
      - `COMBAT_API_TIMEOUT_SECONDS = 120` - Per-call timeout (generous for 46K+ char prompts)
      - `COMBAT_CONNECT_TIMEOUT_SECONDS = 10` - TCP connection timeout
    - **Timeout Applied to 3 Critical API Calls (combat_manager.py):**
      - Line 852: `validate_combat_response()` - Validation LLM (highest hang risk)
      - Line 2576: Initial scene generation - Combat start narration
      - Line 3619: Main combat loop GPT-4.1 - Active code path (likely culprit for 2026-02-09 hang)
    - **Implementation Approach:**
      - Surgical single-line additions with `timeout=COMBAT_API_TIMEOUT_SECONDS` kwarg
      - All marked with `# TABLETOP MODE:` comments for merge tracking
      - Zero code restructuring; timeout exceptions caught by existing retry loops
      - 6 secondary API calls remain unprotected (dialogue summary, log analyzer, GPT-5 paths, re-engage) - acceptable risk
    - **StatusTimer Wiring (Deferred):** Context manager exists but not yet applied to call sites; escalating UX feedback for future iteration
    - **Testing:** All files compile; StatusTimer functional test passed; timeout infrastructure ready
    - **Files:** `model_config.py` (+2), `core/managers/status_manager.py` (+66), `core/managers/combat_manager.py` (+3 timeout additions)

- **MultiPCCombatManager Bug Fixes & Code Quality Improvements (COMPLETED - 2026-02-09):**
    - **Objective:** Fixed 10 synchronization bugs and 5 code quality improvements to `core/managers/multi_pc_combat.py`
    - **Facade Pattern Fixes:** Added `current_round` property getter/setter (Bug 1), fixed orphan attribute writes (Bug 2), refactored 2 methods to delegate (Bugs 3-4)
    - **Code Cleanup:** Removed 3 dead methods from TurnQueueManager (Bug 8, -74 lines), removed dead CombatStateManager method (Bug 5, -28 lines), removed dead `first_round` field (Bug 10, -2 lines)
    - **Method Consolidation:** Converted 4 facade methods from reimplementing to delegating (Bug 6): `get_incapacitated_pcs`, `get_all_active_pcs`, `set_current_pc`, `update_pc_hp`
    - **Windows Compatibility:** Replaced Unicode icons (⏳✓💀☠️😴) with ASCII bracket tags ([WAIT], [DONE], [DOWN], [DEAD], [STBL]) in initiative tracker (Bug 7)
    - **Critical Bug Fix:** Fixed `TurnQueueManager.advance_turn()` to return tuple instead of mutating state; moved round rollover to facade preventing double-increment (Bug 9)
    - **Test Fix:** Updated `scripts/test_multi_pc_combat.py:258` to unpack tuple return value
    - **Quality Improvements:** Removed Unicode emoji (⛔⚠️ → [BLOCKED], [WARNING]), removed stale comments, removed unused imports (Union, re)
    - **Architecture Principle:** Facade methods delegate OR coordinate; never reimplement sub-manager logic
    - **State Sync Bugs Resolved:** Shadow attributes, orphan writes, double-increment all fixed
    - **Verification:** Zero breaking changes, 10/10 bugs from audit fixed, test suite compatible
    - **Pre-existing:** 3 LSP type errors remain (unrelated to changes)
    - **Files:** `core/managers/multi_pc_combat.py` (~200 lines changed), `scripts/test_multi_pc_combat.py` (1 line)

- **OpenRouter Integration - Phase 1 Core Chat/LLM (COMPLETED - 2026-02-06):**
    - **Factory Pattern:** Created `utils/ai_client_factory.py` with `create_chat_client()`, `get_chat_model_name()`, `handle_provider_error()`, `get_fallback_notification()`
    - **Configuration:** Added `LLM_PROVIDER`, `OPENROUTER_CHAT_MODEL`, `ENABLE_PROVIDER_FALLBACK` to `model_config.py` (lines 68-101)
    - **Files Updated (9 total):** `utils/ai_client_factory.py` (NEW), `updates/update_character_info.py`, `utils/startup_wizard.py`, `core/ai/transition_validator.py`, `core/ai/combat_compression_engine.py`, `core/ai/incremental_compression.py`, `core/ai/cumulative_summary.py`, `core/ai/adv_summary.py`, `web/web_interface.py`
    - **Fallback Behavior:** Transparent auto-retry on rate limits/timeouts/503s, switches to OpenAI automatically
    - **Validation:** All 9 files compile successfully with `python -m py_compile`
    - **Backward Compatibility:** Zero breaking changes for existing OpenAI-only users
    - **Quick Start:** Set `OPENROUTER_API_KEY` in config.py, change `LLM_PROVIDER = "openrouter"` in model_config.py
    - **Status:** Phase 1 complete (chat/LLM), Phase 2 stubbed (image/TTS), Phase 3 stubbed (video)

- **OpenRouter Migration - Phase 1B Model Reference Updates (COMPLETED - 2026-02-06):**
    - **Migration Script:** Created `scripts/migrate_to_openrouter.py` (489 lines) - AST-based surgical migration tool with dry-run, unit tests, multi-line import support
    - **Successfully Migrated:** 5 files with 9 total model usages updated
      - `updates/plot_update.py` & `updates/update_encounter.py` - Fixed to use `create_chat_client()` instead of direct `OpenAI()`
      - `web/web_interface.py` - Updated existing import to include `get_model_config`
      - `core/ai/adv_summary.py` & `core/ai/cumulative_summary.py` - Removed direct OpenAI client, now factory-based
    - **Critical Bug Fixed:** Resolved `TypeError: unexpected keyword argument 'thinking'` by ensuring all migrated files use `create_chat_client()` factory instead of direct `OpenAI()` initialization
    - **Task ID System:** Mapped 9 upstream model constants to task IDs for 3-tier configuration (dm_main, summaries, plot_update, encounter_update, etc.)
    - **Temperature Preservation:** Script detects explicit temperature settings and preserves them instead of overriding
    - **Validation:** All migrated files compile successfully, migration script has 11 passing unit tests
    - **Pending:** 3 complex files require manual migration - `core/ai/transition_validator.py` (already has fallback logic), `main.py` (3 usages, high risk), `core/managers/combat_manager.py` (6 usages, highest risk)

- **Tabletop Mode Debug Monitor Skill v2.3.0 (COMPLETED - 2026-02-06):**
    - **Three-Phase Complete Workflow:** 
      - **Phase 1:** `start debug` - Check configuration, auto-enable if needed, prompt for restart
      - **Phase 2:** `check debug` - Enhanced error analysis with timestamped listings, file locations, fix suggestions
      - **Phase 3:** `stop debug` - Revert configs to debug=false, delete all debug logs, prompt for restart
    - **Enhanced Error Reporter (NEW):** Created `scripts/debug_error_reporter.py` with:
      - Automatic error classification (CRITICAL/ERROR/WARNING)
      - Timestamped chronological error listings with source component identification
      - Smart error grouping by exception type (AttributeError, KeyError, etc.)
      - File location extraction (e.g., `core/managers/multi_pc_combat.py:867`)
      - Actionable fix suggestions based on error patterns
      - Usage: `python scripts/debug_error_reporter.py --detailed` or `--critical-only`
    - **Log Cleanup:** Deletes all debug logs on stop (game_debug.log*, game_errors.log*) for clean state between sessions
    - **KISS Principle:** Manual control only, no auto-disable, zero background processes
    - **Script Features:** `scripts/check_debug_logs.py` with flags:
      - `--enable` - Enable debug mode (Phase 1)
      - `--stop` - Disable debug mode and cleanup (Phase 3) **NEW**
      - `--status` - Show configuration status
      - `--warnings` - Include WARNING level entries
      - `--verbose` - Include verbose/INFO entries
      - `--lines N` - Read last N lines (default: 100)
    - **Trigger Phrases:** "start debug", "check debug", "stop debug", "tabletop debug status"
    - **Instrumentation:** 8 debug calls in `core/managers/multi_pc_combat.py`, 2 in `core/managers/combat_manager.py`
    - **Files:** `.opencode/skills/debug-monitor/SKILL.md` (v2.3.0), `scripts/check_debug_logs.py`, `scripts/debug_error_reporter.py` (**NEW**), `utils/tabletop_debug.py`

- **MultiPCCombatManager Audit & Test Suite (COMPLETED - 2026-02-06):**
    - **Comprehensive Verification:** Created and executed 40 unit tests covering 7 categories - all passing
    - **Audit Report:** Documented all LLM prompt integration points and Python function integration points
    - **Test Coverage:**
      - CombatStateManager tests (7): Initialization, party loading, HP updates, death saves
      - TurnQueueManager tests (5): Queue building, turn advancement, current actor
      - Facade tests (7): Delegation verification, coordination methods, sub-manager linking
      - LLM Prompt tests (8): Head context, initiative tracker, required response prompts, PC context formatting
      - Context Manager tests (3): Temporary manager/callback injection, event emission
      - Edge Case tests (7): Empty party, all incapacitated, no enemies, invalid names
      - Integration tests (2): Full combat round, PC death mid-combat
    - **Bugs Fixed:**
      - Line 1183: Fixed missing `enemy_phase_complete` attribute in `get_combat_state_summary()` (changed to hardcoded `False` with comment)
      - Lines 1741-1747: Fixed deprecated direct attribute access in `get_multi_pc_initiative_narrative()` (updated to use `manager._state.*`)
    - **Key Verifications:**
      - All 7 delegation methods working correctly
      - All 5 coordination methods properly updating both sub-managers
      - Context managers enable isolated testing without Flask app
      - Zero breaking changes confirmed
    - **Documentation:** `docs/multi_pc_combat_audit.md`, `scripts/test_multi_pc_combat.py` (750 lines), `docs/test_results_multi_pc_combat.md`
    - **Files Modified:** `core/managers/multi_pc_combat.py` (2 bug fixes), test suite created

- **HP Persistence Bug Fix & Code Quality Cleanup (COMPLETED - 2026-02-06):**
    - **Critical Bug Fixed:** Every PC showing 10/10 HP regardless of actual values; defeated characters resurrecting mid-combat
    - **Root Cause:** `multi_pc_combat.py:initialize_from_party()` reading from non-existent `party_data["characters"][name]["hp"]` structure (defaults to 10)
    - **Solution:** Load character data directly from character JSON files using `characters/{name}.json` path
    - **File:** `core/managers/multi_pc_combat.py` (lines 286-309)
    
    **Code Quality Improvements:**
    1. **Duplicate json Imports Removed:** Eliminated 2 inline `import json` statements (lines 299, 1111), consolidated to module-level import only (line 29)
    2. **Silent Exception Fixed:** Added `debug()` logging for monster AC lookup failures including creature name and exception details (line 381-383)
    3. **Defensive Imports Consolidated:** Removed 4 separate try/except ImportError blocks for internal modules; now fail fast with clear errors. Consolidated `multi_pc_dm_note.py` to use centralized `should_use_abstraction_layer()` from `pc_manager.py`
    4. **Method Refactoring:** Split 130-line `format_initiative_tracker()` into 4 focused helper methods with single responsibilities:
       - `_get_combatant_marker()`: Determines state markers ([>], [X], [D], [ ])
       - `_build_initiative_lines()`: Constructs initiative and tracker line lists
       - `_determine_instruction_block()`: Calculates phase-based instructions
       - `format_initiative_tracker()`: Main orchestrator (~40 lines vs 130)
    5. **Magic Numbers Eliminated:** Added class constants `DEFAULT_AC = 10` and `INITIATIVE_DIE = 20`, replaced 6 hardcoded `ac=10` values and 4 `random.randint(1, 20)` calls
    6. **Error Handling Plan:** Identified 6 print() statements for standardization to `debug()`, `info()`, `error()` logger calls in next session
    
    **Impact:** ~35 lines removed, better separation of concerns, clearer debugging, consistent constants
    - **Files Modified:** `core/managers/multi_pc_combat.py`, `utils/multi_pc_dm_note.py`

- **MultiPCCombatManager Structure Refactoring (COMPLETED - 2026-02-06):**
    - **Phase 3 Completion:** Refactored monolithic MultiPCCombatManager into Facade pattern with 2 focused sub-managers
    - **Sub-Managers Created:**
      - `CombatStateManager` (lines 142-327): PC combat states, HP tracking, combat metadata
      - `TurnQueueManager` (lines 331-635): Initiative order, turn advancement, phase tracking
    - **Delegation Implemented:** 7 methods converted to thin wrappers delegating to sub-managers:
      - State operations: `initialize_from_party()`, `get_available_pcs()` → `self._state`
      - Turn operations: `initialize_turn_queue()`, `get_current_actor()`, `advance_turn()`, `find_target()`, `get_remaining_enemies_for_round()` → `self._turns`
    - **Coordination Preserved:** 5 methods kept in MultiPCCombatManager that require both sub-managers:
      - `update_pc_hp()` - Updates state AND syncs to turn_queue
      - `complete_pc_turn()` - Marks acted + checks phase completion
      - `force_end_pc_phase()` - Force-ends PC phase across both managers
      - `start_new_round()` - Coordinates round increment + resets
      - `get_combat_state_summary()` - Aggregates data from both sub-managers
    - **Verification:** Python syntax valid, instantiation works, all delegations functional
    - **Line Reduction:** 1,943 → 1,756 lines (-187 lines, ~10% reduction)
    - **Architecture:** Cleaner separation of concerns, easier unit testing, clearer responsibilities
    - **Files Modified:** `core/managers/multi_pc_combat.py` (major restructure, zero breaking changes)

- **5e Rest Automation Implementation (COMPLETED - 2026-02-05):
    - **Problem:** Spell slots not automatically updating after long rests despite prompt guidance; players had to manually request updates
    - **Solution:** Implemented code-level automatic resource restoration in `core/ai/action_handler.py` with `_process_character_rest()` function (lines ~1902-2065)
    - **5e Rule Compliance:**
      - Short rest (≥1 hour): Warlock spell slots + shortRest features only; NO auto-heal (players spend Hit Dice manually)
      - Long rest (≥8 hours): Full HP, all spell slots, all features, exhaustion removal
    - **Prompt Contract Fix:** Added "rest" to @ACTIONS (line 24), @PARAMS (line 228), @EXAMPLES (lines 292-295) in prompts/system_prompt_compressed.txt; updated @REST section (lines 109-116)
    - **Bug Fixes Applied:**
      - Fixed character path resolution using `find_character_file_fuzzy()` instead of manual filename building
      - Fixed exhaustion detection (schema uses list[string], not list[dict])
      - Added parameter validation for rest_type ("short" or "long")
      - Added file existence safety checks with proper logging
    - **Files Modified:**
      - `core/ai/action_handler.py` - _process_character_rest() (~164 lines)
      - `prompts/system_prompt_compressed.txt` - rest action documentation
      - `scripts/test_rest_action.py` - **NEW** - Comprehensive test suite
    - **Testing:** Test script created as integration test specifications; requires full application environment to run
    - **Benefits:** No LLM reliance for rest rules; consistent 5e compliance; works for single-PC and multi-PC modes

- **Validation API Sanitization Patch (COMPLETED - 2026-02-05):
    - **Issue:** The `active_pc` field added to messages for multi-PC compression was being passed to validation API calls, causing 400 errors with strict OpenAI-compatible providers
    - **Root Cause:** While `get_ai_response()` already stripped `active_pc` before main DM API calls, the validation paths in both `main.py` and `combat_manager.py` were not sanitizing messages
    - **Solution:** Added minimal 4-line sanitization loops immediately before API calls in both validation paths:
      - `main.py:1231-1234` - Sanitizes `validation_messages_to_send` before export to `debug/api_captures/` and before `client.chat.completions.create()`
      - `core/managers/combat_manager.py:835-838` - Sanitizes `validation_conversation` before combat validation API call
    - **Pattern:** Checks `isinstance(msg, dict)` before key deletion for safety; preserves all other message fields
    - **Merge Safety:** Clearly marked with `# TABLETOP MODE:` comments; zero impact on single-player mode; no upstream behavior changes
    - **Consistency:** Matches the sanitization pattern already established in `get_ai_response()` for main API calls
    - **Files Modified:** `main.py` (4 lines), `core/managers/combat_manager.py` (4 lines)

- **Multi-PC Combat Manager Error Handling Fix (COMPLETED - 2026-02-06):**
    - **Problem:** Inconsistent error handling across `core/managers/multi_pc_combat.py` with mix of `debug()`, `print()`, and silent pass statements
    - **Root Cause:** Module evolved organically without logging standards enforcement; 6 `print()` statements needed standardization
    - **Solution:** Unified all logging to use `utils.enhanced_logger` with proper categories:
      - Import update (line 45): Added `info` and `error` to existing `debug` import
      - Error conditions: `error()` with `category="combat_persistence"` for persist failures (lines 849, 868, 871)
      - Exception handling: `error()` with `exception=e` parameter for full stack traces (lines 871, 1274)
      - Success messages: `info()` for save confirmations (line 866)
      - Lifecycle events: `info()` for combat session management (lines 1310-1314)
    - **Logger Categories:** `combat_persistence` (save/load operations), `combat_events` (callback errors), `combat_lifecycle` (session start/end)
    - **Result:** Zero `print()` statements remaining in file; consistent error handling following codebase standards
    - **Impact:** No functional changes; pure refactoring improves maintainability and enables log filtering
    - **Files Modified:** `core/managers/multi_pc_combat.py` (7 lines total: 1 import + 6 replacements)

- **Context Manager Pattern for Testability (COMPLETED - 2026-02-06):**
    - **Problem:** Global singleton pattern (`_active_combat_manager`, `_combat_callback`) prevents clean unit testing without full Flask app
    - **Root Cause:** Module-level globals require running application context for any combat-related tests
    - **Solution:** Implemented Python context manager pattern for dependency injection:
      - Imports (lines 30-31): `Generator` from `typing`, `contextmanager` from `contextlib`
      - `temporary_combat_manager()` (lines 1251-1269): Replaces global manager temporarily using `@contextmanager` decorator
      - `temporary_combat_callback()` (lines 1272-1290): Replaces global callback for event capture in tests
      - `reset_combat_state()` (lines 1292-1302): Clears global state for test isolation with logging
    - **Pattern:** All use `try/finally` for guaranteed cleanup even if exceptions occur
    - **Benefits:** Zero breaking changes, composable (can nest managers), thread-safe per-thread contexts
    - **Test Scenarios Enabled:**
      - Mock combat scenarios without Flask app running
      - Edge case testing (all PCs unconscious, death saves, etc.)
      - Persistence verification without actual file I/O
      - Web UI event capture and validation
      - Parallel test execution (no shared state pollution)
    - **Usage Example:**
      ```python
      with temporary_combat_manager(mock_manager):
          result = get_combat_manager()
          assert result == mock_manager
      # Original restored automatically
      ```
    - **Files Modified:** `core/managers/multi_pc_combat.py` (3 imports + 3 functions, ~50 lines)

- **Character Data Access Abstraction Layer (COMPLETED - 2026-02-06):**
    - **Purpose:** Centralized character data access with future database migration path
    - **Architecture:** Plugin-based design in `utils/pc_manager.py` with dual-check activation
    - **Dual-Check Pattern:** Checks `config.MULTIPLAYER_MODE` + runtime party size (>1 members)
    - **Functions Added (9 total):**
      - `should_use_abstraction_layer()` - DUAL-CHECK activation logic
      - `get_character_state()` / `update_character_state()` - Main CRUD operations
      - `get_party_character_states()` - Bulk party loading
      - `get_character_field()` / `update_character_field()` - Single field access
      - `character_exists()` - Existence check
      - `_is_multiplayer_enabled()` - Cached config check
      - `_validate_character_name()` - Input validation helper
    - **Safety Features:**
      - Thread-safe statistics with `_stats_lock` for multi-threaded web server
      - Input validation rejects empty/None/invalid types
      - Config caching prevents repeated imports
      - Graceful fallback to direct file access on errors
    - **Upstream Integration (marked # TABLETOP MODE):**
      - `core/managers/combat_manager.py` - Combat character loading (lines ~2279-2289)
      - `core/ai/action_handler.py` - Party filtering for encounters (lines ~704-709)
      - `utils/multi_pc_dm_note.py` - DM note character loading (lines ~283-291)
    - **Verification:** Both combat and narrator LLM paths verified working
    - **Performance:** Neutral (config caching slightly improves; no file I/O changes)
    - **Backward Compatibility:** Zero breaking changes; single-player mode unaffected
    - **Future Ready:** Easy database migration by updating `CHARACTER_STORAGE_BACKEND` constant
    - **Documentation:** Created `docs/functional_verification_report.md` and `docs/character_data_abstraction_implementation.md`
    - **Files Modified:** `utils/pc_manager.py` (~175 lines), `core/managers/combat_manager.py` (6 lines), `core/ai/action_handler.py` (5 lines), `utils/multi_pc_dm_note.py` (12 lines)

- **Multi-PC Conversation Compression (COMPLETED - 2026-02-04):**
    - **Plugin Architecture:** Created `utils/compression/multi_pc_conversation_compressor.py` (~350 lines) extending `ParallelConversationCompressor`
    - **Message Tagging:** User messages tagged with `active_pc` field (e.g., `{"role": "user", "content": "...", "active_pc": "Acheron"}`)
    - **Dual-Check Activation:** Checks `MULTIPLAYER_MODE` from config.py + runtime `active_pc` tag detection
    - **Smart Compression Strategy:**
      - Recent 8 exchanges kept raw for immediate context
      - Cross-PC events preserved (location transitions, combat, plot points)
      - Messages grouped by `active_pc` for coherent per-PC compression
      - DM Notes tagged but not compressed (authoritative state)
    - **Runtime Detection:** `get_ai_response()` checks conversation history for `active_pc` tags to avoid `party_tracker_data` dependency
    - **Integration Points:** 
      - `main.py:3661` - Message tagging with `active_pc` in multi-PC mode
      - `main.py:2274-2291` - Conditional compressor selection for main API calls
      - `main.py:1187-1204` - Conditional compressor selection for validation calls
    - **Zero Upstream Impact:** Standard `ParallelConversationCompressor` used when no `active_pc` tags detected
    - **Architecture Decisions:**
      - Tagging over aggressive compression (all PCs rotate turns, need full narrative)
      - Strict `active_pc` field at message insertion time (no inference)
      - Inheritance pattern for clean merge boundaries
      - ~4 bytes overhead per tagged message
    - **Files Modified:** `multi_pc_conversation_compressor.py` (new), `main.py` (2 locations, ~30 lines)
    
- **Multi-PC DM Note Enhancement (COMPLETED - 2026-02-04):
    - **Plugin Architecture:** Created `utils/multi_pc_dm_note.py` (~250 lines) with clean separation from upstream files
    - **Active PC Marker:** Implemented `[>]` marker consistent with combat prompt syntax for clear active PC identification
    - **Section Organization:** DM Note structured into WORLD STATE, ACTIVE PC, PARTY MEMBERS, PARTY NPCs, PLOT & QUESTS, LOCATION CONTEXT, NARRATIVE RULES
    - **Notable Items Filtering:** Non-Active PCs display only quest items, magic items, consumables, or items >50gp (reduces token bloat)
    - **HP Truth Enforcement:** Added `[SOURCE: DM Note]` tags to HP values to prevent AI hallucination of conditions (observed in chat: Acheron 21/21 described as unconscious)
    - **MULTIPLAYER_MODE Integration:** Respects global toggle from config.py; falls back to single-PC mode when disabled
    - **Prompt Directive:** Added `@MULTI_PC` to `prompts/system_prompt_compressed.txt` (~80 tokens) with rest rules and resource attribution guidance
    - **main.py Refactoring:** Minimal 10-line change with conditional routing; preserves original single-PC logic as fallback
    - **Rest Automation Note:** Documented Option B (code automation) in AGENTS.md for future implementation; current solution uses prompt-based guidance (Option A)
- **ONCNotes Developer Diary (COMPLETED - 2026-02-03):**
    - **Purpose:** Create ongoing conversational record of combat chat log analyses
    - **Location:** `memory-bank/ONCNotes.md` 
    - **Format:** Chronological entries with timestamps, narrative summaries, OCNote analysis
    - **Integration:** `read-combat-log` skill automatically writes entries after analysis
    - **Content:** Entry 001 documents split-party testing with OCNote threading insights
    - **Relationship:** Complements formal docs with informal "in-the-moment" observations
- **Read-Combat-Log Skill Enhancement (COMPLETED - 2026-02-03):**
    - **Location:** `.opencode/skills/read-combat-log/SKILL.md`
    - **Features:** Context-based incremental tracking, OCNote threading, diary writing
    - **Trigger Phrases:** "read combat log", "show chat updates", "read more"
    - **Bookmark System:** `=====LAST LOG [timestamp]=====` format for incremental updates
    - **Output:** Narrative summary + combat interactions + OCNote analysis + diary entry
- **Real-Time Chat Monitoring System (COMPLETED - 2026-02-03):**
    - **Purpose:** Enable AI assistant to monitor live gameplay without polling files
    - **Implementation:** SocketIO middleware in `web/web_interface.py` (lines ~228-290) wraps `socketio.emit()` to intercept `game_output` events
    - **Log Location:** `debug/logs/live_chat_monitor.json` with rotating 100-entry buffer
    - **Utility:** `utils/chat_monitor.py` provides CLI for filtering, following, and exporting logs
    - **Use Cases:** AI debugging, live TTS narration, streaming text feeds, testing prompt changes
    - **Status:** Automatic activation on server start, zero configuration needed
- **Split-Party Combat Enhancement (COMPLETED - 2026-02-03):**
    - **Challenge:** Combat LLM lost context of remote party members after ~8-10 turns of split narrative
    - **Solution:** Added `@SPLIT_PARTY_GUIDANCE` section (lines 146-154) to `combat_sim_prompt_multipc_compressed.txt`
    - **Content:** 20-line minimal guidance for dual awareness (3-5 turns), graceful degradation, and human-assisted recovery
    - **Testing:** 8-10 turn split successfully maintained; human "we rejoin the battle" narration triggers seamless recovery
    - **Token Cost:** ~150 tokens (minimal footprint)
- **Multi-PC Combat PC/NPC Type Classification Fix (COMPLETED):** PCs were being incorrectly added to encounters with `type: "npc"` instead of `type: "player"`, causing LLM confusion during combat.
    - **Root Cause:** The AI prompt examples show all allies in the `npcs` array. When generating `createEncounter` actions, the AI included party members from `partyMembers` in the `npcs` list. The `combat_builder.py` then added them as `type: "npc"`.
    - **Solution:** Added filtering logic in `core/ai/action_handler.py` (line ~700) to remove any party members from the `npcs` array before passing to `combat_builder.py`. This prevents PCs from being misclassified as NPCs.
    - **Encounter File Cleanup:** Fixed existing `encounter_C05-E2.json` to have correct `type: "player"` for all PCs (Acheron, Claris the Good, Tester, Cyrius the Wise) and removed erroneous `npcType` fields from player entries.
    - **Impact:** LLM no longer confuses PCs with NPCs during batch enemy phase processing; combat sync no longer loads PCs as NPC templates; initiative tracking works correctly for all party members.
    - **Files Modified:** `core/ai/action_handler.py`, `modules/encounters/encounter_C05-E2.json`
- **Multi-PC Combat Enemy Armor Class Fix (COMPLETED):** Enemy AC was defaulting to 10 regardless of monster template values (e.g., Mimic AC 12 treated as AC 10).
    - **Root Cause:** `core/generators/combat_builder.py` was not including `armorClass` when building enemy encounter entries. The fallback in `multi_pc_combat.py` only triggered when AC was `None` or `0`, but `combat_builder.py` defaulted to `10`.
    - **Solution:** 
        1. Added `armorClass` field to monster generation in `combat_builder.py` (line ~347) with `# TABLETOP MODE:` comment for merge safety.
        2. Enhanced `initialize_turn_queue()` in `multi_pc_combat.py` (lines ~326-352) to backfill missing AC from monster templates using `ModulePathManager` and `safe_json_load`.
    - **Impact:** New encounters include correct AC; 19 existing encounters will be backfilled at runtime; `/att` command now resolves hits/misses against correct AC values.
    - **Files Modified:** `core/generators/combat_builder.py`, `core/managers/multi_pc_combat.py`
- **Multi-PC Initiative Tracking Fix (COMPLETED):** Fixed scrambled initiative order where the AI would ask for actions from PCs who had already acted.
    - **Root Cause:** The AI initiative tracker (`initiative_tracker_ai.py`) only recognized ONE creature with `type == "player"` as "the player", treating all other PCs as "NPCs to batch process" in the enemy turn queue.
    - **Solution:** Bypassed AI tracker in multi-PC mode. Added `format_initiative_tracker()` method to `multi_pc_combat.py` that uses deterministic state from `turn_queue` and `pc_states` to generate initiative instructions.
    - **Implementation:** Modified `combat_manager.py` to use `multi_pc_manager.format_initiative_tracker()` when `multi_pc_manager` is active, falling back to AI tracker only for single-PC mode.
    - **Result:** All PCs now correctly identified as player characters with proper `[>]` turn markers and individual stops in initiative order.
- **Multi-PC Combat Prompt Rebuild (Task 1):** Created `prompts/combat/combat_sim_prompt_multipc.txt` based on the robust single-player foundation. Integrated `[PC_NAME]` markers, active PC tracking, and multi-PC specific Golden Rule logic.
- **Multi-PC Validation Update (Task 1.5):** Created `prompts/combat/combat_validation_prompt_multipc.txt` to align with the multi-pc prompt. It enforces the "Active PC" stop rule and "Batch Enemy Phase" processing.
- **Plan Update:** Updated `Docs/multi_pc_combat_rebuild_plan.md` to reflect the completion of the foundation and validation tasks.
- **Multi-PC Combat Cleanup (STABILIZATION):** Implemented architectural cleanup to ensure combat determinism even during manual tab switching.
    - **Deterministic Enemy List:** Fixed `get_remaining_enemies_for_round()` in `multi_pc_combat.py` to use "Option B" approach, calculating pending enemies from initiative order and phase state instead of the brittle `current_turn_index` slice.
    - **Explicit Phase Signaling:** Added an authoritative `=== COMBAT PHASE STATE ===` block to the prompt injection in `combat_manager.py`. This provides ground-truth on the active phase and remaining actors, preventing LLM desync when the DM switches tabs.
    - **Legacy Component Removal:** Deleted the obsolete `web/static/js/multi_pc_combat.js` overlay and removed associated SocketIO endpoints. The UI is now driven entirely by the core tabletop mode tabs.
    - **Prompt Instruction Refinement:** Cleaned up `prompts/combat/combat_sim_prompt_multipc.txt` to remove conflicting instructions and formatting artifacts.
- **Data Integrity Fix (CRITICAL):** Resolved a "glitch" where PC damage taken during the Enemy Phase was not being registered.
    - **Root Cause:** In "Batch Mode", the AI was sometimes consolidating PC damage into `updateEncounter` actions. The `update_encounter` system is designed to ignore PC data (treating character files as source of truth), so these updates were silently discarded.
    - **Fix:** Explicitly instructed the AI in both `combat_manager.py` and `prompts/combat/combat_sim_prompt_multipc.txt` that `updateCharacterInfo` MUST be used for PC damage, even during batch processing of enemy turns.
    - **Rule Added:** "DATA INTEGRITY: If a PC takes damage, you MUST use 'updateCharacterInfo' for them. 'updateEncounter' ignores PCs."
- **Aesthetic Cleanup:** Removed verbose `[System: ...]` log messages from the user-facing chat output for `/att` (miss) and `/dmg` commands in `core/managers/multi_pc_combat.py`. The logs are still generated and injected silently for the LLM context.
- **Round Advancement Automation (FIXED):**
    - **Issue:** The AI would narrate the end of a round but fail to increment the mechanical `combat_round` integer, causing the system to stagnate in the current round.
    - **Fix:** Added explicit logic to `core/managers/combat_manager.py` and `prompts/combat/combat_sim_prompt_multipc.txt` requiring the AI to increment `combat_round` whenever the initiative queue is cleared.
- **Enemy Phase Batch Processing (ENFORCED):**
    - **Issue:** During the Enemy Phase, the AI would sometimes process only a few enemies and then stop, returning control to the player prematurely.
    - **Fix:** Implemented strict "Batch Mode" instructions in the system prompt and `/end` command handler. The AI is now explicitly forbidden from returning control until ALL pending enemies and NPCs have acted.
- **Multi-PC Validation Hydration (Task 1.5):** Achieved parity between Multi-PC and Single-PC validation prompts.
    - **Prompt Robustness:** Rebuilt `prompts/combat/combat_validation_prompt_multipc.txt` to include all 350+ lines of standard validation logic (HP math, resource usage, status integrity) merged with Multi-PC specific rules.
    - **Alignment:** Updated `prompts/combat/combat_validation_prompt_multipc_compressed.txt` to strictly align with the new robust ruleset, ensuring consistent behavior regardless of optimization settings.
    - **Feature Parity:** Restored critical sections like "Player Interaction Errors" and "Death Tracking Errors" that were previously missing from the Multi-PC version.
- **Multi-PC Validation Layer (NEW):** Implemented specialized validation logic for Multi-PC combat.
    - **Multi-PC Validation Prompts:** Created `prompts/combat/combat_validation_prompt_multipc.txt` (and compressed version) to enforce Multi-PC specific rules like the "Batch Enemy Phase" and stopping at any active PC turn.
    - **Dynamic Selector:** Updated `core/managers/combat_manager.py` to automatically switch to Multi-PC validation prompts when the `multi_pc_manager` is active.
    - **Rule Enforcement:** Explicitly added rules to prevent the AI from stopping mid-Enemy-Phase and ensured the "Golden Rule" respects the `[>]` active PC marker.
- **Multi-PC Combat Prompt Rebuild (Task 1):** Initiated a complete rebuild of the multi-PC combat prompt based on the production-hardened single-player foundation.
- **Bulletproof Phase Transition (REVISED):**
    - **`/end` Command:** Updated handler in `core/managers/combat_manager.py` to **FORCE** the enemy phase immediately upon request, bypassing the "wait for all PCs" logic.
    - **Manual Control:** User feedback indicated that auto-advancing through tabs was confusing. The system now trusts the DM to manage PC turns manually and use `/end` only when they are ready for the enemies to act.
    - **Prompt Update:** Added `++ TRANSITION TO ENEMY PHASE ++` section to `prompts/combat/combat_sim_prompt_multipc.txt` to explicitly instruct the AI on how to handle the phase transition signal.
    - **Help Update:** Added `/end` to the `/help` command output in `core/managers/combat_manager.py`.
- **PDF Export Fix (COMPLETED):** Fixed the `/api/character_sheet/pdf` endpoint that was failing with "No /AcroForm dictionary in PDF of PdfWriter Object" error.
    - **Root Cause:** The template PDF (`Docs/5E_CharacterSheet_Fillable.pdf`) contains corrupted object references. Using `writer.append_pages_from_reader()` followed by `writer.clone_reader_document_root()` caused IndexError during object translation.
    - **Solution:** Replaced the broken two-method approach with pypdf's atomic `writer.append(reader)` method (line 900-903 in `web/web_interface.py`). This single call copies both pages AND the AcroForm dictionary atomically, avoiding object reference conflicts.
    - **Additional Fix:** Made NeedAppearances flag setting conditional - now only sets it if `/AcroForm` exists in the writer's root object (lines 1045-1055).
    - **Status:** Code fix verified and in place. Testing requires running the server and accessing the endpoint with an active character.
- **Native Browser Print Implementation:** Replaced `html2pdf.js` with `window.print()` in `downloadCharacterSheetPDF` to resolve persistent "blank page" rendering issues.
- **Startup PC Synchronization (FIXED):** Modified `web/templates/game_interface.html` to initialize `window.active_character` immediately on page load by extracting it from the server-rendered active tab. This ensures "Start Game" and subsequent inputs are correctly attributed to the intended PC from the first interaction.
- **Client-Side Image Caching:** Implemented a persistent caching layer in the browser for character portraits and monster thumbnails.
    - **404 Suppression:** Once an image fails to load (404), it is added to a `missingImageCache` Set, preventing future redundant requests during the session.
    - **Reduced Network Noise:** This eliminates repeated 404 logs in the server console caused by periodic UI refreshes for characters without assets.
- **Explicit Agency Labels in Prompts:** Enhanced prompt structure to prevent LLM from "auto-playing" player characters.
    - **Terminological Reinforcement:** Renamed generic "Party members" and "Party NPCs" labels in `main.py` (DM Note) to **"Active Player Characters (User Controlled)"** and **"Accompanied by Party NPCs (DM Controlled)"**.
    - **Agency Enforcement Rule:** Updated `prompts/system_prompt.txt` with a strict rule forbidding the AI from narrating actions, dialogue, or decisions for user-controlled characters.
- **Head-Body-Tail Prompt Architecture:** Implemented a new prompt continuity strategy for combat.
    - **Combat Head-JSON:** Created an authoritative JSON block for all PCs (stats, status, initiative) injected into the system prompt. This ensures the LLM never "forgets" party members even after history compression.
    - **Multi-PC Prompt Activation:** Activated and dynamically populated the previously orphaned `combat_sim_prompt_multipc.txt`.
    - **Future-Proof Metadata:** Added support for `position` and other spatial metadata in the Head JSON to allow for future X,Y map development.
- **Multi-PC Combat Fix (CRITICAL):** Resolved an issue where combat encounters would incorrectly resume previous sessions, leading to narrative confusion and loss of mechanical tracking.
    - **Root Cause:** `combat_manager.py` was resuming any existing `combat_conversation_history.json` file regardless of whether the encounter IDs matched.
    - **Fix:** Implemented strict ID validation. The system now parses the "Current Combat Encounter: {id}" message from the history file and compares it to the requested encounter ID. If they don't match, the history is cleared, ensuring a fresh start for new battles.
- **Weapon/Attack Synchronization:** Implemented a hard-wired synchronization system in `updates/update_character_info.py` to automatically generate attack entries for equipped weapons.
- **Multi-PC Combat Integration:** Successfully integrated `MultiPCCombatManager` into the core combat loop in `combat_manager.py`.
    - Implemented dynamic prompt injection for active PC context and turn status.
    - Synchronized character state (HP/Status) between character files and the combat manager.
    - Automated turn completion and round progression tracking.
    - Honored group initiative rolls in the initial combat prompt.
- **Multi-PC Combat System:** Created `core/managers/multi_pc_combat.py` to handle combat state, turn tracking, and group initiative logic.
- **Frontend Integration:** Created `web/static/js/multi_pc_combat.js` and updated `web/static/css/tabletop_mode.css` to provide a visual turn indicator and combat interface.
- **Server Hooks:** Updated `core/ai/action_handler.py` to initialize multi-PC combat on encounter creation and roll group initiative.

## Next Steps
- **Multi-PC DM Note Testing:** Validate HP truth enforcement prevents hallucination; test rest rules guidance; verify notable items filtering reduces tokens without losing context
- **5e Rest Automation Testing:** Run integration tests with real character files to verify short/long rest logic, spell slot restoration, and exhaustion handling
- **Split-Party Stress Testing:** Long-duration testing of `@SPLIT_PARTY_GUIDANCE` to determine maximum viable split length and optimal rejoin strategies
- **Chat Monitoring Integration:** Explore real-time TTS narration feeds and live audience streaming use cases for the monitoring system
- **Stress Test Combat Cleanup:** Verify that manual tab switching during large encounters does not cause "Enemy turn amnesia" with the new phase block
- **COMPLETED - MultiPCCombatManager Audit & Test Suite (2026-02-06):** Comprehensive testing of refactored multi-PC combat system:
  - ✅ Created 40 unit tests covering 7 categories (CombatStateManager, TurnQueueManager, Facade, LLM Prompts, Context Managers, Edge Cases, Integration)
  - ✅ Verified all 7 delegation methods working correctly
  - ✅ Verified all 5 coordination methods properly updating both sub-managers
  - ✅ Tested all LLM prompt integration points (5 formatting functions)
  - ✅ Tested context managers for isolated testing without Flask app
  - ✅ Tested edge cases: empty party, all incapacitated, no enemies, invalid names
  - ✅ Fixed 2 bugs discovered during testing (missing attribute, deprecated access)
  - ✅ Zero breaking changes confirmed
- **Narrative Optimization:** Refactor `conversation_utils.py` to use a consolidated JSON "Head" for the entire party in narrative mode (similar to the new combat architecture)
- Refine the combat UI based on user feedback
- Test "Quick Create" character flow (manual form)
- **COMPLETED:** Implement "Create New Player" via LLM flow (Added "Create with DM" in Tabletop Mode)

---

## Documentation Update (2026-02-06)
- Memory Bank synchronization performed on request ("update memory bank").
- **COMPLETED:** MultiPCCombatManager Audit & Test Suite fully documented:
  - Created `docs/multi_pc_combat_audit.md` with comprehensive integration point documentation
  - Created `scripts/test_multi_pc_combat.py` with 40 unit tests (750 lines)
  - Created `docs/test_results_multi_pc_combat.md` with test coverage analysis
  - All tests passing, zero breaking changes confirmed
- Updated AGENTS.md and memory-bank with Phase 3 refactoring verification details.
- Current priority shifts to gameplay testing (Multi-PC DM Note + rest automation + combat stress testing).
