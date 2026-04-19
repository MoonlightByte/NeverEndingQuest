## Why

Repeated upload of the same Homebrew markdown currently targets the same module slug and reuses the existing module directory, but the build path does not clear that directory first. That creates overlay rebuild behavior where some generated files are overwritten while stale files may survive, which makes repeated imports non-deterministic and unsafe.

Now that packet-driven build and structural readiness are working, the next slice should make repeated upload of the same module explicit and safe. The toolkit should warn before replacing an existing module, preserve a recoverable backup, and then run the current build plus readiness flow against a clean target directory.

## What Changes

- Add existing-module collision detection before packet-driven Homebrew build starts.
- Add a GUI confirmation step when the derived module slug already exists on disk.
- Add `backup + clean rebuild` as the required overwrite policy for confirmed repeated uploads.
- Preserve a recoverable backup of the existing module directory before any destructive cleanup occurs.
- Route confirmed rebuilds through the same packet build and structural readiness pipeline already used for fresh Homebrew uploads.
- Expose rebuild-specific status and artifact details so operators can tell the difference between a fresh build and a confirmed rebuild.
- MUST block destructive rebuild if backup creation fails.
- MUST leave the existing module untouched when the operator cancels.
- SHOULD keep the change isolated to the Homebrew upload path rather than modifying the legacy concept-builder flow.
- Non-goals: add GUI revalidation for arbitrary existing modules, attach finisher/publication, or redesign module naming/slug derivation in this slice.

## Capabilities

### New Capabilities
- `toolkit-homebrew-existing-module-clean-rebuild`: repeated Homebrew upload can safely rebuild an existing module by requiring confirmation, creating a backup, cleaning the target directory, and then running the existing build/readiness flow.

### Modified Capabilities
- `toolkit-homebrew-md-upload`: repeated uploads that resolve to an existing module slug now require explicit operator confirmation instead of silently reusing the existing module directory.
- `toolkit-homebrew-ingest-job-reporting`: toolkit job reporting now distinguishes confirmed rebuild flow, backup outcomes, and clean-rebuild stage visibility from ordinary fresh-upload progress.

## Impact

- Affected GUI surface: `web/templates/module_toolkit.html`
- Affected upload orchestration: `web/routes/toolkit_homebrew_routes.py`
- Likely new helper surface: `web/extensions/` for collision detection, backup creation, and clean-rebuild staging
- Affected workspace/result contract: rebuild state and backup metadata may need to be persisted alongside existing Homebrew job artifacts
- Filesystem impact: module directories under `modules/<slug>` will be renamed or copied to a backup location before cleanup and rebuild
- Merge-safety impact: SHOULD remain additive by extending the Homebrew upload path only
- SP/MP compatibility impact: no gameplay runtime behavior change; MUST remain toolkit-only
- Rollout risk: destructive rebuild semantics require explicit confirmation, strong backup failure handling, and clear operator messaging
