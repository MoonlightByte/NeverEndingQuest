# #355 reuse and current validation of #116

Authority: #193 v3.1, D-355-1, epoch2026-09-10T20:51:33Z. Owner approved reuse,
fresh review/testing, and separating #323; no publication/merge/closure approval.
Existing full nine-seat converged plan remains the design:
/mnt/c/dungeon_master_v1/docs/superpowers/plans/2026-09-07-116-saved-display-history-plan.md.
That filename is historical, not authority to run disabled Superpowers ceremony.
No new implementation plan or parallel solution replaces its tasks1-4/GL-1.

Current base/main98cced99; isolated fix/355-browser-load-history at
/home/loup/neq-worktrees/355-browser-load-history. Imported existing051a88b0
without a new commit. Five runtime files byte-identical to existing reviewed fix;
their pre-fix baseline also matches current main. Three additive schematic-header
conflicts resolved preserving both main's220/336/340 notes and116's history notes.
No schema, prompt, model, gameplay, progression or unrelated worktree change.

## Approval and inherited gates

D-355-1 resolves355-R3: #323 is a separate failed progression finding, no longer
a dependency for this history repair; it is not relabeled PASSED. All other
observed failures and incomplete evidence remain honestly labeled. Original
acceptance artifacts are retained, not retroactively refreshed. Fresh proof
prioritizes the actual355 failure in354; report precisely which original arms
were freshly tested, which old evidence was independently rechecked, and which
remain NOT-REACHED/FAILED. No blanket whole-plan PASS from one passing rerun.

## Work order

C0 authority/source check and reuse (done). C1 current-code independent five-point
audit plus both raw sentinels; original FULL nine-seat design is unchanged, so do
not ceremonially restart that design loop. Any genuine new code/contract finding
returns to its owning review before changes. C2 native focused I/O/parsing gates,
compile/undefined names, frontend build and EOL/hygiene checks. C3 fresh serial
native React and explicit-legacy SaveA -> actual laterB -> LoadA -> Start -> actual
next turn, ordinary reconnect and old-save-without-cache, plus scoped original
negative controls. C4 evidence/independent PX and five-point audit. Then return to
354's browser sample/status/hidden-tab checks using actual visibility only.
No parallel game operations, provider stubs, state edits or fake responses.

Reuse stopped native fixture C:/354-web-xLy1be to avoid unnecessary disk copies,
with its original Save/evidence preserved. Replace only candidate source files
while no test process exists; build actual React assets with existing matched
dependencies. Record new root, exact fixture/source/prompt hashes and captures.
Old353/354 evidence stays under C:/354-ev-XF6pqV, unmodified. Latest game state is
the authentic selected Save boundary, not an edited synthetic game.

## Review evidence contract

Full plan and its resolution ledger above plus this delta/ledger must be read.
Diff is git diff HEAD in this worktree;5 runtime files match051a88b0. Full original
GL-1 applies. Part2 p8/p9/p10/p12/p13 and schematics are the relevant contract.
No inferred approval from agent consensus. Native claims require actual events,
typed parsed payloads, exact transcript, model/timing provenance and disk checks.

## Tracked follow-ups

#116/#355 one repair;354 failed browser acceptance to resume after fix;
353 natural malformed profile NOT-REACHED;323 separate owner-approved exclusion;
201/270/262 and320/321/282 retain original dispositions, no silent waiver.

## Resolution ledger

|ID|Finding|Disposition|
|355-R1|Same defect already in116|defensible: reuse single existing repair;355 correction comment posted|
|355-R2|Unmerged code not authority|task-C1: current independent review of actual diff|
|355-R3|323 blocked prior acceptance|override: ownerD3551 separates progression, retains failed verdict|
|355-R4|Fix absent frommain|task-C0: reuse locally, no claim shipped|
|355-C0|Three documentation conflicts|fixed-inline: retain both additive sections; runtime exactness verified|
|355-C1|Old telemetry/acceptance incomplete|task-C3/C4: fresh exact evidence and scoped verdicts, no retrospective PASS|

