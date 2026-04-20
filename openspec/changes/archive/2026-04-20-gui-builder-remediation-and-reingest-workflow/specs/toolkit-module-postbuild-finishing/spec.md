# toolkit-module-postbuild-finishing Specification Delta

## MODIFIED Requirements

### Requirement: Toolkit builds run a shared post-build finishing pass
Toolkit-generated module directories MUST run a post-build finishing pass after raw generation succeeds so they do not bypass the quality stages already used by the ingest workflow.

#### Scenario: Same-run toolkit publishability can validate toolkit provenance
- **GIVEN** a toolkit finisher run is evaluating readiness or publishability with `source="toolkit"`
- **WHEN** toolkit provenance is required for that evaluation
- **THEN** the finisher MUST satisfy the provenance contract during the same run
- **AND** MUST NOT fail solely because the final toolkit report has not yet been written at the end of the run.
