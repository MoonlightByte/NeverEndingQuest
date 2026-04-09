# Builder Review - module-publication-semantic-authority-foundation

**Change:** `module-publication-semantic-authority-foundation`

**Builder Objective**

Implement the first publication-semantics substrate only. Build a shared semantic-authority payload for destinations and NPC scene authority, reuse it across ingest and toolkit-finishing flows, and add a standalone audit/report surface. Do not widen this slice into the later `publishable` gate or synthetic gameplay probes.

**Global MUST Constraints**

- Keep the change additive and merge-safe.
- Preserve existing runtime behavior; this is publication substrate work, not runtime travel/NPC behavior redesign.
- Keep ingest and toolkit-finishing flows on one shared enrichment contract.
- Carry source provenance for emitted phrase and NPC authority records.
- Record ambiguity and missing-authority diagnostics instead of hard-failing generation in this phase.
- ASCII only in Python user-facing console/log text.
- Edit Strategy: Apply one anchored patch at a time, then re-run `python3 -m py_compile` on touched Python files before the next patch.

**Global SHOULD Guidance**

- Prefer one new shared helper/service over scattering extraction logic across scripts and web extensions.
- Keep first-pass extraction bounded to authored location names, aliases, plot phrases, hooks, and explicit NPC scene records.
- Prefer report surfaces that later publication audits can consume unchanged.

---
**Step 1 Builder Prompt** (full variant)

Implement OpenSpec `module-publication-semantic-authority-foundation` Step 1 only.

Goal: add the shared semantic-authority helper and its deterministic contract.

Allowed:
- new shared helper under `utils/` or another narrow shared publication layer
- targeted helper tests
- import wiring only where needed by the helper tests

Forbidden:
- ingest integration
- toolkit-finisher integration
- readiness-gate wiring
- runtime travel or NPC behavior changes

Required:
- normalize canonical location aliases
- derive destination phrase records with provenance and ambiguity handling
- derive NPC scene-authority records for visible plus revealable NPC data
- keep weak or ambiguous inputs fail-open inside the helper, with diagnostics recorded in output

Verify:
- `python3 -m py_compile <touched python files>`
- targeted helper tests for alias normalization, ambiguous phrase recording, and visible vs revealable NPC authority

Output:
- files changed
- helper API surface
- representative payload shape
- test/compile evidence

**Verification Gate (after builder reports):**
- [ ] helper exists and is importable
- [ ] payload includes provenance and diagnostics
- [ ] ambiguous inputs degrade safely

---
**Step 2 Builder Prompt** (full variant)

Implement Step 2 only.

Goal: integrate the shared semantic-authority helper into ingest and toolkit-finishing flows.

Allowed:
- `scripts/homebrew_ingest_dev.py`
- `web/extensions/toolkit_module_finisher.py`
- shared helper import sites
- targeted tests for integration/report shape

Forbidden:
- readiness-gate wiring
- runtime validator changes
- synthetic probe harness

Required:
- ingest must emit or persist the shared semantic-authority payload through its publication-oriented output path
- toolkit finisher must reuse the same helper and report the same semantic-authority stage/contract
- report text must state that this improves publication preparation but does not yet provide the `publishable` gate

Verify:
- `python3 -m py_compile scripts/homebrew_ingest_dev.py web/extensions/toolkit_module_finisher.py <shared helper files>`
- targeted tests proving ingest and toolkit outputs stay aligned

Output:
- exact persistence/report surfaces changed
- evidence that ingest and toolkit use the same contract
- compile/test evidence

**Verification Gate:**
- [ ] ingest and toolkit reuse one contract
- [ ] report surfaces stay additive
- [ ] no claim of full publication safety appears

---
**Step 3 Builder Prompt** (full variant)

Implement Step 3 only.

Goal: add the standalone semantic-authority audit/report surface.

Allowed:
- new audit/report script under `scripts/`
- helper reuse
- targeted regression tests

Forbidden:
- `audit_module_readiness.py` gate wiring
- repo-wide `publishable` policy changes
- runtime code changes

Required:
- audit must validate uniqueness, traceability, ambiguity, and missing-authority classes deterministically
- audit must return pass/degraded/fail-style structured output
- audit must surface concrete phrase/NPC findings with provenance
- weak prose must degrade safely while concrete contradictions surface clearly

Verify:
- `python3 -m py_compile <touched python files>`
- targeted tests for pass, ambiguity, and missing-authority cases

Output:
- audit command shape
- finding classes exposed
- compile/test evidence

**Verification Gate:**
- [ ] audit reports ambiguous phrases clearly
- [ ] audit reports missing NPC authority clearly
- [ ] audit remains separate from repo gating

---
**Step 4 Builder Prompt** (full variant)

Implement Step 4 only.

Goal: verify the substrate on a real module and sync planning notes if needed.

Allowed:
- targeted tests or smoke helpers
- `plans/module-publication.md` progress note updates only if implementation findings materially change later sequencing

Forbidden:
- broad documentation rewrite
- starting Phase 2 publication blockers

Required:
- run the audit/report flow against at least one real module with known publication-semantic gaps
- capture whether the emitted diagnostics support the later publication-audit and probe phases cleanly
- update plan notes only if real findings change the later phase order or scope

Verify:
- `python3 -m py_compile <touched python files>`
- targeted test suite
- real-module audit/report run
- `openspec validate module-publication-semantic-authority-foundation`

Output:
- real-module evidence
- whether later phase ordering changed
- final verification evidence

**Verification Gate:**
- [ ] real-module audit evidence exists
- [ ] change still stops short of `publishable` gate work
- [ ] OpenSpec validation passes

---
**Next Step Ready:** user review of Phase 1 scope and builder sequencing
