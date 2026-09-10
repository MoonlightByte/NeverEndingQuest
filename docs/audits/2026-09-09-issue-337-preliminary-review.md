# #337 fresh workup: preliminary independent review

Historical preliminary status: the owner resolved the two-stage scope hold under
D-337-1. See 2026-09-09-issue-337-full-review.md for the subsequent full review.
The original evidence and preliminary verdict below are retained unchanged.

Date: 2026-09-09. This is a controller consolidation, not verbatim seat reports.
Reviewed plan: 2026-09-09-issue-337-canonical-scene-plan.md.
SHA256: 8faf2673c85bb5b8082887705686bc9c655f7fe1a39a439157e43c885140bb37.
Code evidence: current main e754edefb44b550f14121b76fb2829bf2d11d419.
Policy: live #193 v3.1, updated 2026-09-09T22:13:35Z.

## Source forensics

Three independent read-only assignments examined (1) scene/faction consumers,
(2) T065 entrants/snapshot/currentness and (3) original capture chain/acceptance.
Controller independently inspected the original request and relevant code.
The plan records the resulting evidence, including corrections to the handoff.

## Preliminary plan review

Three separate blind plan assignments read the same complete plan and ledger.
They did not see one another's draft reviews.

| Seat | Verdict | Evidence and qualification |
|---|---|---|
| Architecture Custodian | NEEDS_OWNER on D-337-1; no demonstrated task-A architecture blocker | Existing snapshot records at path_encounter_analyzer.py:394 and sole T065 call main.py:10434 support narrow evidence repair. A hostile character-backed NPC still receives party faction at combat_state.py:354 and same-side rejection at resolver.py:239; context repair is not a full side-contract repair. |
| Fail-Forward | No blocking task-A findings | Unavailable evidence continues without inventing absence. Existing busy retries outside party lock at main.py:4698 and 9933, scope checks at 3684 and publication at 5264 remain. No new busy-to-refuse, abandonment, deadline or retry policy. Candidate diff is empty: no implementation FS-1 clearance claimed. |
| Acceptance | No blocking task-A findings | Rechecked original T065[13]/T067[14-16]. A1 requires the real decisive candidate; A2 requires real firing correction and hidden-fact controls; A3 origin/destination polarity; A4 compatibility/currentness; A5 XP only after actual defeat and award. |

All seats agree the plan is honest about #337 versus #279. No gameplay or provider
calls ran. No product files, issues, branches elsewhere or remote state changed.

## Stop condition and next gate

This is NOT a completed FULL Part 3 panel or convergence. The Custodian verified
that the explicit unresolved scope decision pauses that loop under NEQ-REVIEW-09.
Do not dispatch ceremonial confirmation rounds while treating that choice as settled.

Question for the owner: finalize full review of task-A as a separate first wave,
leaving #279/PR #339 unmerged while separately designing the model-authored
combat-side contract, or include that contract before either repair proceeds?
Recommendation: task-A first. This is scope approval, not implementation approval.

After the owner rules, update the plan/ledger and run all applicable FULL seats,
including both sentinels and conditional Consumer/Compat, PX, Legacy and Leanness
as specified. Actual diff scans remain mandatory after code exists. Present the
converged plan for execution approval; no acceptance or shipment is pre-authorized.

Unchecked: actual implementation, runtime fixtures/provider readiness, native
acceptance, full conditional reviewer domains, schema/consumer compatibility audit
of a future combat-side repair, and all proposed-diff sentinel checks.
