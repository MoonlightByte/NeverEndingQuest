## MODIFIED Requirements

### Requirement: Same-module transition execution SHALL commit canonical location state before narration depends on it
For same-module movement, runtime SHALL commit canonical location state successfully before any downstream arrival or scene narration is treated as authoritative history.

#### Scenario: Successful same-module move commits tracker state
- **WHEN** a same-module `transitionLocation` request is validated successfully
- **THEN** runtime SHALL update canonical party location state to the destination before any arrival-dependent scene context is generated

#### Scenario: Failed same-module move leaves canonical location unchanged
- **WHEN** a same-module `transitionLocation` request fails validation or execution
- **THEN** runtime SHALL preserve the prior canonical location state unchanged

#### Scenario: Inferred sublocation commit applies before same-turn encounter creation
- **WHEN** runtime infers a valid same-module sublocation commit from narrow descent reconciliation
- **AND** the same turn also produces `createEncounter`
- **THEN** runtime SHALL apply the inferred canonical location commit before encounter creation consumes location truth
- **AND** encounter identity and downstream history SHALL anchor to the inferred destination rather than the stale parent room
