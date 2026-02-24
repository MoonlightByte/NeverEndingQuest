## Purpose

Define deterministic allied-only NPC portrait auto-generation behavior on media misses, including queueing, dedupe, reuse-first materialization, and safe fallback semantics.

## Requirements

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

### Requirement: Auto-generation MUST reuse existing portrait sources before provider calls

When allied NPC media is missing, the system MUST attempt to reuse existing portrait assets before invoking image generation providers.

#### Scenario: Existing portrait available for allied NPC
- **WHEN** `/media/npcs/<name>_thumb.jpg` misses and `web/static/portraits/<name>.png` exists
- **THEN** system materializes required NPC media variants from existing portrait
- **AND** no provider image generation call is made

### Requirement: Reuse/generated outputs MUST register into NPC media serving paths

Recovered assets MUST be written to paths used by `/media/npcs/...` resolution.

#### Scenario: Materialized NPC media serves on next request
- **WHEN** allied NPC media miss is processed by worker
- **THEN** subsequent request resolves from `modules/<module>/media/npcs` or `web/static/media/npcs`

### Requirement: Queue dedupe MUST be identity-based across image variants

Dedupe logic MUST treat `<name>.jpg`, `<name>.png`, and `<name>_thumb.jpg` as one NPC identity key.

#### Scenario: Variant misses for same NPC within cooldown
- **WHEN** repeated misses occur for `liri.jpg` and `liri_thumb.jpg`
- **THEN** only one task is active/enqueued for canonical key `npcs/liri`

### Requirement: Miss-triggered auto-generation SHALL apply to NPC image keys only

Auto-generation enqueue SHALL ignore non-image NPC media keys.

#### Scenario: NPC video miss
- **WHEN** `/media/npcs/<name>_video.mp4` misses
- **THEN** no portrait auto-generation task is enqueued

### Requirement: Allied NPC auto-generation SHALL hydrate portrait context from canonical character state when available

Before provider generation, allied NPC auto-generation SHALL attempt to hydrate structured NPC context from canonical character records.

#### Scenario: Allied NPC has canonical character record
- **WHEN** an allied NPC miss is processed and character data is available
- **THEN** generation context includes resolved identity fields (for example `name`, `race`, `class`) and available profile context
- **AND** generation avoids generic `Unknown`/`NPC` defaults for those fields

#### Scenario: Allied NPC missing canonical record
- **WHEN** an allied NPC miss is processed and character data is unavailable
- **THEN** generation may fallback to party role/name hints
- **AND** miss handling remains asynchronous and non-blocking
