# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

# OpenSpec Design: tt-narrator-arrival-deadlock-fix

## Architecture Boundaries

### Conversation Assembly and Prompt Authority (MUST)

- `main.py` conversation assembly SHALL enforce a single canonical narrator system prompt in outbound payload.
- Legacy prompt variants present in persisted history SHALL be pruned before API send.
- Compressor replacement behavior SHALL NOT produce duplicate canonical prompt entries.

### Deterministic Arrival Validator (MUST)

- `utils/npc_arrival_validator.py` remains authoritative for arrival sync checks.
- Off-location NPC mention alone SHALL NOT fail unless explicit arrival semantics are present.
- Explicit-arrival semantics remain strict and fail-closed when missing required action.

### Action Name Resolution for State Mutations (MUST)

- `updateCharacterInfo` and `updatePartyNPCs` keep party-tracker canonicalization semantics.
- `moveBackgroundNPC` SHALL use module-known NPC canonical identity resolution.
- Ambiguous module resolution SHALL fail-closed.

### Retry Correction Path (MUST)

- Retry notes remain transient and retry-local.
- Correction note generation SHALL avoid impossible action directives (for example, forcing `moveBackgroundNPC` with names that cannot pass resolver constraints).

## Current Failure Flow

```
Narration mentions off-location NPC in social context
  -> deterministic arrival check fails
  -> correction says add moveBackgroundNPC
  -> AI emits moveBackgroundNPC for module NPC
  -> party-only normalization rejects action name
  -> same correction repeats
  -> retry exhaustion and hard fail
```

## Target Flow

```
Narration mentions off-location NPC in social context
  -> explicit-arrival check = false
  -> deterministic check passes (no arrival state claim)
  -> normal validation proceeds

Narration with explicit arrival claim
  -> deterministic check requires matching action
  -> moveBackgroundNPC name resolution uses module canonical identity
  -> unambiguous pass OR explicit fail-closed ambiguity
```

## Implementation Notes

### Prompt Singularity Guard

MUST:

- Extend main prompt filtering to remove both:
  - current canonical compressed prompt duplicates
  - known legacy prompt preambles.
- Add outbound last-mile dedupe pass over system messages in `get_ai_response()` before API request.

SHOULD:

- Keep dedupe deterministic (content-prefix based, first-kept ordering).

### Explicit-Arrival Semantics Gate

MUST:

- Apply missing-action failure only when `_has_explicit_arrival_semantics(...)` is true.
- Preserve travel fail-soft behavior as additive (not replacement).

### moveBackgroundNPC Resolver Split

MUST:

- For `moveBackgroundNPC`, resolve action names against module NPC canonical set.
- Do not apply party-only rejection path to `moveBackgroundNPC`.
- Fail-closed on ambiguous canonical mapping.

SHOULD:

- Reuse existing resolver helper(s) to avoid new identity logic divergence.

### Retry Guidance Hardening

MUST:

- Keep concise correction note format.
- Ensure correction for arrival-sync failure includes both valid repair paths:
  - add matching state action, or
  - remove explicit arrival wording from narration.

## Observability

SHOULD add deterministic logs:

- `PROMPT_DEDUPE: pruned=N kept=1`
- `ARRIVAL_SYNC: explicit_arrival=<bool> missing_actions=<n>`
- `NPC_NORM: moveBackgroundNPC resolved via module canonical path`
- `RETRY_GUARD: emitted_non_impossible_correction`

## Rollback Strategy

Independent rollback units:

1. Prompt dedupe last-mile pass.
2. Explicit-arrival gating condition.
3. moveBackgroundNPC resolver scope split.
4. Retry correction text generation.

Each unit is reversible without schema or data migration.
