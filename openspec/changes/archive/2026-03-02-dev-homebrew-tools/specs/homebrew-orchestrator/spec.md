# homebrew_ingest_dev.py

## ADDED Requirements

### Requirement: Full Pipeline Orchestration
The tool SHALL execute complete ingestion pipeline with stop-on-failure.

#### Scenario: Successful full ingest
Given a valid Homebrew source
When ingest_dev runs with --strict
Then it SHALL:
1. Run preflight (pass)
2. Transform if needed (pass)
3. Dry-run validate (pass)
4. Registry guard check (pass)
5. Strict ingest (success)
6. Sidecar audit (pass)
7. Registry verify (present)
And return status "success"

#### Scenario: Preflight failure
Given a source that cannot be auto-transformed
When ingest_dev runs
Then it SHALL halt at preflight stage
And return status "failed" with stage "preflight"

#### Scenario: Dry-run validation failure
Given a source that fails strict validation
When ingest_dev runs
Then it SHALL halt at dry-run stage
And not proceed to registry modification

### Requirement: Conditional Transform
The tool SHALL only transform when needed.

#### Scenario: Ready source skips transform
Given source with "ready: true" from preflight
When pipeline runs
Then transform step SHALL be skipped
And dry-run SHALL use original source

#### Scenario: Non-ready source requires transform
Given source with "can_auto_transform: true"
When pipeline runs
Then transform SHALL execute
And dry-run SHALL use transformed file

### Requirement: Comprehensive Reporting
The tool SHALL provide detailed JSON report.

#### Scenario: Success report
Given successful ingest
When pipeline completes
Then JSON SHALL include:
- status: "success"
- module_slug
- areas count
- encounters count
- registry_verified: true

## ADDED Interface

### CLI
```bash
python scripts/homebrew_ingest_dev.py \
  --source <path> \
  [--strict] \
  [--dry-run] \
  [--json]
```

## ADDED Exit Codes
- 0: Full success
- 1-7: Stage-specific failures (see design.md)
