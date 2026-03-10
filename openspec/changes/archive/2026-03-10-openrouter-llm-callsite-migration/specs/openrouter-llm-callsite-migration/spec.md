## ADDED Requirements

### Requirement: Tiered callsite migration completion
The system SHALL migrate all in-scope LLM callsites for this change through a tiered sequence (high -> medium -> low risk) while preserving existing gameplay behavior contracts at each tier boundary.

#### Scenario: High-risk tier is migrated first
- **WHEN** migration work begins for this change
- **THEN** combat and core narration callsites are migrated and validated before medium or low-risk tiers are marked complete

#### Scenario: Tier completion is gated by verification
- **WHEN** a migration tier is claimed complete
- **THEN** that tier includes explicit verification evidence for syntax, runtime smoke tests, and provider fallback behavior

### Requirement: Provider-aware routing and fallback consistency
Every migrated callsite MUST use shared provider-aware routing/factory utilities for client selection, model/profile mapping, timeout policy, and retryable-error fallback behavior.

#### Scenario: Retryable provider failure occurs
- **WHEN** a migrated callsite receives a retryable provider error (rate limit, timeout, 5xx, or transient connectivity failure)
- **THEN** the shared fallback path reroutes to the configured fallback provider and returns a response or terminal error through the same interface

#### Scenario: Non-retryable provider failure occurs
- **WHEN** a migrated callsite receives a non-retryable provider error
- **THEN** the call fails without silent fallback and emits structured error logging for diagnosis

### Requirement: Backward compatibility for SP and MP runtime behavior
The migration MUST preserve single-player compatibility and tabletop multiplayer behavior, including existing prompt contracts and deterministic mechanics/state boundaries.

#### Scenario: Single-player runtime remains functional
- **WHEN** the game runs in single-player mode after migration
- **THEN** narration, validation, and progression flows operate without requiring multiplayer state hooks

#### Scenario: Multiplayer runtime preserves deterministic mechanics
- **WHEN** the game runs in tabletop multiplayer mode after migration
- **THEN** LLM routing changes do not alter Python-enforced mechanical truth, turn sequencing, or state persistence invariants

### Requirement: Observability and rollout safety
The migration SHALL provide consistent logging and metrics for provider selection, fallback activation, and callsite-level migration status to support safe rollout and rollback.

#### Scenario: Fallback event is triggered
- **WHEN** a fallback path is activated in a migrated callsite
- **THEN** logs include originating role/callsite context and source/target provider details

#### Scenario: Rollback is required for a tier
- **WHEN** post-migration verification fails for a tier
- **THEN** the system can revert that tier and continue operating using the previous stable provider path without data corruption
