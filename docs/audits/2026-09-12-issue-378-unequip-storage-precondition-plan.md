# #378: unequip before outgoing storage - narrow proposed plan

Status: PLAN ONLY / REVIEW CONVERGED; post-review execution approval required.
D-U1 and D-U2 ratified by owner. No implementation, tests, commits,
push or merge under this document. The failed candidate remains isolated in
/home/loup/neq-worktrees/374-local-cache-contract, plan/374-local-cache-contract.
HEAD 8562e270dde6b94d05bb21b97ce7b51fb810baf4 is evidence, not runtime authority.
This supersedes only the proposed next correction, not prior failed verdicts.

## 1. Contract and policy

Live #193 v3.1, updatedAt 2026-09-13T04:27:12Z. Part1 refreshed; applicable
Part2: p6 lines129-132 (typed inventory slices/conservation), p8 lines139-142
(character state), p10 lines149-153 (one engine thread/truthful progress), p11
lines155-159 (existing provider routing), p12 lines161-164 (preservation), p13
lines166-171 (real serial acceptance). Part3/4 and D-378-1/2, D-385386-1 read.
Schematics: web-headless-surfaces.md, provider-routing.md. README line867
promises automatic protected inventory transfers; the player must still be
able to say 'put my equipped gear away' as one ordinary request.

Owner now approved the proposed prerequisite in the next message: 'go ahead
with your fix'. D-378-U1 in live #193 records that ruling. D-385386-1 did NOT
authorize this guard; the new ruling, not recycled prior approval, owns it.
Full review and post-convergence presentation remain required by #193.

## 2. Proven failure and lineage

OBSERVED: /mnt/c/385-ev-i7jytd/A1/model_captures/T065.json entry8 accepted
[storageInteraction, updateCharacterInfo, updatePlot] while describing the
opposite order. protocol.ndjson lines2331/2367: storage moved the Shield first.
T079 entries3-5 received current_index1 and a fresh sheet WITHOUT the Shield.
They proposed an absent-item equipment patch; merge appended it and schema
rejected missing item_type, description and quantity. Lines2404-2423 show
three failures, revert, skipped plot and generic failure. No duplicate or loss
persisted; armor stayed18 while narration claimed16. Overall FAILED.

CODE-PROVEN current boundaries (includes uncommitted #378/#385/#386 candidate;
the sibling-stop and complete handback refresh are NOT yet on HEAD/main):
- main.py:6585-6612 executes the accepted array as given. Restoring the old
  character-first sweep would break the already-proven retrieve-before-equip.
- core/ai/action_handler.py:4425-4459 obtains typed T049 storage operation,
  executes it, and hands failed operations back through needs_response.
- core/managers/storage_manager.py:295-350 resolves the exact requested items
  and available quantities. Lines377-399 remove carried items and set the
  stored copy equipped=false, without an equipment-state prerequisite.
- That stored-copy assignment predates this wave: blame 18e7052f9, 'Fix all
  file paths after code reorganization' (relocation, NOT claimed invention).
  Actual origin verified: 22b7dfbc (2025-06-18), 'Fix game file restoration
  and schema validation', root storage_manager.py (no linked issue). The
  candidate's removed character-first sweep exposed this outgoing-order gap;
  that sweep had masked outgoing ordering but broke incoming retrieval/equip.
  This is code-derived lineage, not an old-main live A/B test.
- updates/update_character_info.py:565-593 intentionally supports additions
  of absent items and genuine removals. Banning either globally breaks tools.
- main.py:6749-6785 already stops siblings and rebuilds current T067 context
  on needs_response; #386 adds the missing full character refresh there.

Two-strikes conclusion: another T065 ordering sentence is not the answer.
The existing typed storage operation and canonical equipped value already
identify the exact resource boundary before its ownership changes.

## 3. Proposed behavior / D-U1 owner decision

RECOMMENDATION: ordinary storage must hand an equipped-item prerequisite back
to the DM BEFORE moving anything. The DM then performs the actual unequip
through the existing character/effects tool, followed by the storage tool.
No code guesses verbs, armor math, item names, classes or player intent.

