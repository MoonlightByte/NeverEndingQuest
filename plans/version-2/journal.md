# Journal Diary MVP Phase 1 Plan

Status: Ready for review (MVP only)  
Owner: Kimi Builder  
Target: `plans/version-2/journal.md`  
Scope: Implement a two-point diary model (Start Game draft + Save confirmed), Diary tab in Journal UI, and on-demand "Story so far" PDF download from confirmed entries only.

---

## 1) Objective

Deliver a stable MVP that provides:

1. Automatic Diary refresh on Start Game (draft state).
2. Automatic Diary confirmation on Save (canonical state tied to save branch).
3. Journal modal tabs for Quests and Diary.
4. "Download the story so far..." button in Diary tab.
5. PDF generated from confirmed diary/history only (draft excluded).

This MVP must prove end-to-end behavior and preserve existing gameplay/save flows.

---

## 2) MVP boundaries

### In scope (Phase 1 MUST)
- Save-triggered confirmed diary entries.
- Start Game-triggered draft diary refresh check.
- Diary tab UI with confirmed + current draft visibility.
- PDF endpoint + download flow.
- Third-person anonymous diary style.
- World-time ordering.
- Failure-safe behavior (save never fails because diary fails).

### Out of scope (Phase 2 SHOULD later)
- Map-reduce long-form multi-pass compilation.
- Async queue workers.
- Advanced PDF typography/chapter art.
- Deep cache optimization/fingerprinting strategy beyond basic.
- Background periodic diary generation.

---

## 3) Contract Layer (MUST)

1. `SaveGameManager.create_save_game()` MUST trigger confirmed diary checkpoint generation.
2. `start_game` socket handler MUST trigger diary freshness check and optional draft update.
3. Save failures and diary failures MUST be isolated; diary failure MUST NOT fail save.
4. Diary entries MUST be third-person anonymous narrative.
5. Diary ordering MUST be by game-world time.
6. Journal Quests behavior MUST remain unchanged.
7. "Story so far" PDF MUST exclude draft diary entries.
8. All host-file integration edits MUST be marked with `# TABLETOP MODE:`.
9. All Python output/log strings added in this work MUST be ASCII-only.
10. SP mode and TABLETOP MODE MUST both continue to function.

---

## 4) Guidance Layer (SHOULD)

1. Prefer additive files in `core/memory/` and route extensions in `web/routes/`.
2. Reuse existing LLM provider factory (`create_chat_client`, `get_model_config`).
3. Use bounded source windows for summary prompts to limit latency.
4. Implement deterministic fallback summary if LLM errors/timeouts.
5. Keep one draft row active at a time to avoid UI clutter.

---

## 5) UX model (MVP)

### 5.1 States

- `draft`: current unsaved session summary candidate.
- `confirmed`: save-bound canonical diary entry.
- `failed`: generation failed but system stayed operational.

### 5.2 User-visible behavior

1. User clicks Start Game:
   - Server checks if history advanced since last diary sync.
   - If changed, generate/update draft diary entry.
   - Journal Diary shows "Current Session (Unsaved Draft)" at top.

2. User clicks Save:
   - Save executes as normal.
   - Server generates confirmed diary entry tied to `save_id`.
   - Draft covered by this save window is superseded/cleared.
   - Journal Diary shows new confirmed entry in timeline.

3. User exits without save:
   - Confirmed timeline unchanged.
   - Next Start Game re-checks history and regenerates/updates draft.

4. User clicks "Download the story so far...":
   - PDF builds from confirmed entries only (no draft).
   - Download starts from Diary tab action.

---

## 6) Source-of-truth and checkpoints

- Raw source events: `journal_entries` and/or `memory_events` in memory DB.
- Current game-world clock: `party_tracker.json -> worldConditions`.
- Save branch identity: `save_id` from save metadata.
- Checkpoint control: single-row state tracking processed event bounds.

Checkpoint rules:
1. Draft checkpoint advances on successful draft generation.
2. Confirmed checkpoint advances on successful save-bound generation.
3. Confirmed checkpoint is authoritative for canon timeline.
4. PDF uses confirmed checkpoint/timeline only.

---

## 7) Data model changes (MVP)

Add migration in `core/memory/memory_db.py`.

