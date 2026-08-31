# Replay Test Plan - what the first alpha DID NOT test (2026-08-30)

Companion to: docs/audits/2026-08-30-thornwood-play-forensics-consolidated.md.
Player conduct rules for these runs: docs/GAMEPLAY_GUIDELINES_FOR_AGENT_PLAYERS.md
(attach it to every brief). Tip under test: 46f0269c (integration/premerge-214-combat)
unless the owner designates a newer tip.

The forensics proved the first alpha never exercised several core mechanics because of
the agent's play style. These are UNTESTED, not broken. The replay's job is to test
them by actually playing well.

## R1. Level-up, player-initiated (TOP PRIORITY - never tested anywhere)
Play Thornwood (or Pumpkin King) fighting the XP-bearing encounters so a character
actually crosses 300 XP DURING play. Then, on the player screen, request advancement
in plain language ("Alaric has 300 XP - level him up") and complete the full level-up
conversation.
- PASS: the levelUp flow runs, the sheet shows level 2 with correct HP/features, and
  play continues cleanly afterward.
- FAIL: request refused/ignored, flow crashes, or sheet state wrong afterward - THAT
  would finally be a real level-up defect. Cite the turns.

## R2. Plot-triggered levelUp (PK-023 residue - design question + test)
Pumpkin King's module_plot.json instructs a levelUp after PP005/PP007. Verify during a
PK replay whether anything emits it automatically when those plot points complete.
NOTE: whether auto-fire SHOULD happen is an OWNER design ruling (milestone-style
auto-level vs conversation-initiated). Test observes current behavior; do not "fix"
either way without the owner's mechanical direction.

## R3. Player-screen correction loop (never exercised - 534/534 inputs were actions)
During replay, when a VISIBLE DM error occurs (wrong HP in narration, wrong time,
item not in inventory, omitted modifier), correct it conversationally and record
whether the correction takes effect in both narration and authoritative state.
- The first alpha logged such errors silently (e.g. false "Bex at 0 HP") and moved on,
  so we have ZERO evidence about whether the correction loop works. This is the
  game's designed error-recovery path; it needs coverage more than any single fix.

## R4. Fresh no-retry NC05 roster comparison (TW-F42 disposition)
The Malarok-only roster appeared only after ~40 reload/retries; authored context says
Malarok + 2-4 bodyguards + 2-4 wolves. In a FRESH campaign with minimal retries,
trigger NC05 and record the materialized roster 2-3 independent times (fresh saves,
not reload-grinding). If fresh rosters always land in authored range, TW-F42 is
confirmed retry-context residue (repeat-induced defect); if fresh rosters also
collapse, it is a materialization defect. Either way it becomes actionable.

## R5. Rest + class-feature state commits (defects filed; needs honest re-exercise)
Second Wind (TW-F31), short rest (TW-F37), long rest (TW-F39) all showed narration
without state commit. In replay, exercise each deliberately, verify the sheet/clock
on-screen, and CORRECT the DM when it diverges (per R3) - we need to know whether
the player screen can repair these live, which changes their severity.

## R6. In-fight rescue behavior at 0 HP (informs the owner's death-scene design)
When a companion or the PC drops, first attempt what a player would: healing potion,
stabilize, drag to safety, retreat. Record exactly what the DM/engine allows and
refuses. This is EVIDENCE-GATHERING for the owner's pending mechanical direction on
death (do not design; observe and report).

## R7. Pumpkin King forensic pass (parity with Thornwood)
The PK ledger (PK-001..PK-042 at /mnt/c/pkev/BUG_LEDGER.md) has NOT had the
transcript-level reclassification Thornwood got. Run the same forensic review
(classification key + evidence rules in the consolidated doc) against the PK
transcripts/state at /mnt/c/pk004f3 before treating any PK finding as a defect.
The one row already reclassified: PK-023 -> UNTESTED-CLAIM (and its on-disk premise
is unconfirmed: rowan_ash.json reads 100/300, not 300/300).

## Assignment sketch (owner confirms before dispatch)
- codex-ps (native Windows player): R1 + R3 + R5 + R6 in one well-played Thornwood
  replay under the gameplay guidelines; R4 as a separate short fresh-campaign probe.
- codex-wsl: R7 (PK forensic pass, read-only) first; then R2 inside a PK replay.
- All runs: real OpenAI, official modules, evidence per #193; ledger entries classify
  honestly per the guidelines (mechanic-defect / corrected / design-working /
  play-choice / repeat-induced).
