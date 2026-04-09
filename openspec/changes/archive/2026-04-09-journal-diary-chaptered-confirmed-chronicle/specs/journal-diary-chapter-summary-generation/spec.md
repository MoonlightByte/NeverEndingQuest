## ADDED Requirements

### Requirement: Confirmed Diary SHALL summarize chapter packets after Python sanitization
The system SHALL generate one confirmed Diary summary per journal chapter block from a Python-sanitized chapter packet. Sanitization MUST occur before any optional LLM summary generation.

#### Scenario: Chapter summary uses grouped chapter packet
- **WHEN** a confirmed Diary chapter is summarized
- **THEN** the summary SHALL be generated from the grouped journal entries in that chapter block rather than from a single winner-take-all source row

#### Scenario: Sanitization precedes optional LLM generation
- **WHEN** LLM summary generation is enabled for confirmed Diary chapters
- **THEN** the system SHALL sanitize chapter source content before submitting the chapter packet to the LLM

### Requirement: Confirmed Diary SHALL support deterministic fallback summary generation
The system SHALL provide a deterministic fallback summary path for confirmed Diary chapter generation whenever LLM summarization is disabled, unavailable, or rejected by output sanitization.

#### Scenario: LLM disabled uses deterministic chapter summary
- **WHEN** confirmed Diary chapter generation runs while Diary LLM generation is disabled
- **THEN** the system SHALL store a deterministic chapter summary instead of failing the rebuild

#### Scenario: Invalid LLM output degrades safely
- **WHEN** an LLM-generated confirmed Diary summary is empty, unsafe, or leaks structured artifacts
- **THEN** the system SHALL discard that output and store a deterministic fallback chapter summary

### Requirement: Confirmed Diary summaries SHALL be player-facing and artifact-free
Confirmed Diary chapter summaries SHALL be concise, descriptive, and useful to players. Stored summaries MUST NOT include JSON payloads, system scaffolding, prompt text, or fixed heading/title fragments that duplicate metadata already shown by the Journal modal.

#### Scenario: Summary strips structured artifacts
- **WHEN** chapter source material contains JSON-like text, system notices, or prompt scaffolding
- **THEN** the stored confirmed Diary summary SHALL exclude those artifacts

#### Scenario: Summary strips heading-like preambles
- **WHEN** a journal entry variant includes title-like or heading-like preamble text before the actual prose
- **THEN** the confirmed Diary summary SHALL preserve the narrative prose and remove the heading-like fragment

### Requirement: Confirmed Diary SHALL preserve chapter source traceability for later story work
The system SHALL retain chapter source bounds and source-count metadata for each rebuilt confirmed Diary chapter row so later story-compilation work can trace a chapter back to its journal entry span.

#### Scenario: Rebuilt chapter row records source range
- **WHEN** a confirmed Diary chapter row is rebuilt from grouped journal entries
- **THEN** the row SHALL retain enough source metadata to identify the chapter's contributing journal entry range and source count
