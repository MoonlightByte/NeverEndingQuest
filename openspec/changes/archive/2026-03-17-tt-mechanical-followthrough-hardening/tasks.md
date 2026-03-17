## 1. Contract and Regression Locks

- [X] 1.1 Add focused source-contract and transcript-driven tests for narrated Maelo-style item gifts, malformed nested ops normalization, Rage-style feature depletion, and pre-combat hostile scene presence; verify with `python3 -m py_compile <changed_test_files>`.
- [X] 1.2 Add spec deltas for new capabilities (`tt-scene-item-grant-reconcile`, `tt-pre-combat-hostile-scene-presence`, `tt-dm-note-mechanical-visibility`) and modified capabilities (`tt-structured-character-ops-contract`, `tt-validator-mechanical-truth-pack`, `tt-combat-validator-mechanical-truth-pack`).

## 2. Structured Ops and Scene Gift Follow-Through

- [X] 2.1 Update `updates/update_character_info.py` so runtime normalizes canonical legacy nested-op wrappers into flat `op` records and adds deterministic class-feature usage ops; verify with `python3 -m py_compile updates/update_character_info.py`.
- [X] 2.2 Update prompt/runtime contract touchpoints so canonical feature-usage ops are documented and malformed nested-op drift is covered by regression tests without breaking prose fallback; verify by running the touched contract tests.
- [X] 2.3 Add a narrow scene item grant reconcile path in `main.py` (or a helper it calls) that synthesizes safe inventory updates for explicit narrated gifts/transfers before history refresh/action follow-through; verify with `python3 -m py_compile main.py <helper_files>`.
- [X] 2.4 Replace any transcript-specific or NPC-specific scene-gift hardwire with a generic explicit transfer detector driven by current scene actors, canonical recipient resolution, and ambiguity-safe transfer patterns; verify with `python3 -m py_compile main.py utils/scene_item_reconcile.py`.
- [X] 2.5 Expand regression coverage from Maelo-only gift handling to generic explicit transfer patterns (`gives`, `hands`, `takes`, `receives`, `each`) plus vague-reward no-op cases; verify by running the touched scene-gift tests.

## 3. Truth Surface Alignment

- [X] 3.1 Update `utils/validator_truth_pack.py` and `core/managers/combat_manager.py` truth-pack helpers so nested `classFeatures[].usage` and live-schema inventory/equipment/ammunition data are surfaced correctly; verify with `python3 -m py_compile utils/validator_truth_pack.py core/managers/combat_manager.py`.
- [X] 3.2 Update `utils/multi_pc_dm_note.py` so active-PC and compact party summaries expose bounded live inventory/resource visibility from the actual character schema; verify with `python3 -m py_compile utils/multi_pc_dm_note.py`.

## 4. Pre-Combat Hostile Scene Presence

- [X] 4.1 Extend `web/extensions/tabletop_socket_handlers.py` to emit a separate `location_hostiles` payload sourced from current-location `monsters` when no active encounter controls the strip; verify with `python3 -m py_compile web/extensions/tabletop_socket_handlers.py`.
- [X] 4.2 Update `web/templates/game_interface.html` to render pre-combat hostiles in the top strip without conflating them with party NPCs or combat encounter entries; verify with `node --check web/templates/game_interface.html` or the repository's current JS syntax-check path.

## 5. Verification

- [X] 5.1 Run targeted compile checks for all touched Python files and targeted regression scripts covering gifts, ops normalization, truth-pack parity, DM Note visibility, and hostile pre-combat presence.
- [X] 5.2 Run `openspec validate tt-mechanical-followthrough-hardening`.
- [X] 5.3 SHOULD perform one gameplay smoke pass covering: Maelo gift scene -> Kira potion use -> Chronos Rage spend -> Gorvek pre-combat parlay visibility.
- [X] 5.4 SHOULD perform one second gameplay smoke pass or scripted narrative check proving the scene-gift detector works without Thornwood/`Maelo`-specific phrasing.

## SHOULD Notes

- SHOULD switch action-prediction inspection to raw player input rather than DM-note-augmented conversation text if the touched logging/routing surfaces are already open during this slice.
