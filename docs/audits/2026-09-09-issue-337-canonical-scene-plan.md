# #337: canonical scene evidence and the separate #279 combat-side contract

Status: TWO-STAGE SCOPE APPROVED; stage-one FULL plan review complete; awaiting execution approval.
Date: 2026-09-09. Authority: live GitHub #193 v3.1, policy epoch
2026-09-09T22:13:35Z; D-337-1 codification reverified at epoch 2026-09-09T22:32:52Z.
Revision references below are review evidence, never runtime
authority. Re-fetch policy and main before execution.

## 1. Plain-language outcome and scope decision

The referee should see the same relevant location records that supported the DM's
proposal. Today it sees named NPC lists but not the structured monster and trap
entries. In the recorded fight it rejected a correctly supported boss and trap.
The DM obeyed that rejection; combat then mistook the boss for a party member.

There are TWO independently real faults, not one spelling error:

1. #337: incomplete and asymmetric evidence at semantic review. Proposed task-A
   gives T065 the full applicable location records, without changing its role.
2. #279: combat derives allegiance and completion from storage type/faction even
   though typed scene relations describe hostility. PR #339 attempts this repair
   but is not a safe or complete solution to inherit. Task-B below records the
   required end-to-end contract and the owner decision before designing its code.

Owner scope ruling D-337-1 (2026-09-09): "yes, I approve the two stage approach".
Task-A is the first wave for full review; keep #279 open and decide the model-authored
side contract in its separate second-stage plan. This may prevent the recorded Gorvek misclassification, but
does NOT claim to solve every hostile character-backed NPC or allied monster.
No production edits, live acceptance calls, commits or merges are part of this
planning turn. External writes are limited to D-337-1 codification and the separate
review finding #342, neither of which expands stage-one implementation scope.

## 2. Baseline, sources and corrected handoff claims

Fresh worktree: `/home/loup/neq-worktrees/337-canonical-scene-plan`.
Branch: `docs/337-canonical-scene-plan`, created from current fetched main at
`e754edefb44b550f14121b76fb2829bf2d11d419`. This is an evidence pin only.
Never prune Windows-created worktrees from WSL. Preserve all unrelated worktrees.

Read-before-reliance: `ISSUE_337_HANDOFF.md` in the old
`.worktrees/fix-279-encounter-faction` worktree. It is an untracked historical
handoff, not mainline doctrine. PR #339 remains OPEN and unmerged; its branch tip
was `3219dddc`, repair `94259e40`, base `6c541cc5`. No cherry-pick is proposed.
The prior fresh-review note is
`/mnt/c/agent-room-fleet-kit/local-data/337-fresh-plan-review.md`.
This document supersedes its tentative remedy, not its recorded observations.

Raw evidence root E:
`/mnt/c/vra-native/voice_ship_0214cbdf/debug/voice_ship_0214cbdf`.
Indices below are ZERO-BASED; preserve the files unchanged.

| Evidence | Class | Finding |
|---|---|---|
| E/captures/T067.json[14], invocation 067d7d1a-450a-4518-96af-96b4f7a16c06 | OBSERVED | Gorvek in monsters; six companions in npcs; pit in encounter context |
| E/captures/T065.json[13], invocation b9f1bd8b-410b-4a9f-a8f7-b21e5215207f | OBSERVED | Rejects pit and monster classification |
| E/captures/T067.json[15], invocation 53501a74-77b7-432b-b109-e6aead7a43e5 | OBSERVED | Receives that rejection, moves Gorvek to npcs and removes pit; hostility to PC remains |
| E/captures/T067.json[16], invocation e805781b-c7ac-45f8-80a2-47e18b1bda1d | OBSERVED | Subsequent correction is persistence enum, not another semantic classification |
| E/captures/T096.json[2,4,6] | OBSERVED | Gorvek attacks against PC rejected as attacks against ally |
| E/captures/T097.json[1] | OBSERVED | Narrates Gorvek attacking his own Bandit Warrior; Mira delivers the killing blow |
| E/game/modules/encounters/encounter_TW05-E1.json | OBSERVED | Gorvek persisted alive, npc, party, 12 HP |

