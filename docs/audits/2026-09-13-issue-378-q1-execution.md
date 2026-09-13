# #378 Q1 execution

Owner approved the presented final amendment SHA2a58e2ad (substantive
ef9b1fe7). #193 D-378-Q1 records execution/testing authority; no ship/waiver.
Epoch unchanged04:44:16Z before codification. Original reviewed plan frozen.
Before-slice four files: /tmp/378-q1-before-pgmCI9. HEAD8562e270, isolated
plan/374-local-cache-contract worktree; prior dirty U3 candidate retained.

Q1 applied exact reviewed substring in both T065 prompts. Q2 added only
current-equipment clarification to the two schematics. No Python, schema,
model binding, game state or unrelated armor code changed. No commit/push.
Q3 exact-substring, per-region EOL, ASCII and full/compact paragraph equality
checks PASS. Independent actual-diff audit PASS and simplifier LGTM (static
slice only), saved as local-data/378-q1-{audit,simplifier}-review.md in the
agent-room-fleet-kit. No additional product edits requested.

Q4 fresh native live acceptance started, not yet a verdict. Source
C:/378q-src-noHVLJ matches all 2001 exported tracked working files; game
C:/378q-game-V0wMi5 differs from its authentic source only in the two T065
prompt files. Original 836-file manifest unchanged. Interpreter win32 Python
3.12.3 with OpenAI import confirmed. Evidence C:/378q-ev-rD7KiJ.
Post-codification live policy epoch: 2026-09-13T06:10:18Z.

## Q4 results (2026-09-13, native Windows / real configured OpenAI)

Operator report: /mnt/c/agent-room-fleet-kit/local-data/378-q1-native-report.md.
Raw evidence: /mnt/c/378q-ev-rD7KiJ/Q4 and Q4b; PROGRESS.md in their parent.

- A PASS: actual stale/duplicate equipment draft rejected by T065[1]; reason
  explicitly said already-unequipped Shield needs no equipment update. T067[3]
  removed that action, T065[2] approved, T049[0] transferred once, zero T079
  no-op repair calls. Current prompt verified in the actual request.
- B PASS: real reversed [store, unequip] draft passed model review but hit the
  code guard before transfer. Current equipped facts handed to T067[7]; full
  T065[6] rejected its incomplete repair; T067[8]/T065[7] completed correct
  ordering. T079[3] unequipped then T049[3] transferred exactly one Shield.
  This changes the prior single-item guard NOT-REACHED verdict to OBSERVED.
- C PASS: real T049[5] single items array stored Shield plus Chain Mail.
  Multi-item prerequisite firing remains NOT-REACHED (correct ordering first).
- Save, intervening actual retrieval, Load, relaunch and Quit PASS. Operator
  measured 52/52 restored files equal to save before relaunch. Root separately
  checked character, storage and party bytes equal at Save, Load process exit,
  relaunch before-launch and final Quit; both owned game exits rc0.

Root independently compared all item fields for A (613->1039), B (1924->2565)
and C (2964->3416) prompt snapshots: unchanged except intended equipped=false,
exactly one storage access-log increment each; no duplicate/loss. Root checked
actual T065[1,2,6,7] amended system text and the exact T067[7] current-equipment
handback. Original fixture's 836 hashes remain unchanged.

General armor/PX is NOT claimed PASS: existing T051 issues invent Defense +1,
omit unarmored Dexterity, and treat a value-0 shield effect as +2 while cached.
One player correction accepted, one reverted by T051. Keep #387/#392 separate;
T053 unsupported responses remain #371. Premature initial narration during B
is disclosed under existing #360/#364; no repair made here. Model selection
labels are not response.model proof (response model UNKNOWN).

Root full-candidate git diff --check reports 3 preserved CRLF-line whitespace
warnings in prior prompt hunks (full231/386, compact227), not Q1 LF changes.
Do not normalize the mixed-EOL files to suppress these; exact Q1 byte check
passes. No commit/push/merge.

## Independent final audit

Logged-in Claude Code Opus5 medium acceptance/PX reviewer returned PASS for
the exercised slice, no in-scope blocker. Raw review:
/mnt/c/agent-room-fleet-kit/local-data/378-q1-px-audit-review.md.
Reviewer inspected actual captures and snapshot files, independently confirmed
A/B/C and lifecycle, and disclosed the same separate armor/PX defects. Its
report-file-PENDING header describes inspection time; root subsequently read
the entire finished 175-line operator report and reconciled it against raw
evidence. The AC12->10 overriding write is T051[7], not T053 (review point 2
uses the loose label T053/T051). No additional production change required.

Still not proven in this run: multi-item guard firing, stack quantities >1,
multiple containers, NPC storage, first-draft-clean already-unequipped store,
and full (non-compressed) T065 live selection. These are not converted into
passes or waived. No new scope requested; ship remains owner-gated.
## Shipment authorization and final checks

Owner subsequently said: "commit and merge the fix to main"; recorded as
#193 D-378-SHIP. Remote main fetched explicitly and verified by ls-remote:
8562e270, identical to the native acceptance baseline. No merge conflict or
intervening code exists. All nine candidate tracked files match the native
acceptance export byte-for-byte. The older main workspace is on a different
branch with unrelated dirty files; publication does not alter that workspace.

Fresh Linux and native Windows compile PASS for all five changed Python files.
Q1 exact-text/EOL check PASS. pyflakes has no added undefined names relative
to current main: the same two locals()-guarded diagnostics remain in
update_character_info.py, along with existing style/unused-name warnings.
Raw pyflakes is not globally clean. The older #385/#386 phase-specific static
script passes its forwarding/context/serialization assertions then fails its
historical other-functions-unchanged assertion: U2 intentionally later changed
the two shared review functions. Independent AST comparison against main
confirms exactly the three approved main.py functions changed; do not label
the historical script wholly PASS or modify it to conceal this stage mismatch.

Preserved final native report: 2026-09-13-issue-378-native-closeout.md.
All earlier failed trial reports remain historical, superseded for shipment
by Q4 and the independent final audit above, not rewritten as passes.
