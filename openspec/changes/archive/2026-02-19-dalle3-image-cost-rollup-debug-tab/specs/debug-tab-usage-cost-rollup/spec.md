## MODIFIED Requirements

### Requirement: Debug tab SHALL show session/week token and cost rollups above existing token stats
The Debug tab SHALL render a compact rollup row above existing TPM/RPM/Total values, showing session and rolling-week tokens plus USD and NZD estimates.

#### Scenario: Image generation updates cost rollups
- **WHEN** a successful DALL-E 3 image generation event is tracked
- **THEN** session and rolling-week USD/NZD rollup values SHALL increase on subsequent `token_update` payloads
- **AND** existing TPM/RPM/Total token values SHALL remain behaviorally unchanged for that image-cost event

