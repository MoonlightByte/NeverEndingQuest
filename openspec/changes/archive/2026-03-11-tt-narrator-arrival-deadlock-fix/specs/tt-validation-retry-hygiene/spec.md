# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

# Spec: tt-validation-retry-hygiene
# Capability: Validation Retry Hygiene

## MODIFIED Requirements

### Requirement: Retry correction context SHALL be bounded

When a deterministic failure class has multiple legal repair paths, retry correction text SHALL avoid prescribing an impossible path only.

#### Scenario: Arrival-sync failure with non-party NPC reference
- **GIVEN** deterministic failure reason indicates explicit-arrival state-sync mismatch
- **AND** referenced NPC is not party-tracker-resolvable for the required action path
- **WHEN** correction text is generated for retry
- **THEN** correction SHALL include a legal alternative (for example, remove explicit arrival claim)
- **AND** SHALL NOT force only an unsatisfiable mutation instruction

### Requirement: Existing retry limits SHALL remain stable

Retry loop SHALL short-circuit repeated deterministic impossible-correction cycles.

#### Scenario: Same impossible deterministic reason repeats
- **GIVEN** the same deterministic impossible-correction reason repeats across retries
- **WHEN** retry guard evaluates reason sequence
- **THEN** loop SHALL short-circuit early with deterministic system guidance

## UNCHANGED Requirements

### Requirement: Correction notes remain transient

Correction instructions SHALL remain retry-local and SHALL NOT persist as user turns in canonical history.

### Requirement: Max retry fail-closed behavior remains intact

Validation exhaustion SHALL still terminate turn processing fail-closed.
