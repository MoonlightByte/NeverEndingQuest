# Issue 345: collect an earlier player roll before combat entry

Status: PLAN ONLY, revision 1 with review citation/ledger polish. No implementation,
live run, commit or publication authorized. Full #193 round completed; see the
separate review record for reconciliation. Owner receives the reviewed design before
execution. #323 belongs to another agent and is excluded.

## 1. Authority and scope

Live #193 v3.1, updatedAt 2026-09-09T22:48:31Z, read 2026-09-09.
Spec pins: Part2 p4 NEQ-COMBAT-01/04/06 (model judgment, code-owned bookkeeping,
player dice/initiative); p8 NEQ-WORLD-03 (conversation continuity); p9
NEQ-SAVE-01/02 (Load and continuity); p10 NEQ-WEB-01/03 (shared input/pacing);
p11 NEQ-PROVIDER-01/02 (unchanged routing, measured cost); p12
NEQ-SCHEMA-01/02 (no schema delta, preserve player data); p13
NEQ-ACCEPT-01..03/NEQ-TEST-01..02 (native real evidence, negative controls).
Part1 AP-4..7/B1/B2 and Part5 D-9, D-TRAVEL-2, Fork-1a, D-LCR-1..3 apply.
Schematics read: combat-typed-pipeline, save-load-reset-lifecycle,
web-headless-surfaces, provider-routing. Their historical line pins are not
current authority; the verified current seams appear below.
README Core Game Systems (lines219-224): adaptive DM, tactical initiative,
character preservation and Save/Load must not regress.

Isolation: /home/loup/neq-worktrees/345-pending-roll-plan,
branch plan/345-pending-roll-handoff. Revision evidence only: current origin/main
3c51ee156d7403a5f5c2eb2e94979559fda413d3, exact ancestor at creation.
Fetch explicit refs/heads/main:refs/remotes/origin/main before later gates:
this clone's ordinary fetch did not refresh the tracking ref. No main rollback
occurred; ls-remote confirmed the published tip. Never worktree prune from WSL.

## 2. Observed failure and code-grounded diagnosis

Private authentic evidence root: /mnt/c/337-ev-qdSV6b/A1-afterload.
All indices below are zero-based; line numbers are physical JSON/NDJSON lines.

| Evidence | Observation |
|---|---|
| model_captures/T067.json:1763 index12 | Candidate asks a human DC15 save and emits createEncounter |
| model_captures/T065.json:1173 index11 | Rejects wrong DC, not the missing input boundary |
| model_captures/T067.json:1910 index13 | Corrects save to DC13 but still co-emits combat entry |
| model_captures/T065.json:1271 index12 | Accepts; praises immediate combat creation |
| protocol.ndjson:2970 seq2953 | Says "Roll a Dexterity saving throw, DC 13" |
| protocol.ndjson:4869 seq4852 | Combat introduction, with no intervening human input |
| protocol.ndjson:5055 seq5038 | Seven combat events narrated, none resolves the pit |
| protocol.ndjson:5101 seq5084 | First prompt is ordinary combat actor input |

Saved encounter phase awaiting_actor, pendingTurn:null, PC14/14HP. This proves
the immediate missed input handoff, NOT permanent inability to recover later.
The two recorded T065 times are6.855s/7.377s. Actual response.model is UNKNOWN
in these captures; selected binding is not reported-model proof.

CODE-PROVEN chain: main.py:6517-6519 displays narration; :6627-6643 dispatches
other actions; action_handler.py:3130-3147 builds, :3212-3217 synchronously enters
combat. No runtime code turns a narrated question into a pending main input.
Existing combat pause is not a drop-in fix: combat_state.py:779-811 permits only
the current initiative windows; combat_orchestrator.py:1195-1203 claims that
window; pipeline.py:324-329 pauses a HUMAN actor's requiresPlayerInput;
combat_orchestrator.py:1496-1502 and combat_transaction.py:779-820 persist it
beside that turnId. Forcing the PC into an earlier window would violate initiative.

