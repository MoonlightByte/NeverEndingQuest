# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

## Why

Post-fix audit of `tt-narrator-prompt-validation-refactor` confirmed core failures were addressed, but identified follow-up hardening gaps that should be closed before declaring long-term stability:

- OpenSpec archive used `--skip-specs`, so capability specs were not synced to `openspec/specs/`.
- Deterministic arrival handoff is prompt-mediated but not fully enforced in Python as a hard gate.
- Travel intent detection in `main.py` is overly broad and can over-trigger fail-soft behavior.
- `find_npc_in_areas` fallback is strict lowercase equality and should align with canonical alias resolution expectations.
- Prompt-file edits should stay semantic-only to avoid noisy whole-file diffs.
- Existing tests are strong but still need one end-to-end retry/validation path test.

## What Changes

MUST changes:
- Sync skipped specs from archived narrator-validation change into main specs.
- Add Python-side deterministic handoff guard so arrival-sync pass/fail cannot be re-litigated by LLM output.
- Replace broad travel-intent substring detection with deterministic phrase/verb intent checks.
- Harden NPC move fallback identity matching to canonical alias-aware resolution with fail-closed ambiguity.
- Add end-to-end regression test for validation retry loop with transient correction handling.

SHOULD changes:
- Keep prompt edits minimal and semantic-only.
- Add targeted observability logs for deterministic gate decisions.

Non-goals:
- No rewrite of overall validation architecture.
- No schema changes.
- No combat mechanics changes.

## Impact

Affected areas:
- `main.py`
- `core/ai/action_handler.py`
- `scripts/test_narrator_prompt_validation_refactor.py`
- `scripts/test_validation_payload_hygiene.py`
- `openspec/specs/tt-narrator-validation-contract/spec.md` (new)
- `openspec/specs/tt-validation-retry-hygiene/spec.md` (new)
- `openspec/specs/tt-npc-move-hint-fallback/spec.md` (new)

Risk and mitigation:
- Risk: over-tight deterministic enforcement could suppress valid narrative checks.
  - Mitigation: scope hard gate only to arrival-sync outcomes; preserve non-arrival LLM checks.
- Risk: alias fallback could move wrong NPC.
  - Mitigation: canonical resolver + explicit ambiguity fail-closed path.

Fallback strategy (MUST):
- If regressions appear, revert hard-gate branch and fallback identity matcher first while keeping new tests and spec sync artifacts.
