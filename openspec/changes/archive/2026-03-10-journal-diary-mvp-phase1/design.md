## Context

NeverEndingQuest already has a save pipeline (`SaveGameManager.create_save_game`) and a memory foundation (`core/memory/*`) with idempotent ingestion primitives. The Journal UI currently focuses on Quests and does not expose a durable narrative diary model.

MVP needs two diary checkpoints:
- Draft checkpoint at Start Game so users who exited without saving still see current-session narrative continuity.
- Confirmed checkpoint at Save so campaign canon is branch-safe and tied to `save_id`.

Constraints:
- Preserve existing Start Game responsiveness.
- Preserve save integrity and existing save semantics.
- Keep Quests tab behavior unchanged.
- PDF export must exclude draft state and use confirmed-only timeline.
- Keep host file changes minimal and marked with `# TABLETOP MODE:`.

Stakeholders:
- Facilitators running live tabletop sessions.
- Operators using Save/Restore branching workflows.
- Maintainers requiring merge-safe, additive integration.

## Goals / Non-Goals

**Goals:**
- Implement dual-checkpoint diary state machine (draft + confirmed).
- Expose diary entries in Journal tab with world-time ordering.
- Support user-triggered campaign PDF export from confirmed entries only.
- Ensure diary failures never block save/start.
- Keep implementation additive and backward compatible for SP/MP.

**Non-Goals:**
- Async queue/job architecture in MVP.
- Multi-pass long-form narrative refinement pipeline.
- New session-control buttons.
- Large Journal visual redesign.

## Decisions

1. **Dual-checkpoint state model in memory DB**
   - Decision: store both draft and confirmed entries in `session_diary_entries` with explicit `status` and checkpoint table (`session_diary_state`).
   - Rationale: keeps one timeline store while preserving draft-vs-canon semantics.
   - Alternative considered: separate draft file outside DB. Rejected due to synchronization drift and restore parity complexity.

2. **Start Game triggers draft freshness check only**
   - Decision: `handle_start_game()` invokes `refresh_draft_if_stale(...)` after game thread start, non-blocking to game startup.
   - Rationale: preserves startup UX and addresses unsaved-exit continuity gap.
   - Alternative considered: generate draft on every user turn. Rejected for latency/noise and unnecessary write churn.

3. **Save path owns canon confirmation**
   - Decision: `create_save_game(...)` invokes `confirm_diary_for_save(...)` using `save_id` idempotency key.
   - Rationale: save is canonical branch boundary and already universal across web/cli/combat/AI paths.
   - Alternative considered: confirm on exit. Rejected because current exit path is non-authoritative and non-persistent by design.

4. **Failure isolation as hard invariant**
   - Decision: diary generation exceptions are caught and logged; Start Game and Save continue.
   - Rationale: protects critical user operations from LLM/provider instability.
   - Alternative considered: transactional coupling save+diary. Rejected due to reliability risk.

5. **Confirmed-only PDF source contract**
   - Decision: story compiler queries `status='confirmed'` only; draft rows are never included.
   - Rationale: keeps exported chronicle aligned with save-bound canon and branch semantics.
   - Alternative considered: include draft with warning tag. Rejected per product decision for canon purity.

6. **Minimal Journal UI extension**
   - Decision: add Quests/Diary tabs inside existing modal; do not restructure current quest rendering.
   - Rationale: reduces regression risk and preserves familiar UX.
   - Alternative considered: new standalone diary modal/page. Rejected for MVP scope and integration overhead.

7. **Provider-agnostic LLM integration**
   - Decision: use existing provider factory (`create_chat_client`, `get_model_config`) for diary/PDF summarization.
   - Rationale: avoids model-specific lock-in and preserves existing fallback patterns.
   - Alternative considered: direct provider calls in new modules. Rejected for consistency and maintainability.

## Risks / Trade-offs

- [Start Game draft generation increases startup latency] -> Mitigation: bounded source window, timeout guard, non-blocking execution path.
- [Rapid repeated saves create duplicate canon entries] -> Mitigation: unique idempotency by `save_id` + checkpoint guard.
- [World-time ordering mismatch] -> Mitigation: normalize month index + persisted numeric `world_sort_key`.
- [LLM unavailable during diary/PDF generation] -> Mitigation: deterministic fallback summaries and safe error responses.
- [UI regressions in existing Quests tab] -> Mitigation: preserve existing DOM rendering path for Quests and add isolated Diary panel.
- [Cache staleness for PDF] -> Mitigation: confirmed fingerprint includes confirmed row count/hash; rebuild on mismatch.

## Migration Plan

1. Add additive DB migration for diary/checkpoint/cache tables.
2. Implement diary service module with:
   - world-time normalization
   - draft refresh
   - save confirmation
   - list query helpers
3. Hook Save pipeline with non-fatal confirm call.
4. Hook Start Game pipeline with non-fatal draft refresh call.
5. Add memory routes for Diary listing and confirmed-only PDF download.
6. Add Journal tab UI + client fetch/download handlers.
7. Validate with compile checks and targeted MVP smoke tests.

Rollback strategy:
- Disable/short-circuit diary calls in start/save hooks.
- Keep additive schema in place (no destructive rollback required).
- Hide Diary tab and PDF button if needed while preserving Quests and core gameplay.

## Open Questions

1. Should Start Game draft refresh run synchronously for immediate display or asynchronously with eventual update event?
2. Should confirmed generation clear draft row or retain as historical marker with status transition?
3. Which PDF backend is preferred in MVP (`reportlab` vs existing utility path if present)?

## Verification Strategy

- Compile checks:
  - `python3 -m py_compile core/memory/memory_db.py core/memory/session_diary.py core/memory/story_so_far_compiler.py updates/save_game_manager.py web/routes/memory_routes.py web/web_interface.py`
- Functional checks:
  - Start Game creates/updates at most one draft when stale.
  - Save creates at most one confirmed entry per `save_id`.
  - PDF query excludes draft rows.
  - Save and Start Game remain successful when diary generator fails.
- UI checks:
  - Quests tab unchanged.
  - Diary tab displays draft on top (if present), confirmed timeline below.
  - Download button triggers PDF file download.
