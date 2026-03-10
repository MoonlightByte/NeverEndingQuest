# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

## Why

The narrator prompt and validation pipeline has mission-critical drift that is blocking reliable NPC onboarding and creating unstable retry behavior.

Observed failures that MUST be fixed:
- Scout Kira is accepted in narration but not added to `partyNPCs` when unrelated off-location mentions trigger arrival-sync rejection.
- `moveBackgroundNPC` can fail with "NPC not found" when `currentLocation` hints are stale (for example, Bex) even though canonical identity is unambiguous.
- Deterministic and LLM validation layers can emit contradictory guidance, causing noisy failures and retry-loop instability.
- Correction notes from retries can contaminate conversation history, increasing prompt noise and causing follow-on regressions.

This change is required to restore deterministic state integrity while preserving narrative quality and reducing prompt/validation contradiction.

## What Changes

This change introduces a contract-first refactor for narrator validation behavior, retry hygiene, and NPC movement fallback.

MUST changes:
- Deterministic validator is authoritative for off-location arrival sync hard checks.
- LLM validator SHALL NOT re-litigate deterministic arrival-sync pass/fail outcomes.
- Retry correction instructions SHALL remain validation-local and SHALL NOT be persisted as user conversation turns.
- NPC movement SHALL use strict location-hint lookup first, then canonical identity fallback only when unambiguous.
- Prompt and context contract text SHALL be cleaned so contradictory rules are not emitted together.

SHOULD changes:
- Validation payload noise should be reduced with bounded, non-duplicate rule context.
- Retry loops should converge with fewer attempts for arrival-sync failures.

Non-goals:
- No broad architecture rewrite.
- No schema changes.
- No gameplay mechanics changes outside narrator/validation/action routing.

## Capabilities

### New Capabilities
- `tt-narrator-validation-contract`: deterministic-vs-LLM authority split for arrival-sync validation.
- `tt-validation-retry-hygiene`: retry correction isolation and anti-pollution behavior.
- `tt-npc-move-hint-fallback`: strict-then-fallback NPC lookup with ambiguity fail-closed semantics.

## Impact

Affected areas:
- `main.py` (validation orchestration, retry correction handling)
- `utils/npc_arrival_validator.py` (deterministic arrival-sync contract output)
- `core/ai/action_handler.py` (strict hint plus canonical fallback lookup)
- `core/ai/build_npc_context.py` (context contradiction cleanup)
- Prompt files under `prompts/system_prompt*` and `prompts/validation/validation_prompt*`
- New regression fixtures/tests under `scripts/fixtures/narrator_validation/` and `scripts/test_*`

Runtime behavior impact:
- Arrival-sync hard checks remain fail-closed where required.
- Ambiguous alias cases remain fail-open per existing policy.
- Retry corrections no longer pollute conversational history.
- Stale movement hints recover safely when canonical identity is unique.

Risk and mitigation:
- Risk: over-tightening validation could reject valid narration.
  - Mitigation: fixture-based regression tests before runtime behavior changes.
- Risk: fallback lookup could move wrong NPC.
  - Mitigation: strict-first lookup, unambiguous fallback only, fail-closed on ambiguity.

Fallback strategy (MUST):
- If regressions appear, revert to prior validation routing and disable fallback lookup path while preserving tests and artifacts for controlled re-application.

Merge safety and compatibility:
- MUST keep host edits minimal and marked with `# TABLETOP MODE:` where applicable.
- MUST preserve backward compatibility for single-player mode.
- MUST preserve existing party-member exemption and fail-open ambiguity policy behavior.