Exact T065 rejection:

> Combat initiation is correctly immediate and the action format is valid, but the response invents a concealed pit trap not established in the provided location or event data. It also treats the existing NPC Bandit Captain Gorvek as a monster instead of including him among the encounter NPCs.

The AS-SENT T065 system messages have lengths 13613, 115, 703, 792 and 2882
characters. They DO contain canonical-derived location description/DM instructions,
NPC lists and location IDs. They DO NOT contain the structured monsters, quantities
or traps. The issue's older claim that the explicit pit block appeared in T065 is
contradicted by the capture; it appeared in T067. The handoff's later claim of
"no location data" is also too broad. Selective evidence omission is the precise
finding. Compression is not proved to have caused that historical omission.

Mainline `TW001_BU.json` TW05 lists Gorvek under both monsters and npcs, and the
Concealed Pit Trap under traps (lines 383, 408, 445). Other authored dual listings
include Corrupted Ranger Thane at NC04 and Malarok at NC05. This establishes that
dual listing is legitimate; it does not establish a universal array-precedence rule.

Boss XP repair is UNTESTED. The historical boss remained alive; his saved character
sheet has no CR. Correct monster routing plausibly restores the ordinary CR path,
but neither a generated stat block nor an actual persisted XP award is proven here.

## 3. Soup-to-nuts architecture and lineage

| Boundary | Current main, code proof | What must remain owned here |
|---|---|---|
| Module/atlas | path_encounter_analyzer.py:165,380; main.py:4698 | Canonical module-qualified IDs and detached location records; advisory context, not movement permission |
| DM T067 | Shared prepared party/snapshot request | Model proposes immediate structured actions; no mutation from prose |
| Normalization | main.py:3185 | Existing canonical names, action shape and typed scene checks |
| Membership T114 | main.py shared _review_dm_candidate | Model judges membership intent; not location-name keyword logic |
| Travel preflight | action_handler.py:2126,2173 | Route/target records validated BEFORE T065; accepted facts remain provisional |
| Semantic T065 | main.py:3232,10434 | Semantic coherence, agency, canonical claims and immediate beat; currently missing structured scene evidence |
| Publication | main.py:5264; action_handler.py:2173 | Currentness, real record identity, existing atomic/receipt semantics |
| Encounter builder | combat_builder.py:481-594 | Select sheet/stat-block route, reconcile exact participant IDs and scene facts |
| Combat state | combat_state.py:354 | Currently seeds enemy -> hostile, otherwise party: this is a semantic leak |
| T096 | combat_agent.py:383-400 | Sees creatures/sheets, not sceneFacts; currently receives the leaked faction |
| Legality/retarget | resolver.py:168,220; pipeline.py:94 | Current faction rejects same-side targets and drives ordered retargeting |
| Completion/defeat | combat_state.py:205,259,307; combat_manager.py:4108,4143 | Still combines type with faction; not fixed merely by teaching T096 about relations |
| XP | utils/xp.py:45-61 | Defeated enemy type plus monsterType/CR; no character-backed hostile XP path |

Lineage is mixed. Description-only location evidence traces to `c6323676` initial
import; this is the earliest available mainline evidence, not a claim about earlier
unavailable history. Type/faction seeding and same-side attack rejection trace to
`27a25ce2` (resumable deterministic agentic pipeline). Typed scene facts arrived in
`4290e711` (typed agentic combat foundation) without connecting every consumer.
The analogous canonical plot repair #332 is already on main in `e95bc243`; its
issue status is not evidence that the code is absent. Hub evidence was added by
`addf3809`. Reuse that evidence-boundary pattern rather than a new validator.

