# #355 current-state reconciliation before implementation

HISTORICAL CHECKPOINT: the open gates and recommendations below were superseded
by D-355-1 execution/revalidation and D-355-2 shipment approval. See
2026-09-10-issue-355-execution.md for the current results and owner disposition.

Owner assigned #355 first, then return to #354. No product changes authorized
through a completed new review yet; this is a read-only investigation checkpoint.

## Verified current state

- Fresh origin/main:98cced99f043fa813721438e242c82c1b92a91b1.
- #193 v3.1 policy epoch2026-09-10T20:15:10Z, read live. Relevant pages p8/p9/p10/
  p12/p13 and save-load-reset/web-headless schematics consulted.
- Isolated clean worktree:/home/loup/neq-worktrees/355-browser-load-history,
  branch fix/355-browser-load-history. No prune, source game or foreign-worktree edits.
- #354 actual native evidence remains /mnt/c/354-ev-XF6pqV. Selected Save restored
  canonical files exactly but reconnected browser displayed post-Save content.

## Material correction: this is already within #116

The initial #355 filing described #116 as related missing-history work. Reading
ALL #116 comments now establishes its September5 and September7 owner comments
already recorded the SAME stale-after-Load mechanism and acceptance expectation.
Do not implement a competing solution or claim a novel defect.

Existing local commit051a88b039a4e6316da42018a31d3cb30bd1f5f4 on
fix/116-saved-display-history already implements this repair (9files,+377/-69).
It is NOT an ancestor of current origin/main. Its5 runtime files have no delta
between its parent and current main, so current source overlap is exact; this
does not prove its implementation correct or acceptance complete.

The existing branch is preserved at C:/dungeon_master_v1/.worktrees/saved-display-history.
Its Windows Git registration must not be pruned from WSL. Read committed objects
from the repository, not guessed repaired registrations. No checkout/cherry-pick
or mutation of that branch was performed.

Mechanics of existing proposal, not an approved new design:
1. Save existing browser-delivery records with canonical snapshot; restore
   selected presence/absence through existing manager and rollback ownership.
2. Older saves without a display cache recover explicit typed narration only,
   never dump DM system prompts/actions or invent a rewritten historical scene.
3. Preserve history on Start; replace abandoned client history on server change
   while retaining normal same-session message-ID merging.
4. Shared memory-before-file lock order covers manager/cache coordination;
   cache-only Save failure does not refuse canonical Save; no new model call.

Evidence read:
- local-data/codex-ps-116-owner-gate-handoff.md
- local-data/issue116/post-implementation-audit.md
- local-data/codex-ps-116-execution-progress.md (current status sections)
- docs/superpowers/plans/2026-09-07-116-saved-display-history-plan.md
  (historical plan, NOT an instruction to use disabled Superpowers skills)
- git show051a88b0 runtime diff and ancestry; current-main schematic files.

## Existing gate must not be silently waived

The #116 handoff/audit expressly says no shipping approval: successful level-up
Save/Load acceptance was blocked by separate #323 and some retained telemetry
was incomplete. Several ordinary React/legacy/older-save slices were observed,
but report-only evidence is not current revalidation. #323 belongs to another
agent; this task does not authorize progression repair.

Recommended owner disposition: reuse/revalidate existing #116 work against
current main as the single #355 repair; keep #323's failed progression verdict
separate, with no retrospective PASS. Replace missing timing proof with fresh
scope-appropriate serial native acceptance. Then resume #354's incomplete checks.
Owner must approve changing the earlier explicit acceptance dependency before
we claim the existing repair complete. No issue closure or merge implied.

## Tracked follow-ups

- #116 existing implementation/acceptance: reconcile, not duplicate.
- #355 fresh reproduction: link to #116; leave open until approved disposition.
- #354 browser acceptance: FAILED display arm;2/20 sample, hidden-tab NOT-REACHED.
- #353 naturally malformed T107: NOT-REACHED, no fabricated provider output.
- #323 separate progression work: no fix here and no erased failure.

## Resolution ledger

| ID | Finding | Disposition |
|---|---|---|
|355-R1|Issue already recorded in116 comments|defensible: correct earlier novelty statement; one repair only|
|355-R2|Existing unmerged code is not mainline authority|task: fresh current-main review before adoption|
|355-R3|Prior116 acceptance explicitly blocked by323|escalate:@owner: approve separate attribution/narrow re-acceptance, no silent waiver|
|355-R4|Current main lacks fix|CODE-PROVEN ancestry absence; do not label shipped|

No full new plan or Part3 convergence claimed. Next boundary is owner scope
reconciliation, then the current-main plan amendment/review, implementation if
approved, and real acceptance. Existing evidence stays intact.
