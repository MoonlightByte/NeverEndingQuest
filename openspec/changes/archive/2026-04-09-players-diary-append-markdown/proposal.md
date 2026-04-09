## Why

The current Diary implementation has become over-engineered for the actual user need. The player-facing goal is simple: produce an engaging, concise, fun, fantasy-immersive "Players Diary" that reflects the campaign journey described in `journal.json`. A single LLM prompt over `journal.json` already produced the right artifact shape in a local test, while the current DB-backed confirmed Diary path repeatedly delivered structurally correct but emotionally poor UX.

This change reorients the feature around the actual product outcome: a markdown chronicle generated from `journal.json`, updated incrementally, and rendered directly in the web GUI. It intentionally keeps the build simple, uses a bookmark file instead of polluting `journal.json`, and avoids turning the player Diary into another persistence-heavy subsystem.

## What Changes

- MUST introduce a canonical gameplay/runtime markdown artifact for the player-facing Diary (not under `Local_Docs`).
- MUST introduce a simple bookmark file to track the last processed `journal.json` entry index.
- MUST generate the confirmed players diary by reading `journal.json` and appending only new diary content in a consistent anonymous fantasy-chronicle voice.
- MUST use the existing diary markdown example in `Local_Docs/diary.md` only as the UX/style reference, not as a gameplay file path.
- MUST keep the implementation focused on KISS: minimal files, minimal state, minimal moving parts.
- MUST preserve a full rebuild mode that can regenerate the whole diary from `journal.json` when needed.
- SHOULD keep the current draft/live-session Diary concept separate rather than coupling it to the new confirmed players diary markdown artifact.
- SHOULD render the confirmed players diary in the Journal GUI from the markdown artifact rather than from DB summary rows.

**Non-Goals**
- This change does NOT overhaul Story So Far generation.
- This change does NOT reuse `Local_Docs` for gameplay/runtime storage.
- This change does NOT require a new complex memory DB layer for confirmed diary text.
- This change does NOT attempt to preserve or evolve the current DB-backed confirmed Diary model as the primary UX surface.

## Capabilities

### New Capabilities
- `players-diary-append-generation`: Maintain a canonical markdown players diary by appending new chronicle content from unprocessed `journal.json` entries using a bounded-context LLM prompt.
- `players-diary-gui-rendering`: Render the canonical markdown players diary in the Journal GUI as the confirmed diary UX surface.
- `players-diary-rebuild-repair`: Support a full rebuild path that regenerates the canonical markdown diary from all of `journal.json` when repair or reset is needed.

### Modified Capabilities
- None.

## Impact

- Affected code:
  - new players diary generation service under `core/memory/` or adjacent runtime-appropriate module
  - new gameplay/runtime diary markdown + bookmark paths under `data/`
  - `web/routes/memory_routes.py`
  - `web/templates/game_interface.html`
  - focused tests under `scripts/`
- Affected systems:
  - confirmed Diary UX in the Journal modal
  - diary generation/rebuild tooling
- Runtime/storage:
  - recommended runtime files:
    - `data/players_diary.md`
    - `data/players_diary_bookmark.json`
- Interpreter requirement:
  - all append/rebuild/test commands for this feature MUST use `.venv/bin/python`
- Risks:
  - append mode can drift stylistically over time if no repair path exists
  - bad bookmark state can skip or duplicate diary sections if not validated
  - GUI markdown rendering can diverge from desired style if raw output is not validated
- Fallback:
  - if append mode fails, the existing diary artifact must remain intact and the bookmark must not advance
  - rebuild mode remains the repair/reset path
