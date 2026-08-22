# Canonical agent-guideline activation design

## Status and purpose

This document is an implementation and migration record. It is not policy authority and must be
marked historical after the migration is accepted. GitHub issue #193 is the single canonical source
of design and development policy for NeverEndingQuest.

The migration makes that authority reliable in fresh Claude, Codex, and other repository-aware
sessions without creating a second copy of the rules. It also incorporates the owner's latest
rulings about live approved features, automatic compatibility, real acceptance, review
convergence, revision evidence, combat recovery, and post-review execution approval.

This change governs development process only. It does not alter game code, prompts, schemas,
configuration, tests, models, providers, or deployment.

## Canonical source and bootstrap

GitHub issue #193 is canonical. Repository files, tool memories, plans, handoffs, and this migration
document defer to it on conflict. A policy change is made in issue #193 first; pointers and
bootstrap text may then be updated, but no second document may paraphrase the policy as an
independent authority.

The repository root must contain a tracked `AGENTS.md` bootstrap. It must:

1. identify issue #193 as canonical;
2. require Part 1 at the start of every session;
3. require the relevant Part 2 system page before diagnosis, design, or implementation;
4. require Part 3 after a plan is written and before the plan is presented for owner approval;
5. require Part 5 for owner rulings;
6. stop work when issue #193 is unavailable or conflicts with another authoritative instruction;
7. contain repository-operational facts needed to locate and apply the canonical policy, but not a
   second full copy of the policy.

`AGENTS.md` must not remain ignored. Fresh clones must receive the bootstrap automatically. A
missing, ignored, stale, or untracked bootstrap is an activation failure.

Tool-specific memories may retain project history and current status. Their guideline entries must
contain only a pointer to issue #193 and the tracked bootstrap; they must not copy or paraphrase the
rules. The existing retrospective feedback memory and its index entry become pointers.

## Required amendments to issue #193

### 1. Restart and inherited-work safeguard

Before resuming paused, compacted, handed-off, or previously designed work, the agent must:

1. read issue #193 Part 1 completely;
2. read the relevant Part 2 system page, current design, plan, handoff, and acceptance criteria;
3. fetch and dynamically capture the current branch, revision, ancestry, worktree, platform,
   interpreter, provider, model, endpoint, and mutable game root;
4. inspect the current implementation, complete call paths, persisted state, logs, and runtime
   evidence rather than assuming a document or handoff is current;
5. reconcile contradictions and stale decisions before editing.

Fixed commit hashes must not be embedded as authority in production code, persisted data, feature
gates, schemas, long-lived designs, plans, or handoffs. Evidence records the revision actually used
by reading Git during the run. Historical revisions may appear only as non-authoritative archaeology
in fresh evidence; compatibility authority comes from verified mainline ancestry and owner-approved
releases.

Each workstream has one current design. Superseded designs remain historical and link forward. An
agent never creates a competing design to avoid reconciling the current one.

### 2. Complete intent and compatibility map before proposals

Before proposing or implementing a change, map the complete behavior it can affect:

- the last known working mainline implementation and relevant Git history;
- every direct, indirect, dynamic, sibling, and entry-point consumer of the symbol family;
- callers, callees, callbacks, locks, ordering, side effects, and failure paths;
- authoritative state, advisory indexes, caches, persisted formats, migrations, and recovery;
- player-visible UI, narration, debug output, pacing, and responsive behavior;
- platform, provider, model, and interpreter variants;
- compatibility obligations for existing games, saves, modules, encounters, and configuration.

Write the behavioral invariants before proposing the solution: identity, authoritative source,
desired end state, allowed failure state, and what must never happen. A shared invariant belongs at
a common boundary only when every caller has the same contract. Caller-specific behavior is not
flattened merely to centralize code.

### 3. Preserve and expand working functionality

Bug fixes and features preserve proven working functionality and documentation outside the
explicitly authorized change. The default is to expand the existing capability and add the
technical depth needed at the correct layer, not delete behavior as a shortcut.

Technical depth means stronger semantics, state reconciliation, compatibility, failure handling,
or evidence. It does not mean machinery for its own sake. A simpler replacement is acceptable only
when its behavioral contract shows every affected entry point and consumer as preserved or
owner-retired and real A/B acceptance proves the working paths.

Removal requires documented owner authorization, a proven unsafe or contradictory behavior, a
replacement preserving every required contract, or a legal or security mandate. Useful design
history is marked historical and linked forward rather than erased.

### 4. Approved production functionality is always live

No approved production feature may ship behind a kill switch, hidden rollout flag, default-off
setting, environment-variable opt-in, user opt-in, provider-specific bypass, or silent fallback
that defeats it. Approved code on main must be reachable through every supported applicable entry
point. A feature that is not safe for every applicable player is unfinished and remains on its
implementation branch; dormant code on main is a defect, not a rollout strategy.

Obsolete rollout controls are removed when a feature is activated. Old switch values in saved
settings receive no behavioral authority. Backward compatibility is live code selected
automatically from authoritative persisted state, format version, or provenance. It is never a
player-selected architecture.