The captured compressed author/guardian system instructions were read as sent.
They demand immediate createEncounter at awareness/hostility (author52-64/209;
guardian23/87-94) while the author also demands requesting unresolved player
checks and not narrating their result. The guardian approved the impossible
combination. This is a producer/reviewer ordering-contract failure, not evidence
that #337 location grounding or a new boss-specific mechanic failed.

The trap instructions also say "savingThrow action" (full563/1662,
compressed152), but process_action has no such action. Correct that instruction
at this same boundary; do not create a new tool to satisfy stale prose.

Lineage: full1593-1620 comes from fcdb2647 (Add Combat Commitment Point rules to
fix encounter initiation); full1127-1131 and traps563/1662 blame to a28d8b956
(Fix missing import for save_conversation_history in updatePartyTracker).
Compressed entry/trap instructions come from327ac74d (Add parallel conversation
compression system with progress tracking);
full guardian rule from60a7e776 (fix(travel): harden contextual location
transitions), compressed fromabdeafbd7. Immediate runtime invocation predates
#337 (4290e711 threaded invocation_claim; earlier creation flow in2c472143).
#337 added evidence only. A fresh unmodified-baseline gameplay reproduction is
not claimed; lineage proves inherited instructions/dispatch, not every old run.

## 3. Recommended design and honest boundary

Choose A: align the EXISTING main DM and semantic guardian on a prerequisite
input boundary. Do not add a typed store, field, parser, micro-call, rules engine,
roll generator, timeout, mode or new executor.

The model determines whether an already-triggered immediate scene consequence
must be answered before combat can advance. This may happen even after enemy
awareness was narrated (the actual incident). Until the human answers, the
accepted response asks the question but emits no createEncounter or dependent
mechanical result. The ordinary actionless main turn returns input. The accepted
question remains in existing conversation history (main.py:9505-9512/6857-6859).
Next actual input goes through the same T067/guardian/T065 review. Resolve only
the answered consequence with existing updateCharacterInfo when required, then
createEncounter once no earlier human question remains. Main's existing
sequential character updates precede other actions; an update error/supersession
returns before combat (:6576-6625). No new mutation or rollback machinery.

No blanket action stripping: the MODEL removes only premature/dependent actions;
already-justified independent state changes retain their existing contracts.
For the captured request specifically, the waiting response has actions:[].
No player attack is silently completed; it remains committed intent for formal
combat, subject to actual changed circumstances and the player's next input.
If the player asks a question instead of supplying a roll, answer/clarify without
inventing dice or resolving the dependency. Do not manufacture a trap merely to
delay combat. Once the dependency is resolved, do not ask for redundant combat
consent or create an extra free action for the player or companions.

This is AGENTIC semantic review, NOT a deterministic guarantee over arbitrary
model output. Code will still execute any incorrectly approved createEncounter.
The plan must not claim a durable typed pending-roll guarantee. If real testing
shows repeated uncorrectable co-emission, STOP under two-strikes/layer-down; do
not add regexes or another guessed guard. Bring a typed continuation alternative
to the owner as a new reviewed scope, including schema/compat implications.

Alternatives considered:
- B: typed encounter-entry continuation. Stronger machine-enforced pause, but
  current pendingTurn is initiative-owned. Needs owner-approved protocol/state
  extension and careful #266 coordination. Not hidden inside a prompt fix.
- C: prose search for "roll/save" or a boss/trap name: rejected AP-6/AP-7.
- D: force PC first, auto-roll, skip trap, or move it after NPC attacks: rejected
  agency/causality; solves the symptom by changing the game.
- E: separate classifier call: not justified while the existing semantic
  guardian already has the candidate, player input and canonical scene facts.

## 4. Proposed author/guardian wording (reviewed text, not yet shipped)

Author contract, equivalent in full and compressed prompts:

