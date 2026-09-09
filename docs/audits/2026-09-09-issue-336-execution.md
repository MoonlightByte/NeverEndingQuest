# 336 execution and pressure testing

Owner approved execution and pressure testing after presentation of reviewed
plan SHA2560fdc9cc47b40bed40ade26c812eb36d80b8dc4f4873d80c801cb86e974ed6cf6.
D336-1 CLOSED approved; D336-2 publication remains owner-open.
Isolated worktree /home/loup/neq-worktrees/336-startup-cancel,
branch fix/336-startup-cancel; fetched main still6c541cc5 at start.
Live193 v3.1 epoch2026-09-09T18:51:08Z unchanged at implementation start.
Frozen plan is retained as reviewed; this file records subsequent execution.

## Implementation

task1/2 applied exactly to main.py and utils/startup_wizard.py:28 additions,
15 deletions. Three consumers handle typed cancellation, realFalse/True and
provider supersession unchanged. First patch attempt failed on an incorrect
context heading before changing files; corrected to actual CHARACTER MANAGEMENT.
Per-region EOL restored after patching, removing7 lines of incidental EOL churn.
No schema/lock/persistence/provider changes; dormant legacy collectors untouched.

## Development gates

WSL and native Python3.12 py_compile both files PASSED. Baseline/candidate
pyflakes comparison PASSED: zero undefined names or new warnings; inherited
main61/wizard11 warnings unchanged. Changed bytes ASCII; unchanged lines retain
exact original EOL bytes. Native source equals reviewed worktree bytes.
Independent simplifier/consumer review and final actual-code sentinel audit PASSED.

## Acceptance

Native source /mnt/c/336-src-NfwED7, fresh official-module game
/mnt/c/336-game-sEK68f, evidence /mnt/c/agent-room-fleet-kit/local-data/336-evidence-UxFFxs.
Source exported from current main, only two reviewed files overlaid, private
config copied without disclosure; provider read-back openai. Existing311 relay
in default manual mode (no optional fault injection) records all raw protocol.
Native Python3.12, C:/Python312/python.exe; exactly one real session at a time.

A1 PASSED: module prompt40; Quit42-46 accepted, one neutral pause45, exit0;
A3 relaunch prompt30 proves menu/actionability and no fabricated party.
A3 PASSED: real partial Mira Vale interview; Quit82-86 clean, accepted
history SHA22f3d8c unchanged before/after. Resume39 recalled identity/choices.
Text cancel98 exits99 cleanly, history SHA7b0258e2 unchanged before/after.
A6 Reset PASSED: received39, pause41, ok94, restart96; empty tracker and removed
unfinished history. Save created earlier at A3-resume96 (19 files).
A6 Load PASSED: valid selected save received80, pause82, selected_applied103,
restart105; restored history exact SHA7b0258e2. Subsequent A5 resumes Mira directly.

Disclosed harness mistakes: model_config accessor probe used nonexistent
get_current_provider (correct read-back MODEL_PROVIDER); first manual input used
text rather than protocol content (rejected without game mutation); native PTY
requires CR to submit; first Load supplied an absolute path (contract requires
save_folder ID). Corrected commands recorded, no product patch for these mistakes.

## Final pressure-test dispositions

| Arm | Final disposition | Evidence |
| --- | --- | --- |
| A1 fresh menu Quit/restart | PASS | A1/protocol.ndjson40-46; A3 menu28-31 |
| A2 terminal surfaces | PASS on planned POSIX surface | A2-posix-main-terminal.log actual menu Ctrl-C, exit0; A2-posix-cli-terminal.log actual menu EOF, exit0 |
| A3 partial interview Quit/resume/text cancel | PASS | A3, A3-resume; before/after checkpoint inventory hashes above |
| A4 genuine missing-module failure | PASS | A4/protocol.ndjson26 missing modules,27 existing failure,28 exit; no pause/success/model call |
| A5 real approved creation + restart + gameplay | PASS | A5/protocol.ndjson109-110 complete,270 main prompt,285 welcome; A5-restart24 unchanged sync,107 main prompt,254 real response,301 next prompt,306 clean Quit |
| A6 Reset/Load lifecycle application | PASS functional; inherited wording separately tracked | A6-reset39/94/96; A6-load80/103/105; snapshot equality |
| A7 populated existing-character chooser Ctrl-C | NOT-REACHED; owner disposition required | Authentic issue116 saved-fixture inspection did not find an unfinished wizard with a populated existing-character menu; no state edits or fabricated sheet used |

