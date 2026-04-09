## Context

The existing Diary implementation now has better metadata, source hygiene, remediation, and title cleanup, but confirmed Diary still behaves like a repaired checkpoint digest instead of a chaptered retelling of the player-visible campaign chronicle. The current rebuild path still pulls from broader DB journal history and heuristic candidate selection, which means the Journal modal can drift away from the sequence players actually trust in `journal.json`.

Current state:
- draft Diary is checkpoint-driven via Start Game / Save / Exit hooks in `core/memory/session_diary.py`
- confirmed Diary can be rebuilt, but its source model is still too close to checkpoint history
- optional Diary LLM generation exists, but it is gated by `ENABLE_SESSION_DIARY_LLM` and currently defaults off
- Story So Far currently compiles from confirmed Diary rows, not from the full journal chronology

Constraints:
- Draft Diary MUST remain fail-open and must not be destabilized by this slice.
- Confirmed Diary MUST preserve explicit world date/time/location metadata for UI display.
- The Journal modal shell and route shape SHOULD stay stable.
- Any LLM path MUST run only after Python sanitization and MUST degrade cleanly to deterministic fallback.
- Diary rebuild, remediation, Story So Far, and diary/runtime hook verification commands MUST use `.venv/bin/python` so dependency-sensitive runtime paths execute under the same interpreter as the app.
- Host-file edits SHOULD remain minimal and merge-safe.

Stakeholders:
- players using Diary as a quick recap of the whole campaign journey
- facilitators using Diary to reorient after breaks or between sessions
- future Story So Far work, which should inherit a cleaner confirmed timeline but not be rewritten in this slice

## Goals / Non-Goals

**Goals:**
- Make confirmed Diary a chapter-summary view of `journal.json.entries` rather than a checkpoint-summary view of DB history.
- Preserve exact journal entry order as the canonical sequence for confirmed Diary chapter construction.
- Collapse duplicate and near-duplicate journal retellings into one player-facing chapter entry.
- Generate confirmed Diary summaries that are descriptive, concise, and useful to players.
- Keep draft Diary behavior separate so live-session checkpoint hooks remain stable.
- Preserve enough chapter source metadata for a later Story So Far migration.

**Non-Goals:**
- Rewriting draft Start Game / Save / Exit checkpoint generation in this change.
- Moving Story So Far to full-journal input in this change.
- Replacing `journal.json` or the memory DB as broader repository storage systems.
- Making LLM availability mandatory for confirmed Diary rebuilds.

## Decisions

### Decision: Confirmed Diary rebuilds use `journal.json.entries` as the primary source of truth
Confirmed Diary chapter rebuilds MUST read `journal.json.entries` directly and use entry order as canonical chronology. DB `journal_entries` MAY be used for storage traceability, but MUST NOT be the primary narrative source for chapter grouping and summary content.

Rationale:
- The user's stated trust anchor is `journal.json`, not checkpoint-derived history.
- Direct use of journal entries removes drift caused by broader DB candidate scans.
- Preserving journal order avoids chronology errors caused by reconstructed sort logic.

Alternatives considered:
- Continue using DB `journal_entries` as primary source: rejected because that keeps confirmed Diary coupled to accumulated ingest artifacts.
- Make confirmed Diary entirely checkpoint-driven: rejected because it does not align with the requested campaign-level UX.

### Decision: Keep draft and confirmed Diary on separate source models
Draft Diary MUST remain checkpoint/live-session based. Confirmed Diary MUST become chapter-based and journal-driven.

Rationale:
- Draft and confirmed entries serve different user needs.
- This isolates risk: live hooks stay stable while confirmed Diary UX improves.
- The split prepares the system for a later Story So Far migration without forcing it now.

Alternatives considered:
- Unify draft and confirmed generation under one chapter model: rejected because draft needs to represent unsaved live play.

### Decision: Use deterministic chapter grouping before any summary generation
Python MUST decide chapter boundaries before summary generation. Grouping rules MUST be deterministic and based on adjacent journal entries, explicit order, duplicate collapse, location changes, and meaningful time gaps.

Rationale:
- Chapter identity is structural truth and should not be delegated to the LLM.
- Deterministic grouping is testable and easier to debug.
- It prevents narrative summarization from silently changing chronology.

Alternatives considered:
- Send all journal entries to an LLM and let it decide chapter boundaries: rejected because it is opaque and harder to validate.

### Decision: Chapter summaries use Python sanitization plus optional LLM summarization
Each confirmed chapter summary SHOULD be produced by:
1. Python-sanitized chapter source packet,
2. optional LLM summary when enabled,
3. deterministic fallback summary when disabled or degraded.

Rationale:
- The LLM is useful for descriptive prose, but Python must control source selection and safety.
- The repo already has provider-agnostic summary plumbing that can be reused.
- Deterministic fallback preserves fail-open rebuild behavior.

Alternatives considered:
- Pure deterministic summaries only: rejected because they underdeliver on descriptive UX.
- Raw-entry LLM summarization without Python sanitization: rejected because it invites format leakage and prompt drift.

### Decision: Store one confirmed row per chapter block with explicit journal-backed identity
Confirmed rebuild rows MUST use stable chapter identities such as `checkpoint_type='rebuild'` and `checkpoint_id='journal_chapter:<n>'`. Each row SHOULD also retain chapter source bounds and source-count metadata.

Rationale:
- Stable chapter identities make rebuild results inspectable and easier to reason about.
- Source bounds help future Story So Far migration.
- This avoids pretending rebuilt rows are save/exit checkpoint artifacts.

Alternatives considered:
- Reuse save/exit checkpoint identities for rebuilt rows: rejected because it obscures chapter semantics.

## Risks / Trade-offs

- [Chapter grouping over-collapses distinct scenes at the same location] -> Keep grouping rules deterministic, conservative, and covered by targeted tests for same-location scene separation.
- [Journal metadata is inconsistent or stale, especially module naming] -> Resolve module labels conservatively and avoid blindly trusting top-level `journal.json.module` when obviously wrong.
- [LLM chapter summaries drift from source content] -> Keep the source packet bounded, require Python sanitization, and fail open to deterministic fallback.
- [Draft and confirmed semantics become confusing in code] -> Keep confirmed rebuild logic isolated from draft checkpoint hooks and document the source-model split clearly.
- [Future Story So Far still inherits a compressed layer] -> Preserve chapter source metadata now so the later migration can move to fuller journal input cleanly.

## Migration Plan

1. Add journal-entry normalization helpers that read `journal.json.entries` directly.
2. Add deterministic chapter grouping over ordered journal entries.
3. Add chapter-summary generation helpers (optional LLM plus deterministic fallback).
4. Update `rebuild_diary_from_journal(...)` to rebuild confirmed rows from chapter packets rather than DB candidate history.
5. Keep draft generation code unchanged.
6. Update tests to lock chapter ordering, duplicate collapse, and summary behavior.
7. Manually rebuild the live Diary and review first/middle/last chapter entries in the Journal modal.

Rollback strategy:
- Revert the confirmed rebuild path to the prior implementation while leaving draft hooks untouched.
- Keep additive metadata fields; they remain safe if unused.
- Leave UI title cleanup in place because it is independently beneficial.

## Open Questions

- Should chapter grouping always keep one row per distinct location change, or allow two chapters at the same location when journal prose clearly marks a separate scene beat?
- Should confirmed Diary rows expose chapter index or source-entry bounds in the API payload for easier debugging, even if the UI does not render them?
- When LLM summarization is enabled, should the system prefer one paragraph only, or allow up to two short paragraphs for larger chapter packets?
