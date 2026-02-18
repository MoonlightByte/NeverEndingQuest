## Why

Character and party visuals are uneven in live tabletop sessions.

- Character Sheet currently supports portrait upload but not one-click create.
- Missing NPC media causes repeated warning floods in server logs.
- Allied NPC companions often appear without portraits even though they are long-lived party members.
- Promotion flows (NPC -> PC) rely on name identity and should preserve visual continuity.

We need a merge-safe UX enhancement that improves portrait reliability without changing combat or save semantics.

## What Changes

- Add Character Sheet `Upload / Create` portrait action.
- Add portrait create backend endpoint and shared portrait generation service.
- Add optional appearance fields (`age`, `height`, `weight`, `eyes`, `skin`, `hair`) to character schema and creation defaults.
- Add missing-media auto-generation queue for allied NPC companions only.
- Add missing-media warning throttling to reduce repeated warning spam.
- Add reuse-first NPC media registration so allied misses reuse existing portraits before any provider generation call.
- Add canonical dedupe across NPC image variants (`_thumb`/full) to prevent duplicate generation.
- Add always-open full-profile modal on Character Sheet `Create` to let players amend portrait-driving profile data each time.
- Enforce required portrait profile completeness for create submissions:
  - Appearance: `age`, `height`, `weight`, `eyes`, `skin`, `hair`
  - Personality/Background: `personality_traits`, `ideals`, `bonds`, `flaws`, `backgroundFeature.name`, `backgroundFeature.description`
- Expand portrait prompt composition to include personality and background context in addition to appearance metadata.
- Preserve module-first media lookup and existing fallback behavior.

### Non-goals

- No automatic generation for non-allied NPCs in MVP.
- No automatic generation for monsters in MVP.
- No broad redesign of party/combat UI layouts.
- No rewrite of toolkit pack activation/copy pipeline.
- No change to upload portrait semantics.

## Capabilities

### New Capabilities

- `pc-sheet-upload-create-portrait`
- `allied-npc-missing-media-autogen`
- `missing-media-warning-throttle`
- `appearance-fields-for-portrait-prompts`

### Modified Capabilities

- None.

## Impact

- Affected code:
  - `web/web_interface.py`
  - `web/templates/game_interface.html`
  - `web/templates/partials/character_tabs.html`
  - `schemas/char_schema.json`
  - `utils/character_creation_audit.py`
  - `web/routes/tabletop_party_routes.py`
  - `model_config.py`
  - `core/toolkit/portrait_service.py` (new)
  - `web/extensions/missing_media_autogen.py` (new)
  - `scripts/test_pc_image_create_mvp.py` (new)
- APIs/system surfaces:
  - New endpoint: `POST /api/portrait/create`
  - `POST /api/portrait/create` accepts full profile payload and fail-closed validation for required portrait profile fields.
  - Existing `/media/<media_type>/<filename>` behavior gains warning throttle and allied-only enqueue hook.
- Dependencies:
  - Reuses existing image generation/toolkit infrastructure.
- Rollout risk:
  - Medium (web UI + media serving + background generation).
- Fallback strategy:
  - If create fails: keep existing image and return safe error.
  - If create profile is incomplete: return safe validation error and do not generate.
  - If auto-gen worker fails: keep fallback chain render and continue gameplay.
  - If policy concerns emerge: disable auto-gen via config flag.
- Merge-safety/SP-MP impact:
  - Additive extension-first path with minimal host hooks and `# TABLETOP MODE:` markers.
  - Single-player behavior remains valid.
