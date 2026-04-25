# Tasks: toolkit-build-report-refresh-contract

## 1. Contract Definition

- [x] 1.1 Define the authoritative versus stale lifecycle for `toolkit_build_report.json` in the toolkit/reporting path.
- [x] 1.2 Define the minimum freshness metadata fields and semantics required on persisted toolkit reports.
- [x] 1.3 Confirm the sidebar remains a persisted-report consumer only and does not gain live audit behavior.

## 2. Report Writer Alignment

- [x] 2.1 Identify the canonical toolkit finisher/report-writing helper or path that owns the authoritative report write.
- [x] 2.2 Ensure the canonical writer emits the required freshness metadata alongside existing status/report fields.
- [x] 2.3 Ensure the canonical writer preserves fail-open reader compatibility for missing or malformed older reports.

## 3. Refresh Path Coverage

- [x] 3.1 Identify the narrow remediation/revalidation workflows that are allowed to refresh `toolkit_build_report.json` after publishability-affecting fixes.
- [x] 3.2 Route those eligible workflows through the shared report-refresh contract rather than ad hoc report rewrites.
- [x] 3.3 Ensure known-stale report conditions are represented deterministically rather than left implicit.

## 4. Verification

- [x] 4.1 Add targeted regression coverage for freshness metadata and explicit report refresh behavior.
- [x] 4.2 Add a canary regression proving a stale persisted report can be refreshed into current blocker semantics without sidebar-time live audits.
- [x] 4.3 Verify toolkit build reporting and post-build finishing contracts remain aligned with existing main specs.
- [x] 4.4 Manually review the change against `plans/module-uploader-2.md` to confirm this slice remains a narrow prerequisite, not a scope expansion.

## Guidance

- Keep this change narrow. It is a prerequisite contract hardening slice for report authority/freshness.
- Reuse existing toolkit finisher/reporting infrastructure where possible instead of creating a parallel artifact pipeline.
- Prefer one shared report-refresh path over several bespoke JSON writers.
- Preserve the sidebar's cheap read-only behavior throughout.
