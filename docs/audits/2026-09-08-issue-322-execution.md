# Issues 322 and 328 execution and acceptance

## C0 authority and baseline

Owner approved execution and thorough testing after plan presentation, 2026-09-08.
Live #193 Part5 D-322-1 records that ruling; D-322-2 records coupled scope.
Frozen reviewed plan SHA256:
2d60ce66b984aef1fc4d607cef505adc7c194663797cb18cf4ac39a1d2ad4d0d.
Its historical execution-open status is superseded by this ruling, not silently
rewritten into the previously reviewed artifact. No merge/push authorized.

Worktree: /home/loup/neq-worktrees/322-campaign-export-plan.
Implementation branch: fix/322-campaign-export-hubs.
Fresh git fetch origin main: HEAD=origin/main6d18d09b, ancestry PASS.
Only reviewed plan/review docs were untracked before work. Three source files
are LF; preserve regional bytes. Python3 pyflakes available; native Windows
C:/Python312/python.exe is3.12.3 with OpenAI and psutil importable.

Allowed product seams: campaign_manager T039/importer/shared formatter;
conversation_utils existing hub context; main existing hub DM note. No schema,
validator, provider, lock, archive, companion store or lifecycle changes.
Existing establish_hub creation action remains unchanged. All acceptance runs
must be sequential on isolated copies with real OpenAI, not model stubs.

Acceptance is NOT RUN yet. Runtime outcomes will be recorded with artifacts,
including FAILED/BLOCKED/NOT-REACHED. Plan agreement is not gameplay proof.

## C1-C3 implementation and focused checks

C1 commit2096a343: reviewed prompt exactly, original five goals/full source kept.
C2 commit3f9711a0: one no-fact-first field overlay, no validator change.
C3: one complete JSON formatter at both actual reader seams; surrounding
availability and other DM-note contents unchanged. Separate read-only simplifier
per slice found no removable machinery without losing approved behavior.

Local script local-data/322-primitives.py runs AST-extracted production parsing,
merge and formatting units, avoiding unrelated runtime/provider imports.128
checks PASSED: original captured invalid containers; historical scalar admission;
omitted/null/blank/empty-map preservation; explicit false/zero/empty-list updates;
input immutability/idempotence; complete untruncated formatting. This is pure
contract evidence, NOT simulated/live gameplay or proof of caller wiring.
py_compile all3 PASSED; diff whitespace PASSED. Pyflakes full report has inherited
unused/redefinition/missing-placeholder warnings but ZERO undefined names.
No incidental warning cleanup. Exactly2 production formatter calls found.

Native source/game copies use322-native-src-Elg2UF and322-game-IbP7La under C:/;
private evidence local-data/322-acceptance-oZxruI. Source and game setup must
finish and compare before any process launch. Existing311 source/game untouched.
New local storage approximately400MB, not another complete repository clone.

## C4 first real matched probe: FAILED semantic gate

Native Windows3.12.3, same authentic full T038 source, unchanged T039 profile
gpt-5.6-luna/none, serial calls via existing required child transport. Actual
response.model=gpt-5.6-luna in both results. Source export overlaid from current
worktree; source fixture untouched. Copies completed and party/sidecars compared
before execution. Artifacts under322-acceptance-oZxruI/C4-baseline andC4-candidate.

Baseline:12.156s, validatorFalse, reproduced array containers and object unlocks.
Candidate:11.843s, validatorTrue, but factual/preservation verdict FAILED.
Candidate hubs['Shadowfall Keep'].services=['possible stronghold'] converts a
prospective use into a current service. Existing importer would replace actual
services[rest,storage,sanctuary,information] with that proposal. Source does not
establish their removal/replacement. Unknown ownership was emitted as literal
'Not established'; an innkeeper was also treated as owner without ownership
evidence. Independent reviewer confirmed. No candidate export was imported into
the game; no A1/ordinary gameplay acceptance has begun. Not a PASS on JSON alone.

Failure classification: C1 agent instruction/compliance at the hub fact boundary,
not transport or new code guessing. Evaluating one narrow prompt refinement
under C4; no fabricated rejection/output and no prose-matching workaround.

## C4 single refinement and stop disposition

Seven generic instruction lines distinguish offered services from prospective
uses and explicit ownership from operating/staffing a location. Independent
source/simplifier review confirms this is within the approved C4 refinement,
not a new mechanism, identity rule, input source or model binding.

Real refined call:13.938s,response.model=gpt-5.6-luna,validatorTrue.
Hub-specific verdict PASSED: Shadowfall Keep no longer proposes services;
all four authentic services would survive. Unknown owners are omitted, Cira
is described as operator rather than owner. Existing metadata would survive.
This remains a real-model plus importer-primitive result, NOT persisted A1.

Overall factual C4 verdict FAILED: relationships['Lingering Spirit'] attributes
the unnamed cellar spirit's release to the named Withered Shrine guardian.
The supplied source distinguishes them; this is a T039 attribution error, not
the upstream T038 issue #318. No export was imported. Record filed under the
existing end-to-end identity pressure-test issue #326:
https://github.com/MoonlightByte/NeverEndingQuest/issues/326#issuecomment-5591360533
Exact request/result/capture:322-acceptance-oZxruI/C4-candidate-refined.
Result lines53-54; decoded sent source user-message lines5/19.

This is a different error from the first hub-services failure; it does not prove
that the hub fix failed twice. Nonetheless the second candidate is not globally
factually clean. No further prompt tuning, identity repair or model call is
performed; request owner disposition before moving past this failed probe.

## Consolidated current verdicts

| Gate | Verdict | Evidence and limits |
| --- | --- | --- |
| C0 isolated baseline/authority | PASSED | ac11ed0b, current main6d18d09b, D-322-1 |
| C1-C3 source implementation | PASSED | 2096a343,3f9711a0,b7227859 plus reviewed seven-line prompt refinement |
| Independent source audit | PASSED | Three-file byte-line/AST comparison, unchanged validator/transactions/other goals;2 live helper calls |
| Pure contracts | PASSED |132 WSL and132 native checks; independent reviewer44 additional cases; no gameplay simulation |
| Compile/undefined names/EOL | PASSED | all3 compile, zero undefined names, LF retained; inherited other lint warnings remain |
| C4 old prompt reproduction | PASSED repro |12.156s invalid actual output, retained validator firing shown |
| C4 initial candidate | FAILED |11.843s valid shape but unsupported hub services/owners |
| C4 refined hub contract | PASSED scoped |13.938s supported hubs and preservation semantics; actual import not run |
| C4 full factual output | FAILED |Distinct spirits conflated; #326 evidence above |
| A1 regeneration | NOT-REACHED |Held after C4 factual failure |
| A2 ordinary departure | NOT-REACHED |No gameplay acceptance started |
| A3 actual consumers/player claims | NOT-REACHED |Source wiring proven; actual DM request/narration not yet exercised |
| A4 invalid/unlock polarity | PARTIAL |Captured invalid parser firing and empty unlock real output; positive unlock/natural gameplay fallback not reached |
| A5 Save/Load/Quit | NOT-REACHED |No game process launched |
| A6 actual service/ownership change | NOT-REACHED |Pure replacement polarity only |
| Quiescence/preservation | PASSED scoped |All probe processes exited0; native owned Python scan empty; campaign/party/both sidecars byte-equal to original fixture |
| Postimplementation five-point audit | BLOCKED |Source section passed; live acceptance/owner judgment outstanding |

No merge/push/issue closure. Public issue updates contain observations only,
not private captures/keys. Original fixture unchanged. Three actual serial
OpenAI calls total; no phantom headless or native-gameplay PASS claimed.
