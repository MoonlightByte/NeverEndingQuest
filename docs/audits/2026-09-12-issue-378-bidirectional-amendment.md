# #378 bidirectional ownership-order amendment

Status: REVIEW REQUIRED; owner requested continued testing of the presented
bidirectional correction. No merge/push. This amendment supersedes ONLY C1b's
retrieval-only clause and the stopped trial's next-step status. Read the whole
2026-09-12-issue-378-retrieve-equip-order-plan.md and its resolution ledger with
this document. All runtime steps, allowlists, original #374 passages, shared-loop
contracts, failure handback, no-new-calls and other acceptance arms remain.

## Spec pin and observed warrant

Live #193 v3.1; observed epoch 2026-09-12T18:57:15Z before D-378-2 codification.
Part1 B1/B2/AP6/AP7, Part2 p6 NEQ-INV-01/02, p12 preserve-then-override, p13 real
serial acceptance, Part3 FULL and p4 #345 prerequisite goal all continue to apply.
Datum authority, commits, locks, entry points, provider and schemas unchanged.
Dynamic source evidence: branch plan/374-local-cache-contract in isolated
/home/loup/neq-worktrees/374-local-cache-contract; HEAD8562e270. No main writes.

Prior tested plan37bd2df7: A1 passed, A3 FAILED. Raw
/mnt/c/378-ev-9mLWNY/A1, report local-data/378-native-acceptance-report.md,
issue378 comment5648214130. A3 T065[1] invited an equipment-only update,
T065[2] accepted [store, unequip, plot]. Protocol847 stores/removes the item;
T079[1..3] sees absence and adds it. Snapshot prompt-1065: cache1+sheet1.
This is the same ownership dependency in reverse, not a new unrelated defect.
Source and original fixture preserved; supported Quit exited0. No more inputs.

## Exact proposed C1b replacement (both full and compressed)

> ORDINARY ACTION ORDER: Check the proposed sequence before mutation; ordinary actions execute in their listed order, not all character updates first. Any state update for an already-resolved earlier consequence must precede createEncounter or exitGame, which end the current batch. Reject a candidate that places such a required update after them and request a corrected sequence without dropping the consequence. Do not invent an unresolved roll, choice, or prerequisite. A storage transfer owns the item's inventory movement. Order a carried-item equipment update on the side of that transfer where the character actually owns the item: retrieval before equipping a previously stored item; unequipping before storing a carried item. The equipment update changes equipment state, not a second inventory addition or removal. Reject the reverse dependency order and request the corrected sequence; do not ban the legitimate same-turn transfer and equipment change. Do not impose character-first order on unrelated actions. Existing dedicated travel, module-creation, and level-up contracts remain unchanged.

This replaces one generic dependency explanation; no new parser/guard, item
name, schema field, model call or writer behavior. Pure AC updates not referencing
an absent equipment record are not a new global ordering rule. Original four
#374 passages stay byte-identical. Existing referee's candidate correction is
pre-mutation; runtime executes that accepted list without interpreting prose.
Both models can still get order wrong: this trial cannot prove universal
deterministic conservation. No family-first fallback or storage-specific loop.

## GL-1 delta

| Replaced contract | Origin | Goal | Disposition/proof |
| --- | --- | --- | --- |
| Retrieval-only C1b sentence | Uncommitted D-378-1 trial, plan37bd2df7 | Retrieve before equip; no duplicated movement | PRESERVED and generalized symmetrically; fresh A1 and A3 |
| Store-side incidental old character-first rescue | Same mainline origins in parent GL1; retired by C1 | Item still owned when unequipping | PRESERVED goal via symmetric reviewed sequence, not restoring family-first; A3 firing and disk conservation |
| Terminal-prerequisite and dedicated-path sentences | D-378-1/#345 | Don't drop prior resolved consequence | PRESERVED byte-for-byte; static comparison, parent A6b remains naturally reachable only |

## Slices and checks

