# TW-005 Departure Journal Fail-Forward Plan

Status: DRAFT FOR PART-3 REVIEW. No implementation is authorized by this file.

## Authority and scope

- Owner directive: GO, fix TW-005 narrowly.
- Constitution: GitHub issue #193 v1.7, refreshed 2026-08-27 at
  `2026-08-27T17:30:16Z`; Part 1 and Part-2 pages 8, 10, 12, and 13 apply.
- Canonical acceptance harness: `run_headless.py serve`, per
  https://github.com/MoonlightByte/NeverEndingQuest/issues/193#issuecomment-5442810941.
- Base: `a0bfcd2de8bf0da909463a56aaf52ce73c7232e9`.
- Branch: `fix/tw005-departure-journal-failforward`.
- Production allowlist: `core/ai/action_handler.py` only.
- No premerge edit, merge, provider change, schema change, new marker, new
  recovery subsystem, prompt change, or adjacent blocked-conflict repair.

## Observed failure and attribution

OBSERVED evidence is preserved under
`C:/dungeon_master_v1/.worktrees/premerge-combat-tip-validation/validation_evidence/thornwood_campaign/`.
The real OpenAI headless stream records:

- first RO01 to RO02 travel exiting at protocol events 1547-1548 with
  `RuntimeError: journal is unavailable during departure commit`;
- ordinary restart re-entering the same pending transaction and exiting again
  at events 1718-1719;
- the preserved game has no `journal.json` anywhere;
- `pending_location_transition.json` is `departure_pending`, operation
  `4a85528c-0959-4bb4-906a-51380f4b29af`, with departure status `staged`, origin
  `RO001/RO01`, destination `RO001/RO02`, and `journal_entry_index == 0`.

CODE-PROVEN at `a0bfcd2d`:

1. `_new_current_transition_checkpoint` treats a missing journal as zero entries
   and stages index zero.
2. `resolve_current_transition_departure` later reloads `journal.json`; the
   normal missing-file result is `None` from `safe_json_load`.
3. The guard at `core/ai/action_handler.py:970-973` treats that legitimate fresh
   state as invalid and raises, terminating the player-visible operation.
4. The existing `adv_summary.commit_departure_summary` transaction already
   supports an absent journal when its expected before-state has zero entries;
   it writes the complete area/journal pair through its established recovery
   marker and atomic writers.
5. `run_headless.py` and `HeadlessSession.bootstrap` change CWD to the supplied
   game directory. The relative `journal.json` therefore denotes the preserved
   game root, not the source checkout.
6. This workflow was introduced on the travel-recovery bundle in commit
   `b7f7a8631`, so TW-005 is an OUR-BUNDLE regression rather than mainline
   compatibility behavior.

CODE-PROVEN but not observed in this incident: an outer-preflight ordering gap
could prevent the existing departure-summary transaction from reconciling its
own partial area/journal write. Issue #237 records that distinct defect. AP-5
and the owner's narrow-scope ruling prohibit changing or accepting it in
TW-005.

## Contract to preserve

- A genuinely missing journal is the canonical zero-entry state for a fresh
  campaign and for this staged index-zero recovery.
- A valid `{"entries": []}` journal remains unchanged behavior.
- Malformed or non-object journal content remains an integrity error.
- Missing journal plus expected index greater than zero remains a genuine
  inconsistency and reaches the existing journal-length blocked-conflict path.
- The already-committed comparison remains exact and idempotent.
- Area-before/area-after and journal-length conflict checks remain intact.
- The existing crash-recoverable area/journal commit owns journal creation; the
  fix must not pre-create or separately write `journal.json`.
- The three-agent travel narration chain and one-immediate-beat boundary remain
  unchanged.

## Options

### A - normalize only the absent read to the canonical empty value (selected)

