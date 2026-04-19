## Context

The Homebrew upload flow now persists a normalized packet, requires review, runs packet-driven build, and then runs the structural readiness gate. That path assumes the derived module slug can be built into `modules/<slug>` directly.

Today, repeated upload of the same source title resolves to the same slug and therefore the same module directory. The builder creates directories with `exist_ok=True` and overwrites many generated files in place, but it does not clear the module directory first. The result is an overlay rebuild where stale files can survive and influence later validation.

This change adds a deterministic rebuild boundary for repeated Homebrew uploads without changing the concept-builder workflow or the existing build/readiness logic.

## Goals / Non-Goals

**Goals:**
- MUST detect when a reviewed Homebrew upload resolves to an already-existing module directory.
- MUST require explicit operator confirmation before destructive rebuild begins.
- MUST create a recoverable backup before cleaning the target module directory.
- MUST abort rebuild cleanly if backup creation fails.
- MUST run the same packet build and structural readiness stages after the clean step so fresh and repeated uploads converge on the same validated state.
- SHOULD surface rebuild-specific progress and result details in the existing toolkit UI/status patterns.

**Non-Goals:**
- This change does NOT add arbitrary module revalidation from the builder module list.
- This change does NOT attach finisher/publication to the Homebrew rebuild flow.
- This change does NOT redesign module slug derivation or prompt interpretation.
- This change does NOT change the legacy concept-builder socket workflow.

## Decisions

### Decision: Repeated uploads use `backup + clean rebuild`
- MUST back up the existing module directory before any cleanup occurs.
- MUST then remove the active target directory contents before packet build begins.
- SHOULD use a timestamped sibling backup path so recovery is local, obvious, and does not depend on Git.

Rationale:
- Clean rebuild is deterministic; overlay rebuild is not.
- Timestamped backup gives fast manual recovery if the new build is worse.

Alternative considered:
- Overlay rebuild with warning only. Rejected because stale files remain and validation can observe mixed old/new state.

### Decision: Confirmation happens after review approval but before build starts
- MUST not interrupt normalization or review.
- MUST only ask for overwrite confirmation when the operator actually initiates the approved build and a collision exists.

Rationale:
- The module slug is most authoritative after normalized packet review.
- This keeps review semantics unchanged and scopes rebuild UX to the destructive boundary.

Alternative considered:
- Warn at upload time. Rejected because slug/title may still change during review and the operator has not yet chosen to build.

### Decision: Rebuild reuses existing build and readiness stages unchanged after cleanup
- MUST not fork a second builder pipeline for repeated uploads.
- MUST enter the same packet-driven build and structural readiness logic after backup and cleanup complete.

Rationale:
- Fresh uploads and repeated uploads should converge on the same resulting structure.
- Reusing the existing path minimizes regression risk.

Alternative considered:
- Special rebuild-only orchestration. Rejected because it would duplicate logic and create drift between fresh and repeated imports.

### Decision: Rebuild state is reported explicitly
- MUST distinguish collision-detected, awaiting-confirmation, backup-running, clean-running, and rebuild-running states from ordinary fresh upload states.
- SHOULD persist backup path and rebuild mode in the workspace/job payload for operator inspection.

Rationale:
- Destructive workflows need stronger visibility and auditability than normal builds.

## Risks / Trade-offs

- [Risk] Backup directories accumulate over time -> Mitigation: backup naming SHOULD be structured and discoverable; cleanup policy can be added in a later slice.
- [Risk] Operator confirms rebuild accidentally -> Mitigation: confirmation modal MUST describe that the active module directory will be replaced and that a backup will be created first.
- [Risk] Backup succeeds but cleanup fails -> Mitigation: rebuild MUST stop before builder execution and report bounded failure with preserved backup path.
- [Risk] Existing module contains manual edits that are lost from the active path -> Mitigation: backup is mandatory and rebuild is opt-in only.
- [Risk] Route/UI complexity grows -> Mitigation: scope the change to the Homebrew upload path and reuse existing status/report surfaces.

## Migration Plan

1. Add collision detection based on the reviewed packet's derived module slug.
2. Add GUI confirmation and a route/API contract for confirmed overwrite.
3. Add backup helper and clean helper with fail-closed backup behavior.
4. Resume the existing packet build and readiness flow after cleanup.
5. Expose backup/rebuild metadata in job reporting.

Rollback strategy:
- If the feature regresses, disable the collision-confirmation path and return to non-destructive behavior while keeping backups already created.
- Recovery of a single module SHOULD be possible by restoring the timestamped backup directory manually.

## Open Questions

- SHOULD the backup live under `modules/_rebuild_backups/` or as a timestamped sibling near the module directory?
- SHOULD the UI offer the backup path in the final result, or is status/detail text sufficient for this slice?
