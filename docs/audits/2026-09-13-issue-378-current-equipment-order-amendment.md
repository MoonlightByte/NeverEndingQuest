# #378 current-equipment ordering clarification

PLAN ONLY / REVIEW CONVERGED. Supersedes only the unconditional carried-item wording in the
uncommitted #378 T065 ordering paragraph. The approved U3 implementation and
all earlier failure/NOT-REACHED records remain unchanged. No code edits yet.
Owner asked to keep going after the incomplete live verdict; this authorizes
investigation/review, not a waiver or shipment. Present convergence before edits
under #193 NEQ-REVIEW-13. No commit, push, merge or closure in this phase.

## Evidence and boundary

Live #193 v3.1, updatedAt2026-09-13T04:44:16Z. Part1 read; p6 inventory,
p8 character state, p10 truth/liveness, p12 preservation and p13 acceptance.
Schematics: web-headless-surfaces.md ordinary ordering section and
combat-typed-pipeline.md shared ordinary prerequisite description.
README's protected inventory-transfer promise must survive. D-378-U1/U2/U3
remain authority for the deterministic guard and existing full-review repair.

Worktree /home/loup/neq-worktrees/374-local-cache-contract,
branch plan/374-local-cache-contract; HEAD and locally fetched origin/main
8562e270dde6b94d05bb21b97ce7b51fb810baf4 at inspection (revision evidence,
not runtime authority). Preserve prior dirty candidate; never worktree prune.
No remote freshness claim from a local ref alone; fetch before shipment.

OBSERVED A3: /mnt/c/378u-ev-M6tQiU/A1/model_captures/T065.json[7],
T067.json[8..9], T079.json[5], snapshots prompt-2708/prompt-3175. Current
Shield equipped=false, AC16. Candidate proposed store followed by a character
update 'Stop carrying and wielding ... after storage' and stale18->16 AC.
Rejecting THAT candidate was justified: its later update targets an item the
storage operation removes, and its claimed AC change is stale. However, T065
directed unequip-before-store despite the already-unequipped canonical record.
The subsequent writer committed an unnecessary equipped=false/AC16 no-op.

CODE-PROVEN: both dirty prompts say 'unequipping before storing a carried
item' (full:23, compact:7), not 'currently equipped'. This paragraph is
UNCOMMITTED #378 work under D-378-1/2, absent from HEAD; no mainline origin
exists to invent. It may influence the unnecessary repair; causality is
HYPOTHESIS, not an isolated A/B. Do not call the whole rejection false or this
prompt residue pre-existing. The deterministic store guard already keys only
on canonical equipped is True and is not changed by this amendment.

## Minimal proposed change (task-Q1)

Two prompts ONLY: prompts/validation/validation_prompt.txt and
prompts/validation/validation_prompt_compressed.txt. In their identical
ORDINARY ACTION ORDER paragraph replace this exact substring:

    retrieval before equipping a previously stored item; unequipping before storing a carried item. The equipment update changes equipment state, not a second inventory addition or removal.

with:

    retrieval before equipping a previously stored item; unequipping before storing an item that is currently equipped. Use the supplied current equipment state: an already-unequipped item needs no equipment update merely to be stored. Remove an unnecessary equipment update from the candidate rather than inventing an unequip step; still reject stale state changes or duplicate inventory movement. A necessary equipment update changes equipment state, not a second inventory addition or removal.

Everything else in the paragraph and both files stays byte-identical. No item,
character, armor-value or verb-specific logic. No code-owned semantic decision,
new model/provider/schema/store/guard/config switch. No removal of validation
or forcing a reversed candidate to exercise the code. Existing shared T065
continues to adjudicate the candidate against current facts; storage owns the
movement and the existing character/effects tool owns genuine equipment change.
Current fields/commit points/lock order unchanged. Preserve source line endings
per region (new ordering lines LF; BOTH inherited prompt files have mixed CRLF).

## GL-1 and scope

| Behavior | Disposition and proof |
| --- | --- |
| Unequip before storing currently equipped item | PRESERVED: qualifier plus D-U1 canonical guard; real outgoing control |
| Require unequip just because item is carried | RETIRED as erroneous over-generalization of uncommitted D-378-2 ordering guidance; A3 observation; explicit owner approval of this amendment required |
| Retrieve before equipping previously stored item | PRESERVED byte-identical clause; real incoming control |
| Storage owns inventory movement; no duplicate add/remove | PRESERVED explicit text and unchanged manager; before/after item counts |
| Resolved consequences before combat/exit, unrelated order, dedicated travel/level-up | PRESERVED surrounding bytes; exact-diff check |
| Full reviewer on typed equipment_prerequisite | PRESERVED U3 code and signature; no bypass to manufacture test coverage |

No changes to storage manager, writer, handler, main, AC validation, scene,
schema, character files or provider bindings. Update only the two schematic
paragraphs to distinguish necessary equipment changes from no-op updates, plus
execution ledger, after approval (task-Q2). Older failed reports not rewritten.

## Review and acceptance

FULL because this amends the shared play-path ordering/GL-1 contract within a
FULL wave. Required separate blind seats: Architecture, Fail-Forward,
Acceptance, Consumer/Compat (both prompt consumers), Legacy/GL-1,
Player-Experience, No-Limits, Single-Path. No new machinery/public symbol or
>200-line code delta: Leanness conditional does not newly trigger; existing U3
mechanism review remains its own evidence. Reviewer may challenge applicability.
Each reads this plan and full ledger, reports raw sentinel scans as applicable,
R1-R15, and concrete counter-evidence for blockers. Same-SHA convergence;
post-review owner approval before implementation. After edits independent diff
audit and simplifier; no tracked tests or product harness.

