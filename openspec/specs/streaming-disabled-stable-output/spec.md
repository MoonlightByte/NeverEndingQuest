## Purpose

Define rollback-mode narration behavior as block-only output while preserving dormant streaming foundations for future work.

## Requirements

### Requirement: Stable Block Narration Output
The system SHALL render player-facing narration via canonical block output only when rollback mode is active.

#### Scenario: Startup narration
- **WHEN** a game session starts in web mode
- **THEN** the UI shows canonical narration block output without incremental JSON token drafts

#### Scenario: Runtime narration turn
- **WHEN** a narration turn completes
- **THEN** exactly one canonical block narration is rendered in chat

#### Scenario: Combat narration turn
- **WHEN** a combat narration turn completes
- **THEN** output is rendered as canonical block narration without draft stream token leakage

### Requirement: Dormant Streaming Foundation Retained
The system SHALL retain backend streaming scaffolding while keeping it non-player-facing in rollback mode.

#### Scenario: Helper preserved without UX impact
- **WHEN** streaming foundation modules are present and feature flags are disabled
- **THEN** gameplay output remains block-only and user-visible behavior is unchanged

#### Scenario: Minimal host wiring only
- **WHEN** rollback mode is active
- **THEN** `web_interface` keeps transport and template-flag wiring only, and does not apply stream-based suppression logic to canonical narration emission

#### Scenario: Future re-enable path remains available
- **WHEN** future development revisits streaming UX
- **THEN** existing helper and flag structure can be reused without reintroducing current draft leakage behavior
