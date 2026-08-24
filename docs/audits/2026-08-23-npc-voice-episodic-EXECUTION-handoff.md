# NPC Voice + Episodic Memory — Execution Handoff (2026-08-23)

Operational handoff so multiple agents can work off the repo. This is the OFFICIAL public branch
for the NPC voice / companion-memory line of work. It is SEPARATE from the combat line
(`design/agentic-combat`) — do not cross the two.

## Official branch
- **`integration/npc-voice-episodic`** (public on origin, off current `origin/main` = 691b5a2f;
  tip `05465285`). Contains the integrated NPC line of work:
  - **NPC voice redesign** — enriched say/do/want advisory voices fed to the DM (luna micro-calls).
  - **Companion episodic memory W1-W5** — location-aware retrieval, combat capture + R8 near-death,
    rolling capture, backfill for existing games, seamless upgrade UX.
  - **Travel-gate fix #194** — module-global fail-closed atlas gate + contradictory-validator loop
    root-caused and fixed (T1-T4, commits `767a7237..05465285`); real-headless acceptance passed;
    residual contradictory-validator path tracked as issue **#195**.

## Component branches (also on origin)
- **`feature/npc-voice-redesign`** (`40139e6b`) — voice redesign component; **open PR #163**.
- **`feature/npc-episodic-memory`** (`aca5ba15`) — episodic memory W1-W5 component.

## Status (per the on-branch spec docs; re-verify before relying)
- Voice: P0-P2e implemented + P3 OOC live acceptance PASS; **P4 agentic-combat wiring / P5
  campaign_manager lifecycle / P6 luna-confirm / P7 ship REMAIN**.
- Episodic: W1-W5 committed + live acceptance PASS on real Keep_of_Doom.
- **Voice grounding guard still needs a dedicated live-verification pass.**
- Detailed design/status live in this branch's spec docs (companion episodic-memory master spec;
  npc voice plan) and the NPC memory structural map audit.

## Owner constraints
- **Do NOT merge yet** — owner playtests the voice branch first. No PR merge without owner approval.
- Keep NPC work OFF the combat branch (`design/agentic-combat`) and vice-versa.
- config.py is gitignored — never commit it. (A key was exposed historically + rotated; do not
  reintroduce secrets.)

## For agents picking this up
Work off `integration/npc-voice-episodic` (or a component branch for focused work); read live
issue #193 + the on-branch spec docs first; run real headless/live acceptance (no synthetic tests);
push here, never onto the combat branch.
