## ADDED Requirements

### Requirement: Compressed combat prompts SHALL be the canonical live runtime source
The multi-PC combat simulation and combat validation runtime paths SHALL load the compressed combat prompt variants as the canonical live contract.

#### Scenario: Multi-PC combat simulation loads compressed authority
- **WHEN** multi-PC combat simulation loads its system prompt for live runtime use
- **THEN** it SHALL load `prompts/combat/combat_sim_prompt_multipc_compressed.txt`
- **AND** it SHALL NOT rely on the uncompressed multi-PC prompt as an alternate live runtime authority

#### Scenario: Multi-PC combat validation loads compressed authority
- **WHEN** multi-PC combat validation loads its validator prompt for live runtime use
- **THEN** it SHALL load `prompts/combat/combat_validation_prompt_multipc_compressed.txt`
- **AND** it SHALL NOT rely on the uncompressed multi-PC validation prompt as an alternate live runtime authority

### Requirement: Combat prompt authority change SHALL preserve current compatibility boundaries
Switching combat runtime authority to compressed prompts SHALL preserve current single-player compatibility and TT phase-control behavior.

#### Scenario: Single-player combat path remains compatible
- **WHEN** single-player combat executes after the combat prompt authority change
- **THEN** existing single-player combat behavior SHALL remain compatible
- **AND** no TT-only prompt authority branch SHALL be required for single-player execution
