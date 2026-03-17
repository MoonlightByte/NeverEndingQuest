## Purpose

Ensure explicit narrated scene gifts (item transfers from scene actors to party members) are deterministically reconciled into canonical inventory state when assignment is unambiguous, without requiring manual DM intervention or relying on fragile prose-only tracking.

## Requirements

### Requirement: Runtime SHALL reconcile explicit narrated scene gifts into canonical inventory updates

When narration clearly states that a known scene actor gives a specific item to a named party recipient, runtime SHALL reconcile that gift into canonical inventory state even if the explicit inventory action was omitted from the candidate response.

#### Scenario: Scene actor gifts named items to named party members
- **GIVEN** the current scene includes a known scene actor
- **AND** narration explicitly states that party members receive specific items
- **AND** the candidate response omits matching inventory actions
- **WHEN** deterministic scene-item reconciliation runs
- **THEN** runtime SHALL synthesize canonical inventory updates for the named recipients
- **AND** those updates SHALL occur before later inventory-dependent turns rely on the items

### Requirement: Explicit inventory actions SHALL remain authoritative

Scene-item reconciliation SHALL be additive and SHALL preserve explicit canonical inventory actions when they are already present.

#### Scenario: Explicit grant actions already present
- **WHEN** the candidate response already includes matching `updateCharacterInfo` inventory updates for the gifted item
- **THEN** runtime SHALL preserve the explicit action path
- **AND** SHALL NOT duplicate the same inventory grant through reconcile-first inference

### Requirement: Ambiguous gift assignment SHALL remain fail-safe

Runtime SHALL NOT invent recipients, quantities, or item identity when narrated reward language is not safely resolvable.

#### Scenario: Reward mentioned without clear recipient mapping
- **WHEN** narration states that an NPC offers supplies or rewards to the party
- **AND** item-to-recipient assignment is not explicit
- **THEN** runtime SHALL NOT auto-commit inventory updates
- **AND** the turn SHALL remain narration-only or require explicit action follow-through
