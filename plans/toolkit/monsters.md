# Runtime Monster Seeding Plan (Combat Start Reliability + Authoring Loop)

Status: Draft for implementation
Priority: High
Date: 2026-02-24
Owner: Tabletop combat + content pipeline
Target: `plans/monsters.md`

---

## 1) Objective

Fix the recurring "narrative combat without actual combat start" failure by adding a safe runtime monster seeding pipeline that:

1. Preserves strict anti-hallucination behavior.
2. Allows valid location-declared monsters to resolve even when module-local monster files are missing.
3. Optionally uses AI generation as a controlled fallback for declared encounter points.
4. Creates reusable monster files so encounter points improve over time.

This plan addresses the exact observed failure pattern:
- Narrator emits `createEncounter`.
- Combat builder runs.
- Module monster file missing.
- Tabletop hallucination guard blocks auto-create.
- Encounter creation fails and narration loops at commitment point.

---

## 2) Problem summary and root cause

Current behavior is strict in TABLETOP MODE:

1. `core/generators/combat_builder.py` tries module-local file via `ModulePathManager.get_monster_path(...)`.
2. If not found and `MULTIPLAYER_MODE=True`, it returns `None` and refuses auto-creation.
3. `createEncounter` aborts, so `party_tracker.worldConditions.activeCombatEncounter` is never set.
4. Narration continues to describe combat commitment with no combat manager handoff.

This is not only bad authoring. It is a contract mismatch:
- Module area data can legitimately declare monsters in location JSON.
- Runtime currently requires separate module monster files to exist first.

Result: valid encounter intent can be blocked by missing file materialization.

---

## 3) Product direction

### 3.1 Must
- TABLETOP MODE must continue blocking undeclared hallucinated monsters.
- Declared encounter monsters should not fail just because module monster files are missing.
- Combat start should be deterministic: either succeed with explicit source data, or fail with explicit reason before looping.
- Existing single-player behavior must remain backward compatible.

### 3.2 Should
- Runtime should improve module quality over time by materializing reusable files.
- AI generation should be optional and tightly scoped.
- All new writes should be atomic and auditable.

---

## 4) Proposed architecture

Introduce a new resolver pipeline in combat builder:

`resolve_monster_for_encounter(monster_name, location_id, module_name) -> {status, source, monster_data, error}`

Resolution order:

1. `module_file` (existing behavior)
   - Load `modules/<module>/monsters/<normalized>.json`.
   - If valid, use it.

2. `declared_compendium_seed` (new deterministic fallback)
   - Verify monster is declared in current location area JSON `locations[].monsters[]`.
   - Load from `data/bestiary/monster_compendium.json`.
   - Build schema-compliant monster payload with deterministic defaults.
   - Atomically write module-local monster file.
   - Use seeded data.

3. `declared_ai_seed` (new optional fallback)
   - Only if still missing and monster is location-declared.
   - Only if config toggle allows.
   - Call `monster_builder.py` once.
   - Validate against schema, then atomically write file.
   - Mark provenance metadata as AI-generated.

4. `block` (strict safety)
   - If monster is not location-declared or all allowed sources fail, return explicit failure.

Key principle:
- No declaration -> no generation.
- Declaration unlocks controlled seeding.

---

## 5) Runtime policy and config contract

Add config controls (recommended in `model_config.py`, mirrored in template docs):

1. `TABLETOP_MONSTER_SEEDING_MODE = "declared_compendium"`
   - Options:
     - `strict` (current behavior)
     - `declared_compendium` (recommended default)
     - `declared_compendium_then_ai`

2. `TABLETOP_MONSTER_AI_SEED_REQUIRES_REVIEW = True`
   - Adds metadata for review queue/tooling.

3. `TABLETOP_MONSTER_SEED_WRITE_ENABLED = True`
   - If false, allow in-memory use only (diagnostic mode).

Recommended rollout defaults:
- Start with `declared_compendium` only.
- Enable AI seeding only after deterministic path proves stable.

---

## 6) Data contracts

### 6.1 Declaration gate
Monster is "declared" if normalized name matches any `locations[current].monsters[].name`.

