## Why

NeverEndingQuest currently preserves campaign continuity across chat history, journal files, plot state, and memory DB records, but it does not provide a stable in-product diary and long-form "story so far" experience that turns those sources into readable fiction. The repository already has a prompt plan and UI intent for a journal diary MVP, and the new storyteller chronicle prompt now makes it practical to add a confirmed-only story compiler that preserves meaningful PC chat input while staying aligned with authoritative campaign state.

This change is needed now because the project already has the memory foundation, save/start hooks, and Journal modal surface to support it, but they are not yet connected into a coherent feature. Without an explicit diary/checkpoint pipeline, users cannot review an unsaved session draft, save canonized entries, or download a faithful fantasy-novel retelling of the campaign so far.

## What Changes

- Add a two-checkpoint diary system with one active unsaved `draft` entry refreshed on Start Game and `confirmed` entries created on Save.
- Append explicit Exit auto-confirm behavior so players who end sessions without manually saving still advance the confirmed diary timeline when unsaved diary progress exists.
- Add memory DB tables and service helpers to store diary entries, checkpoint state, and a cached confirmed-only story artifact.
- Add a confirmed-only long-form story compiler that uses the storyteller chronicle prompt to turn campaign history into literary 3rd-person prose.
- Add Journal API routes to list diary data and download a generated "story so far" PDF.
- Extend the Journal modal with Quests/Diary tabs while preserving current Quests behavior.
- Preserve fail-open runtime behavior: Start Game and Save continue to succeed even if diary or story generation fails.
- Preserve source-truth ordering so authoritative JSON/state beats stale narrative when assembling diary/story output.
- Preserve meaningful user/PC chat inputs as in-world story material in both diary generation and full story compilation.

## Capabilities

### New Capabilities
- `journal-diary-dual-checkpoint`: Start Game refreshes one active draft diary entry, Save creates idempotent confirmed diary entries tied to save checkpoints, and explicit Exit can auto-confirm a checkpoint when new unsaved diary progress exists.
- `journal-diary-tabbed-ui`: The Journal modal exposes a Diary tab with draft and confirmed entries while preserving existing Quests behavior.
- `campaign-journal-story-pdf`: Users can build/download a confirmed-only "story so far" artifact with caching and safe failure behavior.
- `campaign-storyteller-chronicle-generation`: The system compiles diary/history context into 3rd-person fantasy prose using a storyteller prompt that incorporates meaningful PC chat input and respects authoritative state.

### Modified Capabilities
- None.

## Impact

- Affected code:
  - `core/memory/memory_db.py`
  - new `core/memory/session_diary.py`
  - new `core/memory/story_so_far_compiler.py`
  - `core/memory/__init__.py`
  - `updates/save_game_manager.py`
  - `web/web_interface.py`
  - `web/routes/memory_routes.py`
  - `web/templates/game_interface.html`
  - new/additional prompt files under `prompts/tabletop/`
- Affected systems:
  - memory DB migrations and retrieval/ingest adjacency
  - Start Game runtime hook
  - Save checkpoint flow
  - explicit GUI Exit checkpoint flow
  - Journal modal UI and download flow
- Merge-safety impact:
  - SHOULD remain additive, with minimal host-file hooks marked `# TABLETOP MODE:`.
- SP/MP compatibility impact:
  - MUST preserve both single-player and TABLETOP MODE behavior.
- Risks:
  - story generation latency/cost,
  - accidental draft leakage into confirmed-only story output,
  - Journal UI regression.
- Fallback strategy:
  - use compact bounded diary prompts for checkpoint generation,
  - use deterministic fallback summaries when LLM generation fails,
  - keep Save, Start Game, and explicit Exit successful even when diary/story generation degrades.
