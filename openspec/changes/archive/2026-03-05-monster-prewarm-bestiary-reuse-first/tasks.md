## 1. Monster Prewarm Reuse-First Refactor

- [x] 1.1 Refactor monster branch in `scripts/homebrew_prewarm_portraits.py` to resolve existing media before generation.
- [x] 1.2 Implement deterministic monster source order: module media -> static media -> graphic-pack/toolkit assets -> provider fallback.
- [x] 1.3 Enforce no monster writes to `web/static/portraits` or active module `portraits/` paths.
- [x] 1.4 Add stage counters for reuse/generation paths in prewarm result payload.

## 2. Monster Generation Fallback Hardening

- [x] 2.1 Replace monster use of character portrait service with monster-specific generator fallback path.
- [x] 2.2 Keep provider generation behind `--allow-provider` only.
- [x] 2.3 Ensure provider-disabled runs report skip/degraded without generation calls.

## 3. Video Handle Support

- [x] 3.1 Update `scripts/homebrew_media_handles.py` to scan monster `*_video.mp4` assets.
- [x] 3.2 Add deterministic handle metadata for video assets while preserving current handle behavior for images.
- [x] 3.3 Ensure no regression in existing image handle generation and ordering.

## 4. Regression Coverage

- [x] 4.1 Add/extend tests for monster prewarm reuse-first resolution and no portrait-path contamination.
- [x] 4.2 Add tests for provider-disabled vs provider-enabled monster fallback behavior.
- [x] 4.3 Add tests for video handle inclusion and dedupe stability.

## 5. Verification

- [x] 5.1 Run compile checks: `python3 -m py_compile scripts/homebrew_prewarm_portraits.py scripts/homebrew_media_handles.py`.
- [x] 5.2 Run targeted tests added/updated for this change.
- [x] 5.3 Run smoke commands on `Night_of_the_Restless_Dead` and confirm:
  - no monster writes to portrait lanes,
  - monster media resolved from reuse chain when available,
  - provider fallback only when explicitly enabled.
- [x] 5.4 Run `openspec validate monster-prewarm-bestiary-reuse-first`.