> A triggered immediate scene consequence that needs the player's own roll or
> choice must be resolved before handing control to formal combat, even if the
> enemies have already become aware and hostile. Ask for the earliest unresolved
> player input and end that response without createEncounter or any result/action
> that depends on the answer. Do not roll for the player, invent a result, or
> advance intervening attacks. Preserve the established scene and hostile intent.
> On the player's reply, resolve only the supplied input and its grounded
> consequence through existing state-update actions; request any still-missing
> input instead of guessing. Once those earlier dependencies are resolved, call
> createEncounter before further combat actions. This takes precedence over
> immediate-create instructions only for that unresolved prerequisite; ordinary
> combat entry with no such dependency remains immediate. It does not move an
> in-combat save/reaction out of its initiative window or allow free attacks.

Guardian contract:

> Reject a candidate that requests an unanswered player roll/choice needed before
> combat proceeds while also emitting createEncounter, dependent consequences,
> or intervening combat actions. Request a corrected candidate that asks for the
> input and waits; do not also demand immediate createEncounter on that waiting
> response. This priority applies to a grounded, already-triggered prerequisite,
> not an invented delay or an untriggered authored hazard. Once the required input
> and consequence are resolved, require ordinary immediate combat entry. Preserve
> all other agency, canonical evidence, action-shape and combat checks.

Trap text becomes "narrate the triggered trap, ask the player for the required
save and wait; use existing updateCharacterInfo only for resolved consequences";
never advertise a savingThrow tool. No DC, dice, names or location constants from
TW05 appear in the production wording. Keep NPC-owned rolls NPC-owned.

## 5. Allowed files, slices and behavioral contract

Runtime-text allowlist, only these four:
prompts/system_prompt.txt; prompts/system_prompt_compressed.txt;
prompts/validation/validation_prompt.txt;
prompts/validation/validation_prompt_compressed.txt.
Docs: this plan/review/execution records, docs/architecture/combat-typed-pipeline.md.
No Python/schema/binding/test tracking, no module edits, no #323 changes.
No entire-file reformat or unrelated prompt cleanup. Preserve per-region EOL;
added text ASCII, baseline bytes outside approved hunks unchanged.

| Slice | Work and gate |
|---|---|
| C0 | Refresh live193/main; freeze prompt bytes/EOL and authentic fixture provenance; preserve original failure captures |
| C1 | Reconcile every immediate-entry occurrence in the four prompts with section4 precedence; correct nonexistent savingThrow wording; do not append contradictory instructions |
| C2 | Fresh independent simplifier, GL-1 and prompt-consumer inventory; both compressed/full forms carry equivalent contract; no other behavioral delta |
| C3 | Native real OpenAI acceptance below, serially; no mid-run repairs; transcript+disk independent PX review |
| C4 | Non-author five-point postimplementation audit, final exact diff/sentinels; owner presentation; no automatic push/merge |

GL-1: each proposed replacement is scoped to the observed mixed request, not a
license to remove working combat constraints. During C1 pin exact baseline line
spans/commit messages for ALL affected siblings, including examples.

| Existing behavior / lineage | Goal | Disposition and proof |
|---|---|---|
| full1127-1131,a28d8b956; full1593-1620,fcdb2647; compressed52-64/209,327ac74d | No free narrative rounds after hostility | PRESERVED for no-prerequisite entry by A2; only earliest human-prerequisite ordering changed, A1/A3 |
| guardian full19 + related examples,60a7e776; compressed23/87-94 + examples,abdeafbd7 | Reject combat bypass | PRESERVED A2/A4; no conflicting demand on valid waiting response |
| trap full563/1662,a28d8b956 and compressed152,327ac74d | Trigger grounded hazards and apply actual consequences | PRESERVED A1/A3; unsupported tool instruction replaced by existing supported actions |
| ordinary no-actions/character-first dispatch main6567-6643 | Input returns; completed prerequisite writes precede combat | PRESERVED byte-identical; A1/A3/A5 verify consumers |
| combat pendingTurn/initiative/controller/dice/voice maps | One combat owner and player-owned dice | PRESERVED byte-identical, A2 and existing roll-pause regression |
| accepted-history/Load/Reset/currentness | Rejected drafts aren't events; controls work | PRESERVED byte-identical, A4/A5 |

