# module-readiness-continuity-gate Specification

## Purpose
TBD - created by archiving change any-order-module-continuity-normalization. Update Purpose after archive.
## Requirements
### Requirement: Readiness Continuity Gate

Module readiness validation SHALL include a continuity gate that evaluates required Continuity Contract v1 fields.

The continuity gate MUST provide machine-readable results with:
- `status` (string: "pass", "fail", "degraded")
- `blocking_errors` (array of error objects)
- `warnings` (array of warning objects)
- `required_keys_present` (array of string key names)
- `continuity_version` (string, expected "v1")

Error object structure:
```json
{
  "type": "missing_required_key",
  "field": "entry_state_variants",
  "message": "Required continuity key 'entry_state_variants' is absent",
  "severity": "blocking"
}
```

Warning object structure:
```json
{
  "type": "alias_ambiguity",
  "entity": "red",
  "candidates": ["red_crimson_binder", "red_wandering_merchant"],
  "message": "Ambiguous alias 'red' matches multiple entities"
}
```

#### Scenario: Continuity gate pass

- **GIVEN** required continuity fields are present and structurally valid
- **WHEN** the continuity gate runs
- **THEN** continuity gate returns pass status with exit code 0
- **AND** `status` is "pass"
- **AND** `blocking_errors` is empty
- **AND** `required_keys_present` contains all four required keys

#### Scenario: Continuity gate fail - missing required key

- **GIVEN** strict continuity mode is enabled
- **AND** a required continuity key is missing
- **WHEN** the continuity gate runs
- **THEN** continuity gate returns fail status with exit code 1
- **AND** `status` is "fail"
- **AND** `blocking_errors` contains an entry for the missing key

#### Scenario: Continuity gate degraded - alias warnings only

- **GIVEN** all required keys are present
- **AND** there are alias ambiguity warnings
- **AND** warn-first profile is active
- **WHEN** the continuity gate runs
- **THEN** continuity gate returns degraded status with exit code 0
- **AND** `status` is "degraded"
- **AND** `warnings` contains alias ambiguity entries
- **AND** module is considered valid for release

### Requirement: Sidecar Continuity Section Audit

Sidecar audit SHALL validate continuity payload shape when `continuity_contract` exists.

The audit MUST check:
- Presence of required top-level keys in `continuity_contract`
- Type validity of `status` field (must be one of: success, warning, error, quarantined)
- Presence of `version` field matching expected "v1"
- Array validity of `required_keys_present`, `missing_required_keys`, `warnings`, `errors`

#### Scenario: Continuity payload present and valid

- **GIVEN** sidecar includes `continuity_contract` section
- **AND** all required fields are present and valid
- **WHEN** sidecar audit runs
- **THEN** audit reports section as present and valid
- **AND** no errors are emitted for continuity section

#### Scenario: Continuity payload present but malformed

- **GIVEN** sidecar includes `continuity_contract` section
- **AND** required fields are missing or have invalid types
- **WHEN** sidecar audit runs
- **THEN** audit fails with explicit continuity section reason
- **AND** error specifies which field is malformed and expected type

#### Scenario: Continuity payload absent but module claims continuity support

- **GIVEN** module `module_context.json` includes `continuity_version`
- **AND** sidecar does NOT include `continuity_contract` section
- **WHEN** sidecar audit runs in strict mode
- **THEN** audit fails with error indicating missing continuity sidecar data
- **AND** error suggests re-running ingest with continuity stage enabled

### Requirement: Cross-Module Reference Validation

The continuity gate SHALL validate that `cross_module_refs` entries conform to the normalized reference schema.

Each reference MUST have:
- `target_module`: non-empty string matching valid module slug pattern
- `entity_id`: non-empty string with underscore-separated identifier format
- `relation`: one of enumerated valid relation types
- `confidence`: one of "high", "medium", "low"

#### Scenario: Valid cross-module reference passes

- **GIVEN** a cross-module reference with all required fields
- **AND** `target_module` matches existing module slug
- **AND** `entity_id` follows canonical identifier format
- **WHEN** the continuity gate validates references
- **THEN** the reference passes validation
- **AND** no warnings are emitted

#### Scenario: Invalid cross-module reference fails

- **GIVEN** a cross-module reference with missing required field
- **OR** `target_module` does not match any known module
- **OR** `entity_id` contains invalid characters
- **WHEN** the continuity gate validates references
- **THEN** the reference fails validation
- **AND** blocking error is added to `blocking_errors`

#### Scenario: Unknown target module generates warning

- **GIVEN** a cross-module reference with `target_module` not in known modules list
- **AND** warn-first profile is active
- **WHEN** the continuity gate validates references
- **THEN** a warning is generated for unknown target
- **AND** validation continues (does not block)

### Requirement: Toolkit-source readiness SHALL support same-run toolkit provenance validation
Toolkit-source readiness validation SHALL support the current toolkit finisher run satisfying toolkit provenance without weakening watcher-source sidecar enforcement.

#### Scenario: Toolkit current-run provenance passes readiness
- **GIVEN** readiness is running for `source="toolkit"`
- **AND** the current finisher run has provided valid toolkit provenance for the requested module
- **WHEN** readiness evaluates provenance
- **THEN** the provenance gate SHALL pass
- **AND** SHALL NOT require a previously completed historical toolkit report.

#### Scenario: Watcher-source sidecar enforcement remains unchanged
- **GIVEN** readiness is running for `source="watcher"`
- **WHEN** ingest sidecar provenance is missing
- **THEN** readiness SHALL fail closed for watcher provenance
- **AND** SHALL NOT treat toolkit provenance as a substitute.

