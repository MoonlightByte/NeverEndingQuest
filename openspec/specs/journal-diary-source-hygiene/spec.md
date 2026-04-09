# journal-diary-source-hygiene Specification

## Purpose
TBD - created by archiving change journal-diary-immersive-recap-refactor. Update Purpose after archive.
## Requirements
### Requirement: Diary checkpoints prefer journal-authored source beats
The diary checkpoint pipeline SHALL use journal-authored beats as its primary source of narrative material. Conversation history and combat history SHALL NOT be the default primary diary source when journal beats exist inside the checkpoint window.

#### Scenario: Journal beats override noisier runtime sources
- **WHEN** one or more journal beats exist between the checkpoint start and end source bounds
- **THEN** the diary generator builds the checkpoint from cleaned journal material first instead of mixing in raw conversation or combat entries by default

#### Scenario: Sanitized fallback is used only when journal beats are absent
- **WHEN** no journal beats exist for the checkpoint window but recent progression exists elsewhere
- **THEN** the diary generator may fall back to sanitized conversation or combat excerpts rather than emitting an empty entry immediately

### Requirement: Diary source sanitization removes out-of-world artifacts
The diary pipeline SHALL sanitize its source window so diary summaries never surface raw JSON payloads, action parameter blobs, system notices, prompt scaffolding, or similar out-of-world runtime artifacts.

#### Scenario: JSON-like source rows are excluded from diary prose
- **WHEN** the underlying source window contains `updateEncounter`, `updateCharacterInfo`, combat summaries, or JSON-shaped assistant content
- **THEN** the resulting diary summary does not reproduce those artifacts in visible diary prose

#### Scenario: Mechanical system notices do not appear as diary beats
- **WHEN** the source window contains rest notices, validation failures, or other `[SYSTEM]` runtime messages
- **THEN** those notices are filtered or translated away rather than displayed verbatim in the diary

### Requirement: Diary checkpoints collapse duplicate narrative beats
The diary pipeline SHALL detect and collapse repeated source beats that describe materially the same scene, especially journal variants that share the same time/location window with only stylistic expansion.

#### Scenario: Long and short journal variants do not inflate one checkpoint
- **WHEN** the source window contains multiple journal entries describing the same scene at the same checkpoint moment
- **THEN** the diary generator uses one consolidated beat instead of repeating both variants in the diary output

#### Scenario: Duplicate scene variants improve story source quality
- **WHEN** confirmed diary entries are later reused by the Story PDF pipeline
- **THEN** repeated journal variants do not cause duplicated chapter beats in the downstream source set

### Requirement: Diary generation remains fail-open with deterministic fallback
The diary pipeline SHALL preserve current fail-open lifecycle behavior. If diary LLM generation degrades, the system SHALL return a deterministic short recap built only from sanitized checkpoint beats.

#### Scenario: Start Game remains successful during diary generation failure
- **WHEN** the draft diary generator fails during Start Game
- **THEN** Start Game still succeeds and the diary path returns either a deterministic sanitized fallback or a safe degraded result

#### Scenario: Save and Exit remain successful during diary generation failure
- **WHEN** confirmed checkpoint generation degrades during Save or explicit Exit
- **THEN** Save or Exit still completes without diary failure blocking the primary lifecycle action

