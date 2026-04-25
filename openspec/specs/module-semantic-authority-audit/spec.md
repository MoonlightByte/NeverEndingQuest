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

### Requirement: Deterministic Thornwood Short-Form Destination Resolution

The Thornwood module semantic authority payload SHALL resolve the authored short-form destination phrase `north tower` to the same canonical location as `north tower overlook`.

#### Scenario: Thornwood short-form destination resolves to RO06

- **GIVEN** `The_Thornwood_Watch` semantic authority payload contains `north tower overlook` resolved to `RO06`
- **WHEN** the module semantic authority audit evaluates Thornwood destination phrases
- **THEN** `north tower` SHALL also resolve to `RO06`
- **AND** `north tower` SHALL NOT appear in `unresolved_destination_phrases`

### Requirement: Thornwood NPC Scene Authority Reflects Authored Placement

The Thornwood semantic authority payload SHALL not flag `Merchant Lira` as missing scene authority when the module already places her at `TW06`.

#### Scenario: Merchant Lira inherits visible location authority from authored placement

- **GIVEN** `module_context.json` places `Merchant Lira` in `TW06`
- **WHEN** the Thornwood semantic authority payload is evaluated
- **THEN** `Merchant Lira.visible_location_ids` SHALL include `TW06`
- **AND** `Merchant Lira` SHALL NOT appear in `missing_npc_authority`

