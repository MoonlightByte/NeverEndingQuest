# Builder Review - module-publication-semantic-audit

**Change:** `module-publication-semantic-audit`

**Builder Objective**

Implement the publication blocker layer only. Upgrade the standalone semantic-authority audit so it fails on publication-unsafe destination and NPC authority contradictions, while keeping weaker substrate issues as warnings. Do not widen this slice into synthetic probes or the final repo-wide `publishable` gate.

**Global MUST Constraints**

- Keep the change additive and merge-safe.
- Preserve the standalone semantic audit surface as the canonical execution path in this phase.
- Promote only deterministic publication-unsafe findings into blockers.
- Keep blocker output explicit with provenance and candidate-target context.
- Do not wire repo-wide `ready` vs `publishable` policy in this change.
- ASCII only in Python user-facing console/log text.
- Edit Strategy: Apply one anchored patch at a time, then re-run `python3 -m py_compile` on touched Python files before the next patch.

**Global SHOULD Guidance**

- Prefer upgrading `scripts/module_semantic_authority_audit.py` instead of creating a second overlapping audit tool.
- Keep any substrate payload additions minimal and only if blocker classification cannot be done deterministically with the current contract.
- Focus first on authored/player-facing phrases, not every theoretical alias overlap.

---
**Step 1 Builder Prompt** (full variant)

Implement OpenSpec `module-publication-semantic-audit` Step 1 only.

Goal: define and codify the blocker policy boundaries.

Allowed:
- change specs/tasks if needed for precision
- source-contract tests only
- no runtime code yet except small helper constants if absolutely necessary

Forbidden:
- probe harness work
- publishable-gate wiring
- broad readiness pipeline changes

Required:
- settle deterministic blocker classes for unresolved destination phrases, ambiguous destination phrases, missing NPC authority, and player-facing phrase collisions
- keep weaker substrate-only duplication cases warning-level
- make the blocking vs warning boundary explicit and testable

Verify:
- source-contract or unit tests for blocker/warning boundary definitions

Output:
- blocker classes defined
- warning-only exceptions defined
- evidence the boundary is testable

**Verification Gate (after builder reports):**
- [ ] blocker classes are explicit
- [ ] warning-only boundary is explicit
- [ ] no probe or publishable-gate work leaked in

---
**Step 2 Builder Prompt** (full variant)

Implement Step 2 only.

Goal: upgrade the standalone semantic-authority audit into publication-blocking behavior.

Allowed:
- `scripts/module_semantic_authority_audit.py`
- `utils/module_semantic_authority.py` only if a small additive field is truly required
- targeted regression tests

Forbidden:
- `audit_module_readiness.py` repo-gate wiring
- runtime travel/NPC behavior changes

Required:
- unresolved authored destination phrases must fail the audit
- ambiguous authored destination phrases must fail the audit
- missing NPC authority for authored visible/revealable NPCs must fail the audit
- player-facing phrase collisions must fail the audit when natural-language routing would drift
- weaker substrate issues must remain warnings

Verify:
- `python3 -m py_compile <touched python files>`
- targeted regression tests for all blocker classes and warning boundaries

Output:
- exact blocking behaviors added
- any additive payload fields added and why
- compile/test evidence

**Verification Gate:**
- [ ] blocker classes fail deterministically
- [ ] weaker issues remain warnings
- [ ] standalone audit surface remains intact

---
**Step 3 Builder Prompt** (full variant)

Implement Step 3 only.

Goal: validate the upgraded audit on a real module and stabilize output for later gate consumption.

Allowed:
- targeted tests or smoke helpers
- minimal reporting-surface note updates if needed
- `plans/module-publication.md` only if implementation findings change later sequencing

Forbidden:
- synthetic probes
- repo-wide publishable-gate rollout
- broad documentation rewrite

Required:
- run the upgraded semantic audit against at least one real module with known publication-semantic gaps
- capture blocking output that demonstrates the phase works on live data
- ensure structured output is stable enough for future CI/readiness integration

Verify:
- `python3 -m py_compile <touched python files>`
- targeted regression suite
- real-module audit run
- `openspec validate module-publication-semantic-audit`

Output:
- real-module blocker evidence
- whether any later phase sequencing changed
- final verification evidence

**Verification Gate:**
- [ ] real-module blocker output exists
- [ ] output is structured and stable
- [ ] change still stops short of probes and publishable-gate policy

---
**Next Step Ready:** user review of the publication audit slice before implementation
