# TW-008 / #238 Compaction-Guard Recovery Plan

Status: DESIGN ONLY - implementation is blocked until the six-lens Part 3
review converges and Claude independently approves this exact document.

Date: 2026-08-27

Branch: `fix/tw008-compaction-guard-recovery`

Base: `d9d1c7db7c6519c096da7bb755cf6dec1166cc46` (the shipped TW-005 tip)

## 1. Authority and evidence

This plan follows live GitHub issue #193 v1.7, refreshed 2026-08-27 at
`2026-08-27T17:30:16Z`:

- Part 1 lines 15-43: never break play; gameplay recovery must fail forward;
  limits may reissue but may not abandon work.
- Part 1 lines 45-92: AP-1 through AP-7 and the leanness law.
- Part 1 lines 94-117: observed evidence, verdict discipline, and mainline
  lineage.
- Part 2 page 8, lines 190-198: conversation compression is never
  load-bearing and must not drop history or progression.
- Part 2 page 10, lines 207-215: on-disk state is UI truth and long work must
  remain live.
- Part 2 page 12, lines 229-238: schemas and player data remain compatible;
  state writers preserve unrelated values.
- Part 2 page 13, lines 240-253: native real-provider play and on-disk state
  decide acceptance; probes run one at a time.
- Canonical native headless harness owner ruling:
  https://github.com/MoonlightByte/NeverEndingQuest/issues/193#issuecomment-5442810941

Observed defect and owner mandate:

- #238: https://github.com/MoonlightByte/NeverEndingQuest/issues/238
- Owner brief:
  `/mnt/c/agent-room-fleet-kit/local-data/tw008-fix-brief.md`
- Native TW-005 recovery capture:
  `validation_evidence/tw005_codex_wsl/a1-protocol.ndjson`
- Copied stopped-game checkpoint and state under the local TW-005 evidence
  tree.

The real stopped transaction proves the following sequence:

1. Its origin segment has 19 entries beginning at index zero.
2. Ordinary startup rebuilds two values before recovery: the generated
   `Current Location` projection changes from committed origin RO01 to
   committed destination RO02, and the last DM note takes the already
   sanctioned legacy-normalized representation.
3. All other entries remain exact.
4. TW-005 commits the one staged journal entry and retains arrival narration.
5. `compact_with_accepted_departure_summary` then rejects the correctly
   rebuilt destination projection and raises
   `departure conversation segment changed before compaction`.
6. The marker remains `narration_retained`, the pending update-time receipt
   remains unapplied, and the engine exits at 09:10 instead of reaching 09:15.

TW-009 is separately shelved as #239. Its T035 provider liveness gap is not
part of this plan: https://github.com/MoonlightByte/NeverEndingQuest/issues/239

## 2. Goal and preserved contracts

A committed within-module travel must resume through compaction when startup
has rebuilt only the code-generated location projection from the staged origin
to the checkpoint's committed destination. The same operation then applies its
already-staged time receipt once, publishes retained narration, clears its
marker at the existing durable boundary, and reopens input.

The change must preserve all of these existing goals:

1. The accepted T016 departure summary is reused; recovery never regenerates
   accepted departure work.
2. The exact source segment and existing legacy-DM-note representation remain
   accepted as before.
3. Any history change not exactly explained by the checkpoint's
   origin-to-canonical-destination projection remains a conflict.
4. Journal, area, time, narration, delivery, marker removal, and input reopen
   keep their current ordering and exactly-once receipts.
5. Startup continues to expose the authoritative committed destination, not a
   stale origin, to models and players.
6. Normal non-crashed travel and legacy repair keep their current compaction
   contract.
7. Existing markers require no migration and no new field.

## 3. Approaches evaluated

### Approach A - exact canonical destination variant (selected)

At the existing resume-only call, load the current location object through the
same canonical party/location path already used for arrival narration. Pass
that object and the checkpoint's exact origin and destination IDs to
`compact_with_accepted_departure_summary`.

The helper constructs two additional exact candidate segments in memory:

- staged source with its one code-generated origin-location envelope replaced
  by the canonical destination-location envelope;
- the same value replacement after the already-supported legacy DM-note
  normalization.

The helper accepts only exact equality to one of the four representations:
original, legacy-normalized, destination-refreshed, or destination-refreshed
plus legacy normalization.

The replacement is legal only when all of these value checks pass:

- the supplied canonical location is a dictionary whose `locationId` equals
  the checkpoint destination ID;