B0: Save the first failure/audit unchanged; verify policy, source hashes, no
active test game; eight independent blind same-plan reviewers of full parent+
amendment, affected code and ledger, FULL retained. No Leanness trigger beyond
existing model guidance; Custodian checks coverage/net-negative. Both sentinels
scan existing full candidate diff and proposed paragraph; inherited hits retain
parent dispositions. Confirmation and controller-only folds per Part3.
B1: Replace ONLY C1b in both prompts, exact identical text/EOL; runtime four
tested hashes (main/action_handler and other source) unchanged. Static gate
script's expected paragraph is a private test specification update only. Fresh
non-author simplifier + actual-diff and sentinel verification.
B2: Export fresh source, copy COMPLETE original game (not the failed edited
copy), refresh prompts/schemas, supported Load save_20260912_103037. Real native
OpenAI, one operator/input at a time. Same A1 sentence and exact failed A3
store sentence, then retrieve/equip again and store again through ordinary play.
Record actual pairs/accepted order and T065 retries; missing paired update means
ordering NOT-REACHED. If only correct arrays are proposed, wrong-order rejection
firing remains NOT-REACHED. Require sheet+cache total1 at EVERY completed turn;
preserve metadata except intended equipment state; receipt narration matches disk.
Capture T049/T079 inputs proving item is present at each equipment update.
New loss/duplication: STOP, preserve, no repair or repeated wording while running.
B3: Continue parent A2/A4/A5 and natural A6/A6b controls after core roundtrip
passes; no fabricated roll/trap or altered model reply. Test a second genuinely
owned eligible item if available. Save, one ordinary intervening turn, Load,
compare actual saved canonical state/history, clean Quit. Do not claim manager
failure handback if models reject before it. Unknown response.model explicit.
B4: Independent raw transcript/disk acceptance+PX audit, all five truth claims,
prompt bytes as SENT, per-call IDs/timings/capture lines and error/degrade counts.
Report original failure separately and current precise verdicts; no merge.

## Tracked follow-ups

Parent plan's numbered issues and boundaries all retained, including #375 inner
storage retry/supersession, #379 AC, #371 other AC validation, #364/#360 failure
narration and #382 level-up prepass. No unrelated repair in this amendment.

## Resolution ledger

| Finding | Resolution | Evidence/check |
| --- | --- | --- |
| A3 store-side duplication in first trial | task-B1/B2 | Real T065[1/2], T079[1..3], prompt-1065; new symmetric clause + fresh bidirectional proof |
| Old-order store conservation was not live A/B | fixed-inline | Code counterfactual only, never label observed |
| Original A1 AC/metadata overstatement | fixed-inline | Equipped changes legitimately; AC18 already present, not an increase proof |
| Owner continued trial | task-B0 | D-378-2; no shipment waiver |

## Review convergence checkpoint

All eight independent blind seats returned zero blocking findings on amendment
f828de14e05db1a94d7688bd4dcfb3474f0553ba4f46bc4a5e8ea78e1544fb58 with parent
88f9b62492adccc3a5ddfb36ef295c4d45c2811cef6cc4d57c8892e3b459ed6c.
Raw reports: local-data/378-bidi-r1-{architecture,failforward,acceptance,consumer,
legacy,player,nolimits,singlepath}.md. Only documentary polish/advisories;
NEQ-REVIEW-11 plan-polish termination applies after this full-coverage review.
No change to the proposed clause, runtime, cases, input sentences or scope.

| Review note | Disposition |
| --- | --- |
| Epoch now includes D-378-2 | fixed-inline: current epoch2026-09-12T19:41:48Z; checked again before B1 |
| Symmetric over-rejection verdict | fixed-inline: correctly ordered equipment-only unequip/store rejected on ordering/duplicate grounds is FAILED, not NOT-REACHED, just as for retrieve/equip |
| Existing C3 docs name only retrieval | fixed-inline: update their explanatory line and parent C1b pointer to this amendment; no new product behavior |
| T079 output/T049 input evidence | fixed-inline: existing full payload evidence includes proof that unequip patched rather than removed and storage still saw the item; quote those fields explicitly |
| Both DM prompt variants consistency | fixed-inline: full1452-1453 permits independent preceding character changes, compact19 forbids duplicate transfer only; no demand to store before unequip |
| Original #374 clarification wording | fyi: carried at update time is coherent; real opposite verdict classified over-rejection FAILED |
| Additional T065/T067 correction cost | fyi: count actual calls on every turn as already required; no assumed latency/cost improvement |
| Retrieval+consumption sibling hypothesis | fyi: no observed failure, do not widen equipment trial |
| Storage attempt success log off-by-one | issue-#383: separate observability finding, no retry change |
| Storage status gap | issue-#384: inherited8-18s observation, separate, no added helper here |
| Architecture inherited T06515/15 wording | defensible: does not establish a total semantic cap; Fail-Forward source trace identifies unbounded semantic correction; inherited provider-class exits remain parent-numbered, not new authority |

The owner's D-378-2 followed presentation of this exact symmetric direction and
authorizes its continued trial after affected review. No merge authorization.

## Execution checkpoint: second trial FAILED beyond the Shield case

Tested document SHA398ab5b0 (before this checkpoint). Four Shield transfers
passed, including real wrong-order rejection/correction. The next owned item,
Chain Mail, was deleted by a quantity0 equipment update before storage; the
accepted action order was correct. No third wording trial. Game quit cleanly,
failure preserved; see 2026-09-12-issue-378-bidirectional-acceptance.md. Runtime
and writer remain unchanged after failure. Remaining acceptance BLOCKED, no merge.
