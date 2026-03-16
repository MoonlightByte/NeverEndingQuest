# tt-npc-scene-presence-reconcile-first Specification

## Purpose
TBD - created by archiving change npc-scene-presence-reconcile-first. Update Purpose after archive.
## Requirements
### Requirement: Runtime SHALL reconcile clear scene-compatible NPC presence

When narration clearly presents one canonical NPC as present in the current scene and the identity is safely resolvable, runtime SHALL reconcile that scene presence instead of failing solely because the explicit movement action was omitted.

#### Scenario: Maelo-style refuge reveal without explicit movement action
- **GIVEN** current turn context makes contact with the hermit's refuge or immediate scene plausible
- **AND** narration clearly presents `Spirit-Touched Hermit Maelo` as present in the scene
- **AND** no explicit `moveBackgroundNPC` action is emitted
- **WHEN** deterministic NPC scene-presence reconciliation runs
- **THEN** runtime SHALL accept or normalize that scene presence
- **AND** the turn SHALL NOT fail solely for missing explicit arrival plumbing

### Requirement: Runtime SHALL preserve foreshadowing and informational mentions as action-free

Narration that references known NPCs without establishing in-scene presence SHALL remain legal without movement or party-mutation actions.

#### Scenario: Off-location informational mention remains legal
- **WHEN** narration refers to a known NPC as stationed elsewhere, rumored nearby, or remembered from another scene
- **AND** narration does not clearly establish current in-scene presence
- **THEN** runtime SHALL treat that mention as legal informational context
- **AND** SHALL NOT require movement action solely for that mention

### Requirement: Scene presence SHALL remain distinct from party membership

Reconcile-first scene presence SHALL NOT implicitly convert an NPC into a durable party member.

#### Scenario: Explicit join still requires party update
- **WHEN** narration explicitly states that a known NPC joins the party or starts traveling with them
- **AND** no explicit `updatePartyNPCs` add operation exists
- **THEN** runtime SHALL keep that turn blocking or clarification-required for party-membership dimension
- **AND** SHALL NOT silently upgrade scene presence into party membership

### Requirement: Ambiguous NPC identity SHALL remain fail-safe

Scene-presence reconciliation SHALL NOT auto-commit a guessed NPC identity when more than one canonical match is plausible.

#### Scenario: Ambiguous scout mention
- **WHEN** narration presents `Scout` as present in the scene
- **AND** multiple canonical NPC identities validly match that alias
- **THEN** runtime SHALL not auto-commit one identity arbitrarily
- **AND** SHALL preserve ambiguity safety through clarification or fail-safe handling

### Requirement: Explicit NPC movement actions SHALL remain supported

Reconcile-first scene presence SHALL be additive and SHALL preserve explicit movement/membership actions as valid inputs.

#### Scenario: Explicit moveBackgroundNPC remains authoritative
- **WHEN** narration includes a valid explicit `moveBackgroundNPC` for the same NPC
- **THEN** runtime SHALL continue to accept the explicit action path normally
- **AND** reconcile-first inference SHALL NOT override it unnecessarily

