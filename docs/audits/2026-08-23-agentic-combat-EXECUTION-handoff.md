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
1. Push both branches to origin (currently local-only).
2. Codex (native Windows + Gemma/LM Studio) runs the AUTHORITATIVE per-slice acceptance matrix; Claude
   runs OpenAI/WSL and reviews Codex's diffs (the #193 dual-agent split).
3. Real acceptance needs a copied live campaign (party_tracker.json + modules/ from the main working
   dir; gitignored, never committed) + config.py copied in, driven via `run_headless.py serve`.
4. Read the converged plan (design branch) + live #193 before each session; re-verify branch/ancestry.
