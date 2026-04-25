## 1. Console UX Surface

- [x] 1.1 Replace the default Homebrew uploader readout with one main live console/output window in `web/templates/module_toolkit.html`.
- [x] 1.2 Add clear active-work feedback in that console flow, such as a blinking cursor or equivalent lightweight running indicator.
- [x] 1.3 Add explicit terminal success copy directing users to the MMG tab for media generation.
- [x] 1.4 Add explicit terminal failure/help copy that points users to developer help and `https://github.com/zeug-zz/NeverEndingQuest-TTRPG/issues`.

## 2. Default-User Action Simplification

- [x] 2.1 Remove `Retry from packet`, `Retry from finishing`, `Cleanup workspace`, and similar operator actions from the normal uploader surface.
- [x] 2.2 Preserve overwrite confirmation as the only destructive confirmation step in the default flow.
- [x] 2.3 Keep advanced/dev access to recovery and artifact-backed actions where practical without exposing them as default-user controls.

## 3. Reporting / Contract Alignment

- [x] 3.1 Keep structured job `status`/`stage` reporting intact while projecting it through the simplified single-console UX.
- [x] 3.2 Preserve top-level `artifact_manifest`, `rebuild_eligible`, and `cleanup_allowed` compatibility for runtime and advanced tooling.
- [x] 3.3 Update regression/source-contract coverage for the new default surface and retained advanced contracts.
- [x] 3.4 Validate the change with targeted tests and `openspec validate toolkit-homebrew-uploader-single-console-ux`.
