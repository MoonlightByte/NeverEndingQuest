# Proposal: toolkit-homebrew-uploader-single-console-ux

## Why

The current Homebrew uploader still exposes operator-style recovery actions and fragmented status surfaces in the default user flow. Even after auto-starting build, normal users still see labels such as `Retry from packet`, `Cleanup workspace`, and multiple readout regions that require internal workflow knowledge to interpret. This creates avoidable confusion during the common upload path.

This change MUST simplify the default uploader experience into one primary live console surface with clear progress, clear completion messaging, and only one destructive confirmation step when an existing module would be replaced.

This change MUST NOT weaken the existing overwrite/backup safety contract, alter ingest/build semantics, or remove advanced recovery capabilities from the system entirely.

## What Changes

- Add a dedicated single-console UX capability for the default Homebrew uploader surface.
- Make the default uploader UI present one primary rolling output/readout window instead of multiple review/artifact/operator surfaces.
- Keep meaningful live status updates in that one console, including a visible in-progress indicator while work is active.
- End successful runs with a clear completion message that points users to the MMG tab for media generation.
- End failed runs with a clear help message that directs users to developer support and the project issue tracker.
- Hide `Retry from packet`, `Retry from finishing`, `Cleanup workspace`, and similar operator recovery actions from the normal user surface.
- Preserve advanced/dev access to artifact-manifest-backed recovery actions where practical, without making them default-user actions.
- Preserve overwrite confirmation as the only destructive confirmation step in the default flow.

## Capabilities

### New

- `toolkit-homebrew-uploader-console-ux`

### Modified

- `toolkit-homebrew-ingest-job-reporting`
- `toolkit-homebrew-artifact-visibility`

## Impact

### MUST

- The normal uploader flow SHALL show one main live console/readout window.
- The default surface SHALL keep live progress feedback meaningful enough for a non-operator user.
- The destructive overwrite confirmation SHALL remain explicit and separate.
- Existing structured job status and artifact data SHALL remain available to runtime code and advanced tooling.
- Existing ingest/build/rebuild behavior SHALL remain functionally unchanged apart from presentation and default-action exposure.

### SHOULD

- The active console SHOULD show a terminal-style working affordance, such as a blinking cursor or equivalent lightweight activity marker.
- Advanced recovery controls SHOULD be hidden behind an `Advanced` or developer-oriented surface rather than deleted.
- The console SHOULD degrade gracefully to raw stdout-like output when richer summaries are unavailable.

### Risks

- UI simplification could accidentally hide important rebuild-state context if console messaging is too thin.
- Hiding recovery controls could make developer troubleshooting slower if advanced access is removed instead of merely tucked away.

### Fallback Strategy

- Keep structured job payloads and artifact manifest contracts intact behind the simplified UI.
- Preserve advanced access paths so recovery actions can still be reached without restoring them to the default user surface.

### Merge-Safety / Compatibility

- Scope is confined to toolkit uploader UX and related reporting presentation.
- No SP/MP gameplay behavior changes are introduced.
- Existing destructive rebuild protections remain authoritative and unchanged.
