# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

## Why

Gameplay testing shows a hard narrator failure loop in social turns:

- Narration mentions off-location known NPCs in conversational context (for example, rumors about Merchant Kael or Hermit Maelo).
- Arrival-sync validation fails and requests arrival actions.
- Retry generation emits `moveBackgroundNPC` actions for those names.
- Runtime name normalization rejects those actions because `moveBackgroundNPC` names are currently constrained to party-tracker identities only.
- Retries exhaust (`5/5`), narrator turn fails closed, and play stalls.

In the same failing payload, conversation assembly can include duplicate copies of the compressed main system prompt due to legacy prompt residue in history plus compressor replacement behavior. This increases prompt noise and correction pressure.

## What Changes

This change introduces deterministic loop-breaking hardening for narrator validation and payload assembly.

MUST changes:

- Arrival-sync deterministic checks SHALL require explicit physical-arrival semantics before demanding state-sync actions for off-location NPC mentions in non-travel turns.
- `moveBackgroundNPC` canonical name handling SHALL resolve against module-known NPC identity (alias-aware), not party-tracker-only identity.
- Retry correction guidance SHALL avoid impossible instructions; when correction requires non-party NPC arrival state, guidance SHALL include valid alternatives (for example, remove arrival claim) and SHALL not force unsatisfiable action shape.
- Runtime narrator payload SHALL contain one canonical main system prompt copy only.
- Existing fail-closed safety SHALL remain for true explicit-arrival violations and ambiguous identity mutation.

SHOULD changes:

- Add deterministic debug logs that explicitly classify failure class (`explicit_arrival_missing_action`, `impossible_movebackgroundnpc_name`, `prompt_duplication_pruned`).
- Keep edits surgical and merge-safe with `# TABLETOP MODE:` markers where host files are touched.

Non-goals:

- No combat flow changes.
- No schema rewrites.
- No relaxation of ambiguity fail-closed behavior for state mutations.

## Impact

Primary files:

- `main.py`
- `utils/npc_arrival_validator.py`
- `utils/npc_name_normalizer.py` (if helper extension needed)
- `prompts/system_prompt_compressed.txt`
- `prompts/system_prompt.txt`
- `prompts/validation/validation_prompt_compressed.txt`
- `prompts/validation/validation_prompt.txt`
- regression tests under `scripts/test_npc_arrival_state_sync.py`, `scripts/test_narrator_prompt_validation_refactor.py`, and a new targeted payload-assembly test if needed.

Risk and mitigation:

- Risk: Over-relaxing arrival checks allows silent state drift.
  - Mitigation: Keep explicit-arrival verbs as strict fail-closed trigger and preserve action-required contract for those cases.
- Risk: Module-level name resolution could move wrong NPC.
  - Mitigation: Alias-aware canonical resolver with unambiguous-match requirement and fail-closed ambiguity.

Fallback strategy (MUST):

- If regressions appear, revert in this order:
  1) prompt dedupe logic,
  2) moveBackgroundNPC resolver widening,
  3) explicit-arrival gating changes,
  while keeping regression tests to reapply safely.
