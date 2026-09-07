# Issue 248 main integration validation

Approved integration of tested branch 50939537898fe1220ecb18cc89837ed91128ecbd
with main b404083b1001c7c0616c9a22c339b93c99410a30.
This supplements the live-acceptance report; it does not upgrade its unproved arms.

## Conflict resolution

Main extracted shared NPC candidate review and relocated the ordinary turn tail.
The sole conflict retained an obsolete duplicate tail after the new reviewer.
Remove that duplicate; retain main's actual turn tail and apply the tested
pending-travel readiness guard there. Both pre-input recovery entry points,
typed cancellation, scope ownership, and queued Save disposition survive.
Incoming T114 supervision and shared candidate review remain intact.
No UI changes were manually resolved; incoming desktop redesign is retained.

Independent read-only comparison against both parents found no blockers:
recovery helpers/continuations are AST-identical to the tested parent;
shared-review helpers are AST-identical to incoming main. No duplicate
top-level definitions, unresolved index entries, or whitespace errors.

## Combined-code checks

- All changed Python files compile; focused Save queue checks pass (fault
  preservation, accepted control cancellation, FIFO, started Save completion,
  callbacks outside lock).
- Frontend: 40 test files, 359 tests passed. TypeScript and Vite build passed.
  The earlier baseline HeaderBar failures do not recur on this combined code.
- Real OpenAI headless recovery uses the untouched authentic pending game at
  /mnt/c/248a1. Only static prompts/schemas were refreshed to the combined code.
  Recovery status seq19; actual arrival seq54; context seq70; first prompt seq107.
  T013/T063/T064 captures exist. RO01, 13:10 -> 13:15; journal remains at three
  entries (departure already committed), pending checkpoint removed.
- One actual subsequent look-at-maps input passes the shared correction loop
  after two rejected drafts, publishes narration seq293, then prompt seq374.
  Location remains RO01 and time remains 13:15. Quit seq376-379; process exits 0.
- This additional run is WSL, not a new native-Windows acceptance run. Prior
  native/browser results and their limits remain in the live-acceptance report.
  It does not claim new live coverage of membership-changing T114 branches.

## Local evidence (private, not committed)

- /mnt/c/agent-room-fleet-kit/local-data/248-evidence/merge-recovery/protocol.ndjson
- /mnt/c/agent-room-fleet-kit/local-data/248-evidence/merge-recovery/model_captures/
- /tmp/248-merge-vitest.log
- /tmp/248-merge-build.log

Existing unrelated findings remain separate; no provider, schema, or gameplay
repair was added during conflict resolution.