Record whether `journal.json` exists, then load it. Only when the file is absent
and the load result is `None`, use `{"entries": []}` as the in-memory
before-state. Change the following structural guard to `elif` so a present JSON
`null`, malformed object, or non-list `entries` still raises. Continue through
the existing idempotency, conflict, and transaction code unchanged. The
established commit revalidates existence and values under its target locks, so
a concurrent create cannot be overwritten silently.

Why selected: this is the smallest value-based correction at the failing
boundary. It exactly matches checkpoint creation and the existing transaction's
absent-file policy. It adds no writer, retry loop, persisted field, heuristic,
or scenario-specific ID/name test.

### B - create `journal.json` before the transaction (rejected)

Writing an empty file before `commit_departure_summary` would split one existing
atomic area/journal transaction into an extra mutation. A crash between the new
write and the transaction would manufacture state outside the receipt, and a
concurrent writer could be overwritten. This is larger and less safe.

### C - catch the RuntimeError at restart/game-loop level (rejected)

This would preserve the invalid guard, risk an endless restart loop, and turn a
local value mismatch into broad lifecycle machinery. It does not complete the
travel and violates B1/FS-1.

## Implementation slices

1. In `resolve_current_transition_departure`, add absent-only journal
   normalization and retain malformed-present rejection.
2. Run the mandatory simplifier review. Expected result: one local branch and
   no new helper because a helper would add surface without a second caller.
3. Run deterministic development checks only to establish branch polarity:
   absent/index-zero proceeds to the existing transaction, empty valid remains
   equivalent, malformed present still rejects, expected index greater than
   zero still records `blocked_conflict`, and already-committed state remains
   idempotent. These checks do not accept gameplay.
4. Run native-Windows real-OpenAI acceptance sequentially through
   `run_headless.py serve`.

## Native acceptance

All runs use copied fixtures and preserve the codex-ps source evidence byte for
byte. Tests and artifacts remain local/ignored.

### A1 - stuck-repro recovery (primary gate)

Copy the preserved `game-a0bfcd2d` directory without editing its state. Record
the source and copy hashes for the pending checkpoint and canonical files.
Launch the copy on this fix branch through native Windows `run_headless.py serve`
with configured OpenAI. Startup is expected to expose its normal prompt while
leaving the v2 record `resume_required`; send one recorded nonblank immediate
input (for example, inspect the depot). The live-turn boundary must finish and
publish the older travel before applying that input, then continue the same
input normally. Require:

- the first nonblank input consumes the existing `departure_pending` operation
  without another player travel command or state edit, and is not lost or
  mistaken for the old travel intent;
- the first nonblank input appears exactly once in durable user history, causes
  exactly one DM resolution, and, if the selected immediate action mutates
  state, has exactly one correlated action receipt and mutation; use a safely
  observable immediate action so all three counts are falsifiable;
- `journal.json` is created with exactly the staged index-zero entry;
- RO01 departure area equals the checkpoint's staged after-value;
- the same operation reaches departure committed, completes arrival narration,
  clears the pending marker only after durable delivery, and reopens input at
  RO02;
- `party_tracker.json` remains at `RO001/RO02`, while the durable pending
  `updateTime` receipt applies its travel cost exactly once from `09:10` to
  `09:15`; an idempotent replay remains at `09:15` (no dropped or duplicated
  movement/time application);
- journal length is exactly one and entry zero deep-equals the checkpoint's
  staged `journal_entry_after`; the origin location deep-equals
  `area_owned_after`; every receipt correlates to the original operation ID;
- no runtime error, duplicate journal entry, duplicate departure, provider redo
  of accepted departure work, lost new input, or blank screen occurs.

Capture the complete timestamped player stream. The input must be acknowledged
within one event cycle; if recovery takes longer than roughly ten seconds, the
stream must show truthful changing progress rather than a stale line. It must
then show completion and an observably reopened prompt. These are acceptance
requirements, not authority for new TW-005 status code.

Then submit one ordinary immediate action at RO02 to prove the recovered game
continues.

