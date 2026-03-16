## Context

The current narrator validation flow already passes deterministic metadata into the LLM validator, but the payload is too flat and the runtime deconfliction logic is too narrow. `main.py` currently carries an arrival-only hard gate keyed off validator reason text. That was acceptable as a transitional patch for explicit arrival-sync, but G2 travel reconciliation and G3 NPC scene-presence reconciliation make that approach insufficient.

The next step is not broader reconciliation. It is authority cleanup: Python has already decided some domains. The LLM validator should still review structure, semantics, and unreconciled mechanics, but it should no longer be able to veto already-reconciled travel/NPC domains or trigger retries for them.

Constraints:
- Keep G4 scoped to narrator validation, routing, and retry behavior.
- Do not widen deterministic authority into all narrative judgment.
- Preserve fail-closed behavior when deterministic domains fail.
- Preserve unrelated LLM validation value for unreconciled semantic, structural, and mechanical issues.

## Goals / Non-Goals

**Goals:**
- Replace flat deterministic validation handoff with domain-scoped payloads.
- Define exactly which domains are authoritative and when.
- Replace arrival-only override heuristics with generic domain deconfliction.
- Reduce retry churn caused by reconciled-domain-only failures.
- Add transcript-driven test inventory before implementation changes.

**Non-Goals:**
- No event ledger in this change.
- No broad system prompt rewrite in this change.
- No combat validation redesign in this change.
- No replacement of the LLM validator with fully deterministic validation.

## Decisions

### Decision 1: Deterministic handoff payload becomes domain-scoped

The runtime MUST stop using a single flattened `deterministic_passed` payload for narrator validation authority and instead use a structured payload with per-domain entries.

Proposed payload shape:

```json
{
  "domains": {
    "travel_state_sync": {
      "passed": true,
      "authoritative": true,
      "reconciled": true,
      "mode": "arrival_autocommit",
      "reason": "",
      "required_action": ""
    },
    "npc_state_sync": {
      "passed": true,
      "authoritative": true,
      "reconciled": true,
      "mode": "scene_presence_autocommit",
      "reason": "",
      "required_action": ""
    },
    "mechanics_precheck": {
      "passed": true,
      "authoritative": true,
      "reconciled": false,
      "mode": "pass",
      "reason": "",
      "required_action": ""
    }
  },
  "summary": {
    "all_authoritative_domains_passed": true,
    "authoritative_failures": [],
    "reconciled_domains": ["travel_state_sync", "npc_state_sync"]
  }
}
```

Rationale:
- Makes authority explicit per domain.
- Supports both suppression and mixed-domain review.
- Avoids reason-text hacks as the primary architecture.

Alternative considered:
- Keep one flat boolean plus extra freeform strings.
- Rejected because it cannot safely represent mixed-domain outcomes.

### Decision 2: Domain suppression is allowed only for authoritative-passed domains

Runtime MUST suppress LLM failures only when the failure targets one or more authoritative domains that already passed deterministic validation.

Rationale:
- Keeps suppression narrow.
- Prevents travel/NPC re-litigation without hiding unrelated LLM findings.

Alternative considered:
- Skip LLM validation for every reconciled turn.
- Rejected because mixed turns can still contain unrelated invalid actions or weak narration.

### Decision 3: Mixed-domain failures remain reviewable

When an LLM failure contains both reconciled-domain complaints and unreconciled complaints, runtime MUST preserve the unreconciled failure path.

Rationale:
- Avoids over-suppressing legitimate semantic or structural problems.

Alternative considered:
- Suppress the entire failure if any authoritative domain passed.
- Rejected as too permissive.

### Decision 4: Retry behavior should ignore reconciled-domain-only failures

Retry correction notes MUST not be generated for failures whose only invalidation source is an already-reconciled authoritative domain.

Rationale:
- This is the shortest path to reducing correction churn.

Alternative considered:
- Keep current retries and only accept on the last attempt.
- Rejected because it preserves the same wasted loop behavior.

### Decision 5: Telemetry should expose deconfliction decisions explicitly

Validation routing telemetry MUST report when domain suppression occurs and which domains caused it.

Suggested additional telemetry fields:
- `authoritative_domain_conflict`
- `suppressed_domains`
- `remaining_failure_domains`
- `deterministic_payload_version`

Rationale:
- Makes debugging and regression analysis practical.

## Risks / Trade-offs

- [Risk] Over-suppression could allow invalid responses through.
  -> Mitigation: suppression only applies to authoritative-passed domains; mixed-domain failures still block.

- [Risk] Failure classification may be too fragile if still based partly on reason text.
  -> Mitigation: G4 SHOULD move toward structured classification at runtime and in validator contract, not rely on keyword-only logic.

- [Risk] The payload shape could become too broad too early.
  -> Mitigation: keep v1 domains limited to `travel_state_sync`, `npc_state_sync`, and `mechanics_precheck`.

## Migration Plan

1. Create transcript-driven G4 tests before runtime implementation.
2. Add new authoritative-domain handoff spec and modify narrator validation/routing/retry specs.
3. Update runtime payload assembly in `main.py` to emit per-domain deterministic handoff data.
4. Update deconfliction and retry logic to consume the new payload.
5. Update validation prompts to align with domain-scoped authority.

Rollback strategy:
- If mixed-domain suppression proves too risky, keep the structured payload but temporarily fall back to blocking on all LLM failures except the already-working arrival/NPC path.

## Open Questions

- Whether the LLM validator output should stay freeform reason text or move to an optional structured failure-domain field in this same change.
- Whether `mechanics_precheck` should be treated as suppression-capable or only as hard-fail authoritative.

## Status Note

Completed foundation in current branch:
- transcript/runtime coverage now exists for authoritative travel suppression, authoritative NPC suppression, mixed-domain blocking, and authoritative mechanics blocking;
- `main.py` now emits the v1 domain-scoped deterministic handoff payload;
- `main.py` now uses generic domain-based deconfliction instead of the arrival-only hard gate;
- `utils/validation_routing.py` now exposes `authoritative_domain_conflict`, `suppressed_domains`, `remaining_failure_domains`, and `deterministic_payload_version`.

Remaining closeout for G4:
- validation prompts still describe the old flat arrival-only handoff rather than the domain-scoped payload;
- retry correction generation still uses broad reason-text buckets instead of deconflicted remaining-domain logic.

That means G4 runtime authority is ahead of prompt/retry alignment. The next implementation slice should close that gap before treating G4 as complete.
