## Context

Current save discovery is bound to `SaveGameManager.current_module`, so `list_save_games()` only returns saves from one module directory at a time. This blocks seamless campaign switching in GUI workflows where operators archive campaign A, run campaign B, then restore A without manual module targeting.

Constraints:
- Preserve existing restore safety behavior (backup creation, directory cleanup, memory preflight, memory import).
- Keep host file edits minimal and TABLETOP MODE marked.
- Avoid breaking existing GUI consumers that currently pass only `saveFolder`.

Stakeholders:
- Facilitators/operators running live tabletop sessions with multiple campaign timelines.
- Maintainers who need merge-safe host integration and backward compatibility.

## Goals / Non-Goals

**Goals:**
- Add a global save discovery path across `modules/*/saved_games/save_*`.
- Expose normalized metadata needed for GUI restore selection (including source module and memory parity indicator).
- Add safe restore routing for cross-module save selection.
- Preserve existing memory preflight/import behavior and restore failure semantics.

**Non-Goals:**
- Implement save zip import/export in this change.
- Redesign save metadata schema beyond additive fields.
- Modify reset/nuclear backup semantics in this change.

## Decisions

### 1) Add global catalog methods without removing local methods
Decision: keep existing module-local list/restore methods intact and add explicit global variants (for example `list_save_games_global()` and `restore_save_game_global(...)`).

Rationale:
- Limits blast radius and preserves current callers.
- Enables staged GUI migration with fallback.

Alternatives considered:
- Replace local methods outright: rejected due to compatibility risk.

### 2) Route restore using validated module plus save folder
Decision: GUI restore action sends both `module` and `saveFolder` for global entries; backend validates they resolve under `modules/<module>/saved_games/save_*` before restore.

Rationale:
- Simple user-facing contract.
- Avoids ambiguous save folder collisions across modules.

Alternatives considered:
- Route by absolute path from client: rejected for security and portability reasons.

### 3) Keep memory parity checks in existing restore pipeline
Decision: cross-module routing delegates into the same restore pipeline used today so preflight memory package validation and managed import are unchanged.

Rationale:
- Preserves existing safety contract and avoids duplicate logic.

Alternatives considered:
- Separate restore implementation for global route: rejected due to divergence risk.

### 4) Add explicit global ordering and additive metadata fields
Decision: global list normalizes metadata shape with additive fields: `source_module`, `save_folder`, `save_path`, and `memory_package_present`; list sorted by `save_timestamp` descending.

Rationale:
- Deterministic UX ordering and clear parity visibility.
- Additive fields remain backward-compatible.

Alternatives considered:
- Per-module grouped response only: rejected because it complicates direct restore selection.

## Risks / Trade-offs

- [Cross-module restore path mistakes could restore wrong timeline] -> Mitigation: strict module + folder validation and explicit source module shown in GUI.
- [Duplicate folder names across modules can confuse operators] -> Mitigation: use `source_module` as required restore input and display field.
- [Global scan adds small list latency] -> Mitigation: bounded directory walk to `modules/*/saved_games/save_*` only, no deep recursive scan.
- [Backward compatibility regressions for old clients] -> Mitigation: preserve legacy action payload handling and local methods.

## Migration Plan

1. Add global save discovery in `SaveGameManager` while preserving local listing.
2. Add restore routing helper that validates module + save folder and then delegates to existing restore flow.
3. Update SocketIO action handling to support global list and cross-module restore payload.
4. Update load dialog rendering to show source module and memory parity indicator.
5. Run validation:
   - `python3 -m py_compile updates/save_game_manager.py web/web_interface.py`
   - targeted save listing/restore smoke across at least two module save directories.

Rollback strategy:
- Revert GUI to local list action and ignore module field.
- Keep existing local restore path active.

## Open Questions

- Should global list become default for all callers immediately, or be gated behind a UI toggle in first rollout?
- Do we want to include worldline lineage badges in the same list response now, or defer to a follow-up UI enhancement?
