# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

# OpenSpec Tasks: tt-narrator-arrival-deadlock-fix

## Step 1.1 - Capture failing contracts as regression tests

- [x] Add/extend tests for narrator deadlock reproduction:
  - [x] Off-location mention without explicit arrival semantics does not require arrival action.
  - [x] Explicit arrival mention without action still fails closed.
  - [x] `moveBackgroundNPC` for module NPC name is not rejected by party-only normalizer.
  - [x] Retry path does not converge to impossible correction loop for this scenario.
- [x] Add/extend payload assembly test ensuring single canonical main system prompt in outbound request.

**Verification:**
```bash
python3 scripts/test_npc_arrival_state_sync.py
python3 scripts/test_narrator_prompt_validation_refactor.py
```

## Step 1.2 - Implement prompt singularity guard in runtime assembly

- [x] Update `main.py` prompt filtering to remove legacy and duplicate narrator prompt entries.
- [x] Add last-mile dedupe in `get_ai_response()` so only one canonical main system prompt is sent.
- [x] Ensure ordering remains: main prompt first, then other system context.

**Verification:**
```bash
python3 -m py_compile main.py
python3 scripts/test_narrator_prompt_validation_refactor.py
```

## Step 1.3 - Align deterministic arrival gating to explicit arrival semantics

- [x] Update `utils/npc_arrival_validator.py` so missing-action failure requires explicit arrival semantics.
- [x] Preserve strict fail-closed behavior for explicit arrivals.
- [x] Preserve travel fail-soft behavior and party-member exemption behavior.

**Verification:**
```bash
python3 -m py_compile utils/npc_arrival_validator.py
python3 scripts/test_npc_arrival_state_sync.py
python3 scripts/test_npc_arrival_party_exemption.py
```

## Step 1.4 - Split action-name normalization by action type

- [x] Update `main.py` (or helper path) to stop enforcing party-tracker-only resolution for `moveBackgroundNPC`.
- [x] Route `moveBackgroundNPC` normalization through module-canonical identity lookup.
- [x] Keep fail-closed ambiguity handling for state mutation actions.

**Verification:**
```bash
python3 -m py_compile main.py core/ai/action_handler.py
python3 scripts/test_narrator_prompt_validation_refactor.py
```

## Step 1.5 - Harden retry correction guidance against impossible loops

- [x] Ensure deterministic arrival correction text includes valid alternative path (remove explicit arrival claim) and not only forced mutation action.
- [x] Keep correction note transient and retry-local only.
- [x] Preserve existing fail-closed exhaustion behavior after max retries.

**Verification:**
```bash
python3 -m py_compile main.py
python3 scripts/test_retry_de_looping.py
python3 scripts/test_narrator_prompt_validation_refactor.py
```

## Step 1.6 - Prompt/validator contract parity cleanup

- [x] Update compressed/uncompressed system prompt arrival-sync wording for explicit-arrival-only enforcement.
- [x] Update compressed/uncompressed validation prompt wording to mirror runtime contract.
- [x] Keep edits semantic-only (no full-file churn).

**Verification:**
```bash
python3 scripts/test_validation_payload_hygiene.py
```

## Step 2.1 - End-to-end verification and OpenSpec validation

- [x] Run targeted compile checks for touched files.
- [x] Run full targeted regression suite for narrator validation path.
- [x] Validate OpenSpec change artifacts.

**Verification:**
```bash
python3 -m py_compile main.py utils/npc_arrival_validator.py core/ai/action_handler.py
python3 scripts/test_npc_arrival_state_sync.py
python3 scripts/test_npc_arrival_party_exemption.py
python3 scripts/test_retry_de_looping.py
python3 scripts/test_narrator_prompt_validation_refactor.py
python3 scripts/test_validation_payload_hygiene.py
openspec validate tt-narrator-arrival-deadlock-fix
```
