## ADDED Requirements

### Requirement: Story PDF export MUST be user-triggered from Diary UI
The system MUST generate campaign story PDF output only when a user explicitly triggers the Diary tab export action.

#### Scenario: User clicks export button
- **WHEN** the user clicks "Download the story so far..." in Diary
- **THEN** the backend generates or reuses PDF output and returns a downloadable file response

### Requirement: Story PDF source MUST exclude draft diary entries
The story compilation pipeline MUST include confirmed diary entries only and MUST exclude all draft entries.

#### Scenario: Draft and confirmed records coexist
- **WHEN** both draft and confirmed diary records exist in storage
- **THEN** compiled PDF content is derived from confirmed records only

### Requirement: Story PDF generation SHALL degrade safely on LLM failure
If narrative compilation fails through LLM/provider errors, the system SHALL return either a deterministic fallback story or a safe error response without mutating confirmed diary state.

#### Scenario: LLM compilation failure
- **WHEN** the LLM call fails during PDF generation
- **THEN** the system returns fallback output or explicit API error and leaves confirmed diary data unchanged

### Requirement: PDF cache reuse SHALL be keyed by confirmed timeline fingerprint
The system SHALL reuse existing generated PDF output only when the confirmed diary fingerprint matches current confirmed state.

#### Scenario: Confirmed timeline unchanged
- **WHEN** user requests PDF and confirmed diary fingerprint matches cached fingerprint
- **THEN** existing cached PDF is returned without full regeneration

#### Scenario: Confirmed timeline changed
- **WHEN** confirmed diary fingerprint differs from cached fingerprint
- **THEN** system regenerates PDF and stores new cache metadata
