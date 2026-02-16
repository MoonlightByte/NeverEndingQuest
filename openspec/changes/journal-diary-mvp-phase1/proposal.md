## Why

The Journal currently exposes quest context but has no reliable, world-time-aligned diary timeline that bridges unsaved active play and save-bound campaign canon. We need an MVP now that gives transparent diary updates during normal play while preserving branch-safe confirmed history and a user-triggered campaign chronicle export.

## What Changes

- Add a dual-checkpoint diary pipeline with two update points:
  - Start Game -> refresh/update one unsaved draft diary entry when source history changed.
  - Save Game -> generate one confirmed diary entry bound to `save_id`.
- Add failure-isolated diary generation so Start Game and Save remain operational if diary generation fails.
- Add Journal modal tab structure with existing Quests behavior preserved and new Diary tab for draft + confirmed entries.
- Add user-triggered `Download the story so far...` action that generates and downloads a PDF from confirmed diary timeline only.
- Add additive memory DB tables for diary entries, diary checkpoints, and minimal PDF cache metadata.
- Add explicit MVP guardrails:
  - MUST exclude draft entries from PDF source set.
  - MUST maintain SP and TABLETOP MODE compatibility.
  - SHOULD keep host edits minimal and `# TABLETOP MODE:` marked.

### Non-goals

- No new gameplay/session-control buttons for diary generation.
- No asynchronous worker queue in MVP.
- No advanced chapter art/layout pipeline for PDF in MVP.
- No changes to combat/game mechanics.

## Capabilities

### New Capabilities
- `journal-diary-dual-checkpoint`: Start Game draft refresh plus Save-bound confirmed diary checkpoints with idempotent boundaries.
- `journal-diary-tabbed-ui`: Journal UI provides Diary tab while preserving existing Quests behavior and world-time ordered rendering.
- `campaign-journal-story-pdf`: User-triggered PDF export of "story so far" compiled from confirmed diary records only.

### Modified Capabilities
- None.

## Impact

- Affected code:
  - `core/memory/memory_db.py`
  - `core/memory/__init__.py`
  - `core/memory/session_diary.py` (new)
  - `core/memory/story_so_far_compiler.py` (new)
  - `updates/save_game_manager.py`
  - `web/routes/memory_routes.py`
  - `web/web_interface.py`
  - `web/templates/game_interface.html`
- APIs/system surfaces:
  - New endpoints: `/api/journal/diary`, `/api/journal/story-so-far/pdf`.
  - Existing save/start flows gain diary side-effects with non-blocking failure behavior.
- Dependencies:
  - No required new infrastructure dependency in MVP; PDF writer dependency may be additive if selected.
- Rollout risk:
  - Medium (save/start touchpoints + DB migration).
  - Mitigated by idempotent checkpoints, strict fallback paths, and keeping save success independent of diary generation.
- Fallback strategy:
  - On diary failure, log and continue save/start flow.
  - On PDF generation failure, return safe error response without mutating save/diary state.
- Merge-safety/SP-MP impact:
  - Additive extension-first architecture with minimal host hooks and explicit compatibility invariants.
