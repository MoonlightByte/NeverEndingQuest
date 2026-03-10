# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

# Spec: tt-validation-retry-hygiene
# Capability: Validation Retry Hygiene

## ADDED Requirements

### Requirement: Correction Instructions Isolation

Correction instructions SHALL NOT be persisted as user conversation turns in the main conversation history.

#### Scenario: Single failure clean retry
**Given** a narrator output that fails validation
**And** a correction instruction generated for the retry
**When** the retry is attempted
**Then** the correction instruction SHALL be passed via validation-local metadata
**And** the main conversation history SHALL NOT contain the correction text as a user message

#### Scenario: Success after retry
**Given** a failed validation followed by a successful retry
**When** checking the conversation history
**Then** it SHALL contain zero correction user messages

### Requirement: Validation-Local Metadata Storage

Correction instructions SHALL be stored as validation-local metadata, separate from conversation history.

#### Scenario: Metadata isolation
**Given** a validation failure with correction
**When** the correction is stored
**Then** it SHALL be in a validation context dictionary or retry-local state
**And** it SHALL NOT be written to `conversation_history.json`

#### Scenario: Metadata lifetime
**Given** validation-local metadata with correction instructions
**When** validation succeeds or max retries reached
**Then** the metadata SHALL be discarded
**And** it SHALL NOT persist for subsequent unrelated validations

### Requirement: No Recursive Amplification

Retry loop SHALL NOT recursively amplify correction notes across multiple attempts.

#### Scenario: Multiple failures bounded context
**Given** a narrator output that fails validation 3 consecutive times
**And** each failure generates a correction
**When** each retry is attempted
**Then** each retry SHALL receive only the current correction
**And** it SHALL NOT receive accumulated history of all prior corrections
**And** total correction context SHALL NOT exceed 3 entries worth

## UNCHANGED Requirements

### Requirement: Retry Loop Behavior

Existing retry-loop behavior (max retries, backoff strategy) SHALL remain unchanged.

#### Scenario: Max retries preserved
**Given** the existing max retry configuration
**When** validation failures occur
**Then** the max retry count SHALL remain at existing value
**And** backoff strategy SHALL remain unchanged

## MODIFIED Requirements

### Requirement: Audit Trail Separation

Correction history SHALL be maintained in separate audit log channel for debugging.

#### Scenario: Audit log format
**Given** validation failures with corrections
**When** audit trail is recorded
**Then** it SHALL be in a structured log format with:
  - timestamp
  - original output
  - correction applied
  - retry result
**And** it SHALL be separate from conversation history