Intentional player choices such as provider and model selection remain. Diagnostic and cost
safeguards remain only when they do not disable approved gameplay or silently change its contract.

### 5. Agentic-first, reconciled by deterministic code

Semantic decisions over natural language are agentic-first wherever the model can evaluate real
state and return structured facts. Code never reconstructs meaning through keyword, verb,
substring, prose, name, entity-type, shape, or regex heuristics.

Deterministic code owns arithmetic, conservation, canonical identity, authorization, existence and
ownership checks, ordering, atomicity, persistence, and final refusal. The model provides meaning;
code reconciles it against authoritative state and enforces integrity.

### 6. Combat recovery contract

Issue #193's Combat system page and consolidated issue #191 govern combat recovery. Only mainline
ancestry is an implementation baseline; aborted worktrees and unmerged combat branches are not
design authority.

The degradation chain must remain explicit in combat plans: encounter creation omitted structured
allegiance and objective facts; the builder substituted broad entity types; later deterministic
code treated non-enemy participants as party members; completion then could not recognize victory
over a hostile named NPC. The correction is a typed, agent-authored encounter manifest containing
canonical participants, allegiance, controller, objectives, and relationships, reconciled against
authoritative character and world state. No additional inference from type, names, prose, or file
shape is permitted.

Preserve the proven legacy interaction and deterministic mechanics that still satisfy their
contracts. New encounters use the repaired agentic contract unconditionally. Existing encounters
with legacy provenance continue automatically through the legacy adapter. Players never select a
combat architecture through a setting.

### 7. Evidence and claim discipline

Every decision-bearing claim is labeled:

- **OBSERVED**: reproduced in runtime, logs, or authoritative on-disk state;
- **CODE-PROVEN**: established by the complete call path or invariant;
- **HYPOTHESIS**: plausible but unverified.

Only OBSERVED and CODE-PROVEN findings may create implementation tasks, blocking severity, or new
issues. A HYPOTHESIS receives one falsifiable verification request in the current review. If it
cannot be established, it remains explicitly unverified and cannot manufacture work or prevent
convergence. A credible security or corruption hypothesis is promptly escalated to the owner with
the proposed verification; agents do not silently assign it severity or redesign production code.

Reports are evidence inputs, not conclusions. Code that could perform an action is not proof that
it did. When a claim collapses, re-derive the conclusion rather than relocating it to another issue.
Environment attribution also requires observed differential or direct evidence.

### 8. Real acceptance and performance evidence

Define acceptance before coding at the layer where the defect or feature lives. Compile, import,
pure-function, isolation, monkeypatched, synthetic, model-free, and test-suite results are
development aids only. They cannot prove end-user functionality, game quality, latency,
throughput, cost, or performance.

Those claims require the real native platform, real configured provider and model, unmodified
headless or browser flow, real player commands, authoritative on-disk state, and wall-clock plus
provider-call evidence when performance is claimed. Narration alone is never state proof. UI work
requires real browser inspection of the complete rendered state in addition to applicable headless
state evidence.

Use deterministic byte comparisons only for deterministic emissions. For model-mediated behavior,
judge structured facts, identities, state transitions, conservation, ordering, and persisted
results rather than exact prose.

Acceptance reports distinguish `PASSED`, `FAILED`, `BLOCKED`, and `NOT REACHED`. They dynamically
capture lineage and record environment, commands, negative controls, and evidence paths. An
operation that never reached a boundary proves nothing about that boundary.

Run the smallest real vertical slice that reaches the changed seam before broad backend suites.
Test one acceptance operation at a time unless concurrency is itself the subject. Do not download,
load, unload, switch, or reconfigure models without explicit owner authorization.

Use one mutable game root, one server, and one acceptance operation at a time unless the acceptance
case explicitly exercises concurrency. Record process IDs and ports and stop or await the prior
operation before starting another. Use a fresh isolated worktree or clone when branch or platform
provenance could be ambiguous.

Implement one independently acceptable unit at a time. Coupled changes remain one unit when
splitting them would create an unsafe intermediate state. Create recovery points only from
agent-owned changes; never commit, stash, reset, overwrite, or otherwise absorb unrelated user
work.

### 9. Fail-forward and commit boundaries

Recoverable player paths fail forward so a valid game remains usable. Unsafe commit,
authorization, corruption, and genuine nonexistence or nonownership boundaries fail closed before
mutation. Busy is queued or awaited, never converted into player refusal. Refusal is delivered as
narration, not silent corruption or a raw system error.

At an atomic commit point, landed success never escapes as failure. Post-commit fallible steps are
contained, observable, and have explicit self-healing semantics. Artificial failure injection may
help development, but production acceptance exercises a real negative control through the
unmodified path and judges real state.

### 10. Review convergence and owner agency

After any plan is written, dispatch every standing reviewer required by the mechanically selected
tier plus every triggered conditional reviewer as separate, parallel, blind agents. The controller
single-writes corrections and re-dispatches all required reviewers against the same current plan
and cumulative resolution ledger.

