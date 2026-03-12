## Purpose

Define the foundational memory schema contract for migration safety, compatibility, and stable entity identity.

## Requirements

### Requirement: Canonical memory schema SHALL be migration-managed and additive
The system SHALL initialize and migrate a canonical SQLite memory schema that is idempotent, additive, and safe to run repeatedly without data loss.

#### Scenario: Idempotent migration rerun
- **WHEN** migration routines are executed multiple times against the same database
- **THEN** schema creation completes without duplicate-table errors and without deleting existing rows

### Requirement: Memory foundation MUST preserve compatibility with existing JSON flows
The system MUST allow existing JSON/compression-based gameplay flows to continue if memory DB services are unavailable or disabled.

#### Scenario: DB path unavailable fallback
- **WHEN** memory DB initialization fails at startup or runtime
- **THEN** the application continues using current JSON-based memory behavior without blocking gameplay

### Requirement: Memory schema SHALL support stable entity identity with temporal role tracking
The schema SHALL represent stable entities and temporal role transitions as separate concerns so the same character identity persists across role changes.

#### Scenario: Role transition with identity continuity
- **WHEN** an entity changes role from player to companion NPC or back
- **THEN** the same entity identifier remains canonical and role history is appended as time-bounded records