The atlas is refreshed in ordinary request preparation and passed to the DM each
cycle (main.py:4698; conversation_utils.py atlas injection). It also supplies the
shared snapshot for route checks and module-validation summaries. An atlas/name
index is NOT the complete current location record and does not resolve combat side.

## 4. Spec pin and authority ledger

Doctrine: #193 NEQ-CORE-03/04 (B1/B2), CORE-05/06 (AP-6/7), CORE-10 (lineage),
Part 2 p4 COMBAT-01/02/06/07, p8 conversation context, p10 WEB-01/03,
p11 PROVIDER-01/02, p12 SCHEMA-01/02, p13 ACCEPT-01/02/03 and TEST-02.
Architecture references read: travel-transitions.md, combat-typed-pipeline.md and
provider-routing.md. Their historical anchors are orientation, not current proof.
README promises preserved: Core Game Systems / Turn-Based Combat, meaningful
progression and living-world continuity; no claim of new game mechanics.

| Datum | Authority | Explicit non-authority |
|---|---|---|
| Current/origin location | Request-local party module+area+location identity | Candidate newLocation, narration |
| Applicable authored records | Same request-local active-module snapshot, unambiguous ID and area | NPC name-index membership alone, backup descriptions |
| Prospective destination | Existing accepted transition_facts plus matching snapshot record | A requested destination before preflight; proof of arrival |
| Hidden facts learned / events occurred | Immediate input and established committed play, judged agentically | Authored trap/quest existence alone |
| Combat intentions and relationships | Model-authored typed proposal reconciled with canonical IDs | Type, controller, name patterns; unrestricted prose parsed by code |
| State mutation | Existing publisher/transaction/currentness checks | New context block, validator approval alone |

Task-A is a read-only addition to an existing prepared request. No new lock, store,
persisted format, public API, mode, provider call or retry policy. Existing lock
order and child ownership remain unchanged; no provider wait under a party lock.
Provider/model: keep current registry selections, with real OpenAI as the primary
acceptance environment and no model/effort tuning in this repair. Native Windows
headless acceptance requires a physically valid checkout, never a WSL .git pointer
copied into a Windows game. WSL focused evidence is separately labeled.

## 5. Task-A: executable #337 proposal

### A.1 Source and selection

Use `module_snapshot` already passed to the single production T065 call. Full
records are `snapshot.nodes[id].location_data`; they were deep-copied from live
area files. Do not add another disk read or rebuild detached welcome history.

Select origin using the passed party's module/area/location. Require snapshot
module identity using the EXISTING space-to-underscore module convention, matching
node area/ID, and exclusion from `invalid_location_ids`. Do not resolve duplicates
by whichever file was loaded first. Snapshot diagnostics are evidence of
unavailability, not an empty room.

When accepted within-module transition_facts exist, add the full matching destination
record as PROSPECTIVE, using its accepted module/destination area/location IDs.
Never select a record from the DM's unapproved prose/newLocation. Cross-module
lookup remains in its existing owner; this change does not build foreign snapshots.
If the accepted facts cannot resolve within this snapshot, explicitly mark that
prospective evidence unavailable instead of substituting origin or another module.

Absent/mismatched/ambiguous record: attach a truthful unavailable label; do not
invent empty monsters/traps arrays, abort the turn, or treat lack of evidence as
permission. Existing route refusal/content-unavailable semantics are untouched.
Origin and prospective destination are independently selected and labeled.

### A.2 Placement and proposed instruction

Append one request-local system evidence block AFTER history compression and BEFORE
`_assemble_validation_messages`. Preserve existing description, NPC/atlas, hub,
plot, inventory and travel context. Preserve exact raw player/candidate adjacency,
strict-template handling and feedback isolation. No context is saved as fiction.
Serialize the complete selected location objects with JSON; no char/token caps,
top-N monster selection, name deny-list or new summaries.

Proposed contract text for owner/reviewer consideration:

