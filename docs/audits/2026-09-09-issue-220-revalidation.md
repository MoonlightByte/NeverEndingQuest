# 220 current-main revalidation (2026-09-09)

User request: determine whether old approved fix is stale or merely unmerged;
test and review, then report. No commit/push/merge/closure this task.

Baseline main1f892928; old isolated commit1b8fff27 (+27/-4, one function).
Fresh review worktree /home/loup/neq-worktrees/220-current-reset.
Only the existing discover_modules hunk is overlaid, unchanged in meaning or bytes;
no new implementation or alternate Reset design. Main still contains original
bug, also re-observed by native acceptance2026-09-05 in open issue220.

Live193 v3.1 Part1, Part2 p9/p12/p13 and Part3 consulted; current lifecycle
schematic read. Old patch's original accepted three structural arms are preserved.
No new store, deadline, routing, schema, name deny-list or model logic.

Native evidence /mnt/c/agent-room-fleet-kit/local-data/220-revalidation-I7V5HF.
Candidate export /mnt/c/220-review-src-TRqTCs; real campaign copy
/mnt/c/220-review-game-iEAGTe from untouched /mnt/c/322-game-IbP7La.
Copy excludes debug/logs/prior backups/saves/locks, fresh candidate prompts.
Native Python3.12, real configured OpenAI; existing311-native-relay default
mode, no optional injections. Reset is explicitly authorized only in test copy.

Checks: compile/diff-whitespace PASS. Pyflakes has9 pre-existing missing-f-string
placeholder warnings, no undefined names; baseline comparison verifies inheritance.
Native isolated filesystem primitive all3 positive layouts PASS; hidden/suffix,
support/nested-backup/malformed/null/list/invalid-UTF8 negative controls PASS.
These controls live only in a temporary IO test directory, not the live campaign.
Initial harness cleanup failed because Windows cannot delete its current working
directory; corrected helper to chdir outside before cleanup, rerun PASS. No
product change or gameplay verdict attributed to that harness error.

Independent220_compat_review: CODE-PROVEN compatible/not obsolete, no blocking
supported-layout counterexample. Shared entrants headless session599, web3141/
3186, reset CLI all retain same discovery/restoration. Lock order, supersession,
backup exclusions, root-character/encounter wipe and restart unchanged. Raw
sentinel scans: old diff empty; current file's six legacy hits are unchanged
Keep root-area migration cleanup, not a new path. No limits hits.

Real reset and virgin restart: PASSED for scoped220. Test before-data inventories compare
every file in both authentic module trees, including SHA256/size/mtime, against
the resulting backup; live restored files compare against actual _BU masters.
This cannot certify unrelated root backup coverage; issue220 concerns mutation
of the backup by incorrectly selected Phase2 directories.

IO A/B (not gameplay simulation): actual main discovery/reset_module primitives
over a temporary file tree with copied real changed JSON admitted backups and
overwrote its live file from _BU. Exact old candidate admitted only the module,
preserved backup and still restored live file. Evidence io-ab.json.

Native real Reset: seq281 acknowledgment,282 starting safely,374 ok:true,
375 Reset complete,376 restart, exit0. Duration0.564s receipt-to-complete.
Discovery found exactly Keep_of_Doom and The_Thornwood_Watch. All470 module
backup files retained exact SHA256/size/mtime and directory membership;38 live
BU restores verified. Empty party snapshot at reset process exit, root characters
empty. Four authentic live-vs-BU differences ensure this is not a vacuous check.

Oracle correction disclosed: initial blanket live-equals-every-BU check included
validation_report.json, which established reset_module cleanup deliberately removes.
Relaunch subsequently recreated that diagnostic. It is excluded ONLY from the
live restore oracle, not the470-file backup comparison. No product change made.

Native relaunch: actual module-choice narration37, wizard prompt39, empty player/
party state40, both modules offered. Quit result42true, player_exit45, exit0.
Separate pre-existing PX finding: deliberate Quit also prints setup-failure ERROR
at44; main.py8043 unchanged from main. Filed issue-#336, no repair in220.

Candidate reset_campaign.py SHA25645800b594d24abf9b0c8a49f6cf7c9eed5afdd6dfcd90a845d42d5bc199d0142
matches native tested source. No commits/pushes/merges; old patch overlay only.
Recommendation: old fix remains technically applicable; publish only that hunk
after owner go, not the entire old branch or old reset_campaign.py file.

Final independent evidence audit220_compat_review PASSED scoped220: recalculated
all470 backup membership/hash/size comparisons and38 live BU comparisons; exact
old discovery AST confirmed in native copy; raw reset/relaunch protocol read.
Native mtime assertions inspected, not independently recomputed through WSL
because timestamp representation differs. No flawless-general-UX claim (#336).
Missing-permission/OS-error arms not injected live; web/raw-terminal entrants
CODE-PROVEN shared implementation, not fresh browser acceptance. No broad Reset
rollback, root-file coverage or all Windows fault guarantee claimed.

## Shipment approval

2026-09-09: owner reviewed these results and authorized "kay, go ahead and merge the narrow fix". Earlier no-shipment wording above records the test-phase boundary. Only the exact tested discovery hunk and its evidence/schematic documentation are included; #336 remains separate. Fresh main1f892928 equals the tested base, so no code integration delta. Post-merge compilation and equality to native-tested bytes are required before push.
