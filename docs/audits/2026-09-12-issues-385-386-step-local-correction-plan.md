# #385 / #386 narrow step-local correction - review draft

Status: PLAN ONLY. Owner requested narrowed review/correction after the failed
#378 trial. No code, live run, commit or merge under this draft. Execution needs
post-convergence presentation/approval (NEQ-REVIEW-13). This is a continuation
in the isolated #374 worktree, not a claim that the prior acceptance passed.

## 1. Scope and policy pin

Live #193 v3.1 updatedAt 2026-09-12T19:41:48Z. Read Part1, Part2 p6
NEQ-INV-01/02, p8 NEQ-WORLD-04, p10 NEQ-WEB-01/03, p11 NEQ-PROVIDER-01/02,
p12 NEQ-SCHEMA-01/02, p13, Part3 and Part4. Schematics read:
docs/architecture/web-headless-surfaces.md and provider-routing.md.
README promises protected automatic inventory transfers (line867) and usable
character sheets/storage (234,715-717). This plan repairs the observed same-turn
tool overlap and stale follow-up state, not all inventory/effects defects.

Dynamic evidence at draft: branch plan/374-local-cache-contract, HEAD and live
origin/main 8562e270dde6b94d05bb21b97ce7b51fb810baf4. Worktree:
/home/loup/neq-worktrees/374-local-cache-contract. Recheck ancestry and policy
before code. Revision/hash pins are evidence only, never production authority.

The parent #374/#378 uncommitted candidate is retained (six tracked files).
Its accepted-order runtime and bidirectional T065 clause are NOT redesigned.
This document supersedes only the stopped trial's proposed next-step status;
both previous failed trials and their reviewed designs stay historical evidence.
Read parent issue-378-retrieve-equip-order-plan, bidirectional-amendment and
bidirectional-acceptance docs alongside this plan. No main changes.

## 2. Evidence, lineage, and two-strikes boundary

Raw /mnt/c/378b-ev-ewtWHx/A1, captures T067[7], T065[6], T079[4], T049[4],
T067[8]; independent audit local-data/378-bidirectional-final-audit.md.
OBSERVED: four Shield transfers conserve quantity and complete metadata; one
reverse-order T065 rejection fires before mutation. Second-item accepted array
already is [updateCharacterInfo, storageInteraction, updatePlot]. Its changes
mix the current operation with future ownership: 'Unequip Chain Mail before
storage. Eirik carries neither Chain Mail nor Shield...'. T079 sees a fresh
owned Chain Mail but returns quantity0; merge deletes it. Store then cannot find
it (protocol2496-2498), handback skips plot but supplies old character text.
T067[8] message6 is identical to [7], AC16/Chain Mail, while disk is AC12/no mail.
Fresh narration2579 falsely asserts unchanged ownership.

CODE-PROVEN: updates/update_character_info.py:565-593 supports genuine quantity0
removal and add-absent merge; generic MODIFY example1533 also uses quantity0.
Example origin f808e3790 'Fix effects tracking and add content sanitization';
merge history visible at 2c4721431 (file reorganization, not necessarily birth).
These are unchanged in the candidate. The old char-first loop would run this
accepted array in the same order. No old-code live A/B: do not claim one.
Example causal influence is HYPOTHESIS; actual contradictory instructions and
the returned deletion are OBSERVED. T079's history contains prior accepted
turns, not this complete accepted candidate (current action is not saved yet).

#386: main.py:6761-6767 refreshes party/plot/module but omits the existing
complete request assembler. Membership-rebuild call origin fdf017739;
_prepare_rebuilt_history_for_t067:7560-7595 already refreshes character data
for post-combat/other rebuilt requests (acd731e4c/7b5cd7367).

Two attempts at ordering alone failed end-to-end. STOP on another ordering
prompt tweak: this plan moves down to the missing current-tool context at the
writer. It neither bans deletion nor reads verbs/item names in code. A model
can still misinterpret; acceptance and explicit residual risk are mandatory.

## 3. Architecture / authority

