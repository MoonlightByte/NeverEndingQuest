# PC Image Create UX Enhancement Plan

Status: Draft for review (openspec-plan-to-builder compliant)
Owner: Tabletop Mode
Date: 2026-02-16
Target: `plans/pc-image-create.md`
Scope: Add `Upload / Create` portrait UX, auto-generate missing images for allied NPC companions, and reduce missing-media warning noise while preserving module-first media behavior.

---

## Preflight (openspec-plan-to-builder)

Preflight: PASS

Checks:
- OpenSpec initialized: `openspec/config.yaml` present
- Frontier profile present: `openspec/frontier_builder_profile.md` present
- OpenCode command scaffolding present: `.opencode/command/*` present
- OpenCode openspec skills present: `.opencode/skills/openspec-*` present
- Two-layer contract present in config: MUST/SHOULD language present in `openspec/config.yaml` context/rules

---

## Builder Orchestration Contract

This plan follows step-gated execution for builder models.

Workflow loop:

```
Plan emits step prompt -> Builder executes ONE step -> Plan verifies -> Plan emits next step
```

Verification gates per step:
1. Syntax/compile
2. Behavior smoke
3. Compatibility/no-regression
4. Scope compliance (only intended files)

Verdict model:
- PASS -> proceed
- FAIL -> retry step with corrections
- NEEDS_FIX -> patch targeted issues before next step

---

## Objective

Implement a reliable portrait UX where:

1. Character Sheet portrait action becomes `Upload / Create`.
2. `Create` generates a portrait prompt from character data and saves portrait assets to canonical locations.
3. Missing portraits auto-generate for allied NPC companions only (party companions), not for all NPCs/monsters.
4. Non-allied NPCs and monsters use deterministic fallback image behavior without API spam.
5. Missing-media warning floods are throttled/aggregated.

---

## User Decisions Locked

1. Auto-generation policy:
   - Enabled for allied NPC companions only.
   - Disabled by default for non-allied NPCs and monsters.

2. Promotion behavior:
   - NPC -> PC promotion must preserve existing image linkage by name.

3. Fallback preference:
   - Keep module-first image lookup.
   - If module missing, fallback to active static media (which may come from activated graphic pack copy), then class/default portraits.

---

## Current Baseline (Confirmed)

1. Module-first media serving already exists in `web/web_interface.py` route `/media/<media_type>/<filename>` with priority:
   - current module media
   - other modules
   - `web/static/media`
   - 404 warning

2. NPC -> PC promotion currently preserves image linkage by shared name identity:
   - role fields changed in place
   - UI player tile already falls back to `/media/npcs/<name>.*` when static portrait missing

3. Activated graphic packs are copied into `web/static/media/*`, so pack assets participate in static fallback after activation.

4. Missing-media logs are currently emitted per miss and can flood warnings:
   - `warning("Media file not found in any location: ...")`

---

## Two-Layer Contract

## Contract Layer (MUST)

1. `Upload` portrait workflow MUST continue to work unchanged.
2. Character Sheet portrait control MUST expose both `Upload` and `Create` actions.
3. Auto-generation on miss MUST apply only to allied NPC companions (from `party_tracker.json -> partyNPCs`).
4. Non-allied NPC and monster misses MUST NOT trigger automatic generation by default.
5. Missing-media auto-generation MUST be asynchronous and MUST NOT block request/response paths.
6. Auto-generation queue MUST dedupe by asset key (name + media type + variant) and apply cooldown.
7. Promotion from NPC to PC MUST preserve existing media linkage by name.
8. If character JSON is unreadable/corrupt, portrait display MUST still fall back to module/static/default image pathing.
9. New Python logs/messages added by this work MUST be ASCII only.
10. Any host-file hooks for TABLETOP behavior MUST include `# TABLETOP MODE:` comments.
11. Character schema additions for appearance fields MUST be backward compatible (optional fields).
12. Existing single-player behavior MUST remain functional.
13. Existing party/initiative rendering paths MUST remain functional when auto-generation is disabled.
14. Missing-media warning output MUST be throttled/aggregated to prevent repeated spam for same missing key.
15. Portrait create failures MUST be failure-isolated and MUST NOT break gameplay/chat loops.

## Guidance Layer (SHOULD)

1. Reuse existing toolkit generators (`NPCGenerator`, `MonsterGenerator`) instead of creating another model client path.
2. Centralize portrait prompt composition in a dedicated service module.
3. Use appearance fields (`age`, `height`, `weight`, `eyes`, `skin`, `hair`) when present, and safe defaults when absent.
4. Prefer queue worker in web layer for miss-triggered generation to avoid blocking media endpoint.
5. Keep generation policy behind config flags so rollout can be tuned without code churn.
6. Emit concise system notifications only when generation starts/completes/fails meaningfully.

