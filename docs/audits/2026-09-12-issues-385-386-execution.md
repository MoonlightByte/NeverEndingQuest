# #385/#386 execution record

Owner approved frozen plan ed4744b1cb7c42dff0ddedc0a06e25cef0f00d97035438ba3d002c613bdff822
after nine-seat convergence. #193 D-385386-1 codified 2026-09-12T21:05:03Z;
pre-implementation epoch was unchanged at 19:41:48Z. HEAD and fresh origin/main
both 8562e270. Isolated plan/374-local-cache-contract; main untouched.

R1/R2 implemented in four allowlisted Python files. R3 schematic and historical
forward pointer added without altering previous verdicts. No T065 changes this
wave. No schema, registry, provider, storage writer, effects arithmetic or merge
changes. Parent #374/#378 candidate retained. No commits/push/merge.

## Focused checks and actual-diff reviews

- Linux py_compile: passed all four files.
- Local AST/serialization check passed: defaults, every forwarding edge,
  unchanged T078, complete/deep-detached array, correct message order, no input
  mutation, unchanged other functions, LF preservation, both R2 consumers.
  Script: local-data/385386-static-checks.py. These are not gameplay tests.
- Initial local AST check selected an earlier unrelated enumerate loop; corrected
  the test selection to the ordinary executable array. No product change for it.
- Native compile initial invocation used Linux paths; rejected by Windows Python.
  Rerun with C:/ paths required; do not report the invalid invocation as a pass.
- Python diff whitespace gate passed. Whole candidate diff-check still flags
  three preserved CRLF prompt lines from the parent wave (no new whitespace edits).
- pyflakes is NOT wholly clean: existing unused imports/f-strings plus guarded
  diagnostic references validation_success and e. Both undefined-name warnings
  also exist in the pre-correction snapshot; each expression checks locals()
  before reading that name. No unguarded new reference. These are not observed
  runtime failures. Raw zero-warning goal remains not met; disclosed, not hidden.
- Four fresh read-only Claude Code Opus5/medium actual-diff reviews PASSED:
  local-data/385386-actual-{simplifier,audit,limits,singlepath}.md.
  Raw sentinel output included; inherited cap/path hits keep prior dispositions.
  Simplifier recommended no change. No live behavior claimed by these reviews.

## Implementation hashes

main.py 10ab9132a8de391225789cc7f4080ae05a41d47bbe37d2a471d2558e9f5292ec
action_handler.py 0acedaa0ca6f5ff738501f1d611aa012102c74fe644dabd8a90fe1ee52df6a7d
effects_runtime.py 37d59f84c3b0f5aa711d3659dde14fe665dff836d44ec08da9f555a1f487c204
update_character_info.py 6271fb53b7ebdcfa120c10caef8b580309dff1cee3196db4db8a26bb340f82d6

## Acceptance

FINAL: FAILED overall; stopped without shipment. Native Windows compile passed with C:/ paths. Fresh source C:/385-src-6r3JcV, game C:/385-game-M3n33I, evidence
C:/385-ev-i7jytd. Original C:/374-game-K6gSX5 is read-only source, never played.
Plan A1-A6 and stop conditions unchanged. Operator brief:
local-data/385386-native-brief.md. Report will be 385386-native-report.md.
Prior failure copies and evidence preserved. No acceptance waiver or shipment.

Setup verified 2001/2001 source files, 836/836 original fixture files except
the two deliberately refreshed validator prompts, 46 prompts/schemas equal
export. Supported Load selected_applied and clean restart; save equality passed.
First test input used the wrong protocol key (text instead of content), rejected
before gameplay at A1/protocol.ndjson line142. The operator then waited for a
prompt that could not arrive; supervisor interrupted only the operator wait and
resumed the same logged-in CLI session with the explicit protocol correction.
Game stayed alive and unchanged. Retain rejected transport attempt; resend the
same sentence with content, not a revised player request. This is harness error,
not a product/model result, and cannot count as a pass or failure of the fix.

