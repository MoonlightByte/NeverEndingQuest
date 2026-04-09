## Context

The current session diary path is already live in the Journal modal, but its checkpoint summaries are still effectively placeholder quality. `core/memory/session_diary.py` builds draft and confirmed diary rows from a broad backfill window that currently includes `journal`, `conversation`, and `combat` sources, then falls back to a simple first-entry/last-entry stitch. Because `core/memory/memory_ingest.py` stores conversation and combat history nearly verbatim, noisy source rows can include raw JSON responses, system messages, combat summaries, mechanical notices, and duplicated location-summary variants.

This creates three user-facing failures:
- the Diary tab is too long and too imprecise for quick recall,
- the in-world illusion breaks when entries surface out-of-world artifacts,
- confirmed diary rows are weak source material for `core/memory/story_so_far_compiler.py`.

Constraints:
- Python ground truth MUST remain authoritative for current world date/time, module, and location metadata.
- Start Game, Save, Exit, and Journal read paths MUST remain fail-open.
- Host file edits SHOULD stay additive and marked with `# TABLETOP MODE:` comments.
- Behavior MUST remain valid in both single-player and TABLETOP MODE.
- The design SHOULD avoid broad changes to the generic memory-ingestion contract unless diary-specific requirements truly need them.

Stakeholders:
- players using the Diary tab as a quick in-world recap,
- facilitators using the diary to recover continuity quickly,
- the Story PDF compiler, which benefits from cleaner confirmed checkpoint text.

## Goals / Non-Goals

**Goals:**
- Deliver diary entries that read like concise in-world log entries rather than raw checkpoint dumps.
- Prefer `journal.json` as the primary diary source so the diary tracks player-facing canon instead of noisy runtime scaffolding.
- Persist explicit world date/time and location stamps for every draft and confirmed diary row.
- Sanitize and deduplicate source material before diary generation.
- Improve the downstream quality of confirmed-only inputs used by the "Story so far..." PDF path.
- Provide a bounded deterministic fallback when LLM diary generation degrades.
- Preserve current fail-open lifecycle semantics and route stability.

**Non-Goals:**
- Replacing `journal.json` or memory DB as source-of-record systems.
- Rewriting the Story PDF compiler into a separate narrative engine.
- Replacing the Journal modal shell or paging layout.
- Making raw conversation/combat history the default diary source again.
- Turning diary generation into a blocking requirement for gameplay lifecycle events.

## Decisions

### Decision: Use a journal-first checkpoint pipeline
The diary pipeline MUST select source material in this order:
1. primary: cleaned journal beats from `journal.json` / `journal_entries` with `source_type='journal'`,
2. secondary: sanitized conversation/combat fallback only when no journal beats exist in the checkpoint window,
3. tertiary: deterministic fallback recap if LLM generation is unavailable.

Rationale:
- `journal.json` already best matches the user expectation for "where we came from" and "story so far".
- Journal-first selection sharply reduces risk of JSON/mechanical leakage.
- Secondary fallback preserves resilience for sparse campaigns without making noisy runtime logs the default.

Alternatives considered:
- Continue mixing journal, conversation, and combat equally: rejected because it preserves current noise.
- Journal-only with no fallback path: rejected because some sessions may not produce timely journal beats.

### Decision: Add explicit diary checkpoint metadata for world-line immersion
Each draft and confirmed diary row MUST persist structured checkpoint metadata for:
- world year/month/day/time,
- module identifier or display name,
- primary location name,
- optional location id when known.

Rationale:
- Players asked for diary entries to feel like real logbook entries.
- Storing metadata separately lets the GUI render immersive diary headings without relying on prose parsing.
- The same metadata strengthens Story PDF chapter ordering and scene labeling.

Alternatives considered:
- Keep metadata only inside summary prose: rejected because it is harder to render consistently and harder to reuse for PDF generation.
- Compute location only at read time from current state: rejected because checkpoints should preserve historical context, not mutate with later travel.

### Decision: Build a diary-specific source sanitizer instead of broad memory-ingest rewriting
Diary cleanup SHOULD live in diary-focused service code (either helper extraction inside `core/memory/session_diary.py` or a new diary utility module) rather than changing the generic meaning of `journal_entries` globally.

Rationale:
- Other memory consumers may still need near-verbatim history storage.
- Diary generation has stricter presentation requirements than generic memory retention.
- This keeps the change narrowly scoped and merge-safe.

