# Issue 374: recoverable local deposits are storage, not item deletion

Status: FROZEN FOR PART 3 REVIEW. No product edits or live tests authorized yet.
Author/controller: codex-wsl. Owner D-369-3 requests #374 investigation and planning;
implementation requires presentation after Part 3 convergence and owner approval.

## 1. Authority, scope and evidence pin

Live #193 v3.1, epoch 2026-09-12T16:17:39Z. Read Part1, Part2 p6 inventory,
p11 providers, p12 compatibility, p13 acceptance, Part3 and Part4. Stable rules:
NEQ-INV-01/02, NEQ-CORE-03/04/05/06, NEQ-SCHEMA-01/02, NEQ-OPS-02/03,
NEQ-REVIEW-01..15. No schema or game-mechanic exception is requested.
Read docs/architecture/provider-routing.md (T065 evidence flow); no inventory
schematic exists in docs/architecture. No new architecture artifact is needed:
the request/commit flow stays unchanged. README storage promise: persistent
location storage and automatic inventory transfers (lines715-717,864-867).

Fresh worktree /home/loup/neq-worktrees/374-local-cache-contract;
branch plan/374-local-cache-contract. Observed HEAD/origin/main
8562e270dde6b94d05bb21b97ce7b51fb810baf4, with shipped #369 ancestor. This is
revision evidence, never runtime authority. Re-fetch before implementation and
merge. Do not touch the dirty shared checkout; never worktree prune from WSL.

Proposed product allowlist: prompts/validation/validation_prompt.txt and
prompts/validation/validation_prompt_compressed.txt ONLY. No Python, schemas,
bindings, action shapes, item-name resolution, writer/transaction/retry changes,
new micro-call, new store, mode, cache type or exception list. Tests/captures stay
private/local/untracked. Documentation: this plan and sanitized acceptance only.

## 2. Observed failure and challenged diagnosis

Issue #374 and raw /mnt/c/369-ev-aO8llh/Acont are the evidence, not an invented
scenario. T065.json[0] at 2026-09-12T15:37:57.950857Z received:
- Explicit player intent to LEAVE the owned shield in a cache for later recovery.
- T067's storageInteraction for that same item/destination plus updatePlot.
- Complete canonical character frame (input message31), including the owned item.
- Current compressed referee prompt: message0 equals the complete current disk
  prompt after normal text loading and strip, 19507 characters. Its SHA256 is
  4f40ce772cc55937f05f287b38f86b0fa5f19f928c12317f17ab177f8b18708e.

T065 rejected: "The shield is being cached beneath tree roots, not moved into
a player storage container. Using storageInteraction is invalid for this local
drop/cache; use updateCharacterInfo ... remove the Shield from his carried
inventory and record it as cached at the marked roots."
T065[1] accepted the revised character removal. T079[0] proposed quantity0.
Protocol line381 narrated stored/recoverable; prompt-648 has no Shield on the
character and playerStorage[]. Next store request was refused for absent item
(prompt-975). Normal player correction restored it (prompt-1403).
Later T049[0] and prompt-1769 prove the SAME destination can use existing storage,
with a real conserved item; no new container implementation is required.

OBSERVED linkage: referee rejection -> corrected candidate -> writer removal ->
missing canonical item. The modified #369 manager block was never entered in the
failure. Not an optional-name bug, absent character evidence, or stale fixture
prompt. The model's hidden reasoning is unknowable; the visible reason explicitly
draws a local-cache-versus-storage distinction absent from runtime capability.

CODE-PROVEN contract conflict: compressed :54 restricts storage to "player storage
container" while :225 says any loss/drop/trade requires updateCharacterInfo.
Full :229-234 describes containers, and :384 broadly requires character updates
for any removed item. Full :792-794 and compressed :54 also forbid duplicate
character deductions for storage. The unqualified removal rule contradicts that
ownership. Class: prompt-contract/coherence gap (NEQ-OPS-02), not a need for code
to recognize nouns/verbs or infer intent. Probabilistic occurrence remains honest.

