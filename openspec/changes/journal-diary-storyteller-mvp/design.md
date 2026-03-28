## Context

NeverEndingQuest already stores campaign continuity across raw conversation history, `journal.json`, module/location/plot JSON, and `memory.db`, but that material is fragmented across runtime and operator surfaces. The project also already has a Journal modal, save hooks, start-game hooks, and a prompt-level desire for a story/diary feature in `plans/version-2/journal.md`, yet there is no implementation that turns those sources into a stable in-product diary or a downloadable literary retelling.

This change is cross-cutting because it introduces new persistent diary state in the memory DB, new generation services in `core/memory/`, Start Game and Save integration hooks, read routes, and Journal UI behavior. It also adds an explicit distinction between short checkpoint summaries and long-form confirmed-only story compilation so the system can remain responsive during normal gameplay while still offering richer retrospective narrative output.

Constraints:
- Python state and current authoritative JSON remain ground truth for final campaign state.
- Save and Start Game are latency-sensitive paths and MUST fail open if diary generation degrades.
- Host-file edits MUST stay minimal and marked `# TABLETOP MODE:`.
- The feature MUST work in SP and TABLETOP MODE.
- New prompt usage SHOULD remain provider-agnostic and routed through the existing AI client/model factory stack.

## Goals / Non-Goals

**Goals:**
- Add a persistent diary model with one active draft row and idempotent confirmed rows tied to saves.
- Surface diary content inside the existing Journal UI without regressing Quests behavior.
- Generate a long-form "story so far" artifact from confirmed entries only.
- Preserve meaningful PC/user chat inputs as in-world narrative material.
- Keep source-of-truth ordering explicit so authoritative JSON beats stale narrative when conflicts appear.
- Provide deterministic fallback behavior when LLM generation or PDF generation fails.

**Non-Goals:**
- Replacing the live narrator prompt path with the storyteller compiler.
- Running full raw-campaign re-summarization on every Start Game or every Journal open.
- Introducing background workers, async job queues, or periodic diary refreshes.
- Adding advanced PDF typesetting, chapter art, or multi-pass novel generation.
- Treating draft diary entries as canonical gameplay state.

## Decisions

### Decision: Use a two-stage narrative pipeline
The system SHALL use two different generation layers:
- a compact diary-entry generator for draft/confirmed checkpoints,
- and a long-form storyteller compiler for confirmed-only story output.

Rationale:
- Start Game and Save hooks need bounded work.
- The full storyteller prompt is better suited to retrospective compilation than checkpoint generation.

Alternatives considered:
- Reuse the full storyteller prompt for every draft refresh: rejected due to latency/cost risk.
- Use only deterministic text stitching: rejected because it would underdeliver on the requested literary retelling.

### Decision: Confirmed entries are the only story compiler source of record
The story compiler SHALL build from confirmed diary entries only, optionally supplemented by current authoritative JSON for final-state reconciliation and metadata.

Rationale:
- This preserves a stable canon boundary.
- It prevents unsaved draft content from leaking into the downloadable story.
- It matches the existing journal MVP intent in `plans/version-2/journal.md`.

Alternatives considered:
- Re-scan all raw chat and JSON sources for every story build: rejected as too expensive and harder to make deterministic.

### Decision: Add diary/cache tables to memory DB rather than separate files
Diary rows, checkpoint state, and story cache metadata SHALL live in `memory.db` via additive migrations.

Rationale:
- The memory DB already exists as the continuity data layer.
- Save/restore portability already understands memory parity packaging.
- This keeps journal/story state queryable and idempotent.

Alternatives considered:
- New JSON files beside `journal.json`: rejected because it would fragment persistence and complicate save/restore invariants.

### Decision: Keep runtime hooks fail-open and observable
`handle_start_game()` and `SaveGameManager.create_save_game()` SHALL call diary services behind guarded try/except blocks, log degraded outcomes, and continue success paths when diary generation fails.

Rationale:
- Gameplay start and save durability are higher priority than narrative convenience.
- Existing repo patterns favor fail-open auxiliary systems around core play loops.

Alternatives considered:
- Failing Save or Start Game on diary error: rejected as unacceptable UX/regression risk.

### Decision: Preserve UI compatibility through additive Journal tabbing
The Journal modal SHALL retain the current Quests rendering path and add a Diary tab rather than replace the existing layout.

Rationale:
- Minimizes host-file risk.
- Preserves current player expectations.

Alternatives considered:
- Full Journal modal rewrite: rejected as unnecessary scope expansion.

## Risks / Trade-offs

- [Story generation latency on demand] -> Use compact checkpoint prompts, cache confirmed story output by fingerprint, and reserve the full storyteller prompt for explicit story compilation.
- [Draft content leaks into canon output] -> Enforce confirmed-only query constraints in compiler and PDF route tests.
- [Journal UI regression] -> Keep Quests rendering path intact and add tab-specific logic rather than replacing the existing handler.
- [State contradiction between narrative and mechanics] -> Reconcile against current authoritative JSON before final story assembly and codify that behavior in specs/tests.
- [Memory DB migration or portability drift] -> Keep migrations additive/idempotent and rely on existing memory-package save/restore path.

## Migration Plan

1. Add memory DB migration for diary/checkpoint/cache tables.
2. Add `core/memory/session_diary.py` and wire draft/confirmed generation behind service boundaries.
3. Add `core/memory/story_so_far_compiler.py` using confirmed-only inputs and storyteller prompt assembly.
4. Integrate Save and Start Game hooks with fail-open logging.
5. Add Journal API routes.
6. Add Journal Diary UI and download action.
7. Add tests for DB, service, route, and UI invariants.

Rollback strategy:
- UI/routes can be disabled independently by removing Journal Diary wiring.
- Save/Start hooks are additive and can be removed without touching canonical gameplay paths.
- DB migration is additive; unused tables can remain in place without runtime harm.

## Open Questions

- Whether the PDF route should also expose a plain-text story endpoint for debugging or future reuse. This is optional for MVP.
- Whether confirmed diary entries should capture the model identifier/generation mode in route payloads or remain internal metadata only.
- Whether the long-form story compiler should reuse only confirmed diary text or also include a compact current-state packet in every compile for ending-state correction. The design assumes yes, but the exact payload shape can stay implementation-level.
