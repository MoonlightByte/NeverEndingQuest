# NPC voice repair implementation slice report

Date: 2026-08-31

Branch: `integration/npc-voice-episodic`

Approved plan SHA-256:
`49203394d2178b154640d44e1a65711f41588ff7368feab2e5ecee0bfd90c116`

This is the implementation review boundary before live acceptance A0-A5. No
live acceptance verdict or ship claim is made here.

## Slice ledger

| Slice | Commit | Result |
|---|---|---|
| C0 forensic baseline | no product commit | Evidence captured under `/mnt/c/vra-evidence/voice_repair_c76e29a4/c0/` |
| C1 lossless contracts/persistence | `e5528086` | Complete voice/profile/sidecar strings; relax-only schema |
| C2 context and advisory lifecycle | `c1ede401` | E1-E4, shared recall, exact beat authority, task-owned reap |
| C3 canonical typed combat map | `1784461c` | Complete T105 map persists pendingTurn to pendingDelivery; T096/T097 share it |
| C4a agent/narration context | `7e8d1802` | Character budgets and prose-length rejection retired; factual lints retained |
| C4b delivery text | `d67e4351` | Complete exchange, request, history, prefix, and retry-candidate strings |
| C5 simplifier/integrated audit | this commit | Dead cap parameters/constants removed where compatible; standalone response schema synchronized |

## Load-bearing structural evidence

- Every changed Python file parses and compiles.
- Encounter, sidecar, and standalone T105 response schemas parse. The standalone
  response schema is byte-semantically equal to the runtime exported contract.
- Ten of ten discovered real `npc_agent_state.json` files validate under the
  relaxed schema; no read rewrites were performed.
- Existing encounter schema compatibility scan found zero old-pass/new-fail
  regressions across 59 encounter files.
- Long sentinels survived packet composition, response validation, combat
  advisory mapping, pending-turn staging, pending-delivery commit, T096/T097
  payload construction, retry evidence, and replay fields.
- The pending advisory lifecycle seals exact beat children, rejects stale work,
  and publishes quiescence only after every child receipt finishes.
- T105/T112 callsite-registration counts did not increase.
- No tracked test file changed and no conflict marker remains.
- Typed combat has one new persisted `npc-voice-intents/v1` map. Legacy T045
  inherits the shared T105 stack through its pre-existing compatibility seam;
  no legacy-only voice path, prompt, store, or field was added.

## Remaining-limit classification

- Combat capability, violation-code, episode, profile, relationship-evidence,
  and packet arrays retain named whole-record selection/retention counts.
- Alignment abbreviations, clock formatting, prompt identity prefixes, and
  debug previews are semantic delimiters or diagnostic-only displays.
- Voice telemetry identifiers and hashes are diagnostic-only and never gate,
  deduplicate, or mutate gameplay.
- The ignored `max_chars` packet argument remains only as a compatibility input;
  it performs no truncation.
- Compression, episodic-storage, and web-TTS limits remain owned by #262 and
  were not changed.

## Tracked-test truth

The pre-implementation merged branch recorded `144 passed, 20 failed`. The
current full NPC suite records `137 passed, 27 failed` with no collection
errors. The seven net newly stale assertions describe mechanisms intentionally
retired or inverted by the owner-approved design: packet/word truncation,
deadline/executor best-effort APIs, no T097 voice input, and bounded profile
repair. Tests were intentionally not edited under the acceptance directive.
This suite is recorded as stale evidence, not presented as a passing gate.

Focused deterministic checks for the replacement contracts all passed. Their
durable local receipts are under:

- `/mnt/c/vra-evidence/voice_repair_c76e29a4/c0/`
- `/mnt/c/vra-evidence/voice_repair_c76e29a4/c3/`
- `/mnt/c/vra-evidence/voice_repair_c76e29a4/c4/`

C1/C2 focused command results are preserved by their reviewed slice commits and
the room receipts listed in the implementation handoff.

## Gate status

Implementation slices C0-C5 are ready for independent review. Live acceptance
A0-A5 has not started. D-VR-9 remains owner-open.