## 6. Spec pin: owners, commits and terminals

Canonical PCs/NPCs/HP: character files via existing shared writer. Canonical
location/trap: current module snapshot; authored presence != triggered result.
Human dice: actual submitted input, interpreted by model; no keyword authority
in code. Model proposes actions; existing guardian/full review/identity/currentness
approve, existing writers commit. Question is retained in ordinary accepted
history, not a new durable obligation type. In-memory failed drafts remain private.

States: normal input -> private review -> accepted prerequisite question ->
normal input -> reviewed answer/consequence -> existing writer -> combat entry.
Invalid/incomplete human answer -> grounded clarification, no fabricated result.
Invalid draft -> existing correction; transient provider -> existing reap/reissue;
supersession -> existing unwind, no stale mutation. Existing completed provider
error policy unchanged; new prose must not authorize terminal rejection.
Save/Load/Reset use existing lifecycle owners; save at the clean question boundary
and resume that saved history, no crash-every-millisecond guarantee. No new locks;
provider waits stay outside existing response fences. Genuine in-combat pending
rolls retain their current separate authority, not copied into main.

## 7. Acceptance designed before code

No acceptance runs during planning. Native Windows Python312, actual
run_headless.py serve/HeadlessClient, real configured OpenAI; one command at a
time, read response then decide next action. Follow gameplay guidelines on main.
Use a fresh isolated source export/valid native checkout, not another agent's
worktree or game. Authentic pre-TW05 save from337 C0; reach TW05 by actual play,
no encounter injection, state editing, invented rolls/transcripts or fixture
boss substitution. Prompt files MUST be refreshed from checkout, loaded hashes
matched, and AS-SENT contract presence shown (compression swaps the DM system
prompt at conversation_compressor_parallel.py:525-536; validator loader
main.py:3844-3854 selects full/compressed). Selected model != response.model.

| Arm | Required reached proof / negative polarity |
|---|---|
| A1 primary | Actual triggered TW05 pit plus hostile intent: asks correct player save, next prompt is main not combat, no build/active encounter/NPC attacks before answer. Submit actual rolled dice, trace consequence through disk and then real combat player prompt. A run without triggered mixed situation is NOT-REACHED, not PASS |
| A2 no-delay | Real combat trigger with NO earlier human prerequisite still builds immediately, correct initiative/controller/HP/voice behavior; ordinary in-combat player roll pause remains unchanged |
| A3 consequence | Actual successful/failed save outcomes as real dice permit; exact HP/effect/damage math and one application, no pre-answer mutation. Noncombat trap without hostiles must not create combat. Missing/clarifying answer keeps real input open; no fabricated roll |
| A4 guardian | Real co-emitted candidate (if naturally produced) rejected for input ordering and corrected; wrong DC/hidden untriggered hazard still rejected. No synthetic response injection. If no mixed candidate occurs, firing-path rejection is NOT-REACHED and requires explicit owner acceptance, not inferred PASS |
| A5 continuity | Supported Save at accepted question, one subsequent real turn, Load that save, resume the question and answer without invented prior result/double consequence. Separate Load/Reset/Quit control checks; preserve all unrelated character fields/memories. Crash resumes last clean supported point, no new mid-flight persistence promise |
| A6 consumer parity | Confirm full and compressed prompt paths independently; actual native run for each affected runtime configuration. Do not claim untested providers. Report added tokens/latency and actual call counts, not assumed zero cost |

