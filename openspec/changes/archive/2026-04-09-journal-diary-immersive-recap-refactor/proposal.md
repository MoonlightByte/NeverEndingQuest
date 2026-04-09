## Why

The GUI diary currently behaves like a raw checkpoint dump instead of a player-facing in-world log. Entries can become oversized, duplicate the same beat in multiple variants, and leak low-signal source text such as JSON-like action payloads, system notices, or mechanical recap fragments, which weakens both diary UX and the quality of confirmed-only inputs later reused for the fantasy-style "Story so far..." PDF.

This change is needed now because the current diary path is already visible in the Journal modal and is shaping player trust. The diary MUST become a concise, immersive world-line reference that helps players remember where they have been, what happened there, and why the current story state matters.

## What Changes

- MUST replace placeholder-style diary checkpoint assembly with a player-facing recap pipeline that prefers journal-authored beats and produces concise in-world summaries.
- MUST stamp every draft and confirmed diary entry with explicit gameworld date/time and location context suitable for a diary log entry.
- MUST sanitize and exclude JSON/action payloads, combat/system scaffolding, and other out-of-world source artifacts from diary text.
- MUST deduplicate overlapping source beats so repeated journal variants do not inflate a single diary checkpoint.
- MUST optimize confirmed diary entries as better source material for the fantasy-style "Story so far..." PDF generator.
- MUST preserve fail-open Start Game, Save, Exit, and Journal-read behavior if diary generation degrades.
- SHOULD keep the existing Journal modal structure and routes stable, improving content quality first rather than rewriting the UI shell.
- SHOULD provide a deterministic fallback recap path when LLM generation is unavailable or low-confidence.

**Non-Goals**
- This change does NOT replace `journal.json` as a source of record.
- This change does NOT rewrite the full Journal modal layout or Story PDF compiler architecture.
- This change does NOT make raw conversation/combat history the default primary source for diary entries.
- This change does NOT make diary generation a hard dependency for Start Game, Save, or Exit success.

## Capabilities

### New Capabilities
- `journal-diary-immersive-recaps`: Generate concise, player-facing diary entries that read like in-world logbook checkpoints with clear world date/time and location stamps.
- `journal-diary-source-hygiene`: Filter, sanitize, and deduplicate checkpoint source material so diary entries never surface JSON payloads, system notices, or other out-of-world artifacts.
- `journal-diary-story-foundation`: Shape confirmed diary entries so they provide stronger, cleaner source material for confirmed-only "Story so far..." PDF generation.

### Modified Capabilities
- None.

## Impact

- Affected code:
  - `core/memory/session_diary.py`
  - `core/memory/memory_ingest.py`
  - `web/routes/memory_routes.py`
  - `web/templates/game_interface.html`
  - `core/memory/story_so_far_compiler.py`
  - focused diary/story tests under `scripts/`
- Affected systems:
  - Start Game draft refresh hook
  - Save/Exit confirmed checkpoint flow
  - Journal modal Diary tab rendering
  - confirmed-only story PDF source quality
- Merge safety:
  - Host-file edits SHOULD stay additive and marked with `# TABLETOP MODE:` comments.
- SP/MP compatibility:
  - Behavior MUST remain valid in both single-player and TABLETOP MODE.
- Risks:
  - Over-sanitizing could remove meaningful player intent or scene memory.
  - Journal-first sourcing could leave sparse checkpoints when `journal.json` is thin.
  - Regeneration of existing diary rows could create timeline inconsistency if not bounded carefully.
- Fallback:
  - If cleaned LLM generation fails, the system MUST fall back to a deterministic short recap built from sanitized source beats only.