A1 Chain Mail inventory PASS observed: T079[0] returned equipped:false without
quantity0; store moved the full 12-key item once. prompt-731 cache has Shield
and Chain Mail, sheet has Longsword only. Current-step frame observed at T079
message9, current_index0, 1207 characters; total request40204 bytes.
T065 reverse-order rejection fired before accepting [unequip,store,plot].
Separate T051 error filed as #387 (not #349): ordinary unarmored Dexterity bonus
omitted, AC12 rewritten to10; unrelated validator/prompt unchanged. T053
unsupported-field exhaustion recurred under existing #371. No mid-run repair.

## STOP: core reverse-order failure remains

A2 initial Chain Mail retrieval falsely rejected by T065 despite real cached
item. Missing current canonical cache frame filed #388. On-screen correction
recovered the item through retrieve then equip; current_index1 and present
retrieved sheet seen by T079. Shield retrieve/equip also passed first candidate.
Metadata/quantity conserved for these transfers, not a universal guarantee.

Shield outgoing failed: T065 accepted [storageInteraction,updateCharacterInfo,
updatePlot] while asserting the opposite unequip-before-store order. The ordinary
dispatcher honored the actual array. Storage committed first; T079 correctly
received current_index1 and the fresh sheet without Shield, but returned a Shield
equipment patch anyway. Existing absent-item merge appended it, then full-sheet
schema rejected missing item_type, description, quantity across three attempts.
Writer returned failure. No duplicate or loss persisted; earlier storage commit
remains, later plot skipped, requested complete turn FAILED. This is core #378,
not an unrelated issue to waive. No more trials or wording changes here.

Supervisor stopped at prompt2493, requested supported Quit and evidence wrap.
Remaining A3-A6 not run after this failed trial; #386 live failure-handback proof
NOT-REACHED (character error is not storage needs_response). Native report and
independent PX audit are now complete. No commit, push, merge, issue closure or state repair.

## Final independent reconciliation

Both final read-only audits agree: acceptance FAILED on outgoing Shield ordering
and player truth; #386 live recovery remains unproven. Reports are under
/mnt/c/agent-room-fleet-kit/local-data/:
- 385386-native-report.md (operator, complete raw paths and capture references)
- 385386-final-acceptance-audit.md (independent acceptance)
- 385386-final-px-audit.md (independent player-experience)

| Arm | Final disposition |
| --- | --- |
| A1 Chain Mail unequip/store | PASS observed inventory; separate AC defect #387 |
| A2 both directions | FAIL: Shield outgoing; mail retrieval after correction and Shield retrieval passed inventory |
| A3 genuine removal | NOT-RUN after stop |
| A4 storage failure follow-up / #386 | NOT-REACHED; character error uses a different sink |
| A5 Save/intervening turn/Load | NOT-RUN; initial supported Load does not substitute |
| A6 standalone/companion compatibility | NOT-REACHED live |
| Quit and preservation | PASS: player_exit, rc0, no python.exe; original 836/836 and export 2001/2001 unchanged |

Reconciliation notes preserve the raw reviewers' reports rather than silently
rewriting them: there were four executed storage transfers, not six. Six is the
number of physical T079 calls over four logical character updates. All six calls
received the current-step frame. The absence of quantity0 in this trial is not
universal prevention proof. Rejected partial Shield additions demonstrate an
add-absent risk; no fourth attempt or persisted duplication was observed.
The PX audit used raw evidence, not the operator report at its actual absolute
path. The acceptance audit's orphan-check caveat is supplemented by the
operator's and supervisor's final native tasklist checks. The narration about
both items being in the cache describes its pre-retrieval state, not the final
cache snapshot; the same narration's claimed AC16 still conflicts with disk18.
The provider reissue message is not independent proof of a remote-network cause.

Separate findings #387 and #388 are filed, not repaired. Stale Shield effect is
#379, not the earlier operator shorthand '#349-class'. #378 has the failure
evidence comment issuecomment-5648940993. No issue is closed. No more code or
trial changes: the next correction requires an explicit ordering-boundary design
decision, not relabeling this failed trial as a pass.
