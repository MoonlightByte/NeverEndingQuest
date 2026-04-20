## ADDED Requirements

### Requirement: Residual spatial reporting SHALL distinguish unchanged authored contradictions from repair-engine gaps

Spatial residual reporting SHALL separate unchanged contradiction sets that survive deterministic remediation from contradictions that changed but still failed validation.

#### Scenario: Unchanged contradiction set becomes authored structural debt

- **WHEN** deterministic spatial remediation runs
- **AND** the post-repair `spatial_contract` contradiction set is identical to the pre-repair contradiction set
- **THEN** residual reporting SHALL classify the result as authored structural debt
- **AND** SHALL NOT report that outcome as blocker-resolution advancement

#### Scenario: Changed contradiction set remains repair-engine gap

- **WHEN** deterministic spatial remediation changes the contradiction set but validation still fails
- **THEN** residual reporting SHALL classify the outcome as an unresolved repair-engine gap
- **AND** SHALL preserve both pre-change and post-change contradiction context
