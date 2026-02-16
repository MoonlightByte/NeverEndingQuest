## ADDED Requirements

### Requirement: Missing portrait auto-generation MUST target allied NPC companions only in MVP

Automatic generation on media miss MUST run only for allied NPC companions represented in party companion state.

#### Scenario: Allied companion portrait miss
- **WHEN** an allied NPC companion portrait request misses module/static media
- **THEN** system enqueues one background generation task for that allied companion

#### Scenario: Non-allied NPC portrait miss
- **WHEN** a non-allied NPC portrait request misses media
- **THEN** no automatic generation is triggered in MVP

#### Scenario: Monster portrait miss
- **WHEN** a monster portrait request misses media
- **THEN** no automatic generation is triggered in MVP

### Requirement: Missing-media auto-generation SHALL be asynchronous and non-blocking

Media request/response path SHALL NOT block on generation.

#### Scenario: Media request during generation
- **WHEN** a media miss occurs and generation is enqueued
- **THEN** request returns fallback response path immediately without waiting for generation completion

### Requirement: Auto-generation queue MUST dedupe and cooldown repeated keys

Queueing logic MUST prevent repeated rapid enqueue for same missing asset key.

#### Scenario: Repeated allied miss for same key
- **WHEN** the same allied portrait key is requested repeatedly within cooldown window
- **THEN** only one generation task is active/enqueued for that key
