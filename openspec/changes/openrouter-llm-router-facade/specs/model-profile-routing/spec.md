## ADDED Requirements

### Requirement: Profile-Based Model Selection
The system MUST select models and provider-specific request parameters from configured model profiles based on task capability classification (for example complex vs simple) instead of hardcoded model IDs in business logic.

#### Scenario: Complex task selects complex profile model
- **WHEN** a task is classified as complex in routing configuration
- **THEN** the router SHALL use the profile's `complex_model` and `complex_params`

#### Scenario: Simple task selects simple profile model
- **WHEN** a task is classified as non-complex in routing configuration
- **THEN** the router SHALL use the profile's `simple_model` and `simple_params`

### Requirement: Safe Profile Defaults and Validation
The system MUST validate required profile fields at startup and MUST use a safe default profile when configured profile values are missing or partially invalid.

#### Scenario: Missing profile key
- **WHEN** configured profile name is not found
- **THEN** router SHALL use default profile values and emit a categorized warning without aborting gameplay startup

#### Scenario: Partial profile with missing model entries
- **WHEN** profile exists but lacks `complex_model` or `simple_model`
- **THEN** router SHALL fall back to configured base model for missing entries and preserve call execution

### Requirement: Provider Parameter Normalization
The system MUST normalize provider-specific request extras into SDK-compatible parameter shapes before API invocation.

#### Scenario: OpenRouter thinking parameters
- **WHEN** selected profile includes thinking-mode parameters
- **THEN** router SHALL pass them using SDK-supported `extra_body` structure and SHALL NOT emit unsupported top-level kwargs

### Requirement: Thread-Safe Usage and Fallback Telemetry
The system MUST maintain thread-safe counters for calls, tokens/cost estimates (when available), fallback transitions, and categorized errors.

#### Scenario: Concurrent requests update stats
- **WHEN** multiple threads issue router calls simultaneously
- **THEN** metrics updates SHALL remain consistent and race-safe

#### Scenario: Fallback event tracking
- **WHEN** a call switches providers due to retryable failure
- **THEN** router SHALL increment fallback counters and record source/target provider context for diagnostics

### Requirement: Runtime Behavior Invariants for SP/MP Compatibility
Routing behavior MUST preserve no-regression invariants across single-player and tabletop multiplayer modes.

#### Scenario: Single-player mode invariant
- **WHEN** game runs in single-player-compatible configuration
- **THEN** profile routing SHALL not require multiplayer-specific state and SHALL preserve existing narration/mechanics response semantics

#### Scenario: Tabletop mode invariant
- **WHEN** game runs with multiple party members in tabletop sessions
- **THEN** profile routing SHALL remain transparent to combat/state managers and SHALL not alter Python truth-source mechanics