No runtime repair beyond the existing candidate has been made. Local source is
staged by no-commit cherry-pick, not committed/pushed. Review/acceptance pending.

## Current execution evidence

New evidence root C:/355-ev-1RPrBA. current-audit.md, no-limits.md and
single-path.md preserve independent current-source results: no new code blocker;
native acceptance is not inferred from their CODE-PROVEN verdicts.
source-manifest.json proves all five native runtime files byte-equal to candidate
and051a88b0, including mixed EOL counts; prompt hashes retained there.
Native Python312 compile PASS; identity/publication and snapshot I/O checks PASS
(dev-results.json and individual logs). Pyflakes exit1 is not called clean:
31 inherited diagnostics, zero new and zero undefined names, with one inherited
unused Path import removed, independently compared against HEAD. npm run build
(tsc -b + Vite8.1.5) PASS; emitted index-DfJcecE-.js in native fixture.

Initial Load click before Start was disabled by actual UI; preserved failed relay
attempt, then started normally. Old authentic save132141 selected through React:
restore_complete selected_applied browser-events.ndjson:351. Refreshed display
oldsave-restored-page.json shows saved narration plus honest reconstruction
notice, no abandoned healing question/response. Actual Start then succeeded;
new Save140016 created38 files including cache. Later real healing question is
currently running, its validator retry is captured rather than skipped. No
blanket PASS yet. Background-tab attempt still reports hidden=false and remains
NOT-REACHED, never simulated. Original354 evidence is untouched.

## Completed fresh history slice (2026-09-10)

The preceding running-state paragraph is superseded by these results. Runtime
candidate remains uncommitted and unchanged; this is not a merge/closure claim.

| Gate | Exact verdict and evidence |
|---|---|
| Old save without cache | PASS: real UI Load132141; original two assistant narrations plus truthful recovery notice, no discarded healing exchange; oldsave-restored-page.json/png/state; original five canonical hashes equal |
| New React Save/Load | PASS: actual Save14001638files, actual healing question and final real reply, Load selected_applied, exact cache hash25861010...7430f plus all five canonical hashes; newsave-restored-page.json/png/state |
| React Start/next turn | PASS: four selected cache contents retained after Start and actual listening turn; final reply once, input enabled; react-next-turn-ready.json/png/state |
| Reattach during turn | PASS narrowly: actual page navigation while listening turn running; same server, selected history retained and final reply once. NOT a same-document retained-memory race or adversarial packet inversion |
| New legacy Save/Load | PASS: explicit --ui legacy; actual Save14081538files, actual Bren question/answer, native Load confirmation; selected_applied at legacy/browser-events-session2.ndjson:676; all six hashes exact, cachebf7e230b...bb6f82 |
| Legacy Start/next turn | PASS: all eight saved cache records retained after Start and actual nod/watch response; abandoned Bren question/answer absent; legacy/next-turn-ready.json/png/state |
| Native parsing/I/O | PASS: identity.log, snapshot.log, projection.log; isolated serialization/file controls, not synthetic gameplay; actual old main/wizard save bytes unchanged |
| Build/static | PASS compile, TypeScript/Vite build, npm lint exit0 with inherited untouched-file warnings. Pyflakes exit1 retained honestly:31 inherited diagnostics, zero added/undefined; not a clean full-suite claim |
| Quiescence | PASS: both actual Exit acknowledgments, browser close, own launcher/server processes stopped and no matching children; cleanup.md |
| Hidden-tab completion | NOT-REACHED: real background-tab attempt still document.hidden=false; never mocked |
| Natural malformed T107 | NOT-REACHED; #353 remains separate |
| Full #354 twenty-sample exercise | INCOMPLETE; only four new real inputs here (two per UI), not twenty |
| #323 progression | Separate FAILED, ownerD3551 excludes as dependency; no fix or relabel |