- the staged segment contains exactly one code-generated `Current Location`
  JSON envelope;
- that envelope parses as a dictionary whose `locationId` equals the
  checkpoint origin ID;
- the replacement envelope is generated from the canonical destination object
  with the same `adventureSummary` omission and compact JSON representation as
  startup;
- every other entry remains byte-for-value exact after the existing optional
  DM-note normalization.

This is value authority, not prose inference or hash authority. The fixed
`Current Location` envelope is generated and consumed by code, its payload is
JSON, both IDs come from the durable checkpoint, and the destination object
comes from canonical area state. Names, verbs, narrative text, and digests do
not decide acceptance.

Why selected: it heals existing markers, preserves current startup truth,
changes only the observed resume seam, and retains exact corruption detection
without a new schema, journal, marker, recovery pass, or heuristic list.

### Approach B - suppress startup location refresh until compaction (rejected)

This would keep the old segment exact, but would deliberately expose stale
origin context after movement committed to the destination. It changes the
working startup and prompt paths, risks incorrect welcome/narration, and solves
the guard by weakening authoritative context. It violates the owner contract
and AP-5.

### Approach C - compact before startup refresh (rejected)

Reordering recovery and startup would touch a much larger lifecycle, could run
provider or mutation work before the UI is ready, and changes multiple crash
boundaries to avoid one exact comparison. It is not the minimum repair.

### Approach D - accept any current slice, or compare only location IDs
(rejected)

Either form would bless unrelated edits to player history or corrupted
location fields. It would turn a precise integrity gate into fail-open behavior
and violate AP-7.

### Approach E - persist a post-refresh segment in new markers (rejected)

It would not heal the existing stopped marker and would add schema/migration
machinery despite the destination projection being derivable from existing
canonical values.

## 4. Planned production change

Production allowlist:

- `core/ai/cumulative_summary.py`
- `main.py`

No other production file may change. There are no schema, prompt, model,
provider, configuration, persisted-field, or UI changes.

### Slice 1 - make the exact helper variant explicit

Extend `compact_with_accepted_departure_summary` with optional resume-only
inputs for the staged origin ID, staged destination ID, and canonical
destination location object. Defaults preserve every current caller.

Add one private, pure value helper that:

1. deep-copies a supplied source representation;
2. recognizes only the exact code-generated `Current Location` JSON envelope;
3. requires exactly one origin-ID match;
4. builds the exact canonical destination envelope;
5. replaces only that entry; and
6. returns no candidate when any structural or identity condition is unmet.

The compaction function compares `current_slice` against explicit exact
candidates. It retains the existing `ValueError` for every unexplained change.

### Slice 2 - authorize the variant only on committed-movement resume

In `_resume_v2_location_transition`, after the existing party-location check,
obtain the canonical current destination location through
`get_location_data_from_party_tracker(party)`. Supply it and the checkpoint IDs
only to the resume compaction call.

Do not pass the allowance from normal travel, legacy repair, or unrelated
compaction callers. Do not change startup refresh, the checkpoint, or the
order of any commit.

### Slice 3 - simplifier pass

After implementation, reread every changed line and remove duplication,
unnecessary branches, broad exception handling, generic abstractions, and any
comment not needed to preserve the authority boundary. Confirm the final diff
still expresses all seven preserved goals and nothing beyond #238.

### GL-1 behavioral contract for the shared guard

Slice 1 replaces the guard introduced by commit
`b7f7a8631d339c4e1b00d7ffd0b81cf0f4020975`, `fix(travel): make agentic
transitions recoverable`, under the owner-approved
`docs/plans/2026-08-23-single-turn-travel-amendment.md`. The originating commit
did not name a GitHub issue; #238 is the observed authority for this narrow
replacement. Nothing in the guard is retired.

| Existing branch / goal | Planned disposition | Proving check |
|---|---|---|
| An already-present summary with the same `message_id` returns idempotently before source comparison. | PRESERVED by the unchanged early return in `compact_with_accepted_departure_summary`. | Development check 9; A1 restart/replay shows no duplicate summary or narration. |
| The exact staged source segment is accepted. | PRESERVED as an explicit exact candidate in Slice 1. | Development check 1; A3 normal-travel control. |
| The existing legacy-DM-note-normalized source is accepted. | PRESERVED as an explicit exact candidate; `normalize_legacy_dm_notes` remains unchanged. | Development check 2; caller/default audit. |
| Every source change not explained by a sanctioned exact representation raises before mutation. | PRESERVED by full-list equality and the unchanged `ValueError`; the only added representations replace one canonical, identity-checked envelope. | Development checks 5-8; every A4 integrity-gate row. |
| Accepted compaction replaces exactly the staged slice with one accepted summary entry and preserves all other history. | PRESERVED by the unchanged slice assignment/result construction. | Development checks 1-4 and 10; A1 durable-history diff and A3 normal control. |
| Legacy-repair and normal-travel callers retain the original two-representation contract. | PRESERVED by optional defaults; only the committed-movement resume caller supplies canonical destination inputs. | Complete three-caller audit; development check 10; A3. |