---

## MVP Scope

In scope:
- Character Sheet `Upload / Create` action
- Portrait prompt composition from character data + appearance fields
- Allied NPC auto-generation on miss with queue dedupe/cooldown
- Warning-throttle for missing media logs
- Backward-compatible schema/default updates for appearance fields

Out of scope (later phase):
- Full auto-generation for all enemies/non-allied NPCs
- Video generation for missing NPC/monster video assets
- Batch cinematic restyling pipeline across entire module
- Deep style-control UI in player-facing character sheet

---

## Architecture Design

## 1) Portrait Generation Service

Add new module:
- `core/toolkit/portrait_service.py`

Responsibilities:
- Build portrait prompts from character payload + optional appearance fields
- Normalize character identity/name for filenames
- Generate image through existing toolkit client patterns
- Save canonical outputs:
  - `web/static/portraits/<normalized_name>.png` (sheet)
  - `modules/<current_module>/media/npcs/<normalized_name>.jpg`
  - `modules/<current_module>/media/npcs/<normalized_name>_thumb.jpg`

Notes:
- For allied NPC auto-heal, this service should accept minimal data and still generate stable prompt
- For player create action, prioritize full character payload from active sheet

## 2) Missing Media Auto-Heal Queue

Add new module:
- `web/extensions/missing_media_autogen.py`

Responsibilities:
- In-memory dedupe set + TTL/cooldown map
- Worker thread that consumes generation tasks
- Policy filter:
  - allow only allied NPC companions when auto policy is enabled
  - reject non-allied NPCs/monsters for automatic generation
- Best-effort execution and error logging

Trigger point:
- Hook into `/media/npcs/<filename>` miss path in `serve_module_media`.

## 3) Warning Throttle

Modify `serve_module_media` in `web/web_interface.py`:
- Add missing-key memo + throttle window
- Log first miss as warning
- Subsequent misses within window as debug/info or suppressed count aggregation

## 4) Character Sheet UI

Modify `web/templates/game_interface.html`:
- Replace overlay text/button behavior with `Upload / Create`
- Add lightweight chooser modal/action list
- Keep existing upload flow function unchanged
- Add create flow:
  - POST to new endpoint
  - refresh portrait URL with cache busting

## 5) Create Portrait API

Add endpoint in `web/web_interface.py` (or extracted route module if preferred):
- `POST /api/portrait/create`

Request:
- `characterName`
- optional `style` / `model`

Behavior:
- Load character JSON if available
- Build prompt via portrait service
- Generate and persist outputs
- Return success payload with generated asset paths

## 6) Appearance Fields

Schema and defaults updates:
- `schemas/char_schema.json`: add optional fields
  - `age` (string or integer; implementation choice must be consistent)
  - `height` (string)
  - `weight` (string)
  - `eyes` (string)
  - `skin` (string)
  - `hair` (string)
- `utils/character_creation_audit.py`: include default empty values for optional appearance fields
- `web/routes/tabletop_party_routes.py`: include fields in manual create payload
- `web/templates/partials/character_tabs.html`: add form inputs for quick-create
- `web/templates/game_interface.html`: display values in character header/details area

Compatibility:
- Do not add new required fields
- Existing character files must validate and load unchanged

---

## Fallback Behavior Matrix

1. PC portrait in sheet:
   - `/static/portraits/<name>.png`
   - `/media/npcs/<name>.jpg`
   - `/media/npcs/<name>.png`
   - `/static/icons/default_portrait.png`

2. Party/initiative player tile:
   - `/static/portraits/<name>.png`
   - `/media/npcs/<name>_thumb.jpg`
   - `/media/npcs/<name>.jpg`
   - `/media/npcs/<name>.png`
   - empty/default tile style

3. NPC tile:
   - `/media/npcs/<name>_thumb.jpg`
   - class fallback portrait in static

4. Monster tile:
   - `/media/monsters/<type>_thumb.jpg/.png`
   - singular/plural fallback variants
   - no auto-generation in MVP

---

## Config Flags (Proposed)

Add to `model_config.py`:

1. `AUTO_GENERATE_ALLIED_NPC_IMAGES = True`
2. `AUTO_GENERATE_NON_ALLIED_NPC_IMAGES = False`
3. `AUTO_GENERATE_MONSTER_IMAGES = False`
4. `MISSING_MEDIA_LOG_THROTTLE_SECONDS = 300`
5. `MISSING_MEDIA_AUTOGEN_COOLDOWN_SECONDS = 900`

Notes:
- Defaults should match locked policy from this plan.

---

## File Plan

Files to add:
1. `core/toolkit/portrait_service.py`
2. `web/extensions/missing_media_autogen.py`
3. `scripts/test_pc_image_create_mvp.py`

