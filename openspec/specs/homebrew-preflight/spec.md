# homebrew-preflight Specification

## Purpose
TBD - created by archiving change dev-homebrew-tools. Update Purpose after archive.
## Requirements
### Requirement: Title Hygiene Detection
The tool SHALL detect and flag title prefixes that need cleaning.

#### Scenario: Detect CLONE prefix
Given a source file with title "CLONE - ADVENTURE: The Secrets of Mangrove Keep"
When preflight runs
Then it SHALL flag "title_hygiene" issue with severity "fixable"
And recommend "The Secrets of Mangrove Keep"

#### Scenario: Detect multiple prefix variants
Given titles with prefixes "CLONE:", "CLONE -", "CLONE - ADVENTURE:"
When preflight runs
Then all SHALL be detected and flagged for stripping

### Requirement: Metadata Completeness Check
The tool SHALL verify required metadata fields are present.

#### Scenario: Missing required metadata
Given a source without description field
When preflight runs
Then it SHALL report "metadata_missing" with severity "fixable"
And set "ready" to false

#### Scenario: Complete metadata
Given a source with title, author, description
When preflight runs
Then it SHALL set "ready" to true (if other checks pass)

### Requirement: Structure Classification
The tool SHALL classify source structure type.

#### Scenario: Room-based structure detected
Given a source with "## Room 1:" headers
When preflight runs
Then "structure_class" SHALL be "room_based"
And "can_auto_transform" SHALL be true

#### Scenario: ACT/LOCATION structure detected
Given a source with "## ACT" and "### LOCATIONS" headers
When preflight runs
Then "structure_class" SHALL be "act_location"
And "can_auto_transform" SHALL depend on parseability

### Requirement: JSON Output Mode
The tool SHALL support structured JSON output.

#### Scenario: JSON flag provided
Given --json flag is passed
When preflight runs
Then output SHALL be valid JSON with documented schema

