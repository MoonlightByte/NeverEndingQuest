# Executor Prompts: tt-mechanical-followthrough-hardening

## Execution Contract

MUST:
- Keep this change narrowly scoped to transcript-proven follow-through gaps: scene gifts, malformed ops compatibility, feature depletion, truth-surface visibility, and pre-combat hostile presence.
- Preserve legacy prose fallback for `updateCharacterInfo` when structured ops are absent or genuinely ambiguous.
- Preserve ambiguity fail-safe behavior for item assignment and feature matching.
- Keep host-file edits additive and mark required host hooks with `# TABLETOP MODE:` comments.
- Keep Python-visible output ASCII-only.
- Use transcript-driven tests before runtime behavior changes.
- Stop and report if scope expands into broad loot parsing, generic encounter redesign, or model-routing rearchitecture.

SHOULD:
- Prefer helper extraction before modifying nested control flow in `main.py` or `core/managers/combat_manager.py`.
- Apply one anchored patch at a time, then re-run `py_compile` before the next patch.
- Treat raw-input action-prediction hygiene as optional final cleanup, not a blocker for the state-follow-through slice.

## Prompt 1 - Contract Locks First (Tasks 1.1-1.2)

Implement tasks 1.1 through 1.2 only.

Goal:
- Lock the transcript-proven drift cases and OpenSpec deltas before changing runtime behavior.

Scope:
- Add focused tests for:
  1. Maelo-style narrated gifts that SHOULD reconcile later,
  2. malformed nested ops that MUST normalize later,
  3. Rage-style feature depletion that MUST become deterministic,
  4. pre-combat hostile scene presence that MUST appear separately from party NPCs.
- Write the spec delta files for all listed new/modified capabilities.
- It is acceptable for the new runtime expectation tests to fail before implementation.

Verification gate before continuing:
- `python3 -m py_compile <changed_test_files>`
- Run the new/extended tests and record which failures are expected pre-implementation.

## Prompt 2 - Ops Compatibility and Feature Usage (Tasks 2.1-2.2)

Implement tasks 2.1 through 2.2 only.

Scope:
- `updates/update_character_info.py`
- prompt/runtime contract tests touched by the ops contract
- any tiny helper needed for ops normalization

Required:
- Normalize unambiguous legacy nested-op wrappers into canonical flat ops.
- Add deterministic feature-usage ops for `classFeatures[].usage`.
- Preserve mixed `changes + ops` compatibility and conservative fallback behavior.
- Do not implement scene gift reconciliation or UI work yet.

Verification gate before continuing:
- `python3 -m py_compile updates/update_character_info.py <changed_test_files>`
- Run the touched ops contract tests.

## Prompt 3 - Scene Gift Reconciliation (Task 2.3)

Implement task 2.3 only.

Scope:
- `main.py`
- one new helper under `utils/` if that keeps `main.py` edits small

Required:
- Reconcile only explicit, safe narrated gifts/transfers.
- Preserve explicit action precedence.
- Fail safe when recipient or item identity is ambiguous.
- Do not broaden into general loot parsing.

Verification gate before continuing:
- `python3 -m py_compile main.py <helper_files> <changed_test_files>`
- Run the new scene-gift tests plus any touched narrator/runtime regressions.

## Prompt 3A - Generic Scene-Gift Detector Refactor (Tasks 2.4-2.5)

Implement tasks 2.4 through 2.5 only.

Goal:
- Replace any transcript-specific or NPC-specific scene-gift hardwire with a reusable generic detector for explicit transfer language.

Scope:
- `utils/scene_item_reconcile.py`
- `main.py` only if call-site behavior or logging must change
- touched regression tests under `scripts/`

Required:
- Remove hard-wired dependency on specific NPC/module names such as `Maelo`.
- Build the detector from current scene and party context:
  - current location NPCs as scene actors,
  - party members and party NPCs as valid recipients,
  - canonical short-name resolution for recipients.
- Support only narrow explicit transfer patterns such as:
  - `X gives Y a Z`
  - `X hands Y the Z`
  - `Y takes the Z`
  - `Y receives the Z`
  - `A and B take a ward stone each`
- Require all of the following before synthesizing inventory actions:
  - known actor,
  - known recipient,
  - concrete item phrase,
  - explicit or safely defaultable quantity,
  - no matching explicit `inventory_add` already present.
- Preserve explicit action precedence and fail safe on vague reward language.

Forbidden:
- Do not build a general loot parser.
- Do not infer gifts from broad narration like `the party receives supplies`.
- Do not widen into plot, encounter, or party-composition inference.

Edit Strategy:
- Apply one anchored patch at a time, then re-run `py_compile` before the next patch.

Verification gate before continuing:
- `python3 -m py_compile utils/scene_item_reconcile.py main.py <changed_test_files>`
- Run touched tests proving:
  - generic named-actor transfer works,
  - `takes/receives` recipient-driven phrasing works,
  - `each` split distribution works,
  - vague reward phrasing remains a no-op,
  - no remaining runtime dependency on `Maelo`-specific gating.

## Prompt 4 - Truth Surface Alignment (Tasks 3.1-3.2)

Implement tasks 3.1 through 3.2 only.

Scope:
- `utils/validator_truth_pack.py`
- `core/managers/combat_manager.py`
- `utils/multi_pc_dm_note.py`

Required:
- Surface nested feature usage from live `classFeatures[].usage`.
- Surface live-schema inventory/equipment/ammunition visibility instead of deprecated `inventory.items` assumptions.
- Keep summaries compact and bounded.

Verification gate before continuing:
- `python3 -m py_compile utils/validator_truth_pack.py core/managers/combat_manager.py utils/multi_pc_dm_note.py <changed_test_files>`
- Run the touched truth-pack and DM Note regressions.

## Prompt 5 - Pre-Combat Hostile Scene Presence (Tasks 4.1-4.2)

Implement tasks 4.1 through 4.2 only.

Scope:
- `web/extensions/tabletop_socket_handlers.py`
- `web/templates/game_interface.html`

Required:
- Emit `location_hostiles` separately from `party_npcs`.
- Render hostiles in the pre-combat strip only when no active encounter owns the strip.
- Keep hostile scene presence visually and semantically distinct from party/encounter state.

Verification gate before continuing:
- `python3 -m py_compile web/extensions/tabletop_socket_handlers.py`
- `node --check web/templates/game_interface.html` or equivalent repo syntax path
- Run the new pre-combat hostile visibility regression.

## Prompt 6 - Final Verification (Tasks 5.1-5.3)

Required checks:
- `python3 -m py_compile main.py updates/update_character_info.py utils/validator_truth_pack.py utils/multi_pc_dm_note.py core/managers/combat_manager.py web/extensions/tabletop_socket_handlers.py <changed_test_files>`
- Run all new/extended regression scripts for this slice
- `openspec validate tt-mechanical-followthrough-hardening`

Report format:
- Files changed
- Commands run
- PASS/FAIL per gate
- Which gift/reconcile cases now canonicalize
- Which ops normalize vs still fail safe
- Which resource usages now update deterministically
- Which pre-combat hostiles now appear in the strip
