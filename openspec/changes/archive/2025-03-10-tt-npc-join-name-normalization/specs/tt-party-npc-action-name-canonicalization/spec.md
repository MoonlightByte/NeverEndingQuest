## ADDED Requirements

### Requirement: Party-NPC action payload names SHALL be canonicalized before LLM validation

Runtime pre-validation SHALL canonicalize unambiguous party-NPC action names for onboarding and movement actions before sending payloads to the LLM validator.

#### Scenario: Short name in updatePartyNPCs add is normalized
- **WHEN** assistant response contains `updatePartyNPCs` add with short NPC name `Kira`
- **AND** canonical identity resolves unambiguously to `Scout Kira`
- **THEN** runtime SHALL rewrite action payload name to `Scout Kira` before LLM validation
- **AND** validation SHALL continue without full-name rejection for that action

#### Scenario: Canonical name is unchanged
- **WHEN** assistant response already uses canonical NPC name `Scout Kira`
- **THEN** runtime SHALL preserve the payload name unchanged

### Requirement: Canonicalization SHALL fail closed on ambiguity

Canonicalization SHALL not auto-select an NPC when multiple canonical candidates match the same short name.

#### Scenario: Ambiguous short name is rejected
- **WHEN** action payload name maps to multiple NPC candidates
- **THEN** runtime SHALL reject validation with explicit ambiguity reason
- **AND** SHALL NOT mutate the action to any candidate automatically

### Requirement: Canonicalization SHALL support action payload shape variants

Canonicalization SHALL handle supported payload forms used by `updatePartyNPCs` and `moveBackgroundNPC`.

#### Scenario: updatePartyNPCs npc object form
- **WHEN** `updatePartyNPCs` uses `parameters.npc.name`
- **THEN** canonicalization SHALL evaluate and normalize `parameters.npc.name`

#### Scenario: updatePartyNPCs string/list add form
- **WHEN** `updatePartyNPCs` uses list or string add payload variants
- **THEN** canonicalization SHALL evaluate and normalize each provided NPC name value

#### Scenario: moveBackgroundNPC name field
- **WHEN** `moveBackgroundNPC` uses `parameters.npcName`
- **THEN** canonicalization SHALL evaluate and normalize `parameters.npcName`

### Requirement: Backward compatibility SHALL be preserved

Canonicalization changes SHALL remain additive and preserve existing single-player behavior and deterministic validation contracts.

#### Scenario: Single-player path remains valid
- **WHEN** single-player validation runs with canonical action names
- **THEN** behavior SHALL match current baseline outcomes
- **AND** no new required action fields SHALL be introduced
