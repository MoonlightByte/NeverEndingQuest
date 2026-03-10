# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

# Spec: tt-narrator-validation-contract
# Capability: Narrator Validation Contract

## ADDED Requirements

### Requirement: Deterministic Arrival Handoff SHALL Be Enforced in Python

Arrival-sync deterministic pass/fail SHALL be enforced by runtime logic, not only by prompt guidance.

#### Scenario: Deterministic pass with conflicting LLM arrival critique
- **WHEN** deterministic validation result is `deterministic_passed = true`
- **AND** LLM validation text includes arrival-sync failure language
- **THEN** runtime SHALL keep arrival-sync verdict as pass
- **AND** SHALL continue evaluating only non-arrival validation dimensions

#### Scenario: Deterministic fail remains blocking
- **WHEN** deterministic validation result is `deterministic_passed = false`
- **THEN** runtime SHALL fail validation with deterministic reason
- **AND** LLM validator output SHALL NOT override to pass

### Requirement: Travel Intent Classifier SHALL Use Phrase-Level Intent

Travel intent detection SHALL use phrase/verb intent checks and SHALL NOT rely on broad token substring matching.

#### Scenario: Non-travel utterance with generic token
- **WHEN** user utterance includes generic words such as `to`
- **AND** no travel intent phrase/verb exists
- **THEN** runtime SHALL classify `is_travel_intent = false`

#### Scenario: Valid travel utterance
- **WHEN** user utterance clearly expresses movement intent
- **THEN** runtime SHALL classify `is_travel_intent = true`
- **AND** fail-soft arrival handling MAY apply per existing explicit-arrival rules