A5 used actual player-approved Mira Vale, Human Fighter1, Soldier background,
Defense, chain mail/shield/longsword. The proposed passive Perception14 was
corrected on the player screen to13 and persisted correctly. Author/reviewer
correction attempts are retained, not reported as a flawless single-shot build.
Real T093 invocation cabb6109-ef18-471e-84ce-52d9b2d6ba67 selected RO001/RO01,
matching canonical tracker. Final author-review invocation
ead3e7b8-39c8-40c0-8a4a-88801d155204 accepted the build. Native char schema validates.
Restart bypasses creation, not sheet normalization: inherited normalization adds
zero spell slots1-9; sheet SHA62bdf957 becomes72e1f8e0, party staysbfc8f55f.
Do not claim unchanged sheet bytes across that ordinary normalization.

A7 inspected authentic fixtures beneath
/mnt/c/agent-room-fleet-kit/local-data/issue116/clean-reset-fixture. Available
saved populated parties bypass startup; saved unfinished wizard has no character
sheet. This is a bounded fixture search, not proof no possible fixture exists.
Static audit covers the changed chooser handler; it is not live branch coverage.

Additional native raw-terminal attempt A2-main-terminal.log FAILED before wizard
entry, exit120: existing debug interceptor string buffer passed to UTF-8 writer.
Filed separately as #340, not repaired or counted as a cancellation pass. Plan
explicitly permits POSIX for A2; native headless A1/A3/A4/A5/A6 remain proven.
Reset's inherited "choices are retained" sentence precedes deletion of the
unfinished interview; separate #341. Functional Reset PASS is not certification
of that retention wording. Existing #338 unavailable-sheet chooser remains open.

## Independent final review / evidence integrity

PX independently read complete A1/A3/A5/A6 transcripts and state and found no
in-scope implementation blocker. It confirmed exact retained checkpoint hashes,
real success and no build replay, and raised the disclosures recorded above.
Final PX confirmation also read A2 terminal logs and A4 native protocol: PASS
with the documented platform distinction, separate340/341 and held A7 gate.
Actual-code Single-Path/No-Limits audit: PASS, no new paths/caps, validators and
correction/finalization unchanged; all full-file scan hits inherited. Simplifier
review: PASS, no additional abstraction or changes recommended. Five-point final
audit: result authority distinct; no new writers/schemas; three consumers caught;
model author/reviewer untouched; required coverage gap A7 explicitly held.

Actual production diff SHA256:
26bf99e44fbb610881487a60e1d8fe4dc7834dc053e3c2932524209c3bf6d0d9.
main.py SHA2566a3c2274836e0333bc3cbf553125f0563996dc02ccb7e02f1d8f3f6717304c36;
wizard SHA256a857d38842401f1a45711a9d14cfa50d77294799004c4dd75fa06cdcfcc85ea9.
Local evidence dev.json, acceptance-index.json, model-call-index.json and
prompt-hashes.json retain exact paths, invocation IDs, timing/token metadata,
exit receipts and all27 loaded prompt hashes (all match fresh source).
37 native captured selected calls. Binding labels are recorded as such;
response.model is not exposed independently by the per-task capture format.
No shadow model probes or synthetic gameplay. POSIX terminal arms have raw logs;
they are not counted in the37 native per-task captures.
All relays cleanly closed. Final native process scan found no Python process
whose command references these336 source/game/empty/terminal directories.
No assertion is made about unrelated processes or historical peak child counts.

## Handoff

Implementation and reached pressure tests complete. Owner subsequently accepted
the A7 coverage gap and authorized commit/merge ("I approve your reocmmendation
and after you commti and merge take on 340 with a full 193 plan"). A7 remains
NOT-REACHED, not retroactively PASSED. D336-2 CLOSED YES. Issues340/341 stay
separate; only planning340 is authorized next. Publication receipts follow.
