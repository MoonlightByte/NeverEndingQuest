# GUI Builder Media Handoff Semantics

## Why
Toolkit builds currently surface an overall failed result when structural build stages are green and the only remaining issue is missing module-local monster or NPC media. Product policy is narrower: the build should complete successfully, the remaining media debt should stay explicit, and the user should be directed to `Module Builder -> Module Media Generator` as the next manual step.

## What Changes
- Define a toolkit finisher outcome that distinguishes true build failure from post-build media handoff debt.
- Keep missing media debt explicit in the returned payload and report.
- Route operators to `Module Builder -> Module Media Generator` instead of treating media-only debt as an overall failed build.
- Preserve manual media generation as a user-invoked workflow; do not add automatic provider generation.

## Capabilities
- Toolkit finisher SHALL return a successful build outcome when build stages are green and only module media debt remains.
- Toolkit finisher SHALL preserve media debt details and expose an explicit handoff path.
- Toolkit finisher SHALL still fail for real structural or finishing failures.

## Impact
- Affected code: `web/extensions/toolkit_module_finisher.py`, targeted finisher tests, and focused reporting/spec artifacts.
- Affected workflows: toolkit finisher result semantics and post-build operator guidance.
- No change to automatic generation policy, hydration/materialization behavior, or gameplay/readiness payload normalization scope.