Lineage: full generic removal originated c6323676, renamed by f5e84dd57 (2025-05-31); storage description
c88affc08 (2025-06-16); compressed removal rule abdeafbd7 (2025-08-29).
#363 commit b7d86bdc introduced the compressed "player storage container" phrase
while correctly narrowing handoffs, leaving the older overlapping removal rule.
Its predecessor described the sole store/retrieve transfer authority. No observed
pre-#363 cache control proves that #363 alone caused a universal caching failure.

Independent forensics: local-data/374-forensics.md, session
bb8acf4d-29c2-47b9-823c-c19186557ed0. Controller independently verified runtime
prompt equality, payloads, current code and blame. Its claim D-369-3 is absent
from live #193 is DISPROVEN by live body (D-369-3 heading and full ruling are
present at the pinned epoch). No new authority gate is needed for that claim.
Fixture contains earlier genuine failed-handoff history; possible influence on
model judgment is HYPOTHESIS, disclosed, not used to erase the observed failure.

## 3. Existing architecture and authority

1. Player intent and accepted scene are interpreted by T067, producing typed
   narration/actions. No regex, name lists or item-specific code decides intent.
2. main.py load_validation_prompt:3854-3864 selects full/compressed variant via
   existing COMPRESSION_ENABLED. Shared T065 request is at :3751; gameplay,
   welcome/auxiliary review callers use the same loader (:6989,:8360,:9883).
3. T065 judges latest candidate and returns valid/reason. Existing rejection loop
   asks T067 to correct; it is not a direct writer. No retry changes in this plan.
4. Accepted storageInteraction reaches core/ai/action_handler.py:4384 onward and
   process_storage_request -> T049. The specialist extracts typed operation with
   existing schema and canonical item/location/current-storage context.
5. core/managers/storage_processor.py:263-267 and
   core/managers/storage_manager.py store_item:345-358 already support implicit
   creation with no ID. The frozen type/default remains #365's separate policy.
6. StorageManager checks actual ownership/quantity then moves item between the
   character file and player_storage.json. Those records, not narration or
   updatePlot, are the item authority. Existing transaction writes stay unchanged.
7. Character-to-character handoffs use separate per-character updates; genuine
   consumption/destruction/loss uses character mutation. Equip state is not
   ownership. Old staged travel storage consumers retain their existing code;
   current one-turn travel cannot smuggle post-arrival storage into a travel turn.

No provider waits/locks/commit points/end-state machinery changes. A corrected
proposal follows existing validation, execution and correction terminals. Ownership
failure remains a no-op before mutation; known false-success handling is #364.
This plan does not claim to repair that terminal or make whole-system atomicity.

## 4. Proposed narrow correction (wording to freeze after review)

Change only the storage definition and overbroad removal clarification in BOTH
referee prompts, maintaining one semantic contract. Exact replacement boundaries:
full :229 lead sentence only; retain :230-234 bullets and required parameters
verbatim. Compressed :54 replace only the prefix ending "it owns that container
movement, so"; retain the remaining REJECT duplicate / distinct fee / NEVER
handoff tail verbatim. Preserve the (store/retrieve/create/view) enumeration.
Full :384 and compressed :225 receive the clarified removal rule below.
Common semantic text to render within these boundaries (not whole-block deletion):

> Judge item movement from the player's intent and accepted scene. Leaving owned
> items at the current location for later recovery is location storage, including
> an improvised cache or hiding place; it does not require a pre-existing container
> record or a purchased/manufactured box. Use storageInteraction for that deposit
> or retrieval. It owns the item movement; do not replace it with, or duplicate it
> by, an updateCharacterInfo removal or addition of the same items. Narration,
> updatePlot, or an updateCharacterInfo change note alone does not create
> a retrievable stored item. Do not demand a separate create action when the
> storage request already describes creating/using the cache.

> updateCharacterInfo remains required for actual consumption, destruction, loss,
> sale, or any other inventory removal not owned by location storage, and for
> equipment-state changes while the item stays with the character. Direct
> character-to-character handoffs still require separate giver/receiver updates.
> It is not the replacement for a recoverable location deposit. Judge an ambiguous
> drop by actual intent/context, not the word used; do not invent permanent loss,
> storage or a recipient the player did not choose. Character-to-character
> handoffs retain the separate giver/receiver updates, never storageInteraction.

