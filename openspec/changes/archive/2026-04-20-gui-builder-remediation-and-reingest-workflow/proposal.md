## Why

The structural stabilization slice separated toolkit-vs-watcher contracts and fixed the monster materialization path, but the first baseline reruns and Numillian re-ingest showed the next layer of problems clearly: same-run toolkit provenance is validated before the finisher writes its own report, warning-only semantic degradation is still collapsing publishability, and real content blockers such as missing structured-monster media now need an explicit remediation workflow instead of being mixed into generic build failure noise.

This change is needed now so the builder can move from structural repair to an operationally usable remediation loop, with `The_Hidden_City_of_Numillian` as the first end-to-end toolkit canary.

## What Changes

- Add a toolkit remediation workflow contract that classifies post-build failures into actionable buckets such as provenance-ordering, semantic warning/tooling debt, and real content remediation.
- Update toolkit post-build finishing so toolkit-source publishability can satisfy its provenance contract during the same finisher run.
- Update readiness gating so toolkit provenance can be validated safely in same-run toolkit execution without weakening watcher-source requirements.
- Update semantic publication and publishability policy so warning-only semantic degradation does not automatically imply the same failure class as true semantic blocking contradictions.
- Update publishability reporting to surface remediation categories and warning-vs-blocking semantics clearly.
- Add rerun/canary expectations for legacy watcher modules versus toolkit-built modules, including a defined Numillian acceptance path.

## Capabilities

### New Capabilities
- `toolkit-module-remediation-workflow`: classify toolkit post-build failures into deterministic remediation buckets, expected source contracts, and canary rerun outcomes.

### Modified Capabilities
- `toolkit-module-postbuild-finishing`: toolkit finishing must satisfy toolkit provenance safely during the same run and preserve remediation-friendly outputs.
- `module-readiness-continuity-gate`: toolkit-source readiness must support same-run provenance validation while watcher-source sidecar rules remain strict.
- `module-semantic-publication-audit`: warning-only semantic degradation and tooling debt must remain distinguishable from true semantic blocking contradictions.
- `module-semantic-publication-probes`: probe fixture/tooling gaps must be reported distinctly from authored hidden-NPC or travel-authority failures.
- `module-publishable-gate`: publishability must fail on semantic blocking findings, not merely on warning-only degraded semantic/tooling status.
- `module-publishability-reporting`: reporting must expose remediation classes and make warning-only degradation legible without collapsing it into generic failure noise.

## Impact

- Affected code:
  - `web/extensions/toolkit_module_finisher.py`
  - `scripts/audit_module_readiness.py`
  - `scripts/audit_module_publishability.py`
  - `scripts/module_semantic_probe_harness.py`
  - reporting/regression suites and baseline artifacts
- Affected systems:
  - toolkit finisher
  - readiness/publishability CLI and JSON reporting
  - toolkit provenance contract
  - baseline rerun/canary workflow
- Merge safety:
  - primarily extension and audit/reporting files; no intended host-runtime gameplay behavior change
- SP/MP compatibility:
  - no gameplay-mode behavior change intended; this is module build/audit workflow only
- Rollout risk:
  - loosening semantic publishability too far could hide real publication blockers
  - fallback strategy MUST preserve fail-closed behavior for true blocking findings while downgrading only warning/tooling-debt cases