> Canonical location records for this review follow. Origin is the party's recorded location. Any prospective destination is supplied by accepted provisional travel facts; it is not proof that movement has committed. Review the candidate against these records together with the actual player input and established events. A location's named NPC list records presence; appearing in that list does not by itself establish party allegiance or invalidate an authored monster entry for the same person. Judge the encounter role using the supplied scenario and typed proposal. Authored traps, secrets and future events establish scenario context, not that the party detected them, triggered them or earned their outcomes. Unavailable evidence is neither evidence of absence nor permission to invent facts. Keep all existing semantic, agency and single-beat checks.

This is agentic evidence and instruction, NOT a new code classifier. T065 remains
able to reject actual unsupported claims. Do not reduce it to format-only review,
blindly trust every model proposal, or force all dual-listed names into monsters.

### A.3 Entrants, failures and scope

One production caller: `_review_dm_candidate` -> validate_ai_response at main.py:10434.
Entrants: ordinary input; detached/synchronous welcome; fresh membership-bearing
internal/post-combat/follow-up; stale reviewed-travel re-review. Existing internal
nonmembership bypass at main.py:9810 is preserved, not silently expanded.
Ordinary preparation reads under existing lock; internal callers use the existing
request-local snapshot path at 9933; detached work retains its frozen base.
Scope checks before/after T065 and publication remain intact.

Provider/malformed-verdict reissues keep the same request. Semantic rejection revises
the candidate via the existing owner and repeats applicable gates. Load/Reset/Quit
supersession propagates and stale work cannot publish. No new exception swallowing,
failure counter, watchdog, refusal or recovery loop is introduced.

Production allowlist: `main.py` only. Documentation: this plan, execution evidence,
and a narrow travel-transitions.md evidence-flow update. No prompt-file rewrite,
schema, combat resolver, builder, XP, atlas generator, persistence or model binding
change. A need outside this boundary returns to the owner; it is not folded in.

## 6. Task-B: #279 dependency and owner contract question

PR #339 is NOT accepted as the solution. Its `apply_scene_declared_sides` recognizes
freeform words hostile/enemy/adversarial/opposed and uses the already misclassified
party set as a reference. Pure value-transform counterexample: PC, ally and boss
all begin faction=party; relations boss->PC hostile and ally->boss hostile. The
proposed helper promotes BOTH ally and boss to hostile. No gameplay run is claimed
by that diagnostic. `all_party_resolved` also still counts hostile type=npc as party.

Required future contract under COMBAT-02: the MODEL supplies structured scene-side
meaning; code reconciles identity/revision, projects declared values without prose
interpretation, and all combat consumers use that one authority. Construction,
T096, legal targeting/retargeting, victory/defeat, XP eligibility, transactions and
old-save continuation must be jointly accounted for. Controller, storage provenance,
presence, side and objectives remain distinct. No loss of companions or memories.

There is no existing typed side-change event in the traced intent/event/commit path.
Relation disposition is an unrestricted string, not a ratified side enum. Therefore
"just use relations" or "just set faction" does not specify a safe implementation.

D-337-1 RESOLVED YES: owner approved the two-stage approach on 2026-09-09.
Proceed with task-A review first, retaining #279 and PR #339 unmerged; second-stage
side/goal contract receives its own design, full review and execution approval.
No enum, side-change action, XP policy or schema change is implicitly approved.
This removes the stage-one scope blocker, not the post-review execution gate.

## 7. Implementation slices after review and owner approval

| Slice | Work and gate |
|---|---|
| C0 | Refresh main/193; clean worktree; freeze original packets, raw prompts and complete scene records; measure EOL by region; preserve baseline. No bulk formatting. |
| C1 | Add task-A record selection and late evidence block in main.py. Preserve existing flow and all currentness checks. |
| C2 | Focused value/serialization/source-selection checks, compile/undefined-name gate, consumer sweep, mandatory simplifier and independent diff review. No mocked gameplay tests. |
| C3 | Native real acceptance below, one operation at a time. Stop to report any new defect; no unrelated repair. |
| C4 | Independent five-point post-implementation audit, player transcript review, record every NOT-REACHED/FAILED arm. Present to owner; separate commit/push/merge authority required. |

