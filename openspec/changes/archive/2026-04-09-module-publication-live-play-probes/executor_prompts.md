# Builder Review - module-publication-live-play-probes

**Change:** `module-publication-live-play-probes`

**Builder Objective**

Implement the publication proof layer only. Add a standalone deterministic semantic probe harness for travel, escort/handoff, and hidden-NPC discovery semantics. Keep this slice separate from the final repo-wide `publishable` gate.

**Global MUST Constraints**

- Keep the change additive and merge-safe.
- Keep probes deterministic and source-driven; do not call live LLMs or runtime narration loops.
- Reuse existing semantic-authority and semantic-audit outputs when possible.
- Emit explicit per-probe structured results plus overall pass/degraded/fail output.
- Do not wire repo-wide `ready` vs `publishable` policy in this change.
- ASCII only in Python user-facing console/log text.
- Edit Strategy: Apply one anchored patch at a time, then re-run `python3 -m py_compile` on touched Python files before the next patch.

**Global SHOULD Guidance**

- Prefer one standalone probe harness under `scripts/`.
- Keep fixture derivation simple and reviewable before introducing any future authored override format.
- Align failure classes with Phase 2 semantic blocker concepts where practical.

---
**Step 1 Builder Prompt** (full variant)

Implement OpenSpec `module-publication-live-play-probes` Step 1 only.

Goal: define the fixture contract for publication probes.

Allowed:
- specs/tasks precision updates if needed
- source-contract tests
- small helper constants/types if needed

Forbidden:
- full harness implementation
- publishable-gate wiring
- runtime AI integration

Required:
- define deterministic fixture shapes for travel, escort/handoff, and hidden/revealable NPC probes
- keep fixtures source-driven and reviewable
- make expected targets and failure classes explicit

Verify:
- source-contract or unit tests for fixture parsing and probe-type boundaries

Output:
- fixture shapes defined
- expected fields per probe type
- evidence the contract is testable

**Verification Gate (after builder reports):**
- [ ] fixture contract is explicit
- [ ] probe types are bounded
- [ ] no harness/publishable-gate leakage occurred

---
**Step 2 Builder Prompt** (full variant)

Implement Step 2 only.

Goal: add the standalone semantic probe harness.

Allowed:
- new standalone script under `scripts/`
- narrow helper additions under `utils/` only if necessary
- targeted regression tests

Forbidden:
- runtime travel/NPC behavior changes
- repo-wide publishable-gate wiring

Required:
- execute travel probes deterministically
- execute escort/handoff probes deterministically
- execute hidden/revealable NPC probes deterministically
- reuse semantic-authority / semantic-audit outputs where appropriate
- emit structured per-probe results, summary counts, blocking errors, and warnings

Verify:
- `python3 -m py_compile <touched python files>`
- targeted regression tests for all three probe classes

Output:
- exact harness entrypoint
- fixture source/derivation path
- structured output example
- compile/test evidence

**Verification Gate:**
- [ ] all three probe classes execute deterministically
- [ ] structured output is explicit
- [ ] no repo-gate wiring leaked in

---
**Step 3 Builder Prompt** (full variant)

Implement Step 3 only.

Goal: validate the probe harness on real module data and stabilize it for later gate integration.

Allowed:
- targeted tests or smoke helpers
- minimal reporting-note updates if needed
- `plans/module-publication.md` only if implementation findings change Phase 4 sequencing

Forbidden:
- final `publishable` gate rollout
- broad readiness pipeline changes
- runtime AI integration

Required:
- run the harness against at least one real module with known semantic publication gaps
- capture structured probe output demonstrating the harness works on live data
- confirm output is stable enough for later CI/readiness/release integration

Verify:
- `python3 -m py_compile <touched python files>`
- targeted regression suite
- real-module probe run
- `openspec validate module-publication-live-play-probes`

Output:
- real-module probe evidence
- whether final gate sequencing changed
- final verification evidence

**Verification Gate:**
- [ ] real-module probe output exists
- [ ] output is structured and stable
- [ ] change still stops short of the final publishable gate

---
**Next Step Ready:** user review of the live-play probe slice before implementation
