# #378 bidirectional trial - conservation PASS for Shield, FAIL for Chain Mail

Historical stopped trial: verdicts below are unchanged. Next-step design is
superseded by `2026-09-12-issues-385-386-step-local-correction-plan.md`, approved
after nine-seat convergence under #193 D-385386-1. New acceptance is separate.

2026-09-12. NOT MERGEABLE; no third wording trial, no further product edits.
Tested amendment SHA398ab5b0ec8738099ef059bd54e051b193b549a80ee48e1fd945327adfde596e.
Isolated plan/374-local-cache-contract, HEAD8562e270 (main unchanged).
Real native C:/Python312, configured OpenAI, one operator, no state edits.
Source /mnt/c/378b-src-JnImTW; copied game /mnt/c/378b-game-v6yRhy;
evidence /mnt/c/378b-ev-ewtWHx/A and A1. Detailed operator report:
/mnt/c/agent-room-fleet-kit/local-data/378-bidirectional-native-report.md.

## Actual implementation and gates

Only the previously reviewed C1b paragraph was replaced in both full/compressed
validator prompts. Python runtime unchanged from first trial: main8a91522b,
action_handler9bfd7cae. Full prompt9fb0c4e3, compressed9a2a266a;
normalized compressed36493dd6 observed in T065. No new item-specific code, model
call, schema or writer change. Eight blind seats clean, fresh simplifier NO
CHANGE, actual-diff/sentinels/static27 gates/native compile PASS. Those are
development checks, not substitutes for the following live verdicts.

## Per-operation results

| Operation | Verdict | Snapshot/capture evidence |
| --- | --- | --- |
| Supported Load original save | PASS | A selected_applied then restart exit0; authentic save_20260912_103037 |
| Retrieve/equip Shield | Conservation/order PASS | prompt110 ->553: sheet0/cache1 ->sheet1/cache0; T049 before T079 |
| Unequip/store Shield | Conservation/order PASS, wrong-order check FIRING PASS | T065[1] rejects store-first; T067[3] corrects; T065[2] accepts; prompt1060 sheet0/cache1 |
| Repeat retrieve/equip Shield | Conservation/order PASS; AC narration FAIL (#349) | prompt1557 sheet1/cache0, full record; T051[2] independently adds unowned Defense bonus, disk19 versus narrated18 |
| Repeat unequip/store Shield | Conservation/order PASS | Correct first candidate, T065[4]; prompt2049 sheet0/cache1 |
| Unequip/store owned Chain Mail | FAIL: quantity1 ->0 | T079[4] quantity0; T049[4] cannot store missing item; prompt2661 no Chain Mail in sheet or any cache |
| Failed-store handback | Mechanism FIRED; overall recovery/PX FAIL | Old plot sibling skipped; fresh T067[8] actions[]; its prior-state assertion is false because earlier writer already removed the item |
| Remaining second-item retrieval, A2 explicit unavailable retrieval, A4/A5/A6 | BLOCKED / NOT RUN | Stopped at second conservation failure; initial Load is not Save/turn/Load proof |
| Clean Quit | PASS | A1 input006 378b-stop-quit, process_exit0; native PID15416 and child/378b process query empty |

The Shield record keeps all nine fields through four transfers, changing
equipped as intended. Its count remains1 at all five snapshots110/553/1060/1557/2049.
That does not establish correctness of unrelated armor calculations or general
inventory safety. Captures expose requested selection labels, not actual returned
response.model: UNKNOWN. Full validator prompt and browser were not exercised.

## Second failure: exact boundary, not another order inversion

Input005 asks to store the genuinely owned Chain Mail but also mentions a padded
tunic absent from the sheet. T065[5] correctly rejects the invented armor bonus;
the accepted retry uses unarmored AC12 instead. That separate correction does not
explain or excuse deleting the genuinely owned Chain Mail.

Accepted T067[7] array is [updateCharacterInfo, storageInteraction, updatePlot].
The first changes string mixes the current step with the intended final state:
"Unequip Chain Mail before storage. Eirik carries neither Chain Mail nor Shield
and has no established worn armor. Set armor class to unarmored AC 12 using
Dexterity 14." T065[6] accepts the order and says no duplicate movement.
T079[4] outputs equipment[{item_name:Chain Mail,equipped:false,quantity:0}], AC12.
The unchanged merge_equipment_arrays removes zero-quantity items. T049[4] asks
to store Chain Mail1, but its input sheet no longer contains it. Protocol2496-2498
records the missing-item failure. Both canonical locations lack Chain Mail at
prompt2661 and process-exit. This is observed loss, not just misleading narration.

CODE-PROVEN: updates/update_character_info.py:565-593 merges the model's quantity
then filters quantity<=0. Its prompt1522 onward asks for minimal requested deltas;
1533's generic MODIFY example uses quantity0, identical to REMOVE1537. That
example predates this work (f808e3790); its causal influence here is HYPOTHESIS,
not proven by finding the text. The supplied changes string itself includes the
ambiguous final-state assertion. The old character-first dispatcher would run
this same array in the same order: no old-code live A/B was run. Thus do not
mislabel the underlying writer behavior as newly introduced by this amendment.

## Next boundary / stop condition

Both trial attempts now have a conservation failure. Apply the two-strikes
stop: preserve evidence and investigate step-local tool instruction versus
whole-turn outcome at the T067 -> T065 -> T079 boundary. Do not make a third
wording tweak here, blanket-ban quantity0 (legitimate removal), change item-name
rules, add a dependency scheduler, or invent whole-turn rollback. No next fix
is authorized or implemented by this acceptance report. The overall #378 trial
remains FAILED pending a reviewed scope/architecture decision.

## Independent audit closeout

The read-only independent audit agrees: four Shield transfers conserve the item;
the second-item loss is real and the overall candidate is NOT MERGEABLE.
Raw review: /mnt/c/agent-room-fleet-kit/local-data/378-bidirectional-final-audit.md.
Equipment-only deletion is tracked separately as #385. The Defense invention is
existing #349, not #371/#379 as the operator initially labeled it. C2 handback
FIRED; this does not satisfy the unrun explicit-unavailable-retrieval arm.

The audit also proved the handback supplied stale sheet text (T067[8] message6
equals T067[7], AC16/Chain Mail while disk is AC12/no Chain Mail). This explains
the false preservation narration and requires separate current-state review.
All 836 original fixture files independently rehashed unchanged; supported Quit
completed with no trial processes remaining. No commit, push, merge, or repair.