This is deliberately NOT 'automatically clear equipped and subtract AC'.
The model retains equipment/effect adjudication. Code merely reports the
canonical fact that the selected item is still equipped. No scheduler, extra
micro-model, new transaction store, action rewrite, schema or persisted field.
The existing corrective T067 call runs only on the unmet prerequisite; a
correct unequip-then-store request adds no call.

D-U1 RATIFIED / #193 D-378-U1: equipped=true is an unmet prerequisite for this
ordinary storage transfer, with automatic in-turn DM correction rather than a
player-facing refusal. B1 currently explicitly names existence/ownership;
do NOT silently stretch that rule to a new equipment prerequisite. It also
changes the old store tool's implicit-unequip behavior. Historical question:
'D-U1 / #378: May ordinary store_item return an uncommitted equipment
prerequisite when any selected canonical item has equipped=true, then use the
existing needs_response DM repair to unequip and finish the requested store?
No turn abort, timer, quantity loss or player resubmission is intended.'
The owner answered directly; no unresolved #293 entry was posted or remains.
Run FULL review now, retaining NEQ-REVIEW-13's post-convergence execution gate.

## 4. Proposed slices under D-U1 and D-U2

### C0: freeze and verify
Recheck policy epoch, source/ancestry, dirty candidate hashes and read-only
fixture. Preserve all earlier failed game copies. No worktree prune. Verify
all store_item callers and staged-storage siblings before editing.

### C1: ordinary storage prerequisite (storage_manager.py)
Per D-378-U1, use the existing exact item-resolution loop, for single and multi-item
requests. After ALL requested records/quantities are resolved, before backups,
container creation, removal, writes, validation or access-log mutation, collect
selected canonical records whose equipped value is the boolean true.
Return an internal result with success=false, stable error_code
equipment_prerequisite and complete character/item/quantity/equipped facts.
No missing-value default becomes true; no string interpretation or name list.
For a mixed multi-item request, move NONE of its items on this result.
Move existing backup creation after this read-only precondition, retaining
backups before every existing write. Do not restructure the normal transfer.
Do not turn this expected result into an exception/rollback path.
In particular storage_backup must still precede implicit create_storage
(current lines344-359); moving it after that write would lose rollback coverage.
The predicate is per selected record, including equipped stacks; it never
guesses which physical member of a stack is worn. No partial-stack heuristic.

The inventory item remains carried and equipped until a real character update
commits. The original accepted array's remaining siblings MUST NOT run. Earlier
unrelated committed steps remain committed; there is no whole-turn rollback.

### C2: truthful existing handback (action_handler.py)
Recognize only that typed error_code before the existing generic ERROR print.
Append complete prerequisite facts as the existing user-role tool-result note:
this storage step did not execute; later siblings did not execute; use current
state and do not replay prior completed steps. The existing needs_response
branch owns repair. No item/effect arithmetic or programmatic action insertion.
No technical error line to player for this expected correction; normal progress
stays visibly live. Propagate the exact error_code through the existing
create_return(response_data={"error_code": "equipment_prerequisite"}) result
(create_return:3040-3044 nests this under response_data). Generic failures
retain their current result and message. This is private tool provenance,
not a model-authored action or persisted permission.
Keep this existing tool-note family (Storage Error:), not Error Note:; the
existing validation-history selector strips the latter and its prior draft
(main.py:3112-3117). This specifies the existing-note reuse, not a new channel.
Do not add a failure-count cutoff. Repeated invalid ordering remains a live
acceptance failure, not a guarantee that repeated model correction will succeed.

### C2b: existing full review on this repair (main.py, D-378-U2)
At the ordinary needs_response seam (6749-6785), derive
require_full_review solely from result.response_data.error_code ==
equipment_prerequisite. Pass it into _process_fresh_dm_response and onward
to _review_fresh_membership_candidate as an internal keyword defaulting false.
The parseable nonmembership shortcut at 9828-9831 is legal only when that keyword
is false. Required repairs enter the SAME _review_dm_candidate implementation,
not a second validator. Every changed draft stays with its existing correction
owner until accepted or genuinely superseded. No prose/action-name inference.
No public/config/provider switch: the typed prerequisite selects the required
existing review automatically for every ordinary caller of this handback.