## 5. Failure semantics and invariants

- Canonical destination unavailable or wrong ID: no extra candidate exists;
  the existing integrity behavior remains. This plan does not change #211's
  generic engine-stop presentation.
- Missing, malformed, duplicated, or wrong-origin location envelope: no extra
  candidate exists.
- Destination envelope differs from the canonical destination object in any
  field: rejected.
- Any other system, user, assistant, ID, order, or length change: rejected.
- Already-compacted summary identity remains idempotent and returns before
  source comparison.
- The helper is pure; it mutates neither the checkpoint nor live history.
- No provider call, dice, semantic decision, or new persistence occurs in the
  new comparison.
- The existing save and checkpoint writes remain the only mutation owners.

## 6. Development checks

Local deterministic checks are aids, not gameplay acceptance:

1. exact staged source passes;
2. legacy-normalized source passes;
3. exact destination-refreshed source passes;
4. destination-refreshed plus legacy normalization passes;
5. wrong destination ID fails;
6. canonical destination field tampering fails;
7. unrelated user/assistant/system mutation fails;
8. missing or duplicate location envelope fails;
9. existing summary entry remains idempotent;
10. default arguments preserve all other callers.

Run native-Windows `py_compile` for both changed files, `git diff --check`, an
ASCII-only added-lines check, and a complete changed-caller audit.

## 7. Native Windows / real OpenAI acceptance

All probes use separate copied game directories and run sequentially through
native Windows `C:\Python312\python.exe run_headless.py serve`. They use the
configured OpenAI provider and actual callsite bindings. Artifacts remain
local/ignored. No source fixture is edited.

### A1 - exact stopped-game recovery (primary gate)

Copy codex-ps's preserved `game-a0bfcd2d` and record source/copy hashes. Start
the copy on this branch. Wait until the welcome has settled, then send one
recorded nonblank immediate action.

Require all of the following:

- the existing pending operation resumes without a new travel command;
- TW-005 leaves exactly one journal entry deep-equal to the checkpoint's staged
  index-zero value;
- compaction accepts only the canonical RO01-to-RO02 rebuilt projection and
  emits no `departure conversation segment changed before compaction` error;
- the existing pending update-time receipt changes 09:10 to 09:15 exactly once;
- narration is durably published, the marker clears at the existing boundary,
  and input reopens at RO001/RO02;
- before or with that prompt, the restarted player surface shows the recent
  player-visible history held in durable conversation state; a blank-history
  restart fails even if later mechanics recover;
- the new immediate action is not lost or duplicated and receives exactly one
  DM resolution;
- one further ordinary action at RO02 completes and input opens again;
- restart/replay remains at 09:15 with one journal entry, no duplicate
  departure/narration/time application, and no accepted-work provider redo.

Capture complete protocol, commands, API-call identities, marker lifecycle,
journal, party tracker, and durable conversation before/after.

The timestamped player stream must also prove the submitted input is visibly
acknowledged within one event cycle. If recovery, chronicle work, or the
subsequent provider-backed resolution takes longer than roughly ten seconds,
the stream must show truthful changing progress rather than one stale line. It
must then show observable recovery completion and the reopened prompt. These
are acceptance oracles only; they do not authorize new TW-008 status or UI
machinery.

The Player-Experience review must inspect the actual retained transition text
in that complete transcript. It must address the sole PC in second person,
reveal no unsensed facts, and choose no player action or roll. Five concrete
narration claims must be checked against authoritative disk state, including
the RO02 location and 09:15 time plus three claims about named participants,
committed events, inventory, or observable surroundings that the narration
actually makes. Any RO01/09:10 claim after the corresponding commit, invented
mechanic, private fact, or player-choice substitution fails the probe.

### A2 - fresh induced crash and recovery

On a fresh copied Thornwood game, play a real connected travel and terminate
the process at the already-defined post-movement/pre-compaction crash boundary.
Do not edit gameplay state. Restart through native serve and require the same
forward recovery, exact-once time/journal/narration behavior, marker cleanup,
and reopened destination prompt.

