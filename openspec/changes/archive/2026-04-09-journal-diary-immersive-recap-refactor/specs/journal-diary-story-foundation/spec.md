## ADDED Requirements

### Requirement: Confirmed diary entries provide clean story-chapter seeds
Confirmed diary entries SHALL store concise, cleaned recap text plus stable checkpoint metadata so they can act as reliable source beats for confirmed-only "Story so far..." generation.

#### Scenario: Confirmed diary rows remain suitable for story compilation
- **WHEN** the Story PDF compiler loads confirmed diary entries
- **THEN** each entry contributes clean recap text and structured checkpoint metadata without requiring raw chat or JSON parsing to recover the narrative beat

#### Scenario: Story ordering follows checkpoint world-line metadata
- **WHEN** multiple confirmed diary entries span different dates, times, and locations
- **THEN** the story compiler can order and label them from stored checkpoint metadata rather than inferred prose alone

### Requirement: Legacy diary rows can be remediated deterministically
The system SHALL provide a deterministic remediation path for previously stored noisy diary rows so existing campaigns can be upgraded to the new diary quality contract without hand-editing the database.

#### Scenario: Existing noisy confirmed entries can be rebuilt
- **WHEN** a campaign already contains oversized or artifact-leaking confirmed diary rows from the old pipeline
- **THEN** a remediation path can rebuild those rows from their checkpoint source windows and updated checkpoint metadata rules

#### Scenario: Remediation does not break normal gameplay lifecycle paths
- **WHEN** remediation tooling is unavailable or fails
- **THEN** normal Journal reads, Start Game, Save, and Exit flows still behave safely without depending on remediation success

### Requirement: Story-source quality improvements do not weaken canon boundaries
This diary refinement SHALL improve the quality of confirmed diary sources for the Story PDF path without changing the confirmed-only canon boundary.

#### Scenario: Draft diary text remains excluded from story compilation
- **WHEN** the story compiler runs after diary refinement is implemented
- **THEN** only confirmed diary entries are used as story source material and draft diary rows remain excluded

#### Scenario: Cleaner diary text improves story output without changing truth source
- **WHEN** confirmed diary entries become shorter, cleaner, and location-aware
- **THEN** the Story PDF pipeline gains better input quality while authoritative current JSON state still remains the final source of mechanical truth