Normalization contract:
- Reuse existing normalization logic from `format_type_name(...)` and character-name utilities where applicable.
- Singular/plural tolerance should be deterministic (ex: `shadows` -> `shadow`).

### 6.2 Seeded monster schema payload
Seed output must satisfy monster schema consumed by combat builder/manager.

Required minimum fields for encounter viability:
- `name`
- `hitPoints`
- `armorClass`
- `challengeRating` (if schema requires)
- attack/effect fields required by downstream combat prompts

Deterministic defaults:
- If compendium lacks stat fields, use safe conservative placeholders and mark provenance.

### 6.3 Provenance metadata
Add optional metadata on seeded files:
- `_tabletop_seed_source`: `module_file|compendium|ai`
- `_tabletop_seed_ts`: ISO timestamp
- `_tabletop_seed_location`: location id
- `_tabletop_seed_needs_review`: bool

These fields must be schema-compatible. If schema blocks unknown fields, keep metadata in a sidecar log instead.

---

## 7) Implementation plan by phase

## Phase 1 - Deterministic declared-compendium seeding (MUST)

### 7.1 Code changes

1. `core/generators/combat_builder.py`
   - Add resolver helpers:
     - `_is_monster_declared_at_location(monster_name, location_id, module_name)`
     - `_load_monster_from_compendium(monster_name)`
     - `_materialize_module_monster_file(monster_name, monster_data, module_name)`
     - `_resolve_monster_for_encounter(...)`
   - Replace direct `load_or_create_monster` branch in encounter generation with resolver pipeline.
   - Keep current strict block path for undeclared monsters.

2. `utils/module_path_manager.py` (optional helper)
   - Add path helper for area file lookup by location id if needed.

3. `core/ai/action_handler.py`
   - Improve returned error payloads to include resolver failure reason and source.
   - Keep existing fail-closed combat abort for zero-enemy encounter files.

4. `modules/logs/game_errors.log` instrumentation path
   - Standardize error categories:
     - `monster_resolution_declared_missing`
     - `monster_resolution_compendium_seeded`
     - `monster_resolution_blocked_undeclared`

### 7.2 Behavior goals
- `Shadow` at AB05 should seed and start combat.
- `Scarecrow` at AB01 should still block if undeclared.

### 7.3 Verification
- Add targeted tests for:
  - declared + missing module file + present in compendium -> success
  - undeclared + missing module file -> blocked
  - declared + compendium missing + ai disabled -> blocked with explicit reason

---

## Phase 2 - Optional declared-AI seeding (SHOULD)

### 7.4 Code changes
1. `core/generators/combat_builder.py`
   - Add optional AI fallback path after compendium miss.
   - Enforce declaration gate before AI call.
   - Respect `TABLETOP_MONSTER_SEEDING_MODE`.

2. `core/generators/monster_builder.py`
   - Ensure generated output includes mandatory combat fields for immediate encounter use.

3. Add review marker output/logging.

### 7.5 Safety constraints
- One AI attempt max per monster per encounter request.
- Add short cooldown cache key: `(module, location, monster_name)`.
- If AI generation fails once, do not retry in same turn loop.

### 7.6 Verification
- declared + compendium miss + AI enabled + builder success -> combat starts
- declared + AI fail -> explicit abort, no loop spam

---

## Phase 3 - Pre-seed tooling and authoring loop (SHOULD)

### 7.7 New tooling
Add script: `scripts/seed_module_monsters_from_areas.py`

Purpose:
- Scan all area location `monsters[]` declarations.
- Materialize missing module monster files from compendium.
- Optionally invoke AI for declared misses (flagged review).

Modes:
- `--dry-run`
- `--apply`
- `--module <name>`
- `--allow-ai`

### 7.8 UX value
This creates exactly the "build encounter points over time" workflow:
- authored declaration -> runtime/tool seeding -> reusable module files -> fewer runtime surprises.

---

## 8) Detailed file-level scope

Primary files:
- `core/generators/combat_builder.py` (main logic)
- `core/ai/action_handler.py` (error payload clarity)
- `model_config.py` (new policy toggles)
- `config_template.py` (doc for toggles)
- `scripts/seed_module_monsters_from_areas.py` (new)
- `scripts/test_runtime_monster_seeding.py` (new targeted tests)

