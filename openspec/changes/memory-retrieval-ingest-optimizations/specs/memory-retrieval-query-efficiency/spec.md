## ADDED Requirements

### Requirement: Timeline retrieval SHALL use bounded candidate pre-selection
The retrieval layer SHALL bound timeline candidate evaluation before final scoring to reduce query work on large datasets while preserving deterministic ordering.

#### Scenario: Large history query uses bounded candidate set
- **WHEN** timeline retrieval runs against a dataset larger than requested output limit
- **THEN** candidate evaluation is constrained to a bounded pre-selected set
- **AND** final output remains deterministic for repeated identical queries

### Requirement: Timeline retrieval SHALL return one row per event
Entity timeline retrieval SHALL de-duplicate multi-link matches so each memory event appears at most once per query response.

#### Scenario: Multiple links for one event
- **WHEN** one event is linked to the same entity through multiple link rows
- **THEN** timeline response returns that event once

### Requirement: Retrieval paths SHALL enforce read-only open semantics
Read-only retrieval operations MUST open memory DB in read-only mode and MUST fail explicitly when the target DB path is unavailable.

#### Scenario: Missing DB in read-only retrieval
- **WHEN** retrieval is invoked with a missing DB path
- **THEN** retrieval returns a controlled failure or empty-safe response according to caller contract
- **AND** retrieval does not create a new sqlite DB file implicitly

### Requirement: All retrieval entry points SHALL enforce read-only semantics
All retrieval APIs (`get_entity_timeline`, `get_context_memories`, `get_retirement_return_memories`) MUST open memory DB in read-only mode and MUST not implicitly create sqlite files.

#### Scenario: Missing DB path for any retrieval API
- **WHEN** any retrieval API is called with a missing DB path
- **THEN** it returns caller-safe empty/controlled output
- **AND** no sqlite DB file is created at that path
