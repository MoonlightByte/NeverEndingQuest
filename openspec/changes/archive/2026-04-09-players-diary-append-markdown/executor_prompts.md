# Builder Prompt - Players Diary Append Markdown

Implement the `players-diary-append-markdown` change with a strict KISS mindset.

## Goal

Build a player-facing confirmed diary that behaves like the successful reference artifact in `Local_Docs/diary.md`, but uses real gameplay/runtime storage and web GUI integration.

The confirmed diary should:

1. read `journal.json` as source of truth
2. append only new diary content during normal updates
3. keep a separate bookmark file
4. store the confirmed diary as a markdown artifact in runtime storage
5. render that artifact directly in the Journal GUI

Do not overengineer this. The UX outcome matters more than DB elegance.

## Non-Negotiables

1. Do NOT use `Local_Docs` for gameplay/runtime files.
2. Do NOT mutate `journal.json` with diary bookmark state.
3. Do NOT rebuild the entire diary during normal append updates.
4. Do NOT reintroduce a DB-heavy confirmed-diary model as the primary UX surface.
5. Use `.venv/bin/python` for all dependency-sensitive commands.

## Required Runtime Targets

Use runtime paths under `data/`, for example:

- `data/players_diary.md`
- `data/players_diary_bookmark.json`

If you choose different names, keep them equally simple and runtime-appropriate.

## Implementation Shape

### Normal update path
1. Load `journal.json.entries`.
2. Load bookmark state.
3. Compute unprocessed journal delta.
4. If no new entries, do nothing.
5. Load existing diary markdown.
6. Extract bounded recent tail for style continuity.
7. Ask the LLM to append only the next diary section(s) in the same anonymous fantasy chronicler voice as the reference example.
8. Validate output.
9. Append to markdown file.
10. Advance bookmark only on success.

### Rebuild path
1. Read all of `journal.json`.
2. Generate full diary markdown in the same target style.
3. Replace the runtime diary artifact atomically.
4. Reset bookmark to latest journal index.

## Prompt Contract

The append and rebuild prompt(s) must target the same UX qualities demonstrated by `Local_Docs/diary.md`:

- anonymous chronicler voice
- concise
- pithy
- fun
- fantasy immersive
- faithful to events in `journal.json`
- markdown output suitable for GUI rendering

The model should not output:

- JSON
- debug text
- system notes
- rewritten prior diary content during append mode

Use these reference prompts unless implementation testing reveals a small wording adjustment is clearly necessary.

### Reference append prompt

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

### Reference rebuild prompt

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

## GUI Contract

The Journal GUI should render confirmed diary content from the markdown artifact directly.

If the current draft/live-session diary surface remains, keep it separate rather than forcing confirmed markdown into the row-based DB display model.

## Verification

Run with `.venv/bin/python`:

1. compile checks for touched Python files
2. focused append/rebuild tests
3. route/render tests
4. manual smoke pass in the GUI

## Review Standard

When finished, the resulting in-game confirmed Diary should feel obviously closer to the reference `Local_Docs/diary.md` than to the prior DB-backed confirmed diary summaries.

If an implementation choice increases complexity without clearly improving the player-facing diary reading experience, do not do it.
