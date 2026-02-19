# debug-tab-usage-cost-rollup Specification

## Purpose
TBD - created by archiving change debug-usage-session-week-nzd-rollup. Update Purpose after archive.
## Requirements
### Requirement: Debug tab SHALL show session/week token and cost rollups above existing token stats
The Debug tab SHALL render a compact rollup row above existing TPM/RPM/Total values, showing session and rolling-week tokens plus USD and NZD estimates.

#### Scenario: Header order
- **WHEN** the Debug tab is rendered
- **THEN** the session/week rollup row SHALL appear above the existing TPM/RPM/Total stats row

#### Scenario: Existing token row preserved
- **WHEN** token updates are received
- **THEN** existing TPM/RPM/Total fields SHALL continue to update as before

### Requirement: Debug tab SHALL consume additive token_update payload fields
The client SHALL bind new rollup fields from `token_update` payloads while remaining compatible with payloads that contain only legacy fields.

#### Scenario: Full payload update
- **WHEN** `token_update` includes session and week cost/token fields
- **THEN** the Debug tab SHALL display those values with localized numeric formatting

#### Scenario: Partial payload compatibility
- **WHEN** `token_update` omits one or more new rollup fields
- **THEN** missing values SHALL render as zero/default placeholders and no UI error shall occur

### Requirement: UI updates SHALL remain non-blocking
Rollup rendering SHALL not block debug message rendering or game output flow.

#### Scenario: High-frequency updates
- **WHEN** debug output and token updates arrive in quick succession
- **THEN** both streams SHALL continue rendering without freezing the Debug panel