Keep response_fences.close() before this review, the existing require_current
checks, detached_context, invocation_claim, authority_check, approved transition
plan and _dm_review_context propagation unchanged. No lock spans provider waits.
Earlier committed actions remain recorded; the rejected storage and later
siblings did not execute, and the fresh reviewed draft owns only remaining work.
The existing full reviewer gets rebuilt current party/history from #386. Do
not normalize/copy a stale pre-storage snapshot as the repair's authority.

Consumer family: direct _review_fresh_membership_candidate callers at 377/1111
and all other _process_fresh_dm_response callers keep default false. The only
true producer is this equipment_prerequisite needs_response branch. Other
storage errors also keep existing behavior. No global #390 repair. Prove this
with a repository-wide call-family sweep and comparison of unchanged callsites;
private signature change creates no public API or saved field. Original bypass
provenance: fdf017739 preserved older nonmembership behavior; do not claim its
introduction is the original defect. Gate coverage is this cause, not all repairs.

Existing #385 frame and #386 fresh-context assembly are prerequisites retained
as-is, NOT declared proven merely because this new plan uses them. If this
handback exposes another defect, stop and report; no opportunistic repair.

### C3: docs and independent gates
Update docs/architecture/web-headless-surfaces.md ordinary-flow subsection,
docs/architecture/combat-typed-pipeline.md shared prerequisite description,
and the execution ledger; prior FAILED records
stay unchanged. Allowlist: storage_manager.py, action_handler.py, main.py and these
scoped docs only. Any required character/effects/schema/registry change
returns to planning, not an implicit scope extension.
Run compile, undefined-name, ASCII/EOL and raw FS-1/sentinel diff checks;
independent simplifier plus actual-diff audit. Pure record-selection checks may
test true/false/absent and mixed requests, but may not mock a game or model.
Doc falsifiers: web-headless-surfaces.md must distinguish the prerequisite's
extra review from its prior 'No new call' claim and describe the full-review
handback. Both schematics must distinguish the deterministic equipment
prerequisite from model-only order checking; neither claims code owns AC.

## 5. Authority, compatibility and GL-1

T049 owns interpretation into action/item/quantity; existing character path
resolves canonical identity; disk owns equipped/ownership/count. An error code
is an internal result, never a saved permission or receipt. Existing storage
writes remain the commit points; their current multi-file backup/write behavior
is NOT upgraded into an atomic whole-turn transaction by this fix.
No new lock or provider wait is introduced in StorageManager. Provider repair
uses existing run_outside_response_fence and supersession; Load/Reset/Quit must
still supersede. No new busy-refusal or acquisition deadline.

| Existing goal / behavior | Proposed disposition / proving check |
| --- | --- |
| Direct storage of equipped item implicitly clears flag | RETIRE only under D-U1; same player request completes through unequip then store |
| Store already-unequipped item | PRESERVED byte-equivalent mutation path, no extra call |
| Multi-item all-or-none prerequisite | New pre-write result, mixed real request proves zero movement before repair |
| Complete metadata and quantity transfer | PRESERVED existing storage implementation, before/after full records |
| Retrieve then equip | PRESERVED no retrieval hunk; real incoming negative control |
| Character genuine addition/removal | PRESERVED merge byte-identical; no add-absent or quantity0 global ban |
| Backups before mutation | PRESERVED, relocated after read-only resolution/prerequisite only |
| Prior completed steps and skipped later siblings | PRESERVED needs_response semantics, capture fresh corrective request |
| Nonmembership shortcut for equipment_prerequisite repair | RETIRED under D-U2 only, fdf017739 preserved shortcut; C2b invokes existing full review and executes its normalized accepted candidate like ordinary turns, A1 captures actual T065 |
| Other internal nonmembership followups and direct membership callers | PRESERVED default-false behavior and unchanged caller bytes; C3 family sweep; broader #390 not fixed |
| Full review correction, currentness, transition plan and accepted-history propagation | PRESERVED existing owner; C2b code trace and A1 fresh accepted candidate evidence |
| Prepared travel storage | NOT CHANGED; existing separate #381, no all-entry safety claim |

Caller-family boundary: execute_storage_operation -> store_item is ordinary;
prepare_staged_operation:614 and apply_staged_operation:837 are the existing
travel path, not callers of store_item. Do NOT insert a guard there that throws
and strands a checkpoint. If review requires a universal cross-travel contract,
escalate rather than absorb #381. No new parallel runtime is created here.

