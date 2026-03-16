# Executor Prompts: narrated-location-arrival-sync

## Execution Contract

MUST:
- Keep this change narrowly scoped to explicit narrated arrival into one known in-module location.
- Preserve explicit `transitionLocation` and explicit `updatePartyTracker.currentLocationId` precedence.
- Fail open on progress-only or ambiguous scene narration.
- Use the Hermit's Refuge transcript as the primary regression lock.
- Keep host-file edits additive and marked with `# TABLETOP MODE:` comments.
- Keep Python log/output text ASCII-only.

SHOULD:
- Prefer packet-backed topology over ad hoc file rescans in every helper.
- Keep module location catalog entries minimal.
- Avoid prompt changes unless runtime parity requires them.

## Prompt 1 - Contract Locks First (Tasks 1.1-1.4)

Add transcript-driven and packet-driven tests before changing runtime code.

Required tests:
1. Hermit's Refuge narrated arrival infers party location commit.
2. Progress-only narration does not commit location.
3. Ambiguous narrated arrival does not commit location.
4. Packet topology now includes module-level location catalog.

Verification gate:
- `python3 -m py_compile <changed_test_files>`
- run the new test file(s) and confirm the expected pre-implementation failure is the missing narrated-arrival sync behavior.

## Prompt 2 - Runtime Fix (Tasks 2.1-2.5)

Implement the minimum runtime fix.

Required scope:
- extend packet topology with module-level location catalog,
- add narrated-location-arrival helper in `utils/travel_state_sync_guard.py`,
- wire inferred `updatePartyTracker` injection in `main.py` before history/UI refresh rehydrates stale location.

Guardrails:
- do not infer from vague clearing prose alone,
- do not infer when more than one destination is plausible,
- do not add duplicate location actions when explicit ones already exist.

Verification gate:
- `python3 -m py_compile main.py utils/travel_state_sync_guard.py utils/authoritative_state_packet.py <changed_test_files>`
- run narrated-arrival tests plus touched travel/packet/NPC scene suites.

## Prompt 3 - Final Verification and Report (Tasks 3.1-3.4)

Required checks:
- compile touched files
- run the new narrated-arrival regression tests
- run existing packet, travel, and NPC scene sync regressions
- `openspec validate narrated-location-arrival-sync`

Report format:
- files changed
- commands run
- PASS/FAIL per verification gate
- which narrated-arrival cases commit location
- which cases deliberately fail open
