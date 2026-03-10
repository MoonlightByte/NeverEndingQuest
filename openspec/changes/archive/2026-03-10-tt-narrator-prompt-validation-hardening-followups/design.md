# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

# OpenSpec Design: tt-narrator-prompt-validation-hardening-followups

## Architecture Boundaries

### Deterministic Arrival Gate (MUST)
- Python deterministic result remains source of truth for arrival-sync checks.
- LLM validator output SHALL NOT override deterministic pass/fail for arrival-sync dimension.
- Scope is narrow: only arrival-sync verdict handoff; other semantic checks unchanged.

### Travel Intent Classification (MUST)
- Replace broad substring matching with phrase/verb intent detection.
- Detection SHALL avoid generic token triggers (for example, standalone `to`).
- Fail-soft behavior stays limited to travel turns without explicit arrival semantics.

### NPC Move Identity Fallback (MUST)
- Keep strict location hint as first pass.
- Fallback SHALL use canonical identity resolution (short/full alias-aware).
- Ambiguous fallback SHALL fail closed with explicit operator message.

### OpenSpec Governance Sync (MUST)
- Specs skipped during archive SHALL be synced into `openspec/specs`.
- Sync is documentation/governance hardening and does not change runtime behavior.

## Observability

SHOULD:
- Log deterministic handoff decisions where hard gate applies.
- Log travel-intent classification reason in debug category.
- Preserve existing fallback and ambiguity logs in NPC lookup.

## Compatibility

MUST:
- Preserve single-player behavior.
- Preserve party-member exemption and fail-open alias ambiguity policy in arrival validator.
- Preserve existing action signatures and return contracts.

## Verification Strategy

1. Targeted compile checks for modified Python files.
2. Existing narrator/arrival/fallback tests remain green.
3. One new end-to-end test verifies retry loop + transient correction + deterministic handoff.
4. OpenSpec change validation passes for this change.

## Rollback Plan

- Roll back in reverse risk order:
  1. Hard gate branch in `main.py`
  2. Travel intent classifier helper
  3. Canonical fallback resolver path in `action_handler.py`
- Keep tests and specs synced even if runtime rollback is needed.
