## Context

The current prewarm monster path in `scripts/homebrew_prewarm_portraits.py` calls character portrait generation and then materializes monster media from portrait outputs. This couples monster prewarm to character portrait write paths and prompt style, causing both wrong imagery and module contamination.

The repository already has reusable monster media in static/bestiary locations (including `_video.mp4`) and a monster-specific generator in toolkit code. The preferred architecture is therefore:

- Reuse existing monster media first (module/static/bestiary), video-first.
- Generate only when necessary and explicitly allowed.
- Keep generated media in monster media lanes only.

## Goals

1. Prevent monster prewarm from writing to character portrait paths.
2. Use bestiary/static monster assets first, with deterministic resolution order.
3. Keep paid generation opt-in and monster-specific when used.
4. Include video assets in media handles so downstream UI has consistent handle coverage.

## Non-Goals

1. No automatic cleanup of already-contaminated portrait files from older runs.
2. No redesign of UI media rendering logic.
3. No changes to NPC prewarm path in this change.

## Decisions

### 1) Monster prewarm source chain is reference-first, not copy-first

- MUST resolve monster media via ordered lookup before generation:
  1) module media (`modules/<slug>/media/monsters`)
  2) static media (`web/static/media/monsters`)
  3) graphic packs / toolkit-managed monster assets (if available)
  4) provider fallback only with `--allow-provider`

- SHOULD avoid unnecessary duplication when static references already satisfy module runtime.

### 2) Monster generation fallback uses monster generator path only

- MUST not call `portrait_service.generate_and_save_portrait()` for monsters.
- MUST use monster-specific generation flow for fallback creation.

### 3) Video support in handles

- MUST add mp4 scan support for monster media handles (`*_video.mp4`).
- SHOULD preserve existing deterministic handle ordering and source_ref dedupe behavior.

## Risks and Mitigations

1. **Risk:** Legacy assumptions that handles are image-only.
   - Mitigation: additive handle kinds/fields for video while preserving existing fields for images.

2. **Risk:** Mixed asset locations (module/static) complicate reporting.
   - Mitigation: explicit stage summary with `reused_module`, `reused_static`, `generated`, `missing` counts.

3. **Risk:** Provider path regressions.
   - Mitigation: targeted tests for provider-disabled and provider-enabled behavior.

## Migration Plan

1. Refactor monster branch in prewarm script to reuse-first chain.
2. Add monster generator fallback integration behind `--allow-provider`.
3. Add video scanning support in media handles script.
4. Add regression tests and run verification gates.

Rollback:
- Revert prewarm monster branch to prior behavior and disable video handle additions.
