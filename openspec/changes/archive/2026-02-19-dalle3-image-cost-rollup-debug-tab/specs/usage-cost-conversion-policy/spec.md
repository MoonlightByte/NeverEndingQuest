## MODIFIED Requirements

### Requirement: Fallback estimation SHALL remain generic and lightweight
If provider-reported cost is missing, the system SHALL continue cost rollups using lightweight fallback behavior and safe defaults.

#### Scenario: Image endpoint uses explicit per-image estimate
- **WHEN** a successful DALL-E 3 image generation event has no provider-reported cost metadata
- **THEN** cost rollups SHALL use configured per-image estimate for that model/size/quality combination
- **AND** telemetry metadata SHALL indicate estimated cost source

#### Scenario: Missing image pricing configuration
- **WHEN** a successful image generation event cannot resolve a valid configured estimate
- **THEN** tracker SHALL degrade safely with unavailable/zero-cost behavior
- **AND** image generation flow SHALL remain successful and non-blocking

