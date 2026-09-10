# #337 stage-one FULL plan review

Date: 2026-09-09. Controller consolidation; original independent reports retained
at the paths below. No implementation or acceptance verdict is implied.

## Pins and owner scope

- Baseline: e754edefb44b550f14121b76fb2829bf2d11d419; fetched main unchanged.
- Reviewed plan SHA256:
  24d90d3743cd416a5aed7c4a2233748e6ef3e5922f31e95ee95eea52d71b82bd.
- Final plan SHA256 after documentation-only folds:
  f32494fe2b2aed32ac5ee92d1c717a404f1899378cf4e35916333dec05ce927d.
- D-337-1 is codified in live #193 Part 5, reverified policy epoch
  2026-09-09T22:32:52Z. Owner explicitly approved separate stages, not execution.
- Stage one: canonical location evidence at T065; stage two: separate #279
  model-authored side/goal contract. PR #339 remains unmerged.

## Independent review results

Nine separate blind read-only reviewers ran in parallel subject to three-worker
capacity. Every seat received the same frozen plan and full resolution ledger,
policy and its role/lane/warrant/evidence contract. No seat read another's report.
The three initial seats used the pre-append policy capture plus the exact owner
scope in the plan; later seats read the same policy with D-337-1 appended. The
controller independently verified codification. No substantive policy change or
unresolved scope disagreement occurred during review.

Raw report prefix: `/mnt/c/agent-room-fleet-kit/local-data/337-r1-`.

| Seat | Raw suffix | Verdict and important evidence |
|---|---|---|
| Architecture Custodian | custodian.md | LGTM. Existing snapshot and late message seam suffice; no deterministic allegiance inference. |
| Fail-Forward | failforward.md | LGTM stage one. Busy/currentness/provider paths retained; separate pre-existing diagnostic failure filed #342. |
| Acceptance | acceptance.md | LGTM. Original decisive candidate, real rejection/correction, hidden-fact restraint, location/currentness and conditional XP evidence required. |
| Consumer/Compat | compat.md | LGTM. Shared caller family, detached ownership, provider adapters and existing internal bypass preserved. No schema/store change. |
| Legacy-Contract | legacy.md | LGTM. Blame/ancestry and evidence ordering verified. No removal authorized; no established two-strikes implementation history. |
| Player Experience | px.md | LGTM. One factual wording correction: Gorvek attacked the warrior, Mira delivered death. Agency, perception, pacing and truth remain real-acceptance duties. |
| Leanness | leanness.md | LGTM. No public symbol, provider call, store, flag, lock or recovery loop proposed; existing records suffice. |
| No-Limits | nolimits.md | LGTM plan/baseline only. Full raw scans and every-hit dispositions included; no planned payload truncation or limit. |
| Single-Path | singlepath.md | LGTM plan/baseline only. Full raw scans and every-hit dispositions included; shared injection outside provider/compression branches. |

No product diff exists. Sentinel results are explicitly NOT certification of a
future patch. Their raw `git diff` outputs are empty, and the reports include all
baseline touched-file matches and classifications. Re-scan the actual C1 diff and
touched files before later gates. Existing diagnostic/presentation slices are not
payload truncation; baseline keyword hits are not blanket approval of those paths.

## Controller reconciliation

| Finding | Classification | Final disposition |
|---|---|---|
| Diagnostic export filesystem error escapes into count-limited provider policy | PRE_EXISTING_OUT, CODE-PROVEN; no runtime test | issue-#342 filed this turn; no stage-one repair |
| Gorvek described as killing the warrior | Evidence wording only; T097 events show 11->2 HP, then Mira 2->0 | fixed-inline; row now says attacks own warrior |
| Scope approval originally absent from live policy | OWNER_RULED_CODIFY | D-337-1 appended to #193; full body refreshed before mutation and result independently re-read |

The #342 mechanism was independently re-read at main.py:3665-3667, 10526-10539,
9710-9719 and provider_errors.py:338,353. Blame proves it predates task-A.
No claim links it to the historical #337 incident. Existing issue searches found
no matching diagnostic-write finding. Its runtime acceptance remains NOT-REACHED.

### Convergence rule applied

All nine seats completed one same-SHA full-coverage round. The only controller
folds were evidence wording, recorded policy epoch, separate-issue ledger and review
status. No implementation steps, tasks, types, states, tests or callsites changed.
NEQ-REVIEW-11 plan-polish termination therefore applies; another confirmation round
is not required under that explicit exception. No code-class finding awaits R2.

Before and after the fold, section hashes were identical:

| Content selected with sed | SHA256 before = after |
|---|---|
| Section 5 task-A through section 6 heading | 7db44c877769d21a10ba25d725884b051eb2378a4e47f947ed95a1227f931f9b |
| Section 7 slices/GL-1 through section 9 heading, including acceptance | e708cb26dbec2d5b167f00fcd6cd84b2608b8c7c422b4ce7292291f9f70600c7 |

These hashes are review evidence only, never gameplay authority.

## Remaining gates

Plan review COMPLETE. D-337-2 post-review owner execution approval remains pending.
There is no product patch, new gameplay evidence, native run, code commit or merge.
After approval: C0-C4, real A0-A5 with honest NOT-REACHED labels, independent
post-implementation audit and player transcript review. Native environment,
fixture readiness, observed cost, cancellation and XP are not certified by this
planning review. Stage-two #279 needs its own plan and owner decisions.

The earlier 2026-09-09-issue-337-preliminary-review.md is historical: its scope hold
was resolved by D-337-1. This report supersedes that hold and preliminary status,
not its recorded evidence.