task-Q3 after approval: isolate exact substring diff, ASCII and per-region EOL,
both paragraph equality, unchanged surrounding bytes, source/export/prompt
hashes. No gameplay claim from static tests or recorded-response replay.

task-Q4 after approval: serial native real OpenAI on a fresh authentic copied
game/current prompt bytes. A: legal carried-only unequip, then ordinary deposit
of that already-unequipped item; capture actual T065 request/current sheet and
candidate. Judge rejection reasons independently: legitimate stale/duplicate
drafts must still be rejected, not counted as a regression. PASS requires a
completed transfer without an invented equipment prerequisite; no-op repair
instruction is FAILED for this clarification. B: actual retrieve/equip and
equipped outgoing request, normal player prose with no dictated tool order;
counts/full metadata and current-tool frame. C: one real mixed items-array
request if naturally emitted, plus Save/intervening turn/Load/Quit. One input
at a real prompt, read response then decide next, no batched play commands.

For U3 guard firing: natural equipped-store execution must hit the actual
precondition and show no pre-write mutation, full current-facts handback,
corrective T067, actual full T065 on that repair and completion. If all accepted
drafts unequip first, retain NOT-REACHED, not a pass. No guaranteed legal
trigger is established; do not direct wrong tool order, change bindings/prompts
to weaken validation, inject captured outputs, edit state or create test-only
entrance. Scope of later acceptance waiver belongs to owner, not reviewers.
Stop on in-scope loss/duplication/unplayable loop; retain artifacts, no mid-run
repair. Do not keep spending on repeated identical trials without new evidence.

## Tracked follow-ups

#392 distinct T053 incorrect shield-only AC application; #371 unsupported T053
fields; #387 T051 unarmored Dex; #388 missing canonical container frame.
Other U3 follow-ups remain in the frozen parent plan, not absorbed or closed.

## Resolution ledger

| Finding | Disposition |
| --- | --- |
| A3 demanded unnecessary unequip despite equipped=false | task-Q1 |
| A3 candidate also invalid for stale/absent-item update | defensible: original rejection retained; only unnecessary repair clarified |
| Guard/full-repair not live reached in U3 | task-Q4: retain NOT-REACHED unless actual boundary fires, no waiver |
| Existing schema/locks/provider/AC mechanics | fyi: no change, #392 separate |
| Schematics and byte-preservation gates | task-Q2/task-Q3 |
| Post-convergence implementation authority | escalate:@owner: present reviewed amendment before edits |

## Review disposition (controller, 2026-09-13)

All eight independent seats returned LGTM on substantive SHA ef9b1fe7:
Architecture, Fail-Forward, Acceptance, Consumer/Compat, Legacy/GL-1,
Player-Experience, No-Limits and Single-Path. Raw returned text is preserved
in /mnt/c/agent-room-fleet-kit/local-data/378-u4-*-review.md. Separate forensic
review confirms no proven defect in the U3 code and characterizes this prompt
clarification as latency/unnecessary-write precision, not a core safety repair.
Do not imply the clarification proves or forces the U3 guard to fire.

Only plan-polish/FYI findings; no production-task change after review. Under
NEQ-REVIEW-11 plan-polish termination no further confirmation round is needed.
The exact proposed replacement text is unchanged. Execution stays owner-gated.

| Review finding | Disposition |
| --- | --- |
| Both files, not only compact, have mixed line endings | fixed-inline: Q3 description corrected; existing per-region check unchanged |
| T065 cannot edit a candidate itself | defensible: Q1 is correction guidance in the existing valid/reason contract; T067 remains sole drafter, no acceptance-while-ignoring implied |
| Harmless redundant pre-store update may still cause a retry | fyi: not a correctness failure; record cost. Q4 fails invented prerequisite or unsafe/stale acceptance, not every legitimate rejection |
| Stale/duplicate negative control must not pass if never emitted | fixed-inline: explicit reading of existing Q1 rejection requirement and Q4 honest NOT-REACHED rule; no new test arm |
| Q4 transfer proof needs disk/counts/unchanged equipment state | fixed-inline: existing Q4/parent acceptance applies to A too; never transcript-only PASS |
| Carried-item lead-in / per-character specificity / missing equipped field | fyi: no proven additional failure; existing named-character canonical frame and U3 strict-true guard retained, no speculative prompt expansion |
| Existing writer history[-10:] | fyi: exact existing issue #324 independently checked OPEN, not a new #262 finding |
| Existing progress-text slices | fyi: #262 umbrella, unchanged and no new incident attributed; no repair here |
| Single-Path S1 proposes collapsing full/compact prompts | defensible: D-374-1 and D-378-1/2 explicitly preserve both existing variants, one reviewer/loader/runtime. No divergent Q1 contract or new behavior fork shown. No collapse task or speculative new issue |
| Legacy alias/effects fallback context hits | fyi: existing #376/#300; no new pathway in Q1 |
| Hypothetical future writer removal after a repair | fyi: no new observed incident or code-class finding, do not manufacture another mechanism |
| Narration-before-storage commit | fyi: existing #360/#364 family; U3 already discloses, not fixed here |

Root independently read full as-sent T065[7] system prompt and exact candidate,
confirmed current code handback/reviewer boundary and both identical ordering
lines. The original A3 rejection outcome was justified; only the requested
repair over-generalized. Earlier report's broad 'over-rejection' label must be
read with this qualification. #392 is exact T053 follow-up, not #371/#387 alone.
