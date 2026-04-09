# campaign-storyteller-chronicle-generation Specification

## Purpose
TBD - created by archiving change journal-diary-storyteller-mvp. Update Purpose after archive.
## Requirements
### Requirement: Story compiler SHALL generate 3rd-person retrospective fantasy prose
The long-form campaign storyteller SHALL compile confirmed campaign history into 3rd-person, past-tense fantasy prose that reads as a retrospective chronicle rather than a raw transcript.

#### Scenario: Generated story follows literary chronicle contract
- **WHEN** the story compiler produces long-form campaign text
- **THEN** the output SHALL be prose-only, 3rd person, past tense, and free of transcript formatting or raw JSON/schema language

### Requirement: Meaningful PC chat input SHALL be preserved as narrative material
The storyteller compiler SHALL incorporate meaningful user or PC chat inputs as in-world dialogue, action, inquiry, or intent instead of omitting them from the campaign retelling.

#### Scenario: Direct PC speech is preserved in story form
- **WHEN** confirmed diary/story source material includes meaningful direct PC speech from chat history
- **THEN** the compiler SHALL preserve that contribution as dialogue or close narrative paraphrase within the prose

#### Scenario: Declared PC actions are reflected in the retelling
- **WHEN** confirmed diary/story source material includes meaningful PC action declarations or decisions from chat history
- **THEN** the compiler SHALL represent those actions and decisions as in-world events in the compiled narrative

### Requirement: Authoritative state SHALL override stale narrative contradictions
When confirmed diary content or supporting history conflicts with newer authoritative campaign state, the storyteller compiler SHALL preserve the event record while aligning the final settled state of the narrative with the latest authoritative JSON/context.

#### Scenario: Final state aligns with authoritative campaign data
- **WHEN** older diary/history text contradicts newer authoritative campaign state for the current settled outcome
- **THEN** the compiled story SHALL resolve the final state in favor of the authoritative campaign data rather than ending in contradiction

#### Scenario: Unsupported events are not invented during compilation
- **WHEN** source material is ambiguous or incomplete
- **THEN** the compiler SHALL prefer omission or conservative phrasing and SHALL NOT invent unsupported scenes, revelations, or outcomes

