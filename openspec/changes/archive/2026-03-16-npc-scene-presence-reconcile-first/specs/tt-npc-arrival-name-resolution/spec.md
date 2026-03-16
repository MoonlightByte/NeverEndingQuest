## MODIFIED Requirements

### Requirement: Ambiguous NPC Alias Mentions SHALL Fail Open

When scene-presence reconciliation is introduced, a short NPC alias that maps to multiple possible identities SHALL remain ambiguity-safe and SHALL NOT be auto-committed to one canonical NPC.

#### Scenario: Ambiguous alias blocks auto-commit under scene presence
- **WHEN** narration explicitly presents an NPC in-scene using an alias that resolves to multiple canonical candidates
- **AND** deterministic scene-presence reconciliation evaluates that mention
- **THEN** runtime SHALL preserve ambiguity safety
- **AND** SHALL NOT silently choose one canonical identity for reconciliation

## ADDED Requirements

### Requirement: Unambiguous canonical identity SHALL gate safe reconciliation

Scene-presence reconciliation SHALL proceed only when identity resolution produces one safe canonical NPC.

#### Scenario: Unambiguous hermit identity enables reconcile-first path
- **WHEN** narration explicitly presents `Maelo` in-scene
- **AND** canonical identity resolution uniquely maps that mention to `Spirit-Touched Hermit Maelo`
- **THEN** deterministic runtime MAY use that canonical identity for scene-presence reconciliation
