# usage-cost-conversion-policy Specification

## Purpose
TBD - created by archiving change debug-usage-session-week-nzd-rollup. Update Purpose after archive.
## Requirements
### Requirement: Cost rollups SHALL prefer provider-reported per-call cost
Usage cost aggregation SHALL use per-call cost from API usage metadata when present.

#### Scenario: Provider-reported cost available
- **WHEN** a usage event includes a cost field in usage metadata
- **THEN** session and rolling-week USD costs SHALL include that provider-reported cost value
- **AND** telemetry metadata SHALL set `cost_source` to `provider_reported`

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

### Requirement: USD->NZD conversion SHALL be explicit and configurable
The system SHALL convert USD rollups to NZD using a configured conversion constant and expose that rate in telemetry payload metadata.

#### Scenario: Conversion applied
- **WHEN** USD rollups are computed
- **THEN** NZD rollups SHALL equal USD rollups multiplied by configured conversion rate

#### Scenario: Invalid conversion config
- **WHEN** configured conversion rate is missing or invalid
- **THEN** system SHALL fallback to safe default conversion behavior without interrupting token update emission

### Requirement: Cost metadata SHALL communicate confidence
Usage telemetry SHALL include explicit metadata indicating cost confidence so UI and operators can interpret totals correctly.

#### Scenario: Fallback estimated cost
- **WHEN** cost uses blended fallback logic instead of provider-reported value
- **THEN** telemetry metadata SHALL indicate estimated cost and non-provider source

#### Scenario: Cost unavailable
- **WHEN** neither provider-reported cost nor fallback estimate can be applied
- **THEN** telemetry metadata SHALL indicate unavailable cost while token rollups continue

