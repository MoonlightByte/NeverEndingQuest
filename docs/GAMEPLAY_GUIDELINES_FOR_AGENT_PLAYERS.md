# GAMEPLAY GUIDELINES FOR AGENT PLAYERS (codex-ps / codex-wsl)

ATTACH THIS DOCUMENT TO EVERY PLAYTHROUGH BRIEF. It exists because the first alpha
pass played like a silent auditor, not a player, which manufactured false "systemic
defects" (level-up broken, finale unwinnable) that dissolved under forensics.
You are a PLAYER first, a tester second. Owner doctrine: deaths and reloads are
game-making 101, not bugs; the player screen is the correction mechanism.

## Prime directive
PLAY TO WIN THE CAMPAIGN THE WAY A HUMAN WOULD: fight the fights, earn XP, level up,
buy gear, rest, and finish the story at an appropriate level. The owner completed
Thornwood at level 3. If you finish at level 1 having bypassed most combat, YOUR PLAY
is the anomaly, not the game.

## Rules of play

1. FIGHT THE ENCOUNTERS. Do not route around combat to avoid risk. Peaceful
   resolutions are legitimate when the scene offers them, but a lineage that bypasses
   most XP-bearing encounters starves progression and invalidates difficulty findings.

2. TRACK YOUR XP AND ASK TO LEVEL. Watch the XP readout (e.g. [XP:296/300]). The
   moment a character crosses the threshold, SAY SO ON THE PLAYER SCREEN in plain
   language: "Alaric has 300 XP - he needs to level up." Complete the entire level-up
   conversation. This mechanic was NEVER tested in the first alpha because nobody
   asked. Testing level-up is mandatory in every future run.

3. USE THE PLAYER SCREEN TO CORRECT THE DM - IMMEDIATELY, IN CHARACTER-ADJACENT PLAIN
   LANGUAGE. When narration contradicts state ("Bex is down!" while her sheet says
   4 HP; wrong time of day; an item you bought missing from inventory; a modifier
   omitted from a roll), tell the DM: "You got that wrong - Bex is at 4 HP, not
   unconscious." Then record BOTH the error AND whether your correction took.
   - Visible error + correction accepted = the system working (log as D2, not a bug).
   - Correction refused, ignored, or impossible = a real defect. Cite the turn.
   - NEVER silently log an on-screen error and continue. That destroys the evidence
     of whether the correction loop works.

4. DEATHS ARE OUTCOMES, NOT BUGS. A PC or companion dying means the fight was
   dangerous. First try in-fight responses a player would try: heal, stabilize,
   retreat, drag to safety. Reloading a save afterward is a legitimate player choice.
   Report a death-scene defect ONLY if the mechanics around it misbehave (prompted
   while unconscious, Load intercepted, death saves absent).

5. LIMIT RETRIES: THREE STRIKES, THEN CHANGE STRATEGY. If you fail the same encounter
   3 times, do what a human does: go earn XP and level up, buy healing potions and
   gear, take a long rest, recruit help, or approach differently. Do NOT grind the
   same fight dozens of times - 40 retries of an underleveled finale is not play, and
   heavy retry loops contaminate state (duplicate encounter IDs, roster residue,
   stale restore context) in ways that pollute findings.

6. PLAY THE FULL RESOURCE GAME. Buy and CARRY healing potions (confirm they land in
   inventory, not storage - correct the DM if not). Use class features (Second Wind,
   spells) and VERIFY their effect on the sheet. Take short and long rests and verify
   HP/time actually changed. These flows carried real defects the first time; they
   must be exercised, on-screen-verified, and corrected-when-wrong every run.

7. ONE COMMAND PER AUTHORITATIVE PROMPT. Wait for the actual player prompt before
   sending input. Input raced ahead of the prompt is your timing error, not a bug.

8. ALPHA MODE: NEVER STOP THE CAMPAIGN. Work around blockers, reload past deaths,
   document everything with transcript citations (file + line/seq), and keep going to
   campaign completion. Stop only for a true hard block (crash/corruption with no
   path forward), and say exactly why.

9. EVIDENCE DISCIPLINE. For every finding: cite the exact transcript turn, state what
   the authoritative state said vs what was narrated/committed, and classify honestly:
   mechanic-defect / visible-error-corrected / design-working / my-play-choice /
   repeat-induced. Distrust your own narrative; the transcripts are the record.

10. STANDING CONSTRAINTS (unchanged): real live play only - NO synthetic injection,
    NO state edits, NO prompt-shopping (reload+retry IS allowed); official modules;
    OpenAI-only provider; ASCII-only in anything you write; config.py never committed.

## What "good play" looks like (checklist per campaign)
- [ ] Majority of authored combat encounters actually fought in the completed lineage
- [ ] At least one level-up requested and completed when threshold reached
- [ ] At least one visible DM error corrected via the player screen (log the outcome)
- [ ] Potions bought AND carried AND used; effect verified on sheet
- [ ] Short rest + long rest taken; HP/time verified
- [ ] Class features used; resource decrement AND effect verified
- [ ] Campaign completed; final level appropriate to content (Thornwood: ~level 3)
- [ ] No encounter retried more than 3x without a strategy change
