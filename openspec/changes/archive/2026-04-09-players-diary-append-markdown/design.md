## Context

The product goal is now clear: the player-facing confirmed Diary should feel like the example generated into `Local_Docs/diary.md`, not like a database of sanitized checkpoint recaps. The current confirmed Diary path became too complex because it tried to serve too many concerns at once: checkpoint persistence, chapter grouping, deterministic rebuildability, future Story So Far reuse, and player UX. The result was structurally tidy but not satisfying to read.

The new direction is intentionally simpler:

- `journal.json` remains the source of truth
- a single markdown artifact becomes the confirmed players diary shown in the GUI
- a bookmark file tracks progress through journal entries
- append mode is the normal path
- full rebuild mode is the repair path

Reference UX target:
- `Local_Docs/diary.md` demonstrates the desired output style and information density
- it is a style reference only, not a gameplay storage path

Constraints:
- confirmed players diary runtime files must live in actual gameplay/runtime storage, not `Local_Docs`
- append/rebuild flows must use `.venv/bin/python`
- implementation must be KISS and avoid unnecessary DB modeling
- if append generation fails, the diary artifact must remain unmodified and the bookmark must not move forward
- the Journal GUI should render the confirmed diary artifact directly rather than reconstructing it from DB summary rows

## Goals / Non-Goals

**Goals**
- Produce an engaging, anonymous, fun fantasy chronicle for players.
- Append new diary content from unprocessed `journal.json` entries using bounded context.
- Keep confirmed diary generation simple and inspectable.
- Provide a repair/rebuild path that can regenerate the entire diary from `journal.json`.
- Render the confirmed diary markdown directly in the GUI.

**Non-Goals**
- Rewriting Story So Far in this slice.
- Turning confirmed Diary into another DB-first subsystem.
- Reusing `Local_Docs` for gameplay/runtime files.
- Solving every possible long-term style drift issue up front.

## Decisions

### Decision: Confirmed Diary becomes a markdown artifact, not DB summary rows
The confirmed players diary MUST be stored as a canonical runtime markdown file. The web GUI SHOULD render that markdown artifact directly for confirmed diary content.

Recommended runtime paths:
- `data/players_diary.md`
- `data/players_diary_bookmark.json`

Rationale:
- The successful local test already proved the artifact-first shape is the correct UX target.
- Markdown is inspectable, easy to repair, and aligns with the desired chronicle feel.
- This removes unnecessary row-level reconstruction complexity.

Alternatives considered:
- continue DB-backed confirmed diary rows: rejected because it keeps the player-facing output tied to the over-engineered model.
- store bookmark inside `journal.json`: rejected for now because the user prefers a clean journal source file and separate bookmark state is simpler to reason about operationally.

### Decision: Append mode is the default, rebuild mode is the repair tool
Normal operation MUST append new diary content from the unprocessed journal delta. Full diary regeneration from all journal entries MUST exist as an explicit rebuild/repair path, not the default update path.

Rationale:
- Full rewrite each update risks unnecessary drift and future context overload.
- Append mode keeps context bounded and style continuity stronger.
- Rebuild mode remains available when bookmark state or style quality needs repair.

Alternatives considered:
- full rewrite every update: rejected as normal behavior because it is unnecessary and risks whole-file drift.

### Decision: Bookmark file tracks progress through `journal.json`
The system MUST track the last processed journal index in a separate bookmark file under runtime storage.

Recommended payload:
```json
{
  "last_processed_index": 19,
  "updated_at": "2026-04-07T06:30:00Z"
}
```

Rationale:
- separate bookmark state keeps `journal.json` clean
- easier to rebuild, inspect, and reset independently
- minimal complexity compared to DB-backed progress tracking

### Decision: Append prompt uses bounded recent diary tail plus new journal delta only
The LLM SHOULD see:
- the current diary tail for style continuity
- only the new `journal.json` entries since the bookmark

It SHOULD NOT see the entire diary or the entire journal during normal append operations.

Rationale:
- bounded context prevents scale problems
- preserves tone continuity without full-file rewrite
- keeps the system operationally simple

### Decision: Prompt/output contract prioritizes UX over structure
The append prompt MUST optimize for the diary reading experience, not for database reconstruction.

Required output qualities:
- anonymous chronicler voice
- concise, pithy, fun
- faithful to journal facts
- markdown-only output suitable for append
- no JSON, no debug text, no rewrite of previous diary sections

The sample style and usefulness target is the local example in `Local_Docs/diary.md`.

#### Reference append prompt