Full variant: storage description :229-234 and clarification5 :384. Compressed:
@ACTIONS.storageInteraction :54 and @CLARIFICATIONS5 :225. Keep exact action shapes
and field names. No item/location examples encoding the repro; no prompt change
to T067/T049 is warranted because both already proposed/executed correct storage.

Why not other approaches: special-case shield/root nouns = AP-7; broader inventory
transaction/referee architecture = unrelated #364/#368 work; new storage schema
or ground-item system = #365 scope; an extra classifier call duplicates a working
T065 interpretation stage before testing its contradictory contract. Prompt-only
repair is a hypothesis to verify by real corrected routing AND durable movement.
Optional T067 prompt expansion is not selected: its captured first candidate was
already correct in the destructive incident. Current T065 ACCEPTED an unequip-only
candidate in A/T065[0] at 15:15:58Z; A1b tests the HYPOTHESIS that the corrected
contract rejects it and obtains storage. system_prompt_compressed.txt:29 has the
unchanged broad drop/updateCharacterInfo wording; this is known, not assumed safe. No
first-candidate T067 success is promised. A separate writer refusal capability
for impossible destination clauses is not added: this incident supplies the
wrong tool, and the plan repairs that selection boundary, not generic partial
intent signaling. Do not assert the writer is globally correct from this finding.

## 5. GL-1 behavioral contract

| Changed source | Origin / goal | Disposition and proving check |
|---|---|---|
| Full storage description; compressed storage definition | c88affc08 / b7d86bdc: use storage for location property, never companion handoffs | PRESERVED and clarified: existing implicit storage remains live; A1/A2/A3, handoff negative control |
| Full clarification5; compressed clarification5 | c6323676 -> f5e84dd57 / abdeafbd7: update real inventory removal | PRESERVED catch-all including sale/trade/theft/confiscation, consumption and equipment changes; RETIRED only application to storage-owned movement under issue374/D-369-3 planning mandate, subject to execution approval; A1/A4/A5/A7 |
| Duplicate movement and fee ordering | full b7f7a8631; compressed abdeafbd7 action_order and b7d86bdc storage clause | PRESERVED: no separate deduction OR addition of stored items; distinct fee still precedes storage; byte/contract comparison plus live capture audit |
| Handoff giver/receiver rule | #363 b7d86bdc | PRESERVED: no storage for direct handoff; A5 routing and separate conservation verdict |
| Storage ownership, schema, naming, existing/staged writers | unchanged mainline #369 and earlier | PRESERVED byte-for-byte; no modified code/schema/binding; state snapshot controls |

## 6. Tasks and focused gates (after owner execution approval)

C0: freeze fresh origin/main ancestry, policy epoch, both prompt bytes/EOL,
schema and relevant writer hashes. No product edits until approval.
C1: modify only the four named prompt sites using apply_patch with the existing
per-region EOL preserved. Full baseline CRLF848/LF53, compressed CRLF184/LF56;
reconfirm dynamically. Whole-file newline rewrite is a failure. All added text ASCII.
C2: independent diff audit and fresh simplifier. Static checks: allowlist exact,
old contradictory clause absent, new clauses present in both variants, protected
handoff/fee/duplicate/ritual/agency/travel clauses retained, addition-side duplicate
rejection and store/retrieve/create/view retained in both variants, full :234
required parameters unchanged, compressed "distinct fee" retained, schemas/code/bindings
byte-identical. No gameplay simulation, synthetic model reply, test-only gate or
tracked test change. Both sentinels scan candidate diff and classify inherited hits.
C3: serial real native acceptance below; no repairs mid-acceptance. Preserve every
failure and exact reached boundary; two failed fixes -> fresh forensics, not a third
prompt patch by guess. C4: independent transcript/PX audit beside disk, record all
verdicts/follow-ups, present owner. No auto-commit/merge/close.

## 7. Acceptance predeclared

