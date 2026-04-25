# Tasks: toolkit-module-builder-progress-feedback

## 1. OpenSpec Contract
- [x] 1.1 Define live ModuleBuilder progress reporting requirements for toolkit Homebrew jobs.
- [x] 1.2 Define rebuild handoff behavior so backup/clean metadata persists while active packet-build progress is shown.
- [x] 1.3 Define fail-open behavior for progress reporting failures.

## 2. Backend Progress Bridge
- [x] 2.1 Add an optional progress callback parameter to the toolkit packet-build entrypoint.
- [x] 2.2 Forward the callback into ModuleBuilder execution using existing progress hooks or a safe `ModuleBuilder.log(...)` wrapper.
- [x] 2.3 Update toolkit job state during active packet builds with `progress_message`, freshness metadata, and active build stage/status.
- [x] 2.4 Preserve rebuild metadata when transitioning from `rebuild_clean_running` into active packet-build progress.
- [x] 2.5 Ensure callback/job-state update failures are logged but do not fail the packet build.

## 3. Frontend Feedback Rendering
- [x] 3.1 Update `pollToolkitHomebrewJob(jobId)` to display `job.progress_message` for active `building` states.
- [x] 3.2 Ensure rebuild handoff states stop appearing frozen once packet-build milestones arrive.
- [x] 3.3 Preserve structured JSON/details visibility in the feedback window.

## 4. Regression Coverage
- [x] 4.1 Add backend coverage proving packet-builder progress callbacks update job state during a fake long-running build.
- [x] 4.2 Add rebuild-mode coverage proving backup metadata remains present after active build progress updates.
- [x] 4.3 Add frontend/source coverage proving active build rendering prefers `progress_message` with fallback to generic text.

## 5. Verification
- [x] 5.1 Run targeted toolkit Homebrew route/packet-builder tests.
- [x] 5.2 Run targeted frontend/source contract tests for `module_toolkit.html` if available.
- [x] 5.3 Run `openspec validate toolkit-module-builder-progress-feedback`.
