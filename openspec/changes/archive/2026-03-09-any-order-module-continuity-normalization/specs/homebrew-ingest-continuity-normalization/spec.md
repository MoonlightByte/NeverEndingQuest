## ADDED Requirements

### Requirement: Ingest Continuity Normalization Stage

Homebrew ingest SHALL include a continuity normalization stage that emits deterministic continuity metadata for sidecar auditing.

The ingest result payload MUST include a `continuity_contract` section with the following structure:
```json
{
  "continuity_contract": {
    "status": "success|warning|error|quarantined",
    "version": "v1",
    "required_keys_present": ["continuity_version", "entry_state_variants", ...],
    "missing_required_keys": [],
    "warnings": [
      {"type": "alias_ambiguity", "entity": "red", "candidates": [...]}
    ],
    "errors": [],
    "normalized_refs_count": 5,
    "alias_resolution": {
      "resolved": 4,
      "ambiguous": 1
    }
  }
}
```

#### Scenario: Strict ingest with complete continuity metadata

- **GIVEN** strict ingest runs on a source that can be normalized to required continuity keys
- **WHEN** the continuity stage completes
- **THEN** ingest returns success with `continuity_contract.status=success`
- **AND** sidecar includes canonical continuity fields
- **AND** `required_keys_present` lists all four required keys

#### Scenario: Strict ingest with missing required continuity keys

- **GIVEN** strict ingest cannot produce required continuity keys
- **WHEN** the continuity stage completes
- **THEN** ingest fails closed with `continuity_contract.status=error`
- **AND** `missing_required_keys` lists absent fields
- **AND** sidecar reports explicit `quarantine_reason`

### Requirement: Warn-first Alias Handling

In warn-first rollout profile, unresolved or ambiguous cross-module alias mappings SHALL generate warnings and SHALL NOT block ingest.

#### Scenario: Ambiguous alias in warn-first profile

- **WHEN** alias resolution yields multiple candidates
- **THEN** continuity stage records warning with ambiguity details
- **AND** ingest remains successful if required keys are otherwise present
