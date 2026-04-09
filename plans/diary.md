# Diary Plan (Reconciled)

Status: Reconciled to current architecture (2026-04-09)
Owner: OpenCode Builder
Scope: Confirmed Players Diary architecture, implementation status, and next implementation steps.

---

## 1) Why this reconciliation exists

Diary work was implemented quickly across multiple slices, and this plan drifted from the actual shipped architecture.

This document now reflects the code that exists in the repository and defines what is still pending.

---

## 2) Current architecture (authoritative)

### 2.1 Confirmed diary is artifact-first

Confirmed Players Diary is now a markdown artifact, not a DB-row-first surface:

- Source of truth: `journal.json`
- Confirmed artifact: `data/players_diary.md`
- Bookmark state: `data/players_diary_bookmark.json`

Primary implementation:

- `core/memory/players_diary.py`
  - `append_players_diary_from_journal(...)`
  - `rebuild_players_diary_from_journal(...)`
  - `get_or_update_players_diary(...)`

### 2.2 GUI rendering prefers confirmed markdown artifact

- Route payload includes confirmed markdown artifact in `players_diary`
  - `web/routes/memory_routes.py`
- Journal Diary tab renders markdown directly when available
  - `web/templates/game_interface.html`

### 2.3 Draft diary remains separate

Draft and checkpointed DB diary path still exists and remains additive:

- `core/memory/session_diary.py`
  - `refresh_draft_if_stale(...)`
  - `confirm_diary_for_save(...)`
  - `confirm_diary_for_exit(...)`

This separation is intentional:

1. Confirmed diary = player-facing chronicle artifact
2. Draft diary = live runtime/session utility

---

## 3) OpenSpec reconciliation matrix

### 3.1 `players-diary-append-markdown`

Status: Implemented in code; tasks reconciled to reflect shipped behavior.

Covered behaviors:

1. runtime artifact and bookmark files under `data/`
2. append-only update from unprocessed journal delta
3. bounded tail continuity context
4. rebuild/repair mode
5. bookmark safety on append failure
6. dedicated API route and GUI rendering path
7. focused append/rebuild tests and operator script

Remaining item before archive:

- manual smoke pass (quality comparison in live GUI)

### 3.2 `players-diary-journal-cadence-hardening`

Status: Pending implementation.

Not yet wired in current runtime:

1. additive transition/long-rest checkpoint metadata written to `journal.json`
2. shared idempotency keys for transition + long-rest journal checkpoints
3. long-rest journal checkpoint hook after successful long rest
4. duplicate/no-delta suppression specific to long-rest cadence

Current transition journaling remains the existing path in:

- `main.py`
- `core/ai/cumulative_summary.py`

---

## 4) Source-of-truth contract

Confirmed diary contract:

1. `journal.json` is canonical gameplay chronology input.
2. Confirmed GUI surface is `data/players_diary.md`.
3. Bookmark state controls append delta and prevents accidental full rewrites.
4. Rebuild mode is explicit repair/reset, not normal operation.

Draft diary contract:

1. Draft remains independent from confirmed markdown artifact.
2. Draft must stay fail-open and non-blocking for Start/Save/Exit flows.

---

## 5) Next implementation path

### Phase A (complete now)

Finalize and archive `players-diary-append-markdown` after manual smoke verification.

### Phase B (next build)

Implement `players-diary-journal-cadence-hardening` with strict scope:

1. preserve transition checkpoint writes
2. add long-rest checkpoint trigger post-success
3. add deterministic checkpoint identity metadata
4. suppress duplicate/no-delta long-rest checkpoints
5. keep fail-open behavior (rest success never blocked)

### Phase C (follow-up quality pass)

After cadence hardening lands:

1. validate diary freshness during extended same-location play
2. tune prompt/fallback quality only if needed
3. avoid reintroducing DB-heavy confirmed diary architecture

---

## 6) Acceptance criteria (reconciled)

This plan is successful when:

1. Confirmed Diary in GUI is driven by `data/players_diary.md` generated from `journal.json`.
2. Append mode updates only unprocessed journal delta and never rewrites prior diary text.
3. Bookmark does not advance when append generation fails.
4. Rebuild mode can regenerate the full confirmed diary artifact safely.
5. Draft Diary remains available as a separate runtime surface.
6. Journal cadence includes transitions and long rests with idempotent suppression.

---

## 7) Verification commands

Use `.venv/bin/python` for dependency-sensitive paths.

Core verification:

```bash
.venv/bin/python -m py_compile core/memory/players_diary.py web/routes/memory_routes.py scripts/rebuild_players_diary.py scripts/test_players_diary_append_markdown.py
.venv/bin/python scripts/test_players_diary_append_markdown.py
.venv/bin/python scripts/test_journal_diary_ui_mvp.py
```

Cadence-hardening verification (next phase) should add dedicated tests for:

1. transition checkpoint identity metadata
2. long-rest checkpoint creation
3. duplicate suppression
4. no-delta suppression
5. fail-open rest success when journal generation degrades

---

## 8) Archive gate

Do not consider diary work fully closed yet.

Archive sequence:

1. archive `players-diary-append-markdown` after manual smoke pass
2. implement and validate `players-diary-journal-cadence-hardening`
3. archive cadence-hardening change

Only after both are archived should this diary plan be considered fully complete.
