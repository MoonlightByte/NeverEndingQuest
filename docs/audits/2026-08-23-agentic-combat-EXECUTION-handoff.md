# Agentic Combat — Execution Handoff (2026-08-23)

Operational handoff for continuing/testing the combat-only agentic-combat build. Not a design
doc: the design authority is the converged plan (see below) + live issue #193.

## Branches
- **`design/agentic-combat`** (SHARED — pushed to origin, off `origin/main`) — THE combat handoff
  branch. Contains: `docs/design/agentic-combat-design.md` (design), `docs/design/agentic-combat-
  implementation-plan.md` (798-line combat-only plan, SHA-256 `48418037...`), the Slice-1
  implementation foundation (combat_state.py provenance/controller helpers + sceneFacts guard), and
  this handoff doc. Push combat work HERE. Do NOT push any NPC-voice/episodic work here.
- **`design/agentic-combat-integration`** (LOCAL ONLY — do NOT push) — the older NPC voice+episodic
  lineage (~45 unmerged commits) the combat plan was originally authored on; superseded as the combat
  home by `design/agentic-combat`. The shelved 1,107-line Codex plan expansion lives there at
  `docs/audits/agentic-combat-plan.CODEX-EXPANDED-9e8f8946.shelved.md`.
- **`combat/agentic-impl`** (LOCAL) — Claude's working branch; its combat commits are rebased onto
  and pushed to `design/agentic-combat`. Continue combat work here and push to the shared branch.

## Owner AC rulings (2026-08-23, binding)
- **AC-D0 harness:** use `run_headless.py serve` (shipped headless mode). Do NOT track any harness.
- **Schema fields:** approve the reviewed combat/encounter field table AS WRITTEN, but ABSENCE-SAFE:
  additive/optional only; an old game/encounter WITHOUT the fields must NEVER break; **NO migration
  script** (existing encounters are complete, stay as-is). Enforced via three-way provenance
  (absent contractVersion -> legacy adapter). Verified safe: encounter schema has no
  `additionalProperties:false` at root/combatState/creatures.
- **Env division:** Claude runs OpenAI-on-WSL headless+live. Gemma (LM Studio absent) and native
  Windows are BLOCKED in Claude's env -> Codex's authoritative acceptance pass.
- **Acceptance provider update (2026-08-24):** Gemma is not available for this implementation.
  The owner directs all combat acceptance to the configured real OpenAI provider on native Windows,
  using shipped `run_headless.py serve` plus both live browser surfaces (legacy `/` and React
  `/play/`). Gemma unavailability no longer blocks combat checkpoint commits.
