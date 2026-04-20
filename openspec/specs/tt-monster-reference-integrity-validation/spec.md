## Purpose

Define deterministic monster-reference integrity validation and startup preflight compatibility semantics.
## Requirements
### Requirement: Module validation SHALL enforce monster reference integrity

The module validator SHALL fail validation when an area/location monster reference cannot be resolved to a monster stat file in the module, and its output SHALL remain consumable by startup preflight remediation flow.

#### Scenario: Unresolved monster reference fails validation

- **WHEN** an area/location references a monster name (for example `Cornfield Shadow`)
- **AND** `monsters/<normalized_name>.json` does not exist in the same module
- **THEN** validation SHALL mark `reference_integrity` as failed
- **AND** validation output SHALL include area/location context, source monster name, and expected file path

#### Scenario: Resolved reference passes validation

- **WHEN** all area/location monster references map to existing `monsters/*.json` files
- **THEN** `reference_integrity` SHALL pass
- **AND** no unresolved-reference errors SHALL be emitted

#### Scenario: Startup preflight consumes validator outcome deterministically

- **WHEN** validator reports unresolved references in `reference_integrity`
- **THEN** startup preflight SHALL treat that result as blocking unless remediated and revalidated
- **AND** startup decision logic SHALL rely on post-remediation validator output, not remediation attempt result alone

#### Scenario: Validator pass remains startup-compatible

- **WHEN** validator reports no unresolved references
- **THEN** startup preflight SHALL allow launch without remediation
- **AND** existing validation report semantics SHALL remain unchanged

#### Scenario: Normalization is deterministic

- **WHEN** a monster reference includes mixed case, spaces, or apostrophes
- **THEN** validator normalization SHALL produce the same slug convention used by combat monster lookup
- **AND** existing correctly named monster files SHALL resolve without false failures

### Requirement: Validator-visible unresolved monster paths SHALL remain repair-targetable

Reference-integrity validation output SHALL remain specific enough for deterministic repair to reconcile the exact expected monster path without ambiguous identity loss.

#### Scenario: Expected monster path drives reconciliation

- **WHEN** `reference_integrity` reports an unresolved path such as `expected monsters/echoes_of_the_party.json`
- **THEN** deterministic repair SHALL be able to derive that exact target slug from validator output
- **AND** reconcile it against authored structured monster evidence in the module

### Requirement: Residual monster reference closure SHALL preserve validator-target identity

Validator-driven monster closure SHALL preserve the exact unresolved target identity surfaced by `reference_integrity` so remediation and reporting remain tied to the file path the validator expects.

#### Scenario: Expected file path remains visible in residual reporting

- **WHEN** `reference_integrity` reports an unresolved monster reference with an expected file path
- **THEN** residual reporting SHALL preserve that expected slug/path in the closure result
- **AND** unresolved outcomes SHALL remain attributable to the validator-targeted file rather than only the authored monster display name

### Requirement: Reference-integrity failures SHALL remain consumable by residual closure repair

Validator reference-integrity outputs SHALL remain precise enough for downstream residual closure to derive deterministic monster targets.

#### Scenario: Validator output exposes expected file path deterministically

- **WHEN** reference-integrity validation fails for a missing monster file
- **THEN** the validator output SHALL include the expected normalized monster file path or equivalent deterministic target
- **AND** downstream residual closure SHALL be able to derive a canonical monster identity from that output without guessing

#### Scenario: Ambiguous reference target remains fail-closed

- **WHEN** validator output cannot be mapped back to a single canonical monster identity safely
- **THEN** residual closure SHALL classify the target as unresolved
- **AND** SHALL NOT invent or guess a replacement monster file

### Requirement: Reference-integrity failures SHALL support deterministic convergence repair

Monster reference-integrity failures MUST remain consumable by deterministic repair and convergence-classification workflows.

#### Scenario: Missing monster file is repair-targeted before final classification
- **GIVEN** validation reports an unresolved module monster reference
- **WHEN** readiness convergence remediation runs
- **THEN** the workflow SHALL attempt deterministic monster closure before final failure classification
- **AND** any remaining failure SHALL preserve area/location context and expected file path in the residual blocker report

#### Scenario: Unresolved reference survives deterministic closure attempt
- **GIVEN** convergence remediation attempted deterministic closure for a missing monster file
- **AND** the reference still cannot be resolved safely
- **WHEN** the workflow stops
- **THEN** the result SHALL be classified as residual monster-reference debt
- **AND** readiness SHALL remain failed