## 6. Acceptance, defined before code

Native Windows C:/Python312 and configured real OpenAI, serial headless play,
fresh authentic save copy, current candidate prompts/schemas AS SENT hashed.
No fabricated commands/results, state edits, forced provider replies or changes
to obtain a pass. Preserve both failed and current source manifests. Capture
actual response.model or UNKNOWN, every call latency relative to input, parsed
payload/frame facts, full narration, canonical snapshots and lifecycle counts.
Starting-state clarification: outgoing A1 requires Shield carried and equipped
as boolean true. The prior before-launch save has it stored; any ordinary
retrieve/equip setup must be captured explicitly as setup, not silently counted
as the outgoing arm or as a second independent negative control. No state edit.

| Arm | Required observation |
| --- | --- |
| A1 bug boundary FIRST | Equipped Shield outgoing; if model orders store first, prerequisite fires BEFORE any storage/accessLog/item mutation; fresh T067 sees carried equipped item; repair unequips then stores exactly once, reaches prompt |
| A1 polarity | If model correctly orders all trials, happy path only; firing path NOT-REACHED, never full acceptance |
| A2 independent second item | Chain Mail outgoing and incoming, plus Shield incoming: full fields/count conserved; correct steps add no new model call |
| A3 already-unequipped storage | Ordinary store goes through existing path directly, no prerequisite/correction call |
| A4 multi-item | Real T049 single items-array operation: no partial move on prerequisite; repair completes both. Separate sibling storage operations do not prove this branch; earlier committed siblings remain committed, and the multi-item boundary is NOT-REACHED |
| A5 genuine writer operations | Owned eligible consumption/handoff and ordinary equip without storage remain legal; naturally unavailable controls NOT-REACHED |
| A6 continuity | Save, intervening quiet turn, Load equals saved canonical state; clean Quit, no orphan, original fixture unchanged |

Mandatory #386 consumer proof when A1 fires: corrected T067 character frame
equals disk before repair, including ownership/equipped/quantity. A generic
character error or model-only pre-rejection does not reach that branch.
Record exact T065 count/payload for each corrective response; zero calls is
not 'validated again'. Verify T065 reviewed the fresh repair rather than only the original failed
candidate: correlate request candidate bytes, call ordering and the ultimately
executed actions. If review corrects the draft, capture the correction chain;
if no rejection occurs, that full-review rejection polarity is NOT-REACHED.
Pure code/caller checks prove dispatch selection only, never live repair success.
Record the full player stream/progress through repair
and absence/presence of technical error output, not just final snapshots.
For headless, player-visible means non-debug narration/status/system/result/
prompt events; preserve debug separately, not as player narration. The existing
character validator inside store_item is baseline work, not a newly added call.
T065 must contain both the actual prerequisite note and fresh candidate; its
mere call count does not prove that it reviewed the relevant facts.
No global AC PASS: independently compare narration with AC/effects and attribute
#379/#387 honestly; this plan neither fixes nor waives them. If an in-scope
step fails, repeats transfer, deletes/adds an item, or leaves the game unable to
continue, STOP and retain artifacts. Never prompt-shop during acceptance.

## 7. Review and authority gates

FULL required: new prerequisite guard, shared primitive, replacement of
implicit behavior. Separate blind seats: Architecture, Fail-Forward, Acceptance,
Consumer/Compat, Legacy/GL-1, Player Experience, Leanness, No-Limits, Single-Path.
Same plan/full ledger, raw scans, controller-only corrections and clean
confirmation per #193. No inline self-approval. D-U1 must be ruled before
convergence can authorize presentation; only post-presentation owner approval
can authorize implementation. Round1 completed on c91aa9f7: eight lane LGTMs,
Acceptance BLOCKED on the false revalidation claim. No convergence and no code.
That is the historical round1 disposition. Round2 all nine returned LGTM on
687890afb24db077f8fea40caa5657532386b06db737c5a83eea9c2a4ee53ef3,
including R2 re-verification of Acceptance F1 against C2b. Only clarification/
lineage/ledger polish followed; no code task/type/state/test/callsite changes.
NEQ-REVIEW-11 plan-polish termination applies; no additional confirmation
round required. Raw round2 reports and exact sentinel scan supplements are
378-u2-r2-*-review.md in the same local-data root as round1. No live PASS yet.

