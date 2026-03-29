## ADDED Requirements

### Requirement: Companion memory extraction recognizes generalized relationship-significant events
The live companion memory extraction path MUST recognize generalized relationship-significant journal events even when they are written in narrative prose rather than narrow exact phrases. The extraction path MUST support companion-relevant event families including coercion or leverage, exposed secrets or hidden allegiance, recruitment or agreement to accompany, watch or escort duties, and narrative combat teamwork.

#### Scenario: Recruitment through leverage produces meaningful interaction output
- **WHEN** a journal entry narrates that a companion NPC's hidden wrongdoing or secret correspondence is exposed and the party pressures that NPC into accompanying them
- **THEN** the extraction path MUST record at least one meaningful interaction for that NPC instead of treating the entry as a mention-only event

#### Scenario: Narrative combat contribution is recognized without mechanical phrasing
- **WHEN** a journal entry describes a companion NPC fighting alongside the party using narrative prose rather than explicit combat log wording
- **THEN** the extraction path MUST recognize that entry as a meaningful companion interaction when the NPC is clearly attributed as participating in the battle

#### Scenario: Guard and escort behavior is recognized as continuity-relevant
- **WHEN** a journal entry describes a companion NPC standing watch, guarding the rear, escorting the party, or following them into danger
- **THEN** the extraction path MUST treat that event family as eligible relationship-significant input rather than ignoring it by default

### Requirement: Companion interaction accounting distinguishes story presence from meaningful interaction
The companion memory system MUST distinguish NPC story presence from parser-confirmed meaningful interaction. A simple NPC mention MUST NOT be interpreted as evidence that the parser successfully derived relationship-significant memory content.

#### Scenario: Mention-only entry does not inflate meaningful interaction count
- **WHEN** a journal entry mentions a companion NPC but does not contain any recognized relationship-significant event for that NPC
- **THEN** the system MUST preserve the NPC's story-presence accounting without incrementing meaningful interaction accounting for that entry

#### Scenario: Meaningful entry increments meaningful interaction accounting
- **WHEN** a journal entry contains one or more recognized relationship-significant events for a companion NPC
- **THEN** the system MUST increment meaningful interaction accounting for that NPC even if the resulting memory does not later crystallize into a durable memory object
