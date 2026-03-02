# homebrew_sidecar_audit.py

## ADDED Requirements

### Requirement: Sidecar Discovery
The tool SHALL find latest sidecar for module slug.

#### Scenario: Find matching sidecar
Given slug "The_Secrets_of_Mangrove_Keep"
And archive contains "20260302_145118_ingested_The_Secrets_of_Mangrove_Keep.md.result.json"
When audit runs
Then it SHALL find and load the sidecar

#### Scenario: No sidecar found
Given slug with no matching sidecars
When audit runs
Then "sidecar_found" SHALL be false
And exit code SHALL be 1

### Requirement: Status Validation
The tool SHALL validate ingest status from sidecar.

#### Scenario: Successful ingest
Given sidecar with status "success"
When audit runs with --require-success
Then "valid" SHALL be true
And exit code SHALL be 0

#### Scenario: Quarantined ingest
Given sidecar with status "quarantined"
When audit runs with --require-success
Then "valid" SHALL be false
And exit code SHALL be 2

### Requirement: Registration Block Verification
The tool SHALL verify registration succeeded.

#### Scenario: Full registration success
Given sidecar with:
- registration_attempted: true
- registration_success: true
- registry_module_present: true
When audit runs
Then all SHALL be reported as true
And audit SHALL pass

## ADDED Interface

### CLI
```bash
python scripts/homebrew_sidecar_audit.py \
  --slug <module_slug> \
  [--require-success] \
  [--json]
```

## ADDED Exit Codes
- 0: Valid (and success if required)
- 1: Sidecar not found
- 2: Status not success
- 3: Registration failed
- 4: Invalid JSON
