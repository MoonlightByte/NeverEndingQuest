## Why

The current Diary work improved metadata, source hygiene, and duplication handling, but it still behaves like a repaired checkpoint digest instead of a player-trustworthy chronicle of the campaign journey. Players are explicitly using `journal.json` as the more useful source of truth, so confirmed Diary now needs to converge on that chronology while staying concise, descriptive, and useful in the Journal modal.

This change is needed now because Diary is already a visible UX surface and the current mismatch is undermining player recall and confidence. Confirmed Diary MUST become a chaptered retelling of `journal.json`, while draft Diary remains a separate live-session feature and Story So Far can later build on the fuller journal source directly.

## What Changes

- MUST reorient confirmed Diary rebuilds around `journal.json.entries` as the canonical source of chapter chronology instead of using checkpoint-window history as the primary narrative source.
- MUST preserve journal entry order as the authoritative campaign sequence and derive chapter blocks from adjacent journal entries rather than from broader DB candidate scans.
- MUST collapse duplicate and near-duplicate journal variants into one confirmed chapter entry when they describe the same scene/beat.
- MUST generate one descriptive, informative confirmed Diary summary per chapter block, with optional LLM generation only after Python sanitization and deterministic fallback when unavailable.
- MUST keep draft Diary checkpoint generation separate from confirmed chaptered Diary behavior.
- MUST keep confirmed Diary rows title-free in the UI and preserve explicit world date/time/location metadata for display.
- SHOULD keep Story So Far behavior unchanged in this slice, while preserving source metadata needed for a later full-journal story compiler migration.

**Non-Goals**
- This change does NOT rewrite the draft/start/save/exit diary checkpoint pipeline.
- This change does NOT move Story So Far to full-journal input yet.
- This change does NOT make LLM availability a hard dependency for confirmed Diary rebuilds.
- This change does NOT replace `journal.json` or the memory DB as broader repository systems of record.

## Capabilities

### New Capabilities
- `journal-diary-chaptered-confirmed-view`: Build confirmed Diary as a chaptered retelling of `journal.json` with canonical journal ordering and explicit world-line metadata.
- `journal-diary-chapter-summary-generation`: Generate one concise, player-facing summary per journal chapter block using Python chapter grouping plus optional LLM summarization with deterministic fallback.

### Modified Capabilities
- None.

## Impact

- Affected code:
  - `core/memory/session_diary.py`
  - `web/templates/game_interface.html`
  - diary rebuild CLI/tests under `scripts/`
- Affected systems:
  - confirmed Diary rebuild path
  - Journal modal Diary tab rendering
  - source metadata retained for later Story So Far evolution
- Merge safety:
  - host-file edits SHOULD remain minimal and marked with `# TABLETOP MODE:` comments where applicable.
- SP/MP compatibility:
  - behavior MUST remain valid in both single-player and TABLETOP MODE.
- Risks:
  - chapter grouping could over-collapse distinct scenes at the same location if heuristics are too aggressive.
  - journal-driven confirmed rebuild could diverge from current checkpoint-based expectations unless draft/confirmed responsibilities stay clearly separated.
  - inconsistent journal metadata may surface stale module labels if module resolution is not conservative.
- Fallback:
  - if LLM chapter summarization fails or remains disabled, confirmed Diary MUST fall back to deterministic chapter summaries built from sanitized journal chapter packets.