GL-1 behavioral contract (additive plan, no guard retirement authorized):

| Existing behavior / origin | Disposition | Proof |
|---|---|---|
| Description/instruction location evidence, c6323676 initial import | PRESERVED | Existing message unchanged; full record appended separately |
| Raw player/candidate isolation and transient feedback, current shared review | PRESERVED | Exact message comparison; correction transcript and history check |
| Travel preflight before semantics and locked publication | PRESERVED | Call-order/code audit + real travel and control regression |
| Canonical hub/plot evidence, addf3809/e95bc243 | PRESERVED | Before/after payload blocks unchanged |
| All schema/type/identity/currentness rejection gates | PRESERVED | Pure schema checks plus real firing-path acceptance; no bypass |
| Provider retry/lifecycle/strict-template handling | PRESERVED | No code touch; cancellation and request-order checks |

Before C1, record exact current blame commits for any line actually replaced;
an unplanned deletion needs its own GL-1 row, not this table as blanket permission.

## 8. Acceptance specified before code

Fixture: official Thornwood, authentic pre-TW05 save copied into an isolated fresh
game with matching current prompts/config. Never modify the source save. Use
`run_headless.py serve` and supported client, one genuine action at a time; no
fabricated provider replies, state edits, model-shopping or concurrent acceptance.
Native interpreter/environment must be verified before launch. Budget/fixture
availability is a disclosed prerequisite, not permission to fabricate an encounter.

| Arm | Required observation and negative polarity |
|---|---|
| A0 forensic/source gate | Reconstruct original AS-SENT T065 and T067 chain; prove exact lost fields and legitimate dual listings. Parse real input records for absent/ambiguous/module-mismatch selection without simulating gameplay. |
| A1 original vertical slice | Real travel to TW05 and real hostile encounter. Actual T065 request contains both Gorvek lists, quantities and pit. Correct monster proposal is not rejected solely for NPC-list membership. Capture resulting roster/sheet path, T096 intent/corrections, T097 verbatim, and return to a real player turn. If no such T065 candidate occurs, NOT-REACHED, not PASS. |
| A2 negative semantics | Through normal play reach a real unsupported candidate/rejection and continuing correction. Verify no invalid mutation or rejected draft in accepted history. Also check authored hidden pit is not auto-revealed/triggered solely because now in reviewer context. No deliberately fabricated model reply. |
| A3 location/prospective polarity | Travel between different canonical locations; show request origin and approved prospective destination are labeled, no stale TW05 trap leaked as current fact elsewhere, arrival follows commit. Unsupported target remains governed by existing route preflight. |
| A4 consumers/compatibility | Existing save Load/relaunch; one normal noncombat turn; naturally reached welcome/follow-up where applicable; cancelled in-flight review cannot publish. Exact raw-input/candidate order and hub/plot blocks survive. Unreached entrant/cancellation arms explicitly NOT-REACHED. |
| A5 conditional XP extension | Only if normal A1 combat reaches boss defeat: inspect generated CR/source, real award and persisted XP. Otherwise no XP-fix claim and record NOT-REACHED. Not a substitute for A1. |

Evidence per arm: checkout/ancestry; loaded prompt hashes matching fresh checkout;
actual provider and response.model when exposed (UNKNOWN if unavailable, never
invented from configured model); callsite/capture indices and request keys;
latency relative to input, turn wall time and tokens; complete player transcript;
before/after canonical location/roster/encounter/history; zero or actual counts of
retry/degrade/invalid/stale events with scan command. Added request size and measured
cost delta reported; no claim that full records are cost-free. PX reviewer checks
five narration claims against disk, perception/agency, own dice, pacing and next move.
Tests prove their assertions only. No real acceptance has run for this plan.

