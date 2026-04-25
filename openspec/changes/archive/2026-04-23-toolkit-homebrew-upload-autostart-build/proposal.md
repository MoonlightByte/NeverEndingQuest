# Why

The current Homebrew markdown upload flow stops after normalization and requires an explicit review decision before the user can start the packet build. In practice this creates a second permission step that does not map cleanly to the user's intent: they clicked import because they want the build to run. The extra `Approve and Build Later`, `Reject`, and `Start Build from Packet` controls add friction and make the flow feel like a detour instead of a single operation.

The toolkit should treat upload as an intent to build immediately, while keeping the separate overwrite/backup confirmation when an existing module would be replaced.

# What Changes

- MUST remove the visible review gate from the Homebrew markdown upload flow.
- MUST auto-advance a successful normalization result into packet build start without waiting for a manual approval action.
- MUST preserve explicit overwrite/backup confirmation before any destructive rebuild of an existing module slug.
- MUST preserve structured job reporting, artifact visibility, and retry-from-packet behavior.
- SHOULD keep an internal review snapshot or equivalent audit artifact if that is the lowest-risk way to preserve reporting compatibility.
- SHOULD avoid introducing a parallel upload workflow; this change updates the existing markdown upload contract.

Non-goals:

- This change does not redesign the concept-builder workflow.
- This change does not remove retry/rebuild-from-packet capabilities.
- This change does not relax any readiness, normalization, or destructive rebuild safety gates.

# Capabilities

- MODIFIED `toolkit-homebrew-md-upload`
  - Upload should auto-start build after normalization instead of pausing for review.
- MODIFIED `toolkit-homebrew-ingest-job-reporting`
  - Job status/stage reporting should reflect the new auto-start progression while keeping collision and confirmation states visible.
- MODIFIED `toolkit-homebrew-existing-module-clean-rebuild`
  - Existing-module collisions should block only on destructive confirmation, not on an earlier review approval step.

# Impact

- User impact: importing Homebrew markdown becomes a one-click build flow unless overwrite confirmation is required.
- Engineering impact: the upload state machine, review-facing UI, and related tests will need to shift from `awaiting_review -> approved_for_build -> build` toward direct build start after normalization.
- Rollout risk: medium. The current review state is embedded in route guards and tests, so the implementation must carefully preserve retry, reporting, and overwrite confirmation semantics.
- Fallback strategy: if auto-start build cannot be launched safely after normalization, the system should fail closed with explicit job error reporting rather than silently leaving the user in a hidden paused state.
- Merge-safety impact: moderate but localized to toolkit upload/build routes and the toolkit template. The change should prefer reuse of existing packet-build and collision-confirmation paths over wider workflow restructuring.
- SP/MP compatibility impact: none expected. This is toolkit-only and does not alter tabletop runtime behavior.
