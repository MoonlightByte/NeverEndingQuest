## MODIFIED Requirements

### Requirement: Campaign initiation SHALL support iterative multi-PC onboarding

The startup character-creation workflow SHALL support creating one or more player characters in sequence for tabletop sessions. After each successful character creation, the workflow SHALL append each accepted character to `partyMembers` without overwriting previously created members, and SHALL keep startup marked incomplete until the facilitator explicitly finishes the onboarding loop.

#### Scenario: DM creates multiple PCs at campaign start
- **WHEN** startup character creation completes for the first player and the DM indicates another player is joining
- **THEN** the system prompts for the next player and repeats creation until the DM declines

#### Scenario: Single-player startup remains valid
- **WHEN** startup character creation completes and the DM declines additional players
- **THEN** startup finalizes with one character and behavior remains backward-compatible with existing single-player flow

#### Scenario: Loop recovery on failed secondary creation
- **WHEN** a secondary player-creation attempt fails validation
- **THEN** the system reports the failure, preserves already-created party members, and allows retry or graceful exit without corrupting `partyMembers`

#### Scenario: Add-more prompt is line-visible in web startup flow
- **WHEN** first PC creation succeeds during startup in web mode
- **THEN** the add-more question is emitted as line-visible output before input collection

#### Scenario: Blank or invalid add-more decision reprompts
- **WHEN** facilitator enters blank input (including timeout-injected blank) or non-yes/no text
- **THEN** startup shows valid options and reprompts without advancing to gameplay

#### Scenario: Startup exits additional-PC loop only on explicit no
- **WHEN** facilitator enters `n` or `no` at add-more or retry decision points
- **THEN** startup exits additional-PC loop and proceeds to party tracker finalization

#### Scenario: Interrupted startup remains resumable on next launch
- **WHEN** the first PC has been persisted but the process exits before the facilitator explicitly finishes the additional-PC loop
- **THEN** the next launch SHALL resume startup onboarding instead of treating gameplay bootstrap as complete

#### Scenario: Resumed startup preserves already-created PCs
- **WHEN** startup resumes after interruption
- **THEN** previously created PCs remain in `partyMembers` and the facilitator can continue onboarding without recreating them

## ADDED Requirements

### Requirement: Tabletop party-management entry SHALL remain accessible in one-PC recovery states

When tabletop mode is intended, the UI SHALL keep a deterministic party-management entry available even if only one player character exists and startup onboarding is incomplete.

#### Scenario: One-PC tabletop bootstrap still shows party-management entry
- **WHEN** tabletop mode is enabled and exactly one PC exists during startup recovery or early tabletop play
- **THEN** the character-tab container and `Manage Party` entry remain visible

#### Scenario: Single-player UI remains unchanged without tabletop mode
- **WHEN** tabletop mode is not enabled and startup is not marked incomplete
- **THEN** the existing single-player UI visibility rules remain unchanged

### Requirement: New player-character requests outside dedicated creation mode SHALL fail closed to creation workflow guidance

Normal gameplay chat SHALL NOT create a brand-new player character through `updatePartyNPCs`. If a facilitator asks to create another PC outside the dedicated creation flows, the system SHALL redirect them with deterministic guidance instead of emitting invalid party-NPC actions.

#### Scenario: Chat request for new PC does not emit updatePartyNPCs for a novel name
- **WHEN** the facilitator asks to create another player character during normal gameplay chat
- **THEN** the system does not emit `updatePartyNPCs` with a brand-new name that is absent from `partyMembers` and `partyNPCs`

#### Scenario: Facilitator receives deterministic creation guidance
- **WHEN** a new-PC request is made outside dedicated creation mode
- **THEN** the system responds with explicit guidance to use the supported creation flow instead of entering a validation retry loop
