# Single-source agent guidelines design

## Purpose

Make the repository-root `AGENTS.md` the one authoritative policy for every agent working on
NeverEndingQuest. Eliminate duplicated behavioral rules in tool-specific memory so a fresh Claude,
Codex, or other repository-aware agent receives the same current instructions.

This change governs development process only. It does not alter game code, prompts, schemas,
configuration, tests, models, providers, or deployment.

## Canonical source and precedence

`AGENTS.md` is the canonical source. Tool-specific project memories may retain project history and
current status, but their guideline files must contain only a pointer to `AGENTS.md`; they must not
copy or paraphrase its rules. When a guideline changes, only `AGENTS.md` is edited.

The existing `feedback_dev_rules_from_week_retrospective.md` Claude memory becomes a short pointer
that says to read the complete repository `AGENTS.md` before design, diagnosis, review, coding, or
acceptance work. The Feedback entry in Claude's memory index remains a pointer, not a second ruleset.

## Required policy structure

The existing project-specific sections remain intact:

- agentic-first semantic resolution;
- headless, on-disk gameplay acceptance;
- inspect reality before making claims;
- preserve proven legacy behavior during refactors;
- repository, test, commit, and security conventions.

A new canonical engineering-discipline section incorporates the corrected retrospective rules.
It is organized by work phase so an agent can apply it as a checklist rather than interpret a long
historical narrative.

### 1. Restart and inherited-work safeguard

Before resuming any paused, compacted, handed-off, or previously designed work, the agent must:

1. read `AGENTS.md` completely;
2. read the current workstream's design, plan, handoff, and acceptance criteria completely;
3. identify the exact branch, commit SHA, worktree, Python version, provider, model, endpoint, and
   mutable game root relevant to the work;
4. inspect the current implementation and runtime evidence rather than assuming the document is
   current;
5. reconcile contradictions and stale decisions before editing.

The design document is the authority for approved intent and decisions. Current code and runtime
evidence are the authority for what actually exists and occurs. A stale design is updated or marked
historical; work does not silently continue from it.

Each workstream should have one current design document. Superseded designs are retained as history
but clearly marked superseded and linked to the current document. An agent does not create a second
competing design to avoid resolving disagreements in the first.

### 2. Complete intent and compatibility map before proposals

Before proposing or implementing a change, map the complete existing behavior that the change can
affect:

- the last known working implementation and relevant Git history;
- every direct, indirect, dynamic, and entry-point consumer of the symbol family;
- callers, callees, callbacks, locks, ordering, side effects, and failure paths;
- authoritative state, advisory indexes, caches, persisted formats, migrations, and recovery;
- player-visible UI, narration, debug output, and responsive behavior;
- platform, provider, model, and interpreter variants;
- backward-compatibility obligations for existing games, saves, modules, and configuration.

Write the behavioral invariants before proposing the solution: identity, authoritative source,
desired end state, allowed failure state, and what must never happen. A shared invariant belongs at
a common boundary only when every caller has the same contract; caller-specific behavior must not
be flattened merely to centralize code.

### 3. Preserve and expand working functionality

Bug fixes and features must preserve proven working functionality and documentation outside the
explicitly authorized change. The default is to expand the existing capability and add the
technical depth needed at the correct layer, not to delete behavior as a shortcut.

"Technical depth" means stronger semantics, state reconciliation, compatibility, failure handling,
or evidence. It does not mean adding machinery for its own sake. Simpler replacement architecture is
preferred when it preserves or improves the behavioral contract and removes a proven liability.

Removal is permitted only when one of these is documented:

- the owner explicitly authorized removal or deprecation;
- the behavior is proven dead, unsafe, contradictory, or the root of the defect;
- a replacement preserves or improves every required contract, including migration and backward
  compatibility;
- legal or security requirements require removal.

Documentation is updated rather than erased when it contains useful design history. Superseded
material is labeled historical and points to its replacement.

### 4. Agentic-first, reconciled by deterministic code

Semantic decisions over natural language are agentic-first wherever a model can evaluate the real
state and return structured facts. Code does not recover meaning through keyword, verb, substring,
shape, or regex heuristics.

Deterministic code continues to own arithmetic, conservation, canonical identity, authorization,
existence and ownership checks, ordering, atomicity, persistence, and final refusal. Invalid gameplay
actions are refused through narration. This is expansion of the existing agentic-first doctrine, not
permission to move deterministic integrity responsibilities into a model.

