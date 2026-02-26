## ADDED Requirements

### Requirement: Off-Location NPC Arrival Narration SHALL Be Paired With State Action
When assistant narration introduces a known NPC who is not currently present at the active location and not already in `partyNPCs`, the same response SHALL include a state action that makes that NPC present.

#### Scenario: Background NPC arrives to current location
- **WHEN** narration states or clearly implies a known off-location NPC has arrived
- **AND** that NPC is not in current location NPC list and not in party NPC list
- **THEN** response SHALL include `moveBackgroundNPC` with matching NPC identity
- **AND** validator SHALL accept the response if other checks pass

#### Scenario: NPC joins traveling party
- **WHEN** narration states or clearly implies a known NPC joins the party
- **THEN** response SHALL include `updatePartyNPCs` with `operation: "add"` and matching NPC identity
- **AND** validator SHALL accept the response if other checks pass

### Requirement: Missing Arrival Action SHALL Fail Validation
Responses that introduce non-present known NPCs without required pairing action SHALL fail validation.

#### Scenario: Narration/state mismatch
- **WHEN** narration introduces one or more non-present known NPCs
- **AND** actions omit required `moveBackgroundNPC` or `updatePartyNPCs` add pairing
- **THEN** validation SHALL return a deterministic failure reason
- **AND** response SHALL enter retry flow

### Requirement: Already-Present NPC Mentions SHALL Not Require New Actions
References to NPCs already present in deterministic state SHALL not trigger mandatory arrival actions.

#### Scenario: Mention of already-present NPC
- **WHEN** narration references an NPC already in current location list or party NPC list
- **THEN** validator SHALL NOT require additional arrival action
- **AND** response SHALL remain eligible for acceptance
