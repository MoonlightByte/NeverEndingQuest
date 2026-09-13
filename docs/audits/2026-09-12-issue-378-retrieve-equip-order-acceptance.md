# Issue 378 ordered-actions trial: FAILED / NOT MERGEABLE

2026-09-12. Isolated worktree plan/374-local-cache-contract, baseline
8562e270dde6b94d05bb21b97ce7b51fb810baf4. Tested plan SHA-256:
37bd2df76d2e4fb542bde6a06ccf58beb976490b63eab9e98ac23eb306f281c7.
No commit, push, merge, or issue closure. Main and original game were not operated on.

## Evidence

Native Windows C:/Python312, real OpenAI, supported headless commands on copied
game /mnt/c/378-game-ucT2Vh; export /mnt/c/378-src-ZOhVtr.
Raw evidence: /mnt/c/378-ev-9mLWNY/A and A1.
Detailed report: /mnt/c/agent-room-fleet-kit/local-data/378-native-acceptance-report.md.
Static gates: /mnt/c/agent-room-fleet-kit/local-data/378-development-gates.md.

| Arm | Verdict | Proof |
| --- | --- | --- |
| Supported Load | PASS | A protocol 176: selected_applied; loaded state equals saved state |
| A1 retrieve then equip | PASS | A1 protocol 369 storage commit precedes T079; snapshot prompt-553 has sheet 1, cache 0 |
| A3 store roundtrip | FAIL | A1 protocol 847 store commit precedes unequip writer; prompt-1065 has sheet 1 plus cache 1 |
| A2 failure handback | BLOCKED / NOT RUN | Stopped on A3 conservation failure |
| A4 controls, A5 persistence, A6/A6b combat | BLOCKED / NOT RUN | No waiver or inferred pass |
| Quiescence | PASS | A1 protocol 1075-1082: supported Quit, ok, player_exit, process exit 0 |

A1 preserved the item's descriptive fields and quantity, changing equipped false
to true as intended. AC remained 18; this does not prove an AC increase. The
welcome's AC 16 statement was not supported by the loaded sheet. Do not generalize
the core A1 pass to every narration claim or unrelated AC semantics.

## Failure mechanism and attribution

T065[1] rejected duplicate inventory removal but explicitly invited a separate
equipment/AC-only update. T065[2] accepted storageInteraction store followed by
updateCharacterInfo unequip. Storage removed the shield from the sheet first.
T079[1..3] then saw an absent item and the unchanged add-absent writer recreated
it. Narration said one shield stored and not carried; disk contained two copies.
This is the reverse-transfer dependency exposed by the current #378 ordering
change, not an unrelated issue to defer. Earlier character-first code would order
these operations differently; conservation on that exact old-code candidate is a
counterfactual code argument, not a fresh live A/B proof.

Proposed next amendment ONLY: have the existing referee enforce the symmetric
ownership prerequisite: an update requiring an item still carried must precede
its outgoing transfer; incoming transfer precedes equipping a previously absent
item. No item-name rules, writer rewrite, automatic family-first order, or extra
model call. This proposal is NOT implemented or validated by this trial.

The failure snapshots were preserved through clean Quit. A native process query
after exit found no PID 33808, children of it, or python process with a 378 game
command. Other agents' games were not touched. Remaining arms must be run on a
revised reviewed candidate; this partial trial cannot authorize shipment.

Post-run integrity: all 836 original-game files listed in fixture-before-hashes.json
were rehashed and matched, with zero missing or changed files.
