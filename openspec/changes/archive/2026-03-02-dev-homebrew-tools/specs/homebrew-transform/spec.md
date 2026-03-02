# homebrew_transform_to_deterministic.py

## ADDED Requirements

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
## ACT I: The Beginning
### LOCATIONS
- **The Dock** - A weathered wooden dock.
- **The Tavern** - A cozy tavern north of the dock.
```
When transform runs
Then output SHALL be:
```markdown
## Room 1: The Dock
A weathered wooden dock.
**Exits:**
- North: Room 2
## Room 2: The Tavern
A cozy tavern north of the dock.
**Exits:**
- South: Room 1
```

### Requirement: Exit Inference
The tool SHALL infer exits from location descriptions.

#### Scenario: Parse directional keywords
Given description mentions "north of the dock"
When transform runs
Then exit SHALL be created linking to referenced location

#### Scenario: Bidirectional exits
Given Room A has exit north to Room B
When transform runs
Then Room B SHALL have exit south to Room A

## ADDED Interface

### CLI
```bash
python scripts/homebrew_transform_to_deterministic.py \
  --source <input_path> \
  --output <output_path>
```

## ADDED Exit Codes
- 0: Success
- 1: Source not found
- 2: Cannot auto-transform
- 3: Output not writable
