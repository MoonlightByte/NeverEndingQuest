# toolkit-restless-dead-semantic-closure Specification

## ADDED Requirements
### Requirement: Restless Dead remediation SHALL restore semantic-authority payload completeness
`Night_of_the_Restless_Dead` remediation SHALL restore the semantic-authority payload required by publication-time semantic tooling.

#### Scenario: Restless Dead currently lacks semantic-authority payload
- **GIVEN** `Night_of_the_Restless_Dead` publishability output reports missing semantic-authority payload in `module_context.json`
- **WHEN** Bucket B remediation lands
- **THEN** the module SHALL emit the required semantic-authority payload
- **AND** semantic auditing SHALL no longer fail for that missing-payload defect.

### Requirement: Restless Dead remediation SHALL close the named destination aliases deterministically
`Night_of_the_Restless_Dead` remediation SHALL close its currently known unresolved destination aliases without converting ambiguity into silent success.

#### Scenario: Restless Dead closes named unresolved travel phrases
- **GIVEN** semantic tooling reports unresolved travel phrases for `cathedral main hall`, `end ritual chamber`, `main hall`, `ritual chamber`, and `ruined cathedral`
- **WHEN** Bucket B remediation lands
- **THEN** each named phrase SHALL map to deterministic semantic-authority output or remain an explicit blocker if unresolved
- **AND** SHALL NOT be silently ignored to force a publishability pass.