Native C:/Python312/python.exe + actual run_headless.py serve/HeadlessClient,
real OpenAI unchanged bindings (capture effective T067/T065/T049 profile and
actual response.model or UNKNOWN). One ordinary command then read full response
and disk. No state edits, invented replies or arbitrary forced tool invocations.
For A1 use the authentic session-A end state used to launch Acont (equivalent to
A/state_snapshots/exit-548, Shield owned and UNEQUIPPED, history retained), or
reach that state through ordinary play. Do not assemble state from partial
snapshots. Record complete fixture provenance/hashes and existing storage before
the turn. If that clean state cannot be recovered or reached, A1 is NOT-REACHED.
Pristine copies of /mnt/c/357-game-b-gF7QPg serve A1b and other controls, not the
clarification that explicitly says the item is already unstrapped. Refresh ALL prompts in
copied game directories and prove T065's actual message0 matches candidate after
normal loader normalization. No stale prompt can count. Reuse observation relay
and C: space economically; no new harness or installation.

| Arm | Required evidence / negative polarity |
|---|---|
| A1 exact recoverable-cache repro | Original clarification on pinned truthful state; T067 storage proposal, no removal-only replacement; real T049/manager persist exactly one item at current location, remove from carrier, next prompt. T065 rejects for local-cache/no-container reasons = FAILED referee. Accepted storage but no persistence = FAILED storage, attributed separately; false narration also FAILED. No candidate and no erroneous adjudication (e.g. clarification) = NOT-REACHED, never PASS. |
| A1b ordinary phrasing | Separate pristine copy, original "tuck it into the hollow ... pick it up on our way back": correct first storage candidate OR T065 rejects unequip/removal-only and T067 repairs; actual container required. T065 accepts remains-carried/unequip-only for recover-later intent = FAILED baseline repeat. Same reached-layer verdict rules as A1. |
| A2 retrieve and re-store | Same actual container ID, no duplicate item/container; record full metadata and any armor differences separately, narration matches disk. |
| A3 persistence | Supported Save, later turn, Load/relaunch, same cache/item/history; retrieve after resumption where naturally reachable. Short safe travel away/back may additionally prove location return; no global return-travel claim if unrun. |
| A4 remains-carried control | Ordinary unequip/hold/strap request: no location storage, ownership stays with character, correct equipped state, prompt. |
| A5 real handoff control | Ordinary owned item to present consenting companion: separate character-update route, no invented container; negative control on overbroad storage interpretation. Distinguish routing verdict from known downstream writer failure; do not hide either. |
| A6 unavailable item gate | Ordinary request for an item not owned: verdict at actually reached boundary; no invented item/no inventory mutation, playable response. Separate any inherited false-success narration as FAILED #364, not a storage-policy PASS. |
| A7 actual loss/use control | An ordinary, explicitly intended permanent disposal or consumption of an actually owned item, on a disposable fixture: no invented recoverable cache; character mutation represents the accepted loss/use. Choose a legal grounded action, never fabricate a consumable. If this branch cannot be reached, record NOT-REACHED rather than substitute a handoff or static proof. |

First meaningful slice is A1. Capture every T065 attempt and its ENTIRE prompt as
sent, all corrections, exact T049 payload and post-processing, snapshot item counts
across all involved sheets/storage, metadata and nonempty-to-empty changes. Record
all narration verbatim next to disk, each call latency relative to accepted input,
whole-turn time, action order and retry/fallback/degrade counts with raw scans.
Owner/gameplay guidelines govern ordinary clarification, never forced JSON or
repeated blind prompt-shopping. Keep historical failure intact. Natural absence of
a firing branch is NOT-REACHED. Full prompt variant requires loader/content parity
and focused review; real default compressed path is primary. Any live claim about
full-mode behavior is NOT-REACHED under this plan (static parity only); changing
COMPRESSION_ENABLED for another live arm is not authorized here.
No browser, power-loss atomicity or universal inventory-safety claim. Clean supported
Quit and orphan check between fixtures; private config never printed or committed.

## 8. Part 3 protocol and owner gates

