# homebrew-registry-guard Specification

## Purpose
TBD - created by archiving change dev-homebrew-tools. Update Purpose after archive.
## Requirements
### Requirement: Duplicate Detection
The tool SHALL detect potential conflicts before ingest.

#### Scenario: Exact slug match
Given slug "Birble_Adventuring_Academy" exists in registry
When guard checks for duplicates
Then "safe_to_proceed" SHALL be false
And conflict type SHALL be "exact_slug"

#### Scenario: Similar title match
Given title "Birble Academy" vs existing "Birble_Adventuring_Academy"
When guard checks for duplicates
Then conflict SHALL be flagged if similarity > threshold

#### Scenario: No conflicts
Given unique slug not in registry
When guard checks for duplicates
Then "safe_to_proceed" SHALL be true
And conflicts array SHALL be empty

### Requirement: Registry Presence Verification
The tool SHALL confirm module is properly registered.

#### Scenario: Module present
Given slug exists in world_registry.modules
And module folder exists
When verify-present runs
Then "present" SHALL be true
And areas_count SHALL be reported

#### Scenario: Module absent
Given slug not in registry
When verify-present runs
Then "present" SHALL be false
And exit code SHALL be 4

### Requirement: Safe Removal
The tool SHALL safely remove modules with backup.

#### Scenario: Safe removal with backup
Given module exists in registry
When remove runs
Then:
1. Registry SHALL be backed up
2. Module SHALL be removed from world_registry.modules
3. Associated areas SHALL be removed
4. Folder removal SHALL be optional
5. "removed" SHALL be true

