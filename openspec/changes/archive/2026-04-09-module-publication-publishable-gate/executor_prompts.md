# Builder Review - module-publication-publishable-gate

**Change:** `module-publication-publishable-gate`

**Builder Objective**

Implement the final publication gate only. Add a standalone release-facing publishability audit that layers on top of readiness, semantic publication audit, and semantic probes. Expose `ready` vs `publishable` clearly without redefining readiness itself.

**Global MUST Constraints**

- Keep the change additive and merge-safe.
- Preserve readiness semantics; do not collapse readiness into publishability.
- Publishability MUST be the stricter release-facing result.
- Emit explicit structured output for both statuses.
- ASCII only in Python user-facing console/log text.
- Edit Strategy: Apply one anchored patch at a time, then re-run `python3 -m py_compile` on touched Python files before the next patch.

**Global SHOULD Guidance**

- Prefer one standalone publishability CLI as the canonical gate.
- Reuse existing readiness/semantic audit/probe outputs instead of duplicating logic.
- Keep toolkit reporting changes narrow and data-oriented.

---
**Step 1 Builder Prompt** (full variant)

Implement OpenSpec `module-publication-publishable-gate` Step 1 only.

Goal: codify the layered gate contract.

Allowed:
- specs/tasks precision updates if needed
- source-contract tests
- small helper constants only if necessary

Forbidden:
- full script implementation
- runtime behavior changes

Required:
- define `ready` vs `publishable` clearly
- preserve readiness as a useful intermediate state
- make exit-code behavior explicit and testable

Verify:
- source-contract or unit tests for layered status behavior

Output:
- final gate contract
- layered status rules
- evidence the contract is testable

**Verification Gate (after builder reports):**
- [ ] layered contract is explicit
- [ ] exit-code behavior is explicit
- [ ] readiness remains distinct

---
**Step 2 Builder Prompt** (full variant)

Implement Step 2 only.

Goal: add the standalone publishability audit surface.

Allowed:
- new standalone script under `scripts/`
- narrow helper reuse/imports
- targeted regression tests

Forbidden:
- runtime travel/NPC/combat changes
- broad rewrite of readiness audit internals

Required:
- compose readiness, semantic publication audit, and semantic probes
- emit `ready_status`, `publishable_status`, nested gate results, blocking errors, and fix guidance
- return success only when publishable

Verify:
- `python3 -m py_compile <touched python files>`
- targeted regression tests for ready-vs-publishable outcomes

Output:
- exact CLI entrypoint
- structured output shape
- compile/test evidence

**Verification Gate:**
- [ ] standalone gate works
- [ ] ready and publishable are both exposed
- [ ] success depends on publishability

---
**Step 3 Builder Prompt** (full variant)

Implement Step 3 only.

Goal: expose the layered result in toolkit/reporting surfaces and verify on real modules.

Allowed:
- toolkit finisher report integration
- narrow bulk/reporting updates if needed
- targeted tests and real-module audit runs
- `plans/module-publication.md` completion/archive prep

Forbidden:
- new runtime behavior
- unrelated UI rewrites

Required:
- toolkit finisher report must show `ready` vs `publishable`
- run publishability audit against at least one real module
- confirm the full publication plan is now complete and ready for archival

Verify:
- `python3 -m py_compile <touched python files>`
- targeted regression tests
- real-module publishability audit run
- `openspec validate module-publication-publishable-gate`

Output:
- real-module gate evidence
- reporting surfaces changed
- final verification evidence

**Verification Gate:**
- [ ] reporting surfaces distinguish ready vs publishable
- [ ] real-module publishability evidence exists
- [ ] publication workflow is complete

---
**Next Step Ready:** plan archival and memory sync after implementation
