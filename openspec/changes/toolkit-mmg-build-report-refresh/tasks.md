# Tasks: toolkit-mmg-build-report-refresh

## 1. MMG Refresh Contract

- [ ] 1.1 Identify the exact successful MMG completion branch that should trigger persisted report refresh.
- [ ] 1.2 Route that branch through the shared `refresh_toolkit_build_report(...)` helper instead of bespoke JSON write logic.
- [ ] 1.3 Preserve fail-open MMG completion behavior when report refresh degrades or raises.

## 2. Sidebar Refresh Wiring

- [ ] 2.1 Reuse the existing module-list refresh path so updated persisted report signals can reach both Module Builder and Module Toolkit sidebars after MMG completion.
- [ ] 2.2 Keep sidebar rendering on persisted module-list data only; do not add live MMG recomputation to the card renderers.

## 3. Verification

- [ ] 3.1 Add regression coverage proving successful MMG generation rewrites persisted report state for a module with prior media debt.
- [ ] 3.2 Add regression coverage proving refresh failure does not block MMG completion and leaves sidebar readers fail-open on the previous persisted report.
- [ ] 3.3 Verify duplicate sidebar renderers remain aligned through the shared module-list refresh path.

## Guidance

- Keep this slice narrow: MMG completion -> persisted report refresh -> sidebar refresh.
- Prefer one anchored backend refresh hook and one existing frontend module-list refresh path.
- Avoid new socket payload shapes unless the existing module-list request/response path cannot cover the need.
