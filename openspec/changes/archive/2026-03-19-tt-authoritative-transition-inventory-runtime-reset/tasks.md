## 1. Authority audit and regression locks

- [x] 1.1 Add a regression test that proves `NIG04 -> NIG05` succeeds when current area connectivity declares the edge.
- [x] 1.2 Add a regression test that proves a rejected `transitionLocation` action does not generate arrival narration or rewrite conversation history.
- [x] 1.3 Add a regression test for explicit tracked-item transfer atomicity (giver remove + receiver add succeed together or fail together).
- [x] 1.4 Add a regression test for tracked-item possession queries (for example, `Do I still have the reliquary?`) that must resolve from committed character state.
- [x] 1.5 Add a regression test proving multi-PC inventory grounding uses the active character instead of `partyMembers[0]`.

## 2. Same-module transition authority reset

- [x] 2.1 Add an authoritative same-module transition validator/helper that reads fresh current-module topology instead of stale cached graph state.
- [x] 2.2 Route same-module `transitionLocation` handling through the authoritative validator while preserving broader graph support where still required.
- [x] 2.3 Ensure canonical party location state commits before downstream arrival-dependent scene generation can run.

## 3. Transition failure history hygiene

- [x] 3.1 Update the special transition branch in `main.py` to fail closed when `process_action(transitionLocation)` returns an error status.
- [x] 3.2 Disable or bypass active runtime use of `generate_arrival_narration()` and `generate_seamless_transition_narration()` until a future validated change re-enables or removes them.
- [x] 3.3 Ensure failed transition turns preserve the correct failure outcome in conversation history instead of replacing it with synthetic arrival prose.

## 4. Inventory possession authority reset

- [x] 4.1 Add deterministic tracked-item possession query handling so explicit missing-item or check-my-pack turns read committed character state.
- [x] 4.2 Add transactional runtime handling for explicit tracked-item party-to-party transfers so partial persistence cannot leave split ownership.
- [x] 4.3 Update multi-PC inventory-context building to use `active_character` as the primary grounding source.
- [x] 4.4 Narrow `narration_only` skip eligibility so possession contradiction turns must pass authoritative inventory checks first.

## 5. Documentation and dormant-layer hygiene

- [x] 5.1 Mark the seamless transition post-processor as disabled/dormant in code comments near the relevant helpers and callsites.
- [x] 5.2 Update `AGENTS.md` or equivalent repo guidance so future builders know the dormant transition layer is not active runtime architecture.
- [x] 5.3 Record cleanup intent for the dormant transition layer so follow-up removal or re-enable work has an explicit starting point.

## 6. Verification

- [x] 6.1 Run `python3 -m py_compile` on all touched Python files.
- [x] 6.2 Run the new same-module transition and failed-transition-history regressions.
- [x] 6.3 Run the new tracked-item transfer, possession-query, and active-character inventory-context regressions.
- [x] 6.4 Re-run affected existing suites for location sync, validation routing, and inventory persistence behavior.
- [x] 6.5 Run `openspec validate tt-authoritative-transition-inventory-runtime-reset`.

## SHOULD Notes

- SHOULD prefer additive helper/service extraction over widening monolithic control-flow blocks in `main.py`.
- SHOULD keep same-module validation logic simple and data-driven from fresh area JSON.
- SHOULD scope initial transactional inventory enforcement to tracked/key items first if broad rollout proves too disruptive.