Files to modify:
1. `web/web_interface.py`
2. `web/templates/game_interface.html`
3. `web/templates/partials/character_tabs.html`
4. `schemas/char_schema.json`
5. `utils/character_creation_audit.py`
6. `web/routes/tabletop_party_routes.py`
7. `model_config.py`

---

## Step-by-Step Builder Execution

## Step 1 - Appearance Field Scaffolding

Goal:
- Add optional appearance fields across schema/defaults/manual-create/UI display.

Acceptance:
- Existing characters still validate
- New fields visible on sheet header/details

Verification:
- `python3 -m py_compile utils/character_creation_audit.py web/routes/tabletop_party_routes.py web/web_interface.py`
- `python3 core/validation/validate_module_files.py`

## Step 2 - Portrait Service and Create Endpoint

Goal:
- Implement portrait generation service and `POST /api/portrait/create`.

Acceptance:
- Create call generates portrait assets and returns success payload
- Existing upload route still works

Verification:
- `python3 -m py_compile core/toolkit/portrait_service.py web/web_interface.py`
- manual smoke: create portrait from character sheet, confirm file writes

## Step 3 - Character Sheet Upload/Create UX

Goal:
- Add UI chooser and create action path.

Acceptance:
- User can select Upload or Create
- Generated portrait refreshes immediately

Verification:
- manual smoke: Upload path unchanged
- manual smoke: Create path completes and image updates in sheet

## Step 4 - Missing-Media Warning Throttle

Goal:
- Prevent repeated warning floods for same missing media key.

Acceptance:
- First miss logs warning
- repeated misses in throttle window are reduced/aggregated

Verification:
- manual smoke: repeated requests for same missing key produce throttled logs

## Step 5 - Allied NPC Auto-Heal Queue

Goal:
- Auto-generate missing media only for allied NPC companions.

Acceptance:
- missing allied NPC image enqueues one generation task
- non-allied NPC and monster misses do not auto-generate in MVP
- gameplay remains non-blocking

Verification:
- `python3 -m py_compile web/extensions/missing_media_autogen.py web/web_interface.py`
- manual smoke: remove allied NPC image, verify generation then render
- manual smoke: remove monster image, verify no auto-generation trigger

## Step 6 - Regression and Policy Validation

Goal:
- Validate promotion and fallback invariants.

Acceptance:
- NPC -> PC promotion retains image linkage
- corrupt/missing character JSON still allows fallback image render for tiles
- single-player behavior unchanged

Verification:
- `python3 scripts/test_pc_image_create_mvp.py`
- `python3 scripts/test_multi_pc_combat.py`
- targeted manual smoke (sheet, party display, initiative display)

---

## Manual Smoke Checklist

1. Character sheet:
   - open active PC sheet
   - click `Upload / Create`
   - test both actions

2. Allied NPC auto-heal:
   - remove one allied NPC thumb file from module/static
   - refresh party/initiative display
   - verify background generation and image appears on next refresh

3. Promotion invariance:
   - promote NPC companion to PC via Manage Party
   - verify portrait still resolves through existing fallback chain

4. Non-allied/monster policy:
   - force missing image for non-allied NPC or monster
   - verify fallback render only, no auto-generation call

5. Log behavior:
   - repeat same missing asset request
   - verify warning throttle suppresses flood

---

## Risks and Mitigations

1. API cost spikes from repeated misses
   - Mitigation: strict dedupe + cooldown + allied-only policy

2. Main thread blocking on generation
   - Mitigation: queue worker thread only, never generate inside media request path

3. Filename mismatch across name normalization variants
   - Mitigation: centralize normalization in portrait service and reuse same key strategy as UI fallbacks

4. Character JSON corruption causing sheet failures
   - Mitigation: failure-isolated rendering fallback for portrait paths; graceful UI messaging for missing stats payload

5. Merge divergence in host files
   - Mitigation: mark hooks with `# TABLETOP MODE:` and keep extension modules for core logic

---

## Rollback Plan

If rollout issues appear:

1. Set `AUTO_GENERATE_ALLIED_NPC_IMAGES = False` to disable auto-heal while keeping new UI create action.
2. Keep warning throttle active (safe regardless of generation policy).
3. If needed, disable create endpoint path in UI and preserve upload-only behavior.

No data migrations are destructive in this plan; appearance fields are optional.

---

## OpenSpec Change Skeleton (Suggested)

Change name:
- `pc-image-create-and-allied-npc-autogen`

Candidate capabilities:
1. `pc-sheet-upload-create-portrait`
2. `allied-npc-missing-media-autogen`
3. `missing-media-warning-throttle`
4. `appearance-fields-for-portrait-prompts`

This plan is ready for conversion into OpenSpec proposal/design/specs/tasks or direct builder step prompts.