### A3 - normal non-crashed travel negative control

Run one ordinary connected travel without interruption. Require the existing
three-agent transition narration, one immediate semantic beat, exact time and
journal increments, marker cleanup, and a destination prompt. Then run a
subsequent connected travel to confirm prior journal entries remain exact.

### A4 - integrity gate polarity

On disposable copies, alter one value at a time before compaction:

- a non-location user/assistant entry;
- one canonical destination location field in the current projection;
- destination `locationId`;
- duplicate or remove the code-generated location envelope.

Each must reach and fire the retained integrity gate; none may compact, apply
the pending time receipt, clear the marker, or overwrite the altered history.
These are deterministic corruption controls, not simulated gameplay proof.
Record the exact exit/state and retain #211's presentation as out of scope.

### A5 - compatibility and cleanup

Diff every rewritten persisted file for non-empty-to-empty changes. Verify no
orphan Windows processes, no source-fixture mutation, no tracked evidence, and
no change outside the two-file allowlist. Report actual provider/model from
captures. A1 is mandatory; a NOT-REACHED downstream boundary is not a pass.

### Mandatory verdict table

Every probe and every boundary receives its own `PASSED`, `FAILED`, `BLOCKED`,
or `NOT-REACHED` verdict with the exact command plus protocol, exit, and
relevant on-disk artifact. No arm receives a single aggregate PASS that hides a
different failed boundary.

| Probe | Separately reported boundaries |
|---|---|
| A1 | prior compaction guard reached; canonical destination variant accepted; time receipt committed; narration published; marker cleared; recent history visible; first input resolved once; follow-up prompt/action; replay idempotency |
| A2 | crash boundary reached; restart recovery; exact-once mechanics/delivery; marker clear; prompt reopen |
| A3 | first normal travel; subsequent travel; three-agent narration; journal/time preservation; prompt reopen |
| A4, each mutation independently | **Integrity gate** verdict and **player continuation** verdict are separate. Expected evidence may be `integrity gate: PASSED` and `player continuation: FAILED (#211)`; that continuation failure is attached to #211 and is never labeled a TW-008 pass. A mutation that never reaches the gate is `NOT-REACHED`, not pass. |
| A5 | persisted-state compatibility diff; provider/model truth; process cleanup; fixture preservation; two-file allowlist |

An artifact missing from a row makes that claim HYPOTHESIS. The final report
must preserve mixed verdicts instead of converting an expected tracked failure
into success.

## 8. Tracked follow-ups

These findings are intentionally excluded from TW-008 and already have issue
authority; none is treated as an unnumbered limitation:

| Issue | Disposition in this plan | Reason |
|---|---|---|
| #211 | TRACKED / NOT FIXED | Generic transition-recovery exceptions can stop the engine. TW-008 preserves its polarity while A4 proves the retained gate still fires. |
| #237 | TRACKED / NOT FIXED | Partial area/journal pair recovery can be intercepted by the outer preflight. It is a different earlier ordering seam. |
| #239 / TW-009 | SHELVED / NOT FIXED | T035 NPC generation lacks task-local liveness recovery. It is a different callsite and provider-liveness design. |

No other deferred finding is known. A newly observed adjacent defect must be
filed in the same turn and added here rather than absorbed into implementation.

## 9. Resolution ledger