### 7.1 `session_diary_entries`
Columns:
- `diary_id INTEGER PRIMARY KEY AUTOINCREMENT`
- `status TEXT NOT NULL`  // draft|confirmed|failed
- `save_id TEXT`          // nullable for draft
- `draft_key TEXT`        // nullable; unique active draft identity
- `world_year INTEGER NOT NULL`
- `world_month TEXT NOT NULL`
- `world_month_index INTEGER NOT NULL`
- `world_day INTEGER NOT NULL`
- `world_time TEXT NOT NULL`
- `world_sort_key INTEGER NOT NULL`
- `summary TEXT NOT NULL`
- `source_start_event_id INTEGER`
- `source_end_event_id INTEGER`
- `source_counts_json TEXT NOT NULL DEFAULT '{}'`
- `generation_mode TEXT NOT NULL DEFAULT 'llm'` // llm|fallback
- `llm_model TEXT`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`

Indexes:
- `(status, world_sort_key DESC, diary_id DESC)`
- `(save_id)` unique where not null
- `(draft_key)` unique where not null

### 7.2 `session_diary_state`
Single-row checkpoint table:
- `state_id INTEGER PRIMARY KEY CHECK(state_id = 1)`
- `last_draft_event_id INTEGER NOT NULL DEFAULT 0`
- `last_confirmed_event_id INTEGER NOT NULL DEFAULT 0`
- `last_confirmed_save_id TEXT`
- `last_draft_key TEXT`
- `updated_at TEXT NOT NULL`

### 7.3 `story_so_far_cache` (minimal MVP)
- `cache_id INTEGER PRIMARY KEY AUTOINCREMENT`
- `confirmed_fingerprint TEXT NOT NULL UNIQUE`
- `pdf_path TEXT NOT NULL`
- `created_at TEXT NOT NULL`
- `confirmed_count INTEGER NOT NULL DEFAULT 0`

Note: fingerprint includes only confirmed rows.

---

## 8) Backend modules and responsibilities

### 8.1 New: `core/memory/session_diary.py`
Functions:
- `compute_world_sort_key(world_conditions) -> int`
- `get_latest_source_event_id(conn) -> int`
- `refresh_draft_if_stale(db_path, world_conditions) -> Dict[str, Any]`
- `confirm_diary_for_save(db_path, save_id, world_conditions) -> Dict[str, Any]`
- `list_diary_entries(db_path, include_draft=True, limit=20, before_sort_key=None)`
- `build_fallback_summary(source_events) -> str`

Rules:
- Keep at most one active draft row.
- Draft creation is idempotent using `draft_key`.
- Confirmed creation is idempotent by `save_id`.
- Save path never raises hard failure on diary generation exception.

### 8.2 New: `core/memory/story_so_far_compiler.py`
Functions:
- `build_confirmed_story_text(db_path) -> Dict[str, Any]`
- `render_story_pdf(story_text, output_path) -> str`
- `get_or_build_story_pdf(db_path) -> Dict[str, Any]`

Rules:
- Query confirmed rows only.
- Draft rows are excluded by WHERE clause.
- If LLM fails, compile deterministic fallback narrative from confirmed entries.

### 8.3 Update: `core/memory/__init__.py`
Export diary and story compiler helpers.

### 8.4 Update: `updates/save_game_manager.py`
Integrate `confirm_diary_for_save(...)` inside `create_save_game(...)`.

Integration rule:
- Wrap diary confirm in guarded try/except.
- Save result remains success if diary step fails.
- Attach diary status to save metadata message block.

---

## 9) API and socket integration

### 9.1 Web socket: `start_game`
File: `web/web_interface.py`

Add in `handle_start_game()` after thread start:
- Load current world conditions.
- Call `refresh_draft_if_stale(...)`.
- Emit optional system notification only on meaningful draft update.
- Do not block game start on diary failure.

### 9.2 REST routes in `web/routes/memory_routes.py`

#### GET `/api/journal/diary`
Returns:
- confirmed entries
- optional top draft entry
- pagination cursor

Response shape:
```json
{
  "status": "success",
  "draft": {
    "diary_id": 1,
    "status": "draft",
    "summary": "...",
    "world": {
      "year": 1492,
      "month": "Springmonth",
      "day": 3,
      "time": "19:09:00",
      "sort_key": 14920403190900
    }
  },
  "entries": [
    {
      "diary_id": 2,
      "status": "confirmed",
      "save_id": "uuid",
      "summary": "...",
      "world": {
        "year": 1492,
        "month": "Springmonth",
        "day": 3,
        "time": "18:40:00",
        "sort_key": 14920403184000
      }
    }
  ],
  "next_before_sort_key": null
}
```

#### GET `/api/journal/story-so-far/pdf`
Behavior:
- build/reuse cache from confirmed fingerprint
- return attachment download
- safe JSON error response on failure

---

## 10) UI implementation (`web/templates/game_interface.html`)

1. Keep existing Journal modal and Quests rendering.
2. Add tab controls:
   - Quests
   - Diary
3. Diary panel behavior:
   - render draft card first when present:
     - title: `Current Session (Unsaved Draft)`
   - render confirmed timeline list under it.
4. Add button in Diary panel:
   - `Download the story so far...`
5. Button click:
   - disable while processing
   - fetch PDF endpoint
   - trigger browser download
   - re-enable button on completion/failure

No new gameplay/session-control buttons.

---

## 11) Prompt contracts (MVP)

### 11.1 Draft/confirmed diary prompt
Constraints:
- third-person
- anonymous narrator
- no direct player address
- no first-person diary voice
- no mechanics hallucination
- compact prose

Output:
- 1 to 2 short paragraphs, plain text only.

### 11.2 Story PDF prompt
Constraints:
- "The story so far..." narrative tone
- preserve chronology and major canon events
- confirmed entries only

Output:
- plain text sections suitable for PDF body.

---

## 12) Failure handling and invariants

1. Save path invariant:
   - save success independent from diary success.
2. Start path invariant:
   - game starts even if draft refresh fails.
3. PDF invariant:
   - draft excluded always.
4. Data invariant:
   - max one active draft row.
5. Idempotency invariant:
   - same `save_id` cannot create duplicate confirmed entries.

---

## 13) File-level task checklist (MVP only)

### M1 - DB migration
- [ ] Add MVP tables/indexes in `core/memory/memory_db.py`.
- [ ] Register migration id in ordered migration set.
- [ ] Add migration smoke check script snippet if needed.

### M2 - Diary service
- [ ] Create `core/memory/session_diary.py`.
- [ ] Implement draft refresh and save confirm functions.
- [ ] Implement world-time normalization and sort key logic.
- [ ] Implement fallback summary path.

### M3 - Save integration
- [ ] Update `updates/save_game_manager.py` to call `confirm_diary_for_save(...)`.
- [ ] Ensure try/except isolation and metadata status annotation.

### M4 - Start Game integration
- [ ] Update `web/web_interface.py:handle_start_game()` for draft freshness check.
- [ ] Add guarded non-blocking call and logging.

### M5 - Routes
- [ ] Extend `web/routes/memory_routes.py`:
  - [ ] `/api/journal/diary`
  - [ ] `/api/journal/story-so-far/pdf`
- [ ] Ensure route registration remains intact in `web/web_interface.py`.

### M6 - Story compiler + PDF
- [ ] Create `core/memory/story_so_far_compiler.py`.
- [ ] Confirm query excludes draft entries.
- [ ] Build simple cached PDF generation path.

### M7 - Journal UI
- [ ] Add Quests/Diary tabs in `web/templates/game_interface.html`.
- [ ] Add diary list rendering and draft card.
- [ ] Add download button and fetch/download logic.

### M8 - Tests and validation
- [ ] Add `scripts/test_session_diary_mvp.py`.
- [ ] Add `scripts/test_story_so_far_pdf_mvp.py`.
- [ ] Run compile checks.
- [ ] Run manual smoke.

---

## 14) Verification plan

### 14.1 Compile
`python3 -m py_compile core/memory/memory_db.py core/memory/session_diary.py core/memory/story_so_far_compiler.py updates/save_game_manager.py web/routes/memory_routes.py web/web_interface.py`

### 14.2 Automated checks
1. Draft refresh runs on start and creates/updates one draft row.
2. Save creates one confirmed row tied to save_id.
3. Duplicate save_id does not duplicate confirmed row.
4. Draft remains excluded from PDF source query.
5. Save still succeeds when diary generation is forced to fail.
6. Start Game still responds `game_started` when draft generation fails.

### 14.3 Manual smoke
1. Start game -> open Diary -> draft visible.
2. Save -> draft replaced/superseded by confirmed entry.
3. Exit without save after new actions -> restart -> draft refreshes.
4. Download story PDF -> includes confirmed timeline, excludes draft.
5. Quests tab unchanged and functional.

---

## 15) Time estimate (MVP Phase 1)

- M1-M2: 1.5 to 2.0 days
- M3-M5: 1.0 to 1.5 days
- M6-M7: 1.0 to 1.5 days
- M8 + smoke fixes: 0.5 to 1.0 day

Total: 4 to 6 days

---

## 16) Acceptance criteria (MVP exit gate)

1. Diary updates at two points:
   - Start Game (draft refresh)
   - Save (confirmed checkpoint)
2. Confirmed entries are branch-safe and tied to save_id.
3. Story PDF excludes draft entries by design.
4. Save and Start Game remain robust under LLM failures.
5. Journal Quests behavior has no regression.
6. MVP runs in SP and TABLETOP MODE.
