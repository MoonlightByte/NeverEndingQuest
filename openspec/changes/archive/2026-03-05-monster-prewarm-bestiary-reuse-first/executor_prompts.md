## Kimi Builder Execution Prompts - monster-prewarm-bestiary-reuse-first

---

## Execution Contract

- MUST keep provider image generation opt-in only (`--allow-provider`).
- MUST keep monster prewarm out of portrait write lanes (`web/static/portraits`, active module `portraits`).
- MUST preserve existing NPC prewarm behavior unless explicitly scoped.
- MUST keep Python-visible text ASCII-only.

---

## Prompt 1 - Monster Reuse-First Refactor

Implement tasks 1.1-1.4.

Scope:
- `scripts/homebrew_prewarm_portraits.py`

Requirements:
- Refactor monster flow to resolve media from module/static/pack sources first.
- Prefer video asset (`*_video.mp4`) when available.
- Record source-path counters in payload.
- Ensure monster path does not call character portrait write flow.

Verify:
- `python3 -m py_compile scripts/homebrew_prewarm_portraits.py`

---

## Prompt 2 - Monster Generator Fallback

Implement tasks 2.1-2.3.

Scope:
- `scripts/homebrew_prewarm_portraits.py`
- monster toolkit integration points only as needed

Requirements:
- Provider fallback for monsters must route through monster generator path.
- Keep provider disabled default behavior unchanged.
- Output clear counters for generated vs reused vs missing.

Verify:
- `python3 -m py_compile scripts/homebrew_prewarm_portraits.py`

---

## Prompt 3 - Video Handles

Implement tasks 3.1-3.3.

Scope:
- `scripts/homebrew_media_handles.py`

Requirements:
- Include `*_video.mp4` scanning for monster media handles.
- Preserve deterministic ordering and dedupe semantics.
- Keep image handle behavior unchanged.

Verify:
- `python3 -m py_compile scripts/homebrew_media_handles.py`

---

## Prompt 4 - Tests and Final Verification

Implement tasks 4.1-5.4.

Scope:
- Targeted tests in `scripts/`

Required commands:
- `python3 -m py_compile scripts/homebrew_prewarm_portraits.py scripts/homebrew_media_handles.py`
- run targeted tests added for this change
- smoke on `Night_of_the_Restless_Dead`
- `openspec validate monster-prewarm-bestiary-reuse-first`

Smoke checklist:
1. Monster prewarm does not write to portrait lanes.
2. Existing static/bestiary monster assets are reused first.
3. Provider fallback only used when `--allow-provider`.
4. Video handles appear in media handles output when videos exist.
