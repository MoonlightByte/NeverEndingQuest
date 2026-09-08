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