Continue until every required reviewer returns zero in-scope OBSERVED or CODE-PROVEN findings on
the same plan revision, followed by one clean confirmation pass. There is no round cap, one-round
shortcut, residual-finding escape hatch, or agent authority to declare a concern acceptable. A
bare `N/A` does not omit a triggered gate; it requires cited evidence. Product disagreements are
escalated to the owner and review resumes after the ruling.

Convergence completes review only. It never authorizes implementation, merge, deployment, or the
next phase. The controller stops and presents the converged plan, evidence, decisions, scope, cost,
and separately tracked issues to the owner. Only the owner may approve execution or provide new
direction. Approval must follow presentation of the converged plan; pre-review authorization,
silence, generic prior instructions, or reviewer consensus do not authorize the changed plan.

Review effort follows the quickest trustworthy path: independent reads run in parallel, all writes
remain single-controller, and the smallest real acceptance slice falsifies the central claim first.
Do not repeat unchanged scans, generate test-only scaffolding, or spend a round restating settled
findings. Each review pass must add evidence, resolve a cited finding, or escalate a genuine owner
decision. There is no cap on productive convergence work and no license for ceremonial loops.

### 11. Mechanism, hygiene, and artifacts

Every new mechanism answers an observed failure or owner-mandated capability and passes a
zero-callers audit. Open product decisions are resolved before coding. Working paths are changed
reactively or by explicit owner mandate, never reshaped speculatively.

Before commit, review the exact staged diff and run applicable mechanical checks: diff extent,
`git diff --check`, line endings, encoding, ASCII-only added production text, banned prose-matching
and revision-authority patterns, dangling references, secrets, configuration, and generated
artifacts.

Never print credentials into output, logs, screenshots, comments, or evidence. Keep configuration
untracked and sanitize excerpts. Place evidence in a named scoped directory, measure large artifact
growth, and remove only agent-owned artifacts after evidence is preserved or the owner authorizes
cleanup. Record the owner-approved model and endpoint used for every real provider call.

## Migration steps

Amend the current issue in place. Preserve its existing v1.1 Player-Experience reviewer, player
contracts, community-module, first-run, media, and cost coverage unless the owner separately
authorizes a change. This migration adds and reconciles safeguards; it does not replace the useful
work already accepted into the canonical issue.

1. Amend issue #193 first. Remove every conflicting round cap, one-round limit, post-merge-only
   sweep, fixed-revision handoff, and auto-execution implication. Add the owner rulings above to
   Part 1, the affected Part 2 system pages, Part 3 convergence, Part 4 operations, and Part 5.
2. Separate Part 5 into ratified rulings and open owner decisions. Open entries are not described as
   ratified and cannot be cited as settled behavior.
3. Remove `AGENTS.md` from `.gitignore` and add the minimal tracked bootstrap described above.
4. Replace duplicate tool-memory guideline files and indexes with pointers to issue #193 and the
   bootstrap. Do not alter unrelated project-history memories in this migration.
5. Mark this design historical and link to the accepted issue #193 revision after activation.

## Validation

Validation is documentation-only and must prove:

1. issue #193 contains the approved rules and no contradictory cap, fixed-revision authority,
   hidden-rollout permission, post-review execution authority, or post-merge-only gate remains;
2. the root `AGENTS.md` is tracked, present in a fresh clone, and points to issue #193 without
   becoming a competing policy copy;
3. tool memories contain pointers rather than duplicated policy;
4. all changed documentation is ASCII-clean and renders correctly;
5. the candidate diff contains only authorized documentation and bootstrap changes;
6. no game code, prompts, schemas, configuration, tests, models, providers, or deployment changed.

## Tracked follow-ups

- Issue #193: canonical amendment, contradiction removal, and owner-ruling ledger update.
- Issue #193 activation: tracked root bootstrap and tool-memory pointer conversion after the
  canonical text is accepted.
- This migration record: mark historical and link forward after activation is complete.

## Resolution ledger

| Decision | Owner ruling | Status |
| --- | --- | --- |
| D-1 | Issue #193 remains the single canonical policy authority. | RATIFIED |
| D-2 | Approved production features are live without kill switches, hidden rollouts, default-off controls, or opt-in architecture. | RATIFIED |
| D-3 | Compatibility is selected automatically by live code; old player switch values have no authority. | RATIFIED |
| D-4 | Required reviewers continue until evidence-backed convergence with no round cap or residual-finding escape. | RATIFIED |
| D-5 | Review convergence does not authorize execution; the owner approves the converged plan afterward. | RATIFIED |
| D-6 | Revision provenance is captured dynamically and never embedded as long-lived authority. | RATIFIED |
| D-7 | End-user functionality and performance require real native provider-backed acceptance; synthetic checks are development aids only. | RATIFIED |
| D-8 | Combat recovery preserves valid legacy interaction while new encounters use the repaired structured agentic contract unconditionally. | RATIFIED |

Open owner decisions: none for this migration design.

No merge, deployment, or production-code change is part of this work. After review convergence, the
controller stops and presents the migration plan to the owner for explicit execution approval.