### 5. Evidence and claim discipline

Every decision-bearing claim is labeled by evidence:

- **OBSERVED**: reproduced in runtime, logs, or authoritative on-disk state;
- **CODE-PROVEN**: conclusively established by the complete call path or invariant;
- **HYPOTHESIS**: plausible but not yet verified.

Reports are evidence inputs, not automatic conclusions. Independently verify claims that determine
severity, scope, architecture, or completion. Code that could perform an action is not proof that it
did. When a claim collapses, re-derive the conclusion from evidence rather than relocating it to a
neighboring issue.

Environment attribution requires differential or direct evidence. Suspected security, corruption,
and compatibility risks may receive provisional severity when the reasoning and uncertainty are
explicit.

### 6. Acceptance before implementation

Define acceptance before coding at the layer where the bug or feature lives. Development aids such
as compile, import, pure-function, and isolation checks are never reported as production acceptance.

Use deterministic byte comparisons only for deterministic emissions. For model-mediated behavior,
judge structured facts, state transitions, identities, conservation, ordering, and on-disk results.
UI changes require real browser verification in addition to the headless state proof applicable to
gameplay seams.

Acceptance reports distinguish `PASSED`, `FAILED`, `BLOCKED`, and `NOT REACHED`. They record the
exact SHA, environment, commands, negative controls, and evidence paths. An operation that never
reached a boundary cannot prove that boundary.

### 7. Fail-forward and fail-closed boundaries

Recoverable play paths fail forward so a valid existing game remains usable. Unsafe commit,
authorization, corruption, and ambiguity boundaries fail closed before mutation. A refusal is
delivered as narration for gameplay, not as silent corruption or a raw system error.

At an atomic commit point, a landed success must never escape as a failure. Post-commit fallible
steps are contained, logged, and given explicit self-healing or recovery semantics. Failure injection
covers each fallible pre- and post-commit step. The failure path is part of the feature.

### 8. Isolated execution and one acceptance unit at a time

Use one mutable game root, one server, and one acceptance operation at a time unless the test itself
explicitly exercises concurrency. Record process IDs and ports, and stop or await the previous
operation before starting another. Use a fresh isolated worktree or clone when branch or platform
provenance could be ambiguous.

Implement one independently testable acceptance unit at a time. Coupled changes remain one unit when
splitting them would create an unsafe intermediate state. Establish a rollback point only from
agent-owned changes; never commit, stash, reset, or overwrite unrelated user work.

### 9. Mechanism, decisions, and mechanical checks

Every mechanism answers either an observed failure or an explicit evidence-supported invariant,
security threat, or compatibility requirement. Open design decisions are resolved before coding
toward a preference. Do not proactively reshape a working path when a reactive, no-op-on-success
solution satisfies the requirement.

Before commit, review the exact staged diff and run the applicable mechanical checks: diff extent,
`git diff --check`, line-ending and encoding changes, ASCII-only added production text, banned prose
matching and hash-authority patterns, dangling references, secrets, configuration, and unintended
generated artifacts.

### 10. Secret, model, and artifact hygiene

Never print credentials into tool output, logs, screenshots, comments, or evidence. Keep local
configuration untracked and sanitize shared excerpts. Treat any exposure as compromised and report
the need for rotation without reproducing the secret.

Do not download, load, unload, switch, or reconfigure models unless explicitly authorized. Record the
approved model and endpoint used for real calls. Place evidence in a named, scoped directory; measure
large artifact growth and remove only agent-owned artifacts after evidence is preserved or the owner
authorizes cleanup.

## Migration and validation

Implementation changes only documentation:

1. Extend `AGENTS.md` with the canonical engineering-discipline section.
2. Replace Claude's duplicate retrospective feedback file with a pointer to `AGENTS.md`.
3. Update Claude's Feedback index entry so it identifies `AGENTS.md` as canonical.
4. Do not alter unrelated project-history memories in this change; stale project state is a separate
   maintenance task and must not be mixed into the guideline migration.

Validation consists of direct reads proving that the complete rules exist once in `AGENTS.md`, the
Claude feedback file contains no duplicate rules, the index points to the canonical source, Markdown
renders cleanly, the diff contains only the intended documentation, and no game files changed.

No merge, deployment, or production-code change is part of this work.
