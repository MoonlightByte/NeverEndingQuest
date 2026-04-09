**Change:** `scene-entity-combat-validity-contract`

**Builder Objective**

Implement a reusable scene-entity contract so authored location NPCs can remain visible and narratable without being implicitly combat-valid. Preserve monster authorization boundaries, add deterministic violence-resolution handling for incorporeal and helpless/nonresisting scene entities, and prove the pattern by annotating `Red (The Crimson Binder)` in `Night_of_the_Restless_Dead`.

**Global MUST Constraints**

- Keep all host-file edits minimal and marked `# TABLETOP MODE:`.
- Preserve existing monster authorization and hydration for true monsters.
- Do not widen unannotated location NPCs into combat targets.
- Keep additive metadata optional and backward compatible.
- Use atomic JSON operations and existing scene/background-NPC mutation paths where possible.
- ASCII only in Python user-facing console/log text.
- Edit Strategy: Apply one anchored patch at a time, then re-run `py_compile` before the next patch.

**Global SHOULD Guidance**

- Prefer one shared helper for scene-entity decisions over duplicating logic across action handling, combat build, and UI surfaces.
- Keep prompt changes narrow and targeted to scene-only versus escalatable routing.
- Limit first-pass module data changes to Red as the proving case.

---
**Step 1 Builder Prompt** (full variant)

Implement OpenSpec `scene-entity-combat-validity-contract` Step 1 only.

Goal: add the additive data contract and shared runtime helper for scene entities.

Allowed:
- `schemas/loca_schema.json`
- new `utils/scene_entity_contract.py`
- tests that only exercise the new helper/contract shape

Forbidden:
- combat flow rewrites
- prompt changes
- module data annotation
- encounter-schema redesign

Required:
- extend location NPC schema to allow optional `sceneEntity`
- support `combatValidity`, `manifestation`, `violencePolicy`, `combatProxy`
- helper must answer whether a current-scene entity is scene-only or escalatable
- helper must fail safely for missing or malformed metadata

Verify:
- `python3 -m py_compile schemas/loca_schema.json` is not applicable; validate touched Python only
- `python3 -m py_compile utils/scene_entity_contract.py`
- add targeted unit tests or source-contract tests for helper behavior

Output:
- files changed
- helper API surface
- test/compile evidence

**Verification Gate (after builder reports):**
- [ ] helper exists and is importable
- [ ] malformed metadata fails safe
- [ ] unannotated NPCs preserve legacy behavior

---
**Step 2 Builder Prompt** (full variant)

Implement Step 2 only.

Goal: add createEncounter guard and explicit scene-entity failure surfacing.

Allowed:
- `core/ai/action_handler.py`
- `core/generators/combat_builder.py`
- shared helper import sites
- targeted regression tests

Forbidden:
- broad combat-manager rewrites
- changing monster authority for real monsters

Required:
- detect current-scene entities with `sceneEntity` metadata before generic monster failure messaging
- emit dedicated non-combat-valid scene-entity error
- preserve existing unauthorized/hydration errors for true monster references
- remove or relocate any premature success log that fires before builder success is confirmed

Verify:
- `python3 -m py_compile core/ai/action_handler.py core/generators/combat_builder.py utils/scene_entity_contract.py`
- targeted regression proving Red-style scene-only rejection surfaces correctly

Output:
- exact failure class/message behavior
- evidence that true monster paths remain unchanged

**Verification Gate:**
- [ ] scene-only entity gets specific error
- [ ] generic monster failures still work
- [ ] no misleading success log remains

---
**Step 3 Builder Prompt** (full variant)

Implement Step 3 only.

Goal: add bounded violence-resolution runtime for scene entities.

Allowed:
- `main.py`
- `core/ai/action_handler.py`
- `utils/scene_entity_contract.py`
- existing scene/background NPC mutation helpers
- targeted tests

Forbidden:
- universal NPC combat system
- broad encounter-state redesign

Required:
- support `incorporeal_no_effect` without starting combat
- support `helpless_kill_else_escalate` using deterministic scene-state mutation when helpless/nonresisting
- require explicit `combatProxy` when escalation is needed; fail closed if absent

Verify:
- `python3 -m py_compile main.py core/ai/action_handler.py utils/scene_entity_contract.py`
- targeted tests for incorporeal no-effect and helpless-kill-else-escalate

Output:
- exact decision path for no-effect vs deterministic harm vs escalation
- evidence for fail-closed missing-proxy case

**Verification Gate:**
- [ ] incorporeal attack does not start combat
- [ ] helpless deterministic harm persists state
- [ ] missing proxy fails closed clearly

---
**Step 4 Builder Prompt** (full variant)

Implement Step 4 only.

Goal: align narrator and validator contracts with the new scene-entity rules.

Allowed:
- `prompts/system_prompt_compressed.txt`
- any mirrored prompt that already carries the same combat-routing contract
- prompt contract tests only

Forbidden:
- broad prompt rewrites
- non-scene-entity contract changes

Required:
- distinguish visible scene entities from combat-valid monsters
- allow narration-only no-effect resolution for incorporeal attacks
- keep createEncounter commitment rules intact for true combat-valid threats

Verify:
- prompt/source-contract tests
- no unrelated prompt sections changed

Output:
- exact contract lines added/changed
- evidence that existing combat rules remain intact

**Verification Gate:**
- [ ] prompt distinguishes scene-only vs combat-valid
- [ ] no broad combat prompt drift

---
**Step 5 Builder Prompt** (full variant)

Implement Step 5 only.

Goal: annotate Red and add proving-case regressions.

Allowed:
- `modules/Night_of_the_Restless_Dead/areas/NIG001.json`
- mirrored backup file if required by module data pattern
- targeted regression tests

Forbidden:
- broad module rewrites
- adding Red as a monster statblock

Required:
- annotate Red as scene-only, incorporeal, `incorporeal_no_effect`
- add tests proving Red remains visible but cannot enter combat
- keep existing module semantics intact otherwise

Verify:
- module schema validation for touched module
- targeted regression tests

Output:
- exact annotation block
- evidence that Red is visible and non-combat-valid

**Verification Gate:**
- [ ] Red remains present in scene
- [ ] Red attack resolves no-effect
- [ ] createEncounter with Red is blocked explicitly

---
**Final Verification Gate**

- `python3 -m py_compile <all touched python files>`
- relevant targeted tests green
- relevant schema validation green
- `openspec validate scene-entity-combat-validity-contract`

**Next Step Ready:** review artifacts and approve implementation sequencing