| Datum | Owner | Non-authority |
| --- | --- | --- |
| Meaning of player request and per-tool changes | Existing DM/referee/writer models | Code word matching |
| Accepted action list and current position | Ordinary dispatcher | Historical candidate text |
| Item ownership/count/metadata | Fresh canonical sheet + StorageManager | Planned final narration |
| Transfer mutation | Existing storage transaction | Character equipment-only step |
| Actual step commit | Existing character/storage safe writes | Action index (not a commit receipt) |
| Follow-up facts | Existing full context assembler reading current disk | Pre-turn sheet/system text |

One runtime, no persisted format, schema, store, new model, retry policy, timer,
default item, action name or global transaction. The new optional call context
is ephemeral model INPUT, never permission to mutate or a persisted receipt.
Indexes identify ordering only: earlier actions are not asserted committed.
Fresh sheet remains state authority. Genuine removal is still legal when the
current character action owns consumption/sale/handoff/loss; storage is not
used for character-to-character transfers (#363 preserved).

## 4. Proposed tasks and precise boundaries

### R0 - freeze and verify
Re-read governance and owner rulings; snapshot dirty candidate hashes/EOL and
original fixture manifest. Independent layer-down forensics is complete:
local-data/385-386-independent-forensics.md and controller-forensics-dispositions
under the same prefix. Missing current-action context and omitted full refresh
are confirmed; example priming remains HYPOTHESIS. The proposed extra
removal-triggered retry is rejected: a removal plus a sibling storage action
does not prove that storage owns the removed item. FULL review and sentinels required.
No product edits in R0; no worktree prune, cleanup or test-game restart.

### R1 - give the existing writer the actual current tool boundary (#385)
Allowlist: main.py, core/ai/action_handler.py,
core/managers/effects_runtime.py, updates/update_character_info.py.

In the ONE ordinary accepted-action loop, enumerate the actual executable
actions after existing post-combat echo filtering. Pass an optional keyword
action_context containing a detached copy of the complete accepted action
array and its current index. This is the post-filter executable list; the index
addresses that list, not removed already-committed combat echoes. Do not replace
any action/changes string. Handler
forwards this keyword only through update_character_with_effects to the shared
T079 writer; all other handlers remain unchanged. Thread optional default None
through update_character_info and _update_character_info_unlocked, including
both existing migrated/unmigrated effect entrances and both inner wrapper calls
(update_character_info.py:1348 and :1353); no new pipeline branch.
Do not send this context to T078 (effect classification contract unchanged).
Existing standalone/prepared-travel callers omit it and retain call paths and
defaults; their shared T079 prompt gains the same instruction/example correction.

At T079 message assembly, AFTER the existing history-insertion loop, insert the
provided complete context immediately before fresh character data. Final order:
system, history, action_context (when supplied), current character data, changes.
The frame is inserted directly into messages, never through capped history. It
is not durable history and has no truncation. No parsing prose to infer ownership.
The following generic system instruction is UNCONDITIONAL for the single shared
T079 prompt; only the user context frame is conditional on supplied data. There
is no caller-specific system-prompt branch. Historical turns are background:

> You are executing only the current character-update step, not the entire
> player turn. When accepted action context is supplied, its current index
> identifies this step; the other actions belong to their own tools. The fresh
> character data is the state before this step. Do not apply another action's
> inventory movement or a described future end state. Equipping or unequipping
> changes equipment state and its actual mechanical consequences, not item
> ownership or quantity. If a separate storage action moves the item, leave
> that movement to storage. Preserve legitimate additions, removals and quantity
> changes when they are the requested responsibility of this character step.
> Prior narration and prior actions are history, not instructions to replay.

Replace ONLY the misleading MODIFY example's quantity0 with equipped:false;
retain REMOVE quantity0, actual destruction example, field/effects/ammunition
contracts and every writer/validation/commit path unchanged. Example item name
is pedagogy already in the prompt, never code authority. No T065 wording changes
in this wave. No blanket conservation gate that would block legitimate removals.

### R2 - assemble fresh follow-up context (#386)
Allowlist: main.py only. In the ordinary needs_response branch, after existing
history reload and party/location rebuild, run the existing
_prepare_rebuilt_history_for_t067 on that history. Pass that refreshed detached
history to both get_ai_response and _process_fresh_dm_response, as the existing
post-combat branch does. Preserve candidate-before-user-error chronological
order, user-role tail, earlier commits, skipped later siblings and invocation
arguments. No whole history rollback, no new refresh helper/recovery loop.
Assembly executes inside the existing response fence; provider call remains
run_outside_response_fence, with original supersession revalidation. No new lock
or provider call. No broad edit to every context-rebuild caller.

### R3 - docs, focused checks, independent gates
Add a historical forward pointer to the stopped bidirectional-acceptance status,
without changing any prior FAILED or NOT-REACHED verdict. Update the trial
subsection of web-headless-surfaces.md to show current
tool context and complete failure follow-up. No unrelated schematic cleanup.
AST/caller-family checks, mixed-EOL diff check, native/Linux py_compile and
pyflakes undefined-name gate; no simulated game tests. Pure serialization check
may prove complete context/no mutation of input objects and the pinned frame
order, not model correctness. A context-less request has the same system
instruction but no context frame. Verify both inner wrapper forwards explicitly.
Check schema/registry/provider files unchanged, prompt branches only intended
delta, defaults preserve every existing caller. Independent simplifier, actual
diff audit, both raw sentinels before live acceptance. No commit/push yet.

## 5. GL-1 and compatibility

| Replaced boundary | Origin / goal | Disposition and proof |
| --- | --- | --- |
| Ordinary loop iteration | Parent #378 runtime, original lineage in parent GL1 | PRESERVED order/terminal/echo guards; index is advisory, static and live arrays |
| Writer partial MODIFY example | f808e3790 delta-only updates | PRESERVED modification goal; equipped-only example, live second item |
| Writer without current accepted context | Existing T079 assembly | PRESERVED history/current data/changes; additive request-only facts; captured current-index plus actual array |
| Failure request with stale sheet | fdf017739 shared rebuild | PRESERVED party/module/history and added existing total refresh; raw failing-branch request vs disk |
| Quantity0 removal | Existing merge565-593 | PRESERVED byte-identical; genuine-removal negative control |
| Effects migration/standalone/travel callers | Existing effects runtime | PRESERVED optional-argument compatibility, no T078 contract change, family sweep |

Schema-Freeze: no schema delta; compare hashes. No save migration; real original
files remain byte-identical. No always-live flag: ordinary accepted tool calls
always supply context; missing context means an existing standalone caller, not
an opt-out. Scope is NOT a claim of global conservation enforcement. Prepared
travel storage/character overlap remains separately tracked #381.

## 6. Acceptance defined before implementation

Serial real native Windows C:/Python312 / configured OpenAI, logged-in Claude
Code operator with fresh copied source and complete authentic saved game.
Use original /mnt/c/374-game-K6gSX5, NOT either failed mutated copy. Refresh all
prompt/schema files from checkout, hash actual T079 system string and T065
prompts AS SENT. Response.model unknown if capture omits it, never inferred
from requested labels. Preserve captures, full output, prompt snapshots, item
metadata/count/AC and per-call timing relative to each player input. No synthetic
responses, state edits, binding edits, scripted action batches or forced gates.

| Arm | Required proof / failure polarity |
| --- | --- |
| A1 second-item first | Supported original save; ordinary Chain Mail unequip/store request; capture current accepted array/index in T079; item remains owned after equipment step then moves once; no invented garment |
| A2 both directions | Retrieve/equip and unequip/store, Shield and Chain Mail; complete fields and total quantities preserved at every prompt, writer sees current item, no duplicate movement |
| A3 genuine removal | Product-legal removal/use/handoff of a genuinely owned eligible item: deletion/decrement remains possible exactly once; otherwise NOT-REACHED, never fake an item |
| A4 failure follow-up | Naturally grounded unavailable storage request with an earlier legitimate completed update if accepted; capture actual manager failure, skipped sibling, T067 fresh sheet equals partial committed state, no replay/false rollback. Model pre-rejection is NOT-REACHED |
| A5 persistence | Save, intervening ordinary turn, Load; copied canonical state/metadata and displayed continuity equal actual save; clean Quit and orphan check |
| A6 compatibility | Already-carried equip without storage, companion if naturally grounded; original full/compressed coherence and parent terminal-prerequisite controls, honest NOT-REACHED. Standalone combat/level-up/prepared-travel callers remain NOT-REACHED unless naturally exercised; static signature safety is not live behavior proof |

Any new deletion/duplication or stale recovery sheet: STOP, preserve and report;
no repair or prompt shopping mid-run. No number of green isolated transfers
proves deterministic safety. A4 NOT-REACHED leaves #386 live acceptance unproven.
Do not require destruction or risky player choices solely to fill a matrix.
Independent Acceptance/PX reads verbatim narration versus five disk claims,
correctly labels inherited #349 AC faults separately and reports them immediately.
Log per-call T079 request size as well as timing: the uncapped array has a real
input cost, no added call. No merge/issue closure without owner acceptance of
the actual complete report. Preserve user-tail chronology in durable history;
request-time atlas/system framing remains unchanged, not a new tail guarantee.

## Tracked follow-ups

#385 task-R1 and #386 task-R2 are in this amendment because they block the
tested same-turn ownership/failure contract. #349 AC invention, #371 validation,
#375 storage cancellation, #381 staged overlap, #382 level-up prepass, #383
attempt logging, #384 storage progress remain separate. #368 genuine-handoff
loss is a negative control, not a claim this plan repairs every writer meaning.
#360 premature initial narration remains out; truthful *fresh* failure narration
is in R2. Existing inherited history[-10:] and writer retry exits are #324;
effects leases #202; prepared validation #356; effects runtime bifurcation #300;
stale pre-turn inline note #223; legacy action aliases #376. These are
PRE_EXISTING_OUT, not repaired. Debug-only preview/ring slices do not truncate
model context. Preserve remaining parent ledger dispositions.

## Resolution ledger

| Finding | Resolution | Evidence |
| --- | --- | --- |
| Equipment step deletes item before storage | task-R1 | #385, T079[4], protocol2496 |
| Missing current accepted batch at writer | task-R1 | Current candidate absent from T079[4] history |
| Failure call carries stale sheet | task-R2 | #386, T067[7]/[8] message6 same |
| Two-strikes | task-R0 | Layer-down evidence; no new T065 wording; new input-boundary plan |
| No universal model guarantee | fyi | Explicit residual; real acceptance required |
| Scope/execution approval | escalate:@owner | Present converged plan per NEQ-REVIEW-13 |

## First-round review resolution

All nine seats reviewed draft86f3d520; raw reports local-data/385386-r1-0..8.md.
No product edits. Because one seat classified instruction conditionality as
code-class, run all required seats on this frozen revision for confirmation.

| Review row | Resolution |
| --- | --- |
| System paragraph conditionality | task-R1: unconditional shared instruction, data-conditional user frame; confirm before implementation |
| Suggested caller-specific instruction | defensible: do not fork shared prompt; conditional wording is inside the one instruction |
| Context message position / both wrapper forwards | task-R1/R3: exact final order and four forwarding edges pinned |
| Post-echo array/index | fixed-inline: executable list explicitly named, no new filtering |
| Inherited issue numbers | fixed-inline: #324/#202/#356/#300/#223/#376 named |
| Historical marking | fixed-inline: R3 adds forward pointer, preserves failed verdicts |
| Standalone caller behavior overstatement | fixed-inline: API defaults preserved, shared prompt changes disclosed; unrun legs explicitly NOT-REACHED |
| Forensics H1 certainty / extra retry | defensible: captured linkage is not a controlled cause isolation; speculative guard not included |
| Token cost of full array | fyi: record size/timing, never truncate |
| Raw scanner completeness | task-R3: unabridged preimplementation scan saved local-data/385386-preimplementation-raw-scans.md; actual changed-code scan owed |

## Review protocol / gates

Run the plan review protocol. FULL: shared play-path entry changes; parent
deletions; model context and player truth. Separate blind seats: Architecture,
Fail-Forward, Acceptance, Consumer/Compat, Legacy/GL1, Player-Experience,
Leanness (new optional boundary data), No-Limits, Single-Path. Current plan and
full ledger supplied to every seat; raw proposed/actual diff and touched-file
scans mandatory for sentinels. Root single writer; read-only review delegation.
Converge and present before execution. No author inline approval.
