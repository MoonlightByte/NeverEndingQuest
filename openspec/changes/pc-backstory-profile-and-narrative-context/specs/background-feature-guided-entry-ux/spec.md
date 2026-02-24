## MODIFIED Requirements

### Requirement: Portrait profile modal SHALL collect Backstory instead of background-feature fields
The portrait Create profile modal SHALL require a `Backstory` field for narrative identity and SHALL no longer require `backgroundFeature.name` and `backgroundFeature.description` in that modal flow.

#### Scenario: Portrait profile modal guidance
- **WHEN** the user opens the portrait profile modal
- **THEN** the modal displays a required `Backstory` field with guidance-oriented placeholder text
- **AND** submitted payload persists `backstory` before portrait generation

### Requirement: Character creation surfaces SHALL continue guided background-feature entry
Character creation forms that explicitly manage background-feature data SHALL continue to show guided examples for `backgroundFeature.name` and `backgroundFeature.description`.

#### Scenario: Roll Your Own guidance preserved
- **WHEN** the user opens manual character creation inputs
- **THEN** background-feature labels/placeholders remain guidance-oriented and custom authored values are preserved
