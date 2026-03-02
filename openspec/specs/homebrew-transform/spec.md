# homebrew-transform Specification

## Purpose
TBD - created by archiving change dev-homebrew-tools. Update Purpose after archive.
## Requirements
### Requirement: Title Normalization
The tool SHALL strip known prefixes from titles.

#### Scenario: Strip CLONE prefix
Given title "CLONE - ADVENTURE: The Secrets of Mangrove Keep"
When transform runs
Then output title SHALL be "The Secrets of Mangrove Keep"

#### Scenario: Handle multiple prefix patterns
Given prefixes "CLONE:", "CLONE -", "CLONE - ADVENTURE:"
When transform runs
Then all SHALL be stripped leaving clean title

### Requirement: Metadata Block Injection
The tool SHALL ensure metadata fence exists with required fields.

#### Scenario: Missing metadata block
Given source without metadata fence
When transform runs
Then output SHALL include:
```metadata
title: <normalized_title>
author: <placeholder>
description: <placeholder>
party_size_min: 1
party_size_max: 6
```

### Requirement: ACT/LOCATION to Room Block Conversion
The tool SHALL convert ACT/LOCATION structure to room-based format.

#### Scenario: Convert location bullets
Given:
```markdown