Possible helper updates:
- `utils/module_path_manager.py`
- `utils/encoding_utils.py` (if additional atomic helper wrappers are needed)

---

## 9) Testing strategy

### 9.1 Unit tests

1. Resolver declaration matching:
   - exact match
   - case-insensitive match
   - plural normalization

2. Compendium seeding:
   - compendium hit writes valid file
   - malformed compendium entry fails with explicit reason

3. Strict blocking:
   - undeclared monsters never seed/generate in TABLETOP MODE

### 9.2 Integration tests

1. AB05 Shadow commitment flow:
   - `createEncounter` emitted
   - encounter file created with enemies
   - `activeCombatEncounter` set
   - combat manager transition occurs

2. AB01 Scarecrow commitment flow:
   - remains blocked unless declared
   - user gets deterministic system error, no silent loop

3. Regression:
   - single-player path unchanged when strict/upstream mode selected

### 9.3 Manual smoke checklist

1. Run multi-PC session at AB05 with declared `Shadow`.
2. Trigger commitment narration and confirm immediate combat handoff.
3. Confirm seeded file appears in module monsters directory.
4. Repeat same encounter and confirm no reseed call (file reuse).
5. Trigger undeclared monster name and confirm block + clear reason.

---

## 10) Observability and diagnostics

Add structured logs in resolver:
- `MONSTER_RESOLVE start name=<n> location=<id> mode=<m>`
- `MONSTER_RESOLVE source=module_file success=1`
- `MONSTER_RESOLVE source=compendium_seed success=1 write=1`
- `MONSTER_RESOLVE source=ai_seed success=0 reason=<...>`
- `MONSTER_RESOLVE blocked undeclared=1`

Add user-safe system feedback for blocked cases:
- "Encounter blocked: creature '<name>' is not declared for this location."

---

## 11) Risk analysis

### Risk 1: Accidentally re-opening hallucinations
Mitigation:
- Hard declaration gate before any seeding/generation.
- Keep strict mode available.

### Risk 2: Bad AI-generated stats
Mitigation:
- Phase 1 deterministic compendium path first.
- AI path optional and review-flagged.
- Schema validation and bounded retries.

### Risk 3: Runtime write contention
Mitigation:
- Atomic writes only.
- Per-monster materialization lock if needed.

### Risk 4: Narrative loop still occurs on block
Mitigation:
- Explicit error payload and non-ambiguous system narration from Python side.

---

## 12) Acceptance criteria

Must pass:
1. Declared AB05 `Shadow` starts combat successfully even when module monster file was initially missing.
2. Undeclared monsters still fail closed in TABLETOP MODE.
3. No repeated commitment-point narration loop when encounter creation fails.
4. Encounter failure reasons are explicit in logs and surfaced safely to user.
5. Existing single-player behavior remains compatible.

Should pass:
1. Optional AI fallback can materialize declared monsters not present in compendium.
2. Seeder script can pre-materialize all declared monsters for a module.

---

## 13) Recommended rollout

Step 1 (safe default):
- Implement Phase 1 only (`declared_compendium` mode).

Step 2 (stability pass):
- Run focused gameplay tests on The_Pumpkin_Kings_Curse AB05 flow.

Step 3 (optional expansion):
- Enable `declared_compendium_then_ai` in a canary branch/session.

Step 4 (authoring ops):
- Use seeding script to backfill module monster files.

---

## 14) Notes on NPC creator idea

The same pattern is useful, but for this bug class the failing entities are monsters, not NPCs.

Recommendation:
- Apply runtime seeding to monster resolution first.
- Keep NPC generation pipeline separate (already exists in `load_or_create_npc`).
- Later, a similar declaration-gated seeding model can be designed for NPC encounter companions if desired.

Future expansion note:
- Once the `world-narrative` system is in place, extend this model so runtime declarations can come from evolving world-state (not only module area files).
- In that phase, world-narrative-declared NPCs and enemies can be materialized into game data via the same gated seeding pipeline and then added to active play.
- Safety rule remains the same: only declared entities from trusted sources (module data and validated world narrative state) are eligible for creation/materialization.
