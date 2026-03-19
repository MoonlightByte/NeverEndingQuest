## ADDED Requirements

### Requirement: Dormant seamless transition post-processor status SHALL be documented explicitly
Repository guidance SHALL explicitly state that the LLM-based seamless transition post-processor is disabled/dormant in active runtime flow until a future validated change re-enables or removes it.

#### Scenario: AGENTS or equivalent runtime guidance records dormant status
- **WHEN** maintainers or builders read repository guidance for movement architecture
- **THEN** the guidance SHALL identify the seamless transition post-processor as disabled/dormant rather than active architecture

### Requirement: Dormant runtime layers SHALL carry cleanup intent
When an LLM runtime layer is intentionally disabled, repository guidance SHALL record whether it is retained temporarily for future review or slated for removal.

#### Scenario: Disabled helper is not mistaken for live dependency
- **WHEN** a future builder audits transition code paths
- **THEN** code comments or guidance SHALL make clear that the disabled helper is not part of the authoritative runtime path
- **AND** the artifact SHALL record cleanup or re-enable intent