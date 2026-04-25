# Context

`core/generators/module_stitcher.py` derives sidebar build status from persisted `toolkit_build_report.json`. The persisted-report read path is correct, but the derivation currently ignores freshness metadata that was added by the build-report refresh contract. As a result, legacy failed reports can keep poisoning the sidebar after later remediation made the module pass.

# Goals

- Preserve the sidebar as a persisted-report consumer.
- Surface compact failure text only from current authoritative reports.
- Preserve structural media handoff semantics for genuinely current debt.

# Non-Goals

- Live audit fallback from the sidebar.
- New template/UI rendering contracts.

# Decisions

1. Sidebar failure derivation SHALL require freshness authority.
   - If `report_freshness.authoritative` is true and `report_freshness.state == "current"`, the report is authoritative.
   - Legacy failed reports without freshness metadata SHALL fail open and produce no sidebar failure signal.

2. Existing compact failure mapping SHALL remain intact for authoritative reports.

3. Media handoff classification SHALL continue to use structural media debt and explicit remediation categories rather than optional media warnings.

# Architecture

- Add a helper in `module_stitcher.py` that evaluates report freshness authority.
- Short-circuit `_derive_sidebar_audit_signals(...)` when the persisted failure report is not authoritative.
- Extend sidebar regression tests to cover stale/legacy suppression and explicit non-authoritative suppression.

# Risks / Trade-offs

- Some older valid reports may disappear from the sidebar until refreshed.
- This is acceptable because the persisted report contract now includes freshness metadata and stale failures are more misleading than absence.

# Migration Plan

1. Update `module_stitcher.py` helpers.
2. Update regression tests.
3. Validate against Numillian/Thornwood behavior.

# Verification Plan

- `python3 -m py_compile core/generators/module_stitcher.py scripts/test_module_sidebar_audit_failure_signals.py`
- `.venv/bin/python scripts/test_module_sidebar_audit_failure_signals.py`