Source manifest, analysis.json, legacy/analysis.json, raw model_captures/T*.json,
server logs, browser event files and screenshots are private/local evidence, not
tracked provider captures. Turn timing uses actual manual UI-command timestamp
through first ready status packet, includes input dispatch and the whole pipeline:
React134.938s/100.769s; legacy40.311s/85.263s (turn-timings.json with line numbers).
Per-call binding/latency/tokens are preserved in both analysis files; selected
T067 luna|none and T065 luna|low measured, no invented response.model or cost.
Longer turns include actual semantic corrections/compression, not cache recovery
model calls. The history projection makes no model call; startup/game calls are
separate. Read exact payloads before drawing claims from diagnostic model banners.

React independent PX: react-px-review.md. Historical additional controls have
been independently reviewed at historical-evidence-review.md, with source/version
and raw-log limitations retained, not upgraded to fresh acceptance. Inherited
hidden-pit disclosure remains #80/#260; resumed source narration is faithfully
displayed, not newly invented by reconstruction. Validator retries in these real
turns are recorded; no gameplay/prompt repair added. Inherited TTS cap stays #262.

Conclusion: the reproduced #116/#355 history bug passes fresh native real-OpenAI
React and legacy acceptance, plus continued play. Whole original plan acceptance
is not blanket PASSED: unobserved schedules, historical telemetry limitations,
and the separate354/353 tasks retain exact dispositions. No main change, push,
issue closure or publication performed. Final independent audit pending below.

### Final independent audit

Completed final-audit.md: no missed in-scope blocker or concrete discrepancy.
Independently checked actual selected/restored bytes, old two-narration projection
plus notice, four/eight selected display records across Load/Start/continued play,
both abandoned exchanges absent, final reply once and input enabled. React and
legacy PX reports are react-px-review.md and legacy-px-review.md. Timing arithmetic
cross-checked for all four actual inputs. Scoped reproduced-bug verdict PASSED;
the explicit full-plan/354/hidden/353/historical limitations above still apply.
No new model or game calls ran during final review. No source changes after tests.

## Owner-authorized shipment

Owner subsequently said "okay, proceed with the commit and merge to main then".
Recorded live #193 D-355-2 at policy epoch2026-09-10T21:54:15Z. Prior no-publication
statements above describe the earlier execution phase, not the current gate.
Merge only the reviewed runtime repair plus scoped documentation. No unrelated
fix, provider change, new mechanism or test-suite edit.

Resumed354 evidence C:/354-resume-OlHrRC/ACCEPTANCE.md independently confirms
busy/ready and genuine cross-page hidden notification. Foreground reset remains
NOT-REACHED;3/20 inputs before distinct grounded-narration failure. Character
evidence refusal is attached to344 comment5625776980, not attributed to355 or
silently waived.353 invalid-profile live branch remains NOT-REACHED,323 separate.
Owner was informed of these limits before authorizing narrow355 shipment.

Pre-commit repeat: native Python312 py_compile for all3 changed Python files
exit0; check_cache_identity_persistence.py, check_snapshot_io.py and
check_narration_projection.py exit0 against byte-identical tested native files.
Native pyflakes exit1 remains31 inherited diagnostics, zero undefined names;
not called globally clean. git diff --cached --check exit0. All five runtime
files equal the fresh live-tested native fixture and reviewed051a88b0 bytes.

Build approach correction: invoking Windows npm in the fixture failed TS2688/
TS5033 because its node_modules is an existing WSL symlink. This is a measured
setup mismatch, not a product-build PASS. Re-run via the existing WSL npm and
same dependency tree, as used to produce the native-browser-tested React assets;
no dependency install, package edit or copied environment.

Correct toolchain rerun: npm run build && npm run lint from the fixture frontend
under WSL exited0. tsc/Vite8.1.5 produced the same index-DfJcecE-.js asset;
Oxlint retained20 inherited warnings, no errors. Native gameplay acceptance
still refers to the actual Windows browser/Python sessions, not this build host.
Fresh explicit fetch of refs/heads/main confirmed98cced99 unchanged; no runtime
merge conflict or new product delta. Only reviewed repair and evidence are staged.