```text
You are writing the Players Diary for an ongoing fantasy campaign.

Write as an anonymous chronicler recounting the party's journey in an engaging, concise, pithy, fun, fantasy-immersive style for players reading the in-game GUI.

Your job is to APPEND only the next diary section(s), based strictly on the new journal entries provided below.

Rules:
- Keep the same tone and style as the existing diary excerpt.
- Be faithful to the facts in the new journal entries.
- Do not invent events, outcomes, or character moments not supported by the journal entries.
- Do not rewrite, summarize, or repeat earlier diary content except where needed for a smooth transition.
- Output markdown only.
- Do not output JSON, notes, commentary, headers like "Here is the update", or system text.
- Do not mention prompts, journal files, bookmarks, or metadata.
- Prefer vivid, readable prose over exhaustive detail.
- Keep sections clean and GUI-friendly.

Existing diary tail for style continuity:
<DIARY_TAIL>

New journal entries to incorporate:
<JOURNAL_DELTA>

Return only the new markdown to append.
```

#### Reference rebuild prompt

```text
You are writing the Players Diary for an ongoing fantasy campaign.

Write as an anonymous chronicler recounting the party's journey in an engaging, concise, pithy, fun, fantasy-immersive style for players reading the in-game GUI.

Using the full journal chronology below, generate the complete current Players Diary as a polished markdown chronicle.

Rules:
- Be faithful to the journal events.
- Group events naturally into readable diary sections.
- Keep the tone lively, immersive, and player-facing.
- Do not invent plot developments not supported by the journal.
- Output markdown only.
- Do not output JSON, notes, commentary, or system text.
- Keep the result readable in a game GUI.

Full journal chronology:
<JOURNAL_FULL>

Return only the complete markdown diary.
```

### Decision: Keep draft/live-session diary behavior separate
The new confirmed players diary markdown flow SHOULD coexist with any retained draft/live-session diary surface. Draft behavior should not force the confirmed artifact into a DB-backed shape.

Rationale:
- draft and confirmed serve different jobs
- avoids another round of overcoupling

## Workflow

### Normal append workflow
1. Load `journal.json.entries`.
2. Load `data/players_diary_bookmark.json`.
3. Determine unprocessed journal delta.
4. If no new entries exist, do nothing.
5. Load `data/players_diary.md`.
6. Extract bounded tail context from the diary for style continuity.
7. Prompt the LLM to append only the next diary section(s) based on the new journal delta.
8. Validate output.
9. Append to `data/players_diary.md`.
10. Update the bookmark.

### Repair/rebuild workflow
1. Load all `journal.json.entries`.
2. Prompt the LLM to regenerate the full diary markdown artifact in the target style.
3. Replace `data/players_diary.md` atomically.
4. Set bookmark to the latest journal index.

## Validation Rules

Append mode must enforce:
- if generation fails, do not modify the diary file
- if generation fails, do not advance the bookmark
- output must be markdown append content only
- output must not duplicate the already-present recent tail verbatim

Rebuild mode must enforce:
- atomic replacement of the full diary artifact
- bookmark reset to the last journal entry index on success

## Risks / Trade-offs

- [append drift accumulates over many sessions] -> keep full rebuild tool available and keep prompt style tail bounded.
- [bookmark mismatch causes duplicated or skipped sections] -> validate bookmark against current journal length and optionally store a minimal integrity marker if needed later.
- [GUI rendering differs from intended markdown style] -> keep markdown contract simple and inspectable.
- [attempting to preserve old DB confirmed diary behavior causes scope creep] -> explicitly treat this change as a replacement UX path for confirmed diary reading, not an extension of the row-based model.

## Migration Plan

1. Add runtime artifact paths for confirmed players diary markdown and bookmark state.
2. Add append generator service from `journal.json` -> markdown append.
3. Add full rebuild service from `journal.json` -> complete markdown replacement.
4. Add web route to return the confirmed players diary markdown artifact.
5. Update Journal GUI confirmed diary view to render the markdown artifact.
6. Keep any existing draft UI separate.
7. Add focused tests for append, rebuild, bookmark, and GUI rendering.

## Open Questions

- Should normal append mode always produce exactly one appended section per update, or allow multiple sections when the new journal delta spans multiple clear locations/scenes?
- Should the confirmed diary route return raw markdown only, or return markdown plus lightweight metadata such as last updated timestamp?
- Should rebuild mode reuse the same prompt family as append mode or use a slightly richer full-chronicle prompt tuned to the `Local_Docs/diary.md` reference output?
