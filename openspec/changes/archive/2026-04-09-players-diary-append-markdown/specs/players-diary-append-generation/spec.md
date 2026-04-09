## ADDED Requirements

### Requirement: Confirmed players diary SHALL append from unprocessed journal delta
The system SHALL maintain the confirmed players diary by appending new diary content derived from unprocessed `journal.json.entries` rather than rewriting the full diary during normal updates.

#### Scenario: No new journal entries means no diary append
- **WHEN** the players diary update runs and there are no `journal.json` entries after the stored bookmark
- **THEN** the confirmed diary artifact SHALL remain unchanged

#### Scenario: New journal entries append diary content only once
- **WHEN** the players diary update runs and there are new journal entries after the stored bookmark
- **THEN** the system SHALL append new diary markdown for only the unprocessed journal delta and advance the bookmark on success

### Requirement: Confirmed players diary SHALL use bounded context for append generation
The system SHALL use bounded context for append generation by reading only the new journal delta and a limited recent tail of the existing diary for style continuity.

#### Scenario: Append generation avoids full diary rewrite context
- **WHEN** the players diary append flow runs
- **THEN** it SHALL read a bounded tail of the existing diary and SHALL NOT require the entire existing diary as normal append prompt context

#### Scenario: Append generation avoids full journal rewrite context
- **WHEN** the players diary append flow runs
- **THEN** it SHALL use only the unprocessed journal entries since the bookmark rather than the full journal chronology

### Requirement: Confirmed players diary append output SHALL match the intended player-facing chronicle style
The appended diary content SHALL be anonymous, concise, pithy, fun, fantasy-immersive, and faithful to the source events in `journal.json`. The UX target is the style and usefulness demonstrated by the local example artifact used for review.

#### Scenario: Append output is player-facing markdown only
- **WHEN** the LLM returns append content for the players diary
- **THEN** the stored append output SHALL contain only markdown chronicle content suitable for GUI rendering and SHALL NOT include JSON, debug text, or system scaffolding

#### Scenario: Append output preserves prior diary content
- **WHEN** the append flow succeeds
- **THEN** the system SHALL append new markdown without rewriting or duplicating the prior confirmed diary body

### Requirement: Append mode SHALL fail safely
If append generation fails, the confirmed diary artifact MUST remain unchanged and the bookmark MUST NOT advance.

#### Scenario: LLM failure does not corrupt diary state
- **WHEN** append generation fails or returns unusable content
- **THEN** the confirmed diary markdown file SHALL remain unchanged and the bookmark SHALL retain its previous index
