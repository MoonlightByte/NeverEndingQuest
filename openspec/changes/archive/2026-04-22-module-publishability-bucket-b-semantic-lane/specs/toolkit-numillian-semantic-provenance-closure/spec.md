# toolkit-numillian-semantic-provenance-closure Specification

## ADDED Requirements
### Requirement: Numillian remediation SHALL close the named destination ambiguity canary explicitly
`The_Hidden_City_of_Numillian` remediation SHALL treat `paradox sanctuary` as an explicit ambiguity/probe closure target.

#### Scenario: Numillian closes `paradox sanctuary`
- **GIVEN** semantic tooling reports unresolved destination phrase `paradox sanctuary`
- **WHEN** Bucket B remediation lands
- **THEN** the phrase SHALL resolve to deterministic semantic-authority output or remain an explicit blocker if unresolved
- **AND** SHALL NOT be removed from audit visibility merely to improve the pass count.

### Requirement: Numillian remediation SHALL include provenance closure, not semantic closure alone
Numillian remediation SHALL include the sidecar/provenance closure needed for readiness, because semantic remediation alone is insufficient.

#### Scenario: Numillian still has readiness debt until sidecar exists
- **GIVEN** `The_Hidden_City_of_Numillian` has a sidecar/provenance gap that keeps `ready_status=fail`
- **WHEN** Bucket B remediation lands
- **THEN** the module SHALL produce the required sidecar/provenance artifact
- **AND** verification SHALL rerun both readiness and publishability rather than publishability alone.