- **AC-D11 DROPPED** ("AC-D11 is stupid"): NO token limits, NO rate throttling; full token access;
  player experience first, optimization later. (Consistent with #193 no-max_tokens.)

## Spun-out (NOT in this plan) — independent issues
#200 companion-memory persistence · #201 crash-safe Save/Load/Reset · #202 busy-lock/D-6 debt ·
#203 terminal out-of-turn input · #204 build/startup liveness + cross-process build cancellation (under #186).

## #193 execution constraints (do not violate)
- Acceptance = real headless/live play, ONE operation at a time; NEVER fan out acceptance to
  subagents. Subagents legal for reads/research + review only.
- Single-writer per file. Per slice: implement -> real acceptance -> commit -> next. Slice N+1
  depends on Slice N being actually accepted.
- No synthetic/monkeypatched/simulated-player tests as acceptance. Backend content-free logic
  checks are dev aids only. config.py is gitignored — NEVER commit it.

## Build state
- **Task 0 DONE:** clean base (`combat/agentic-impl` off 691b5a2f), harness runs (exit 0).
- **Slice 1 IN PROGRESS — foundation committed (DORMANT, not yet wired):**
  - `combat_state.combat_provenance()` (typed/pre_typed/legacy; absent=legacy) — content-free 10/10.
  - `combat_state.resolve_creature_controller()` (typed participant -> human/actor_agent; type fallback).
  - `ensure_combat_state` absence-safe sceneFacts guard (malformed/unknown-version -> recovery_required;
    absent untouched) — content-free 4/4.
- **Slice 1 REMAINING:** wire provenance/controller into the activation path (combat_builder /
  ensure_combat_state) + orchestrator player-stop/roll-ownership; have `createEncounter` emit the typed
  participant manifest (prompts) + `reconcile_scene_manifest`; run ONE NPC attack through the atomic
  claim->freeze->atom->commit path; recovery-conflict path; then REAL headless acceptance (live NPC
  attack + legacy A/B proving an old encounter plays unchanged + kill/restart). Only then does Slice 1
  commit as accepted (not WIP).
- **Slices 2-8 + Task 9 gate:** pending, per the plan's per-slice tables.

## To continue / hand to Codex
This original handoff checklist is superseded by the 2026-08-24 checkpoint below. The shared
`design/agentic-combat` branch is public and is the only branch to push. The local integration branch
must remain local, and the owner has replaced Gemma acceptance with configured real OpenAI acceptance
on native Windows.

1. Continue and push combat-only checkpoints on `design/agentic-combat`.
2. Run the authoritative per-slice matrix with the configured real OpenAI provider on native Windows.
3. Real acceptance needs a copied live campaign (party_tracker.json + modules/ from the main working
   dir; gitignored, never committed) + config.py copied in, driven via `run_headless.py serve`.
4. Read the converged plan (design branch) + live #193 before each session; re-verify branch/ancestry.

## Native-Windows OpenAI checkpoint (2026-08-24)

This checkpoint was executed on `design/agentic-combat` from pre-commit revision
`7d1a1b3534359ae0b2c7549ec0a4fbc2f14c5e3a`; `origin/main` was
`691b5a2f06b472e31c7a123964844d9506862535` and was verified as an ancestor. Live issue #193 was
OPEN, protocol v1.7, `updatedAt=2026-08-24T05:39:19Z`. Platform/provider were native Windows and
the configured real OpenAI provider. Browser acceptance used port 8368 because 8358 was occupied by
another agent.

### Frostmere acceptance fixture

The historical Frostmere runtime copy contained stale root-tracker state (`A01/FV001`) from the old,
unsuccessful campaign while the module-local tracker and canonical `FV001.json` identify Frostbound
Guildhall as `AJ01/FV001`. Per owner ruling, this was repaired only in an ignored copied acceptance
fixture. No production location code or source campaign file was changed.

- Fixture helper/test (ignored): `.superpowers/local-tests/combat/prepare_frostmere_fixture.py` and
  `.superpowers/local-tests/combat/test_prepare_frostmere_fixture.py`.
- Prepared fixture (ignored):
  `validation_evidence/agentic_combat/slice1/baseline-native-windows-frostmere-fixed/game`.
- Result manifest (ignored):
  `validation_evidence/agentic_combat/slice1/baseline-native-windows-frostmere-fixed/fixture-preparation-result.json`.
- Fresh verification: 5 fixture tests passed; fixed-copy validation exited 0; the unmodified stale
  source negative exited 2 before any provider call; all 278 source relative paths, hashes, sizes,
  and mtimes matched before/after; provider calls were zero.

### Full-combat acceptance and complete transcripts

- Headless, exit 0, combat observed and completed:
  `validation_evidence/agentic_combat/slice1/headless-openai-full-combat-r7/combat-transcript.md`.
- Exact command:
  `python .superpowers/local-tests/combat/run_headless_full_combat.py validation_evidence/agentic_combat/slice1/headless-openai-full-combat-r7/game validation_evidence/agentic_combat/slice1/headless-openai-full-combat-r7`.
- Raw result: `validation_evidence/agentic_combat/slice1/headless-openai-full-combat-r7/result.json`
  (`combat_seen=true`, `combat_complete=true`, 8 transcript entries, 2,567 delivered DM characters).
- React `/play/`, exit 0, real human controller/initiative, combat completed:
  `validation_evidence/agentic_combat/slice1/browser-react-openai-full-combat-r9/combat-transcript.md`.
- Exact command:
  `.superpowers/local-tests/combat/run_browser_combat.ps1 -Surface react -GameDir validation_evidence/agentic_combat/slice1/browser-react-openai-full-combat-r9/game -EvidenceDir validation_evidence/agentic_combat/slice1/browser-react-openai-full-combat-r9 -Port 8368`.
- Raw result/progress: `result.json` and `harness-progress.jsonl` in that evidence directory
  (`combatComplete=true`, `playerActive=true`, no blocking request failures).
- Legacy `/`, exit 0, real human controller/current turn, combat completed:
  `validation_evidence/agentic_combat/slice1/browser-legacy-openai-full-combat-r6/combat-transcript.md`.
- Exact command:
  `.superpowers/local-tests/combat/run_browser_combat.ps1 -Surface legacy -GameDir validation_evidence/agentic_combat/slice1/browser-legacy-openai-full-combat-r6/game -EvidenceDir validation_evidence/agentic_combat/slice1/browser-legacy-openai-full-combat-r6 -Port 8368`.
- Raw result/progress: `result.json` and `harness-progress.jsonl` in that evidence directory
  (`combatComplete=true`, `playerActive=true`, no blocking request failures).

Each transcript records every player submission and the complete delivered DM output. The legacy
browser harness needed one ignored, structural observation fix after two failed runs: it now samples
`player-turn` versus `complete` atomically instead of racing across separate DOM reads. No production
browser code changed for that correction.

Observed, still-open quality findings are not hidden: player actions are sometimes narrated in third
person rather than second person, raw duplicate display names such as `Snow Rat_2`/`Snow Rat_3` reach
player prose, and this old Frostmere fixture lacks several portrait/video/monster media files, causing
browser 404s. These do not invalidate the invocation checkpoint but prevent claiming Slice 1 complete.

### Overlapping invocation checkpoint

Production rollback point: `7579fad2` (`fix(combat): reject overlapping invocation dispatch`).

`core/combat/invocation.py` now allocates the contender's logical/attempt identity before structural
waiting and prevents a contender submitted behind a live invocation from gaining later dispatch
authority. This overlap rejection attaches the contender claim to `InvocationSupersededError` for
auditable identity evidence.
An invocation delayed only by Load/Reset fencing may still proceed after that barrier; this change is
specific to overlapping logical combat operations.

- Content-free development suite: `python -m pytest .superpowers/local-tests/combat -q` ->
  `52 passed in 2.10s`.
- Real same-state OpenAI command:
  `python .superpowers/local-tests/combat/run_same_state_openai.py validation_evidence/agentic_combat/slice1/browser-legacy-openai-full-combat-r6/game validation_evidence/agentic_combat/slice1/same-state-openai-r7/game validation_evidence/agentic_combat/slice1/same-state-openai-r7`.
- Result: process exit 0; contender rejected with distinct logicalInvocationId/attemptId/generation;
  exactly one T096 attempt; one accepted/committed turn; restart action
  `deliver_committed_events`; no contender dispatch.
- Compact raw result:
  `first.generation=1; contender={rejected:true,generation:2}; t096AttemptCount=1; committedEventCount=1; restartAction.action=deliver_committed_events`.
- Complete same-state transcript:
  `validation_evidence/agentic_combat/slice1/same-state-openai-r7/transcript.md`.
- Raw result and call evidence:
  `validation_evidence/agentic_combat/slice1/same-state-openai-r7/result.json` and
  `agentic_attempts.jsonl` in the same directory.

The unrelated user-owned `web/frontend/src/components/party/party.test.tsx` worktree modification was
not edited or staged.
