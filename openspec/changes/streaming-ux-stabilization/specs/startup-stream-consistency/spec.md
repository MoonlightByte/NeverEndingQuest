## ADDED Requirements

### Requirement: Deterministic Startup Narration Policy
The system SHALL apply one deterministic startup narration policy across both injected-return and normal-start branches.

#### Scenario: Injected-return startup path
- **WHEN** startup narration is generated from an injected return-note branch
- **THEN** streaming enablement and commit behavior match the configured startup policy used in normal-start branch

#### Scenario: Normal-start path
- **WHEN** startup narration is generated from normal-start branch
- **THEN** the same startup streaming policy and canonical commit rules are applied

#### Scenario: Streaming disabled startup
- **WHEN** streaming is disabled by feature flag
- **THEN** both startup branches use the same non-stream fallback behavior