### D-U2: ordinary storage-repair review boundary (RATIFIED)

CODE-PROVEN and root independently verified: needs_response ->
_process_fresh_dm_response -> _review_fresh_membership_candidate; a normalized
candidate without membership actions returns accepted before _review_dm_candidate
and T065. This bypass is inherited from fdf017739 (HEAD main.py:9874-9877;
candidate main.py:9827-9831). No new live reproduction was run in this round.

Owner approved: permit the narrow main.py call-boundary extension so
THIS ordinary storage prerequisite repair uses the existing shared full review
owner before execution. No new reviewer/model type; no global change to every
internal follow-up; no replay of committed steps. Main.py is now in the narrow
allowlist for C2b only. Owner said 'yes, continue with your plan, it sound better';
#193 Part5 D-378-U2 records it. #293 decision resolution comment5651136304.
This is scope authority, not post-convergence execution authority. Required
FULL same-plan review is re-run because C2b changes actual call boundaries.

Review records: /mnt/c/agent-room-fleet-kit/local-data/378-u1-r1-*-review.md.
The earlier same-prefix .md files are failed CLI launches, not review verdicts.
Bypass filed as #390; scope decision posted to #293 D-378-U2 at
https://github.com/MoonlightByte/NeverEndingQuest/issues/293#issuecomment-5651058227.
The broader two-file storage crash window is separately filed #391, not #375.

## Tracked follow-ups

#387 unarmored Dex math; #379 stale Shield effects; #388 missing canonical cache
review frame; #371 T053 contract failures; #324 inherited writer limits;
#381 staged travel overlap; #360 premature initial narration; #375 T049
retry-class policy; #390 inherited internal-followup referee bypass (ordinary
prerequisite subset addressed by C2b under D-U2); #391 two-file storage crash-consistency window.
#367 inherited five-retry provider stop in the existing full reviewer, now
reachable for this repair; wider retry design #284/#293 D-8. Both verified OPEN.
This can end logical work even while the game stays playable; not a B2 safety
claim, not fixed or waived here. T114 is conditional on membership proposals,
not an unconditional extra call on a storage repair.
No broader fixes or closures under this plan. Their
occurrence is recorded separately, never used to claim whole-game correctness.

## Resolution ledger

| Finding | Disposition |
| --- | --- |
| Store first removes equipped item before character step | task-C1 |
| Expected prerequisite must not use generic technical error sink | task-C2 |
| Fresh handback must match still-owned item | task-C2 / A1, existing #386 must be proven |
| New equipped precondition and implicit-unequip retirement | task-C1 under ratified #193 D-378-U1 |
| Old prompt/writer trials failed | task-C0 preserve evidence; no new wording-only attempt |
| Other writer additions/removals must remain legal | task-C3 / A5 |
| Prepared path not covered by ordinary precondition | fyi: existing #381 remains separate; no universal coverage claim |
| AC/cache/lifecycle residuals | fyi: numbered tracked follow-ups above, no repair |
| Acceptance F1: promised revalidation bypassed for nonmembership repair | task-C2b under ratified D-U2; broader issue-#390 remains separate |
| Fail-Forward F4 crash-window attribution corrected | issue-#391; no repair in this scope |
| Policy epoch, candidate/main distinction, origin and schematic names | fixed-inline: plan-polish, no production task change |
| Single T049 multi-item versus multiple sibling operations | fixed-inline: clarify original per-operation oracle, not whole-turn atomicity |
| Backups before implicit container creation | fyi: explicit line-pinned implementation falsifier |
| Round2 cite/note-prefix/normalization/fixture and surface clarifications | fixed-inline: existing code and A1 contract clarified, no changed task or test |
| Inherited five-failure shared-provider stop | fyi: exact issue-#367, wider #284/D-8; no repair |
| Deferred-loop coverage, travel-worded status, repeated-order cost | fyi: #381/shared-owner existing behavior, actual A1 artifacts govern; no new tasks |

Review is converged after round2 plus plan-polish. C2b specifies the missing
connection under owner authority. Present this final plan before execution
per NEQ-REVIEW-13. No implementation or acceptance claim yet.