### A2 - fresh-game first travel

In a separate true-virgin copied game directory, use native headless and real
OpenAI to create a character, enter Thornwood, and make the first RO01 to RO02
travel while `journal.json` is absent. Require the same successful initialization,
single entry, arrival narration, cleared marker, and actionable RO02 prompt.

### A3 - subsequent-travel negative control

From the accepted A2 game, perform one connected subsequent travel. Require
journal entries `[0:N]` to remain deep-equal to their canonical before-values,
length to become exactly `N+1`, only entry `N` to be new, the travel to complete
once, and input to reopen at the new destination.

### A4 - integrity polarity and cleanup

First use local deterministic I/O checks (not gameplay acceptance) to prove:

- valid empty journal follows the same normal path;
- malformed present journal still raises without mutation;
- absent journal with expected index greater than zero reaches the existing
  blocked-conflict receipt and does not write the staged entry;
- already-committed area plus matching journal entry remains idempotent;
- native `py_compile`, relevant pytest suite, diff check, ASCII-added-lines,
  process/port cleanup, and source-fixture hash preservation pass.

Then run the malformed-present and absent/index-greater-than-zero firing paths
one operation at a time through native `run_headless.py serve`, capturing the
complete player stream and restart behavior. Issue #211 already tracks the
raised transition-recovery exception branch that can stop startup rather than
fail forward. Per the owner's explicit narrow-scope ruling, TW-005 records these
gate-polarity results against #211 and does not change those separate integrity
policies. If either probe produces an untracked distinct stop, file a separate
numbered issue before TW-005 acceptance; do not expand this diff.

## Failure safety and rollback

- Before commit, the only new behavior is a local value substitution for an
  absent file. No disk mutation occurs.
- The established `commit_departure_summary` remains the sole mutation owner.
- The distinct outer-preflight ordering gap around a partially written existing
  transaction remains unchanged and is tracked by #237.
- Reverting the single production commit restores the exact prior behavior.
- No merge occurs without independent diff review and both real acceptance
  gates passing.

## Part-3 review gate

Run the same plan through Architecture, Fail-Forward/FS-1, Acceptance,
Consumer/Compatibility/GL-1, Player Experience, and Leanness reviewers. Each
blocking finding must provide a concrete failing sequence. Claude independently
reviews the plan SHA. Implementation remains blocked until one converged panel
pass and Claude's approval.

## Resolution ledger

| ID | Decision/finding | Resolution | Status |
| --- | --- | --- | --- |
| TW005-D1 | Missing journal meaning | Absent is canonical zero-entry state only at this read boundary. | RESOLVED by disk/code evidence. |
| TW005-D2 | Mutation owner | Existing `commit_departure_summary`; no pre-create write. | RESOLVED by leanness and transaction trace. |
| TW005-D3 | Expected index greater than zero | Existing length conflict remains authoritative. | RESOLVED; negative control required. |
| TW005-D4 | Malformed present journal | Existing fail-closed integrity rejection remains. | RESOLVED; negative control required. |
| TW005-D5 | Retained raised conflict/error gates | Native polarity evidence is recorded against existing #211; owner explicitly prohibited expanding TW-005 into those paths. | RESOLVED by owner scope; evidence required. |
| TW005-D6 | Partial pair before outer preflight | Out of this observed incident and narrow fix; tracked separately as #237. | RESOLVED by AP-5 and owner scope. |
| TW005-R1 | Six-lens review | Architecture found the initial core boundary sound; Fail-Forward/Acceptance caused the first revision; Consumer/Compatibility was CLEAN; PX required exact-once input and pacing evidence; Leanness removed the unobserved #237 expansion. Full same-SHA confirmation pending. | BLOCKS implementation. |
| TW005-R2 | Claude independent plan review | Claude approved prior SHA `85e29f4c`; this panel-converged revision requires re-review. | BLOCKS implementation. |
