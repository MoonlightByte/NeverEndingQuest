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
