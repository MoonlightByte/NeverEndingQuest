## ADDED Requirements

### Requirement: Runtime SHALL reconcile explicit party-to-party item transfers into canonical inventory state

When the transcript clearly establishes that one party member gives a specific item to another party member, runtime SHALL reconcile canonical inventory ownership even if the model omits one side of the transfer.

#### Scenario: One-sided reliquary handoff recovers canonical giver and receiver state
- **GIVEN** the transcript explicitly states that `Redax` hands the `Reliquary of Saint Rydal` to `Xorn`
- **AND** the candidate response omits the giver-side inventory mutation or omits the transfer actions entirely
- **WHEN** deterministic party-item transfer reconciliation runs
- **THEN** runtime SHALL reconcile canonical ownership so `Xorn` possesses the reliquary
- **AND** runtime SHALL remove the reliquary from `Redax` when giver ownership is uniquely resolvable

### Requirement: Later receiver-side item handling MAY recover missing ownership when the transfer chain is uniquely established

If a prior explicit transfer should have placed an item with a receiver but canonical state is still missing that item, a later receiver-side handling turn SHALL be allowed to recover ownership when identity remains uniquely resolvable.

#### Scenario: Receiver later stows the reliquary after earlier transfer drift
- **GIVEN** recent transcript history explicitly entrusted the `Reliquary of Saint Rydal` to `Xorn`
- **AND** canonical inventory state still lacks that item for `Xorn`
- **AND** a later turn explicitly states that `Xorn` places the reliquary into the explorer's pack
- **WHEN** deterministic item recovery runs before narration-only acceptance
- **THEN** runtime SHALL recover canonical possession of the reliquary for `Xorn`

### Requirement: Explicit inventory actions SHALL remain authoritative

Party-item transfer reconciliation SHALL be additive and SHALL NOT duplicate or override explicit canonical inventory actions when they already exist.

#### Scenario: Explicit transfer actions already present
- **WHEN** the candidate response already includes the full canonical transfer updates for both giver and receiver
- **THEN** runtime SHALL preserve the explicit action path
- **AND** SHALL NOT synthesize duplicate recovery updates

### Requirement: Ambiguous transfer evidence SHALL remain fail-safe

Runtime SHALL NOT invent ownership changes when giver identity, receiver identity, or item identity is not uniquely resolvable.

#### Scenario: Vague offer language without unique item ownership
- **WHEN** narration says that someone offers supplies or passes over a bundle
- **AND** the transcript does not uniquely resolve the item and ownership chain
- **THEN** runtime SHALL NOT auto-commit a transfer
- **AND** the turn SHALL remain narration-only or require explicit action follow-through