| ID | Round / lens | Evidence class and finding | Resolution | Status |
|---|---|---|---|---|
| TW008-R1-ARCH-1 | Round 1 / Architecture | CODE-PROVEN: the production design is sound, but mandatory `Tracked follow-ups` and `Resolution ledger` sections were absent. | Added both sections; enumerated #211, #237, and #239; recorded every round-1 result. | RESOLVED IN PLAN; re-review required |
| TW008-R1-FF-1 | Round 1 / Fail-Forward | CODE-PROVEN CLEAN: legitimate canonical rebuild can complete; corruption remains retained; no B1/B2 bound or abandonment is added. | No plan change required. | CLEAN; same-SHA re-confirmation required |
| TW008-R1-PX-1 | Round 1 / Player Experience | CODE-PROVEN: A1 allowed a silent 30-60 second recovery while otherwise satisfying its state oracles. | Added one-cycle acknowledgment, truthful changing progress after roughly ten seconds, observable completion, and prompt-reopen transcript requirements; acceptance-only, no new mechanism. | RESOLVED IN PLAN; re-review required |
| TW008-R2-ARCH-1 | Round 2 / Architecture | CODE-PROVEN CLEAN: mandatory ledgers, caller scoping, canonical value authority, and mutation ownership all pass. | No plan change required. | CLEAN on prior SHA; same-SHA re-confirmation required after PX amendment |
| TW008-R2-FF-1 | Round 2 / Fail-Forward | CODE-PROVEN CLEAN: the pacing oracle is CONTINUES-class evidence, not a timeout; no B1/B2/FS-1 blocker. | No plan change required. | CLEAN on prior SHA; same-SHA re-confirmation required after PX amendment |
| TW008-R2-PX-1 | Round 2 / Player Experience | CODE-PROVEN CLEAN: the round-1 acknowledgment and pacing blocker is resolved. | No further change for PX-1. | CLEAN |
| TW008-R2-PX-2 | Round 2 / Player Experience | CODE-PROVEN: A1 captured protocol and disk history but did not require the restarted surface to display recent durable player history. | Added a protocol-to-durable-history comparison and made blank-history restart a failure. | RESOLVED IN PLAN; re-review required |
| TW008-R2-PX-3 | Round 2 / Player Experience | CODE-PROVEN: once-only narration could still pass while using wrong voice, leaking hidden facts, choosing for the player, or contradicting RO02/09:15 disk state. | Added actual-transcript voice, perceivability, agency, and five-claim truth-to-disk checks. | RESOLVED IN PLAN; re-review required |
| TW008-R3-ARCH-1 | Round 3 / Architecture | CODE-PROVEN CLEAN: PX additions are acceptance-only; canonical authority, callers, ledgers, and mutation ownership remain sound. | No plan change required. | CLEAN on prior SHA; same-SHA re-confirmation required |
| TW008-R3-FF-1 | Round 3 / Fail-Forward | CODE-PROVEN CLEAN: PX evidence adds no runtime bound, refusal, retry, or abandonment. | No plan change required. | CLEAN on prior SHA; same-SHA re-confirmation required |
| TW008-R3-PX-1 | Round 3 / Player Experience | CODE-PROVEN CLEAN: all seven applicable PX contracts have explicit oracles. | No plan change required. | CLEAN on prior SHA; same-SHA re-confirmation required |
| TW008-R3-LEAN-1 | Round 3b / Leanness | CODE-PROVEN CLEAN: failure citation, three-caller coverage, net-negative, cascade, and mechanism audits pass. | No plan change required. | CLEAN on prior SHA; same-SHA re-confirmation required |
| TW008-R3-ACC-1 | Round 3b / Acceptance | CODE-PROVEN: A4 could report expected integrity-gate firing as a pass while concealing the separate #211 engine-exit failure. | Added mandatory per-boundary taxonomy/artifacts for A1-A5 and separate A4 integrity/continuation verdicts; mixed verdicts cannot become aggregate pass. | RESOLVED IN PLAN; re-review required |
| TW008-R3-COMPAT-1 | Round 3b / Consumer-Compat + GL-1 | CODE-PROVEN: the shared guard replacement lacked the mandatory origin/goal/disposition/proof table. Consumer and existing-marker compatibility otherwise passed. | Added the GL-1 behavioral contract for commit b7f7a8631; every branch/goal is PRESERVED with planned location and evidence. | RESOLVED IN PLAN; re-review required |

Open owner decisions: none. Implementation remains blocked by review
convergence and independent Claude approval; convergence itself does not grant
execution authority.

## 10. Review pins and owner gates

The six Part 3 lenses must independently verify this exact plan:

- Architecture: the destination variant is derived from existing canonical
  authorities and reaches only the resume compaction call.
- Fail-Forward/FS-1: the legal restart variant completes, while corruption is
  neither overwritten nor mislabeled as recovered.
- Player Experience: recovery publishes the retained transition, advances the
  committed clock, and visibly reopens play without duplicate narration.
- Acceptance: A1 proves the full previously blocked lifecycle; A4 proves gate
  polarity; synthetic checks make no gameplay claim.
- Compatibility/GL-1: every preserved goal and every other caller remains
  intact; existing markers require no migration.
- Leanness: two files, one private pure helper, no new state, no lifecycle
  reorder, no generic recovery framework, and no work on #211/#237/TW-009.

Implementation remains blocked until all six review the same SHA cleanly and
Claude approves that SHA. Any scope-changing revision resets the review gate.

Merge, push, premerge mutation, and deployment remain owner-only after native
acceptance and independent evidence review.
