# module-semantic-authority-audit Specification

## Purpose
TBD - created by archiving change module-publication-semantic-authority-foundation. Update Purpose after archive.
## Requirements
### Requirement: Semantic-authority audit SHALL validate the shared payload deterministically
A dedicated semantic-authority audit surface SHALL validate the shared payload for uniqueness, traceability, and contradiction classes without yet becoming the repo-level `publishable` gate.

#### Scenario: Audit passes uniquely traceable semantic-authority payloads
- **GIVEN** a module semantic-authority payload contains uniquely resolved location aliases, destination phrases, and NPC authority records
- **WHEN** the semantic-authority audit runs
- **THEN** the audit SHALL return pass output with deterministic summary fields

#### Scenario: Audit surfaces ambiguous destination phrases clearly
- **GIVEN** a destination phrase resolves to multiple targets or no uniquely supported target
- **WHEN** the semantic-authority audit runs
- **THEN** the audit SHALL surface the phrase, candidate targets, and provenance in deterministic output

#### Scenario: Audit surfaces missing NPC authority clearly
- **GIVEN** an authored NPC can appear in-scene or be revealed but lacks a deterministic scene-authority record
- **WHEN** the semantic-authority audit runs
- **THEN** the audit SHALL surface a missing-authority finding with canonical NPC identity and source context

#### Scenario: Audit remains separate from repo publishable gating in this phase
- **GIVEN** the semantic-authority audit returns degraded or fail findings
- **WHEN** this phase is implemented without the later `publishable` gate change
- **THEN** the audit SHALL remain callable as a standalone report surface
- **AND** SHALL NOT by itself redefine repo-wide `ready` versus `publishable` release policy