For every arm: exact input/protocol lines, entire visible narration, parsed
candidate/actions and T065 reason, model-call IDs/actual response.model or UNKNOWN,
per-call timings relative to input and total turn wall time, prompts hashes,
before/after canonical files and counts of invalid/retry/degrade/fallback events
with search commands. Review five narration claims against disk and no extra
attacks or chosen player actions. Pause/restart alone != consequence resolution.
End each arm with Save/Quit when safe, native exit and child-quiescence receipts.
No guaranteed player-experience PASS from pure tests; no broad boss/XP claim.

Development gates: prompt occurrence/consumer sweep; semantic-equivalence review
of full/compressed contracts; git diff --check; ASCII additions/EOL exactness;
unchanged Python/schema hashes; both sentinel scans over diff AND all touched
files, classify every hit. No tracked tests. No new Python undefined-name gate
target if implementation remains text-only; any Python addition triggers re-scope.

## 8. Full review and decision gates

FULL despite text files: replaces gameplay ordering/validation instructions,
GL-1 applies. Separate blind seats: Architecture, Fail-Forward (B1/B2 verbatim),
Acceptance, Consumer/Compat, Legacy-Contract, Player-Experience, Leanness,
No-Limits and Single-Path. Each independently assesses Schema-Freeze,
Platform/Provider/Hygiene. Run concurrent seats up to available worker slots;
never combine standing seats. Controller is sole writer, all get identical frozen
plan and full ledger. Review draft, reconcile concrete findings, all-seat clean
confirmation unless the precise plan-polish exception applies. No agent agreement
substitutes for owner mechanics or execution authority.

D-345-1: owner must approve the explicit prerequisite-before-entry exception
and its model/guardian-enforced (not mechanically guaranteed) scope after review.
If a reviewer finds an unratified product choice, draft #293/D-345-1 and stop
convergence for that ruling, not endless reviewer rewording. No #193 mutation by
fiat. D-345-2: execution after presentation, NOT granted by review.

## Tracked follow-ups

- #266: player-target defensive save/reaction inside another combat actor window;
  D-266-1 storage authority is not permission to silently absorb that project.
- #279: general combat-side/goal semantics, not this boundary repair.
- #343/#344 evidence retains separate profile-liveness and modifier-context
  issues; no model tuning or character-writer redesign to get a green run.
- #323 another agent's level-up work; no overlap authorized.
- #347: inherited hard40-word Plot Themes limit in full author prompt1646,
  found by No-Limits and filed this turn. PRE_EXISTING_OUT, no module-creation
  cap repair inside #345. Related inventories #262/#276.
- Historical combat schematic voice/retirement pins remain explicitly historical;
  C2 documents only this changed entry seam, not a repo-wide diagram rewrite.

## Resolution ledger

| Finding | Resolution |
|---|---|
| Unanswered main question co-emitted with synchronous encounter handoff | task-C1 |
| Author/guardian both require immediate create with no prerequisite precedence | task-C1 |
| Unsupported savingThrow action in same trap instructions | task-C1 |
| Existing pendingTurn cannot be repurposed out of initiative order | defensible: no combat runtime/state change proposed |
| Model enforcement is not universal deterministic pause proof | task-C3; explicit residual, D-345-1 owner presentation |
| Typed mid-combat defensive parity | fyi: existing issue266, excluded |
| Separate observed profile/modifier failures | fyi: existing343/344, excluded |
| Inherited module-creation Plot Themes word cap | issue-#347; PRE_EXISTING_OUT, no #345 contract/runtime change |
| Full-prompt/trap blame origins conflated in draft | fixed-inline: citation-only correction from Legacy review, no code/test/task change |
| Failed prerequisite writer emits protocol error before returning | fyi: existing main4956-4962; task-C3 must not call this successful resolution, no failure-policy repair here |
| Existing deterministic provider terminal and builder subprocess | fyi: current handling unchanged; task-C3 cannot certify arbitrary builder liveness or all failure branches |
| Stale remote-tracking ref initially used for worktree | fixed-inline: explicit fetch+fast-forward before source review; remote verified |
| Implementation/publication | escalate:@owner after reviewed-plan presentation |
