## Why

Current homebrew monster prewarm uses the character portrait service for monster entities. This causes two critical issues:

1. Cross-module contamination: portrait writes go to active module portrait directories unrelated to target ingest slug.
2. Wrong visual outputs: monster prompts are routed through character-sheet style portrait prompts, producing humanoid/PC-like art.

For ingest workflows, we need deterministic monster media behavior that prefers existing bestiary/static assets (including video), and only falls back to provider generation through monster-specific tooling when explicitly allowed.

## What Changes

- Switch monster prewarm to a reuse-first source chain that references existing bestiary/static monster media before generation.
- Remove monster dependence on `portrait_service.generate_and_save_portrait()`.
- Keep provider generation opt-in only; when enabled, use monster-specific generator fallback.
- Add video-aware media handle support so monster `_video.mp4` assets are represented in manifests.

## User Decisions Applied

- Bestiary/static reference-first behavior is preferred over copying by default.
- Manual cleanup of already-contaminated portrait artifacts is out of scope for this change (operator-managed).

## Capabilities

### New capability: `homebrew-monster-prewarm-reuse-first`

- Monster prewarm SHALL resolve from module/static monster media first, with video-first preference.
- Monster prewarm SHALL NOT write to `web/static/portraits` or active module `portraits/` paths.

### Modified capability: `homebrew-ingest-media-cost-guard`

- Provider generation remains explicit opt-in only.
- If provider is enabled and no reusable media exists, fallback SHALL use monster generator path, not character portrait path.

### New capability: `homebrew-monster-video-handle-support`

- Media handle generation SHALL include monster video assets (`*_video.mp4`) as deterministic handles.

## Impact

- Improves visual correctness for monsters.
- Prevents cross-module write contamination during ingest prewarm.
- Reduces unnecessary generation cost by reusing existing bestiary/static monster assets.
