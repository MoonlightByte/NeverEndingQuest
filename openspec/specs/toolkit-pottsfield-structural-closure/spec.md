# toolkit-pottsfield-structural-closure Specification

## Purpose
TBD - created by archiving change module-publishability-bucket-a-quick-wins. Update Purpose after archive.
## Requirements
### Requirement: Pottsfield quick-win remediation SHALL close the named monster definition gap
`A_Pottsfield_Burial` quick-win remediation SHALL close the currently identified missing monster definition for `crawling_claws`.

#### Scenario: Pottsfield is blocked by missing `crawling_claws.json`
- **GIVEN** readiness reports `Create: modules/A_Pottsfield_Burial/monsters/crawling_claws.json`
- **WHEN** Bucket A remediation lands
- **THEN** that monster definition SHALL exist in the module monster set
- **AND** readiness SHALL no longer report that missing-file blocker.

### Requirement: Pottsfield quick-win remediation SHALL close the module-local monster media gap
Pottsfield quick-win remediation SHALL close the currently identified module-local monster image debt for `crawling_claws`.

#### Scenario: Pottsfield is blocked by missing module-local monster image
- **GIVEN** readiness reports `Add media: modules/A_Pottsfield_Burial/media/monsters/crawling_claws.jpg`
- **WHEN** Bucket A remediation lands
- **THEN** that module-local monster image SHALL exist
- **AND** readiness SHALL no longer treat `crawling_claws` as unresolved media debt.

### Requirement: Pottsfield verification SHALL surface any newly exposed residual blockers
Pottsfield verification SHALL rerun the normal gates after the bounded closure and SHALL NOT assume the module passes without checking for newly surfaced debt.

#### Scenario: Pottsfield reruns readiness and publishability after bounded closure
- **GIVEN** the `crawling_claws` JSON and media closures have landed
- **WHEN** readiness and publishability audits are rerun
- **THEN** the result SHALL either pass or surface any remaining blocker explicitly
- **AND** SHALL NOT collapse new debt into an ambiguous generic success/fail note.

