## MODIFIED Requirements

### Requirement: Deterministic validator is authoritative for arrival sync

Deterministic validation SHALL remain authoritative for runtime-reconciled narrator state domains, not only arrival-sync wording.

#### Scenario: Deterministic travel pass with conflicting LLM complaint
- **GIVEN** deterministic runtime marks `travel_state_sync` authoritative and passed
- **WHEN** LLM validation complains only about travel action plumbing already reconciled by runtime
- **THEN** runtime SHALL preserve the deterministic travel result
- **AND** SHALL NOT fail solely on that travel-sync complaint

#### Scenario: Deterministic NPC pass with conflicting LLM complaint
- **GIVEN** deterministic runtime marks `npc_state_sync` authoritative and passed
- **WHEN** LLM validation complains only about NPC movement or arrival sync already reconciled by runtime
- **THEN** runtime SHALL preserve the deterministic NPC result

#### Scenario: Unrelated LLM failure still blocks
- **GIVEN** deterministic travel/NPC domains passed
- **AND** LLM validation reports an unrelated invalid action or semantic failure
- **WHEN** runtime evaluates the validator result
- **THEN** runtime SHALL still block the response on the unreconciled failure