Run the plan review protocol: FULL conservatively for shared player-visible prompt
replacement. Separate blind parallel seats: Architecture Custodian, Fail-Forward,
Acceptance, Consumer/Compat, Legacy/GL-1, Player Experience, No-Limits, Single-Path.
Leanness DA applicability: no new mechanism/public symbol/guard/runtime branch or
>200 net lines; not mechanically triggered; Custodian runs coverage/net-negative
checks and reviewers may escalate if this assessment is wrong. Schema gate = no
schema delta; Platform/Provider and Hygiene apply. Every reviewer receives this
same plan and full ledger, R1-R15 including concrete counter-evidence to block.
No draft leakage. Controller single-writes corrections, full confirmation until
convergence or ratified plan-polish termination. No numeric review cap. Escalate
unratified gameplay semantics to #293, never resolve by fiat.

D-374-1: post-review owner execution approval required. No implementation or probe
run is authorized by this planning assignment. Merge/ship remains separate.

## Tracked follow-ups

#364/#360 failure propagation/narration; #365 default container policy; #366 ammo
lookup; #368 handoff ownership; #370 identity retention; #371 armor validation;
#373 empty-name divergence; #324 inherited validator bounds; #375 ordinary T049
count-keyed exhaustion; #376 obsolete full-prompt action aliases. These are not
repaired or implied solved. #363 handoff direction remains protected. #369 shipped
and closed, reused as the now-working implicit-create behavior, not new work.
Inherited log attempt-label mismatch is fyi only, not a requested product fix.

## Resolution ledger

| ID | Evidence/class | Disposition |
|---|---|---|
| F1 | OBSERVED T065 local-cache rejection -> writer removal -> absent item | task-C1, core issue374 |
| F2 | CODE-PROVEN contradictory broad removal/storage ownership rules | task-C1, both prompt variants |
| F3 | OBSERVED later same-location storage succeeds; no new runtime needed | defensible: existing implicit storage reused; #365 representation stays separate |
| F4 | False-success narration and stale armor in prior live run | issue-#364 / issue-#371, existing open evidence, not folded |
| F5 | All controls/policy/lineage/prompt provenance | task-C0/C2/C3/C4 |
| F6 | Forensics says D-369-3 absent | defensible: live #193 explicitly contains it; read-only recheck resolves claim |
| F7 | Optional DM prompt expansion/new writer partial-intent signal | defensible: destructive incident had correct first candidate; A/T065[0] accepted unequip-only, so A1b must prove corrected routing, not assume it. Generic writer design not inferred |
| R1-Arch-P1 / Legacy-P1..3 | Correct origin and replacement boundary | fixed-inline lineage/path corrections; #363 causal attribution remains unproven |
| R1-Legacy-L1 | Catch-all removal omitted in draft | task-C1: retain any actual non-storage removal, including sale; GL-1 preserved, code-class confirmation required |
| R1-Legacy-L2 / Consumer-C1,C2 / Arch-P2 | Duplicate-add, fee, view, parameter preservation ambiguous | task-C1/C2: exact sentence boundaries and explicit protected tails; code-class confirmation required |
| R1-ACC-1,2 | False NOT-REACHED and unpinned clarification fixture | task-C3: distinct reached-layer FAIL and exact truthful fixture; test-class confirmation required |
| R1-ACC-3..5 / PX-1,2 | Unequip baseline accepted; notes not storage; full-mode evidence | corrected evidence label and contract; full-mode NOT-REACHED, returned model UNKNOWN unless actual field exists |
| R1-FF-1 / No-Limits | Inherited ordinary T049 count exhaustion | issue-#375, no code change here |
| R1-Single-Path | Full prompt obsolete aliases | issue-#376, no code change here |
| R1-FYI | First-existing-container selection, ambiguous intent, original context influence | fyi: record baseline container; #365 policy separate; no new claims or test levers; ambiguous clarification is legal |
| D-374-1 | Owner approval after panel/presentation | escalate:@owner after convergence, blocks execution only |

Independent forensics and Part 3 results will be recorded with frozen plan SHA.
