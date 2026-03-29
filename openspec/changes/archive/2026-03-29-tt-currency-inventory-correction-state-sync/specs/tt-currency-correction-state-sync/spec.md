## ADDED Requirements

### Requirement: Explicit bookkeeping correction claims SHALL require executable character updates
When a candidate narrator response claims that currency, coin ownership, or inventory bookkeeping has already been corrected for a character, the same response SHALL include matching `updateCharacterInfo` action coverage for the committed state change.

#### Scenario: Coin is reclassified from inventory to currency
- **WHEN** the response says a specific coin or coin stack is not a miscellaneous inventory item and is now tracked in a character's coin pouch or currency totals
- **THEN** the response SHALL include matching `updateCharacterInfo` action coverage for the correction
- **AND** a narration-only `actions: []` response SHALL be treated as invalid

#### Scenario: Payment, refund, or gain is narrated as already applied
- **WHEN** the response says a character has paid, received, refunded, found, split, or otherwise already gained or lost currency
- **THEN** the response SHALL include matching `updateCharacterInfo` action coverage for that currency mutation
- **AND** runtime SHALL not accept the turn as a committed bookkeeping update when such action coverage is absent

### Requirement: Ruling-only clarification SHALL remain distinct from committed bookkeeping changes
The system SHALL continue to allow pure clarification or adjudication turns to remain narration-only when they explain policy or future handling without claiming that persisted character state has already changed.

#### Scenario: Pure rules clarification without state mutation
- **WHEN** the response explains that copper coins are generally tracked as currency rather than miscellaneous inventory
- **AND** the response does not claim that the current sheet has already been corrected
- **THEN** the turn MAY remain narration-only with `actions: []`

#### Scenario: Clarification becomes a committed correction
- **WHEN** the response moves from policy clarification into a claim that the character now has an updated coin total or reorganized inventory
- **THEN** the turn SHALL be treated as a state-changing bookkeeping correction
- **AND** matching `updateCharacterInfo` action coverage SHALL be required in the same response

### Requirement: Prompt and validator contract text SHALL distinguish clarification from committed correction
Prompt and validator guidance SHALL clearly distinguish between allowed ruling-only clarification and invalid narration-only bookkeeping correction so correction responses produce actionable retries instead of silent drift.

#### Scenario: Prompt examples reinforce currency semantics
- **WHEN** the system prompt documents currency bookkeeping examples
- **THEN** it SHALL describe coins as currency changes rather than generic inventory storage
- **AND** it SHALL document that committed bookkeeping corrections require `updateCharacterInfo`

#### Scenario: Validator rejects correction-only narration
- **WHEN** the validator evaluates a response that claims a bookkeeping correction already happened but has no matching state mutation actions
- **THEN** it SHALL treat that response as invalid
- **AND** the failure guidance SHALL direct the narrator to emit the missing `updateCharacterInfo` action coverage instead of continuing with narration-only text
