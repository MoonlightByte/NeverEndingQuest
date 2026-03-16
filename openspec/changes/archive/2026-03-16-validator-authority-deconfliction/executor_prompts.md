# Executor Prompts: validator-authority-deconfliction

## Execution Contract

MUST:
- Keep G4 scoped to narrator validation authority, routing, and retry behavior.
- Replace the flat deterministic handoff with a domain-scoped payload before broadening any suppression logic.
- Keep payload v1 limited to `travel_state_sync`, `npc_state_sync`, and `mechanics_precheck`.
- Preserve blocking behavior for unreconciled failures.
- Preserve single-player compatibility.
- Mark host-file integration points with `# TABLETOP MODE:` comments.

SHOULD:
- Prefer structured runtime classification over reason-text keyword hacks.
- Keep deconfliction auditable through explicit telemetry fields.
- Add transcript-driven tests before runtime implementation changes.

## Prompt 1 - Transcript Locks First (Tasks 1.1-1.5)

Before touching runtime code, add tests for these transcript families:

1. Travel reconciled, validator still complains:
   - Runtime already inferred legal travel action bundle.
   - LLM validator still says missing `transitionLocation`/travel sync.
   - Expected G4 result: accepted, no retry.

2. NPC scene presence reconciled, validator still complains:
   - Runtime already inferred safe scene-presence `moveBackgroundNPC`.
   - LLM validator still says off-location NPC arrival missing state action.
   - Expected G4 result: accepted, no retry.

3. Mixed-domain failure:
   - Travel or NPC reconcile-first domain is valid.
   - Separate unrelated invalid action or semantic failure is still present.
   - Expected G4 result: still blocked.

4. Deterministic authoritative failure:
   - Travel/NPC/mechanics deterministic domain fails.
   - Expected G4 result: still blocked, never suppressed.

5. Telemetry path:
   - Suppression records `suppressed_domains` and `remaining_failure_domains` deterministically.

Verification gate before continuing:
- `python3 -m py_compile <changed_test_files>`
- Run new G4 tests and confirm pre-implementation failures are about missing deconfliction, not bad fixtures.

## Prompt 2 - Domain Payload Foundation (Tasks 2.1-2.3)

Implement the new deterministic handoff payload in `main.py`.

Required payload shape:

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

Verification gate before continuing:
- `python3 -m py_compile main.py <changed_test_files>`
- Run payload-shape/source-contract tests.

## Prompt 3 - Runtime Deconfliction and Retry Narrowing (Tasks 3.1-4.3)

Implement domain-based suppression and retry narrowing.

Rules:
- If the LLM failure targets only authoritative-passed domains, suppress it.
- If the LLM failure includes unreconciled domains, keep blocking.
- Do not generate retry correction notes for reconciled-domain-only failures.
- Expose telemetry for suppressed and remaining domains.

Verification gate before continuing:
- `python3 -m py_compile main.py utils/validation_routing.py <changed_test_files>`
- Run narrator validation, retry hygiene, and telemetry regressions.