## 9. Review protocol and gates

Run the plan review protocol. FULL chosen because shared gameplay evidence,
canonical-semantic boundary and rejected replacement proposals need full scrutiny.
Standing seats: Architecture, Fail-Forward (B1/B2 verbatim), Acceptance, No-Limits,
Single-Path. Conditional: Consumer/Compat (shared T065), PX (semantic/player output).
Legacy-Contract is applicable to the proposed replacement alternatives/GL-1 review;
Leanness checks that task-A adds no public mechanism and task-B does not smuggle one.
Schema-Freeze: no schema edit, inspect and retain baseline contracts. Platform,
provider, ASCII/secrets hygiene apply. Large-change gate not currently triggered.

Separate blind reviewers read this exact plan and full resolution ledger; controller
single-writes. Every blocker needs concrete failing input/sequence and code/evidence.
Same-SHA convergence plus confirmation as #193 requires; owner contract questions
escalate rather than churn. Sentinel plan-stage scans of baseline touched files must
be labeled baseline, NOT candidate-diff approval: no product diff exists yet. Both
sentinels re-scan actual C1 diff+touched files before execution/merge gates.
No review result authorizes implementation; return plan to owner after review.

## Tracked follow-ups

- #279 / PR #339: full allegiance, completion/defeat and XP consumer repair remains
  unresolved. Existing issue, no new duplicate filing. Task-B describes why.
- #337: owner of task-A; old issue/handoff claims require evidence correction when
  external updates are authorized, not silently re-used as truth.
- #332: plot-context repair exists on main; stale open status is bookkeeping, not
  missing code. No duplicate implementation.
- #342: diagnostic-file write failure can terminate candidate review and be
  misreported as provider failure. Independently code-proven, runtime NOT-REACHED;
  filed separately during review, not repaired by stage one.
- No unrelated fixes are included in stage one.

## Resolution ledger

| ID | Evidence/finding | Disposition |
|---|---|---|
| F1 | T065 asymmetric scene evidence | task-A |
| F2 | NPC-list presence treated as exclusive combat category | task-A |
| F3 | Handoff/issue disagree with actual T065 packet | task-C0; corrected in section 2 |
| F4 | PR339 hostile-word parser can promote ally attacking misclassified boss | override: D-337-1 owner-approved second stage under existing #279, PR339 unmerged |
| F5 | Main type/faction consumers contradict typed scene authority | override: D-337-1 owner-approved second stage under existing #279 |
| F6 | XP remediation claimed without kill/award proof | task-A5; no XP-fix claim otherwise |
| F7 | #332 fix already present on main | fyi; no duplicate code |
| F8 | Pre-existing diagnostic-file failure can abandon player action | issue-#342; PRE_EXISTING_OUT, code-proven/runtime NOT-REACHED |
| F9 | Historical narration summary overstated who delivered the killing blow | fixed-inline; evidence wording only, task-A and acceptance unchanged |
| D-337-1 | Scope/sequence of narrow evidence repair versus full side contract | override: owner approved two stages 2026-09-09; stage-one full review may proceed |
| D-337-2 | Post-review execution approval | escalate:@owner; plan only |

Review status: all nine independent FULL seats returned no in-scope blocking
findings on SHA256 24d90d3743cd416a5aed7c4a2233748e6ef3e5922f31e95ee95eea52d71b82bd.
Controller folded only evidence wording, scope-ruling epoch and ledger/status
polish after full coverage. No code steps, tasks, types, states, tests or callsites
changed. NEQ-REVIEW-11 plan-polish termination applies; no code-class correction
awaits R2. See 2026-09-09-issue-337-full-review.md for raw-report paths and limits.
Actual product-diff scans and all native acceptance remain pending. This completes
plan review, not the D-337-2 execution gate.
