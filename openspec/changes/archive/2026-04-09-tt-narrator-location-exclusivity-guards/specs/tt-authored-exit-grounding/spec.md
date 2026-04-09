## ADDED Requirements

### Requirement: Route-blocking narration SHALL be grounded in authoritative state or authored blockers
Narrator claims that an authored adjacent route is blocked SHALL require deterministic support from committed state/actions or authored blocker metadata.

#### Scenario: Unsupported blockade claim is rejected
- **WHEN** authoritative location has authored adjacent exits (for example `NC01 -> NC02/NC03`)
- **AND** narrator claims those exits are blocked without deterministic support
- **THEN** validation SHALL fail closed with correction guidance

#### Scenario: Supported blockade claim is accepted
- **WHEN** narrator route-blocking claim is supported by committed deterministic state/action or authored blocker metadata
- **THEN** validation SHALL allow the claim

### Requirement: Guard SHALL not block valid travel progression
Route-block grounding checks SHALL preserve valid transition behavior.

#### Scenario: Valid adjacent progression remains available
- **WHEN** no supported blockade is present
- **THEN** narration SHALL preserve availability of authored adjacent travel options
