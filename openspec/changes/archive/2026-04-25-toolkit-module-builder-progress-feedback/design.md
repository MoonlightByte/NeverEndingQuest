# Design: toolkit-module-builder-progress-feedback

## Problem

The toolkit job lifecycle has a long silent section between rebuild cleanup and packet-build completion. `_run_homebrew_build_job(...)` sets `status='rebuild_clean_running'` after backup/cleanup succeeds, then calls `_run_homebrew_packet_build(...)`. The packet builder invokes `ModuleBuilder.build_module(...)`, which prints useful milestones to stdout but does not update the toolkit job store while the call is in progress.

The frontend polls successfully, but it receives the same stale `rebuild_clean_running` payload every time. This makes a live build look frozen even though stdout is active.

## Approach

Add a narrow progress reporting bridge from packet-driven builder execution to the existing toolkit job state.

1. Extend the packet builder entrypoint to accept an optional progress callback.
2. Install that callback on `ModuleBuilder` execution by using the existing `builder.progress_callback` hook and, if necessary, wrapping `builder.log(...)` so existing milestones become progress events.
3. In `_run_homebrew_build_job(...)`, pass a callback that updates the existing job record with active build status fields such as `progress_message`, `progress_updated_at`, `progress_stage`, and `progress_tick`.
4. Keep rebuild metadata (`rebuild_mode`, `rebuild_backup_path`, backup result/details) on the job while changing the visible active state to packet-build progress.
5. Update the toolkit frontend to prefer `job.progress_message` for active build states while continuing to show structured job details.

## Backend Contract

Active toolkit build jobs SHOULD expose these additive fields when progress is available:

- `progress_message`: concise latest builder milestone text.
- `progress_stage`: current logical stage, initially `build` unless a more specific stage is available.
- `progress_updated_at`: timestamp of the latest progress update.
- `progress_tick`: monotonically increasing integer useful for polling/render freshness.

The job `status` during packet build SHOULD be `building` after rebuild preparation has handed off to the packet builder. Rebuild-specific metadata MUST remain present in the job record so the operator can still see that this was a rebuild and where the backup was created.

## Progress Source

Preferred source order:

1. Existing `ModuleBuilder.progress_callback` milestone calls.
2. Existing `ModuleBuilder.log(...)` milestone messages wrapped at the packet-builder boundary.
3. A minimal heartbeat only if no builder milestone source is safely available.

The implementation MUST NOT invent percent-complete values. The user-facing message should be milestone-based, for example `Step 3: Generating locations for each area...`.

## Frontend Contract

`pollToolkitHomebrewJob(jobId)` should render active build states using the latest progress message when present:

- For `building`, show `job.progress_message` before or instead of the generic `Packet-driven Homebrew build in progress` text.
- For rebuild handoff states, show backup/clean preparation success once, then active packet-build milestones as they arrive.
- Continue displaying the structured JSON payload so support/debugging still has access to job metadata.

## Failure Handling

- Progress callback exceptions MUST be caught or isolated so they cannot fail the module build.
- Job-state update failures MUST degrade to logging only.
- Existing final build result, readiness result, and error result paths MUST remain authoritative.

## Test Strategy

- Unit-test that packet builder accepts and forwards progress callbacks.
- Unit-test that a fake builder/executor progress event updates the toolkit job state while build is still active.
- Source or DOM contract test that the frontend renders `progress_message` for active build states.
- Regression test for rebuild mode proving backup metadata remains available after status transitions to active build progress.

## Open Questions

- Whether wrapping `ModuleBuilder.log(...)` is sufficient or whether additional explicit `progress_callback(...)` calls should be added around major builder steps.
- Whether the frontend should display `progress_updated_at` as elapsed/freshness text or rely only on message changes.