Alternatives considered:
- Rewrite `core/memory/memory_ingest.py` to aggressively sanitize all conversation/combat rows on ingest: rejected because it could silently weaken unrelated memory features.

### Decision: Deduplicate at checkpoint-build time using narrative-beat similarity rules
Checkpoint assembly MUST collapse repeated source beats that describe the same event with only stylistic variation, especially duplicate journal variants sharing the same time/location window.

Rationale:
- Current journal data often contains both short and long retellings of the same scene.
- Deduping before generation keeps diary entries brief and avoids repetitive PDF chapters.

Alternatives considered:
- Leave duplicates in place and trust the LLM to compress them away: rejected because deterministic fallback would still be noisy and LLM output could remain inconsistent.

### Decision: Use a bounded diary generator plus deterministic short-form fallback
The diary generator MUST produce concise output shaped for quick recall, with a deterministic fallback path that never emits raw JSON or out-of-world syntax. The LLM path SHOULD use the existing provider-agnostic client factory and the existing diary prompt file, but with a much smaller sanitized input packet than today.

Rationale:
- The diary must remain readable even during provider failures.
- Using the current client factory preserves provider-agnostic behavior and fallback patterns already used elsewhere in the repo.
- A bounded input packet reduces prompt drift and accidental inclusion of noisy raw content.

Alternatives considered:
- Pure deterministic diary generation only: rejected because it underdelivers on immersion and prose quality.
- Rich full-context storytelling prompt on every checkpoint: rejected because it is too heavy for Start Game/Save/Exit hooks.

### Decision: Regenerate existing diary rows through explicit remediation rather than silent live mutation
Existing bad draft/confirmed diary rows SHOULD be repairable through a targeted remediation path that rebuilds summaries from stored source windows and refreshed checkpoint metadata. The Journal read route MUST NOT silently rewrite large numbers of entries on every open.

Rationale:
- Existing stored rows will remain noisy unless explicitly rebuilt.
- Silent read-time mutation adds latency and obscures operator control.
- A bounded remediation path is safer to verify and easier to rerun.

Alternatives considered:
- Auto-rewrite rows whenever `/api/journal/diary` is opened: rejected because it risks unexpected delays and hidden state changes.

## Risks / Trade-offs

- [Sparse journal coverage leaves thin checkpoint windows] -> Use sanitized conversation/combat fallback only when journal beats are absent, then deterministic fallback if needed.
- [Over-sanitization removes meaningful player choice or named entities] -> Keep sanitization rule-based and test against representative journal/chat cases, especially location transitions and major decisions.
- [Checkpoint location metadata drifts from source prose] -> Derive checkpoint location from authoritative world/module state first, then supplement from source beats only when state is missing.
- [Existing diary rows remain low quality after code ship] -> Include explicit remediation tooling and tests for source-window rebuild behavior.
- [Story PDF changes become too tightly coupled to diary implementation] -> Limit this change to improving confirmed diary source quality and optional metadata consumption, not a full compiler rewrite.
- [Shared state writes cause duplicate draft/confirmed rows] -> Preserve existing idempotent checkpoint keys and add tests for draft singleton behavior plus confirmed save/exit reuse.

## Migration Plan

1. Add additive checkpoint metadata support for module/location stamps in the diary entry persistence layer.
2. Implement diary-specific source selection, sanitization, and deduplication helpers.
3. Replace the current placeholder fallback recap builder with a bounded diary recap builder and wire the LLM prompt path to sanitized inputs.
4. Update Journal route payloads and GUI rendering to surface location-aware diary headers/meta cleanly.
5. Update the Story PDF compiler to consume the improved confirmed diary metadata/text where useful, without changing confirmed-only canon boundaries.
6. Add remediation tooling for existing stored diary rows and cover it with focused tests.
7. Run diary/service/UI/PDF regression checks before implementation is considered complete.

Rollback strategy:
- Journal GUI rendering can ignore new location/module metadata if needed while retaining old summary display.
- Lifecycle hooks can fall back to deterministic diary generation only if the LLM path proves unstable.
- Additive DB fields can remain unused safely if rollback removes the feature path.
- Remediation tooling can be withheld from runtime if needed without breaking new diary generation.

## Open Questions

- Should the diary header show both module and location in the GUI by default, or only location with module available via tooltip/secondary text?
- Should conversation/combat fallback be enabled for both draft and confirmed checkpoints equally, or draft-only first with confirmed remaining stricter?
- Should remediation update existing confirmed diary rows in place, or write a backup/export before rebuild?
