# Agentic Combat Provenance and Controller Acceptance

Date: 2026-08-24

Branch: `design/agentic-combat`

Provider: real OpenAI production routing (`gpt-5.6-luna` observed)

Browser port: `8368` (isolated from the other agent on `8358`)

Candidate base before this chunk: `6784a6274d5c7cae979523fb0a8dab2ce1a03624`

Live `origin/main`: `691b5a2f06b472e31c7a123964844d9506862535` (verified ancestor of the candidate base)

This handoff records the complete player/DM transcript captured for each
three-way provenance and reversed-controller acceptance run. Raw ignored
results, traces, screenshots, server logs, and authoritative game trees remain
under the evidence directories named below.

## Result matrix

| Surface | Scenario | Persisted result | Verdict |
| --- | --- | --- | --- |
| Headless | Reversed controller | typed; player actor agent-controlled; enemy actor human-controlled | PASS |
| React | Reversed controller | `pipelineMode=agentic`, `sceneFacts` retained; Snow Rat shown as current human actor | PASS |
| Legacy UI | Reversed controller | `pipelineMode=agentic`, `sceneFacts` retained; Snow Rat shown as current human actor | PASS |
| Headless | Pre-typed agentic | provenance remained `pre_typed`; no typed scene rewrite | PASS |
| React | Pre-typed agentic | `pipelineMode=agentic`; `sceneFacts` remained absent | PASS |
| Legacy UI | Pre-typed agentic | `pipelineMode=agentic`; `sceneFacts` remained absent | PASS |
| Headless | Legacy | provenance remained `legacy`; no typed scene rewrite | PASS |
| React | Legacy | `pipelineMode=legacy`; `sceneFacts` remained absent | PASS |
| Legacy UI | Legacy | `pipelineMode=legacy`; `sceneFacts` remained absent | PASS |

## Legacy readiness defect found and fixed

The first legacy reversed-controller run reached the real human combat prompt
but remained visually stuck on `Starting...`. The engine writes `input(prompt)`
without a newline; `WebOutputCapture` only recognized completed prompt lines, so
the legacy-only `game_started` fallback never fired. React derived playability
from status state and therefore did not expose the adapter defect.

`WebOutputCapture` now recognizes the same authoritative HP/XP prompt while it
is buffered. A focused red/green test proves the no-newline case, and the final
legacy reversed-controller browser run reached `Game Running`, accepted the Snow
Rat command, and persisted its mechanics.

## Complete transcripts

### Headless - reversed controller

Raw evidence: `validation_evidence/agentic_combat/slice1/headless-openai-reversed-controller-r2/`

#### Dungeon Master

The Frostbound Guildhall has fallen quiet again. Frost dusts the benches, overturned tankards lie scattered across the floor, and three snow rats lie defeated near the hearth. You stand with your mace lowered as Ranger Thane, Scout Elen, and Scout Kira catch their breath and scan the hall. What do you do next?

#### Dungeon Master

Eirik Hearthwise completes his combat action, but no target is affected and no visible change follows. The battlefield holds its breath as the turn passes onward.

#### Player

As the snow rat, I spring at Eirik's shield side and bite. I rolled 17 to hit and 4 piercing damage.

#### Dungeon Master

The snow rat springs at Eirik’s shield side, its teeth finding a gap as it bites him. Eirik remains standing, though the attack wounds him.

#### Dungeon Master

Eirik Hearthwise’s turn passes without a visible change in the fray. The battlefield holds its breath, awaiting his next command.


### Headless - pre-typed agentic

Raw evidence: `validation_evidence/agentic_combat/slice1/headless-openai-pretyped-r1/`

#### Dungeon Master

The Frostbound Guildhall has fallen quiet after the brief clash. Three snow rats lie defeated among overturned benches and scattered tankards, while the hearth throws warm light across the frost-dusted floor. Ranger Thane, Scout Elen, and Scout Kira remain alert, watching the doors and checking the room. You stand with mace in hand, breathing hard but steady. What do you do next?

#### Dungeon Master

The Snow Rat lunges at Scout Kira, but its teeth snap harmlessly short. Kira answers with a swift shot from her shortbow; the arrow strikes the Snow Rat, leaving it wounded but still standing. Eirik Hearthwise, it is your turn.

#### Player

I step inside the rat's lunge and strike with my mace. I rolled 18 to hit and 3 bludgeoning damage.

#### Dungeon Master

Eirik steps inside the Snow Rat’s lunge and brings his mace down hard, leaving the beast reeling but alive. Ranger Thane’s longbow sings next; the arrow strikes true and fells the Snow Rat. Scout Elen holds position and defends.

#### Dungeon Master

The guildhall is secure for the moment. The last snow rat lies beneath your mace, while scattered benches, overturned tankards, and claw marks testify to the sudden violence. The hearth crackles softly as the party regains its breath. Kira lowers her bow. "No more surprises, I hope." Elen scans the doors and shadowed corners. "The room is clear." Thane looks toward the damaged entrance and the slush beyond it. "Those tracks are still fresh." Eirik the Elder approaches from the council table, his expression grave. "We should discover what drove them here before the trail fades." The sealed watch notice remains nearby, untouched. What do you do next?


### Headless - legacy

Raw evidence: `validation_evidence/agentic_combat/slice1/headless-openai-legacy-r1/`

#### Dungeon Master

The Frostbound Guildhall has gone quiet after the brief clash. Three snow rats lie defeated among overturned benches and scattered tankards, while the hearth throws warm light across the frost-dusted floor. Ranger Thane, Scout Elen, and Scout Kira remain alert, bows lowered but ready. You stand with your mace in hand, breathing hard as the last echoes fade. What do you do next?

#### Player

I step inside the rat's lunge and strike with my mace. I rolled 18 to hit and 3 bludgeoning damage.

#### Dungeon Master

You step inside the rat's snapping jaws and bring your mace down hard. The blow cracks against its shoulder, sending frost and loose fur skittering across the guildhall floor. The beast recoils with a shrill screech, claws scraping against the timber boards, but it stays upright. The hearth pops behind you as your companions tighten their grips and watch the wounded creature. The next round is ready -- what do you do?

#### Dungeon Master

The rat's teeth snap against your shield and find no purchase. Then Kira's bowstring cracks like a rifle shot. Her arrow drives deep into the creature, folding it sideways across the frost-dusted boards as fur and splinters scatter beneath the benches. She keeps her bow trained for one tense breath, then glances to you. Kira: Finish it.


### React - reversed controller

Raw evidence: `validation_evidence/agentic_combat/slice1/browser-react-openai-reversed-r2/`

#### Dungeon Master

Dungeon MasterDM▶Generate ImageWelcome back! You stand in the Frostbound Guildhall, its hearth glowing against the chill of Frostmere Vale. Fresh slush tracks lead toward the eastern entrance, while a sealed watch notice rests on a nearby table. Scout Kira gives you a bright, knowing grin. "Back with us, Trouble Magnet?" Ranger Thane checks the hall in silence, and Scout Elen keeps her attention on the notice. The distant howls have not stopped, and the missing scout remains unaccounted for. What do you do next?

#### Player

⚔️YouI look around the guildhall and quietly assess the room.

#### Dungeon Master

Dungeon MasterDM▶Generate ImageYou quietly assess the Frostbound Guildhall. The hearth burns low but steady, throwing amber light across benches, training dummies, and frost-rimmed beams. Scout Kira keeps still beside you, while Thane watches the entrances and Elen studies the room's details. Near the eastern doorway, fresh slush tracks cross the floor and end beneath a bench. On the table nearby lies a sealed watch notice bearing the local guard mark. Nothing moves, and no immediate threat reveals itself, but the tracks and notice both feel recent.

Please make a Perception check. Roll 1d20 and add your Wisdom (Perception) modifier.

#### Player

⚔️YouI look around the guildhall and quietly assess the room.

#### Dungeon Master

Dungeon MasterDM▶Generate ImageYou move quietly through the Frostbound Guildhall, letting your eyes adjust to the hearth's amber glow and the pale light leaking through the frosted windows. The benches, training dummies, eastern entrance, and sealed watch notice reveal no obvious threat. Kira remains motionless beside you, Thane watches the doors, and Elen studies the floor and rafters with practiced patience.

Please make a Perception check. Roll 1d20 and add your Wisdom (Perception) modifier (+3).

#### Player

⚔️YouI quietly verify the guildhall exits and return to my place.

#### Dungeon Master

Dungeon MasterDM▶Generate ImageThe Frostbound Guildhall has fallen quiet again. Hearthlight glints across overturned benches and scattered tankards, while three defeated snow rats lie motionless on the frost-dusted floor. Ranger Thane, Scout Elen, and Scout Kira remain alert nearby, weapons lowered but ready. You stand amid the aftermath, mace in hand, with the brief clash still echoing beneath the vaulted beams. What do you do next?

#### Dungeon Master

Dungeon MasterDM▶Generate ImageEirik Hearthwise’s turn passes without a visible strike or spell, and the battlefield holds its breath. The Snow Rat remains poised to act next. What does Eirik do?

#### Player

⚔️YouAs the snow rat, I spring at Eirik's shield side and bite. I rolled 17 to hit and 4 piercing damage.

#### Dungeon Master

Dungeon MasterDM▶Generate ImageThe snow rat springs toward Eirik’s shield side and clamps its teeth into him. The bite lands, but Eirik remains standing behind his shield as the pain tears through his guard.


### Legacy UI - reversed controller

Raw evidence: `validation_evidence/agentic_combat/slice1/browser-legacy-openai-reversed-r3/`

#### Dungeon Master

--- Previous Session Messages ---

#### Dungeon Master

Dungeon MasterDM▶Generate ImageWelcome back! You stand in the Frostbound Guildhall, its hearth glowing against the chill of Frostmere Vale. Fresh slush tracks lead toward the eastern entrance, while a sealed watch notice rests on a nearby table. Scout Kira gives you a bright, knowing grin. "Back with us, Trouble Magnet?" Ranger Thane checks the hall in silence, and Scout Elen keeps her attention on the notice. The distant howls have not stopped, and the missing scout remains unaccounted for. What do you do next?

#### Player

⚔️YouI look around the guildhall and quietly assess the room.

#### Dungeon Master

Dungeon MasterDM▶Generate ImageYou quietly assess the Frostbound Guildhall. The hearth burns low but steady, throwing amber light across benches, training dummies, and frost-rimmed beams. Scout Kira keeps still beside you, while Thane watches the entrances and Elen studies the room's details. Near the eastern doorway, fresh slush tracks cross the floor and end beneath a bench. On the table nearby lies a sealed watch notice bearing the local guard mark. Nothing moves, and no immediate threat reveals itself, but the tracks and notice both feel recent.

Please make a Perception check. Roll 1d20 and add your Wisdom (Perception) modifier.

#### Player

⚔️YouI look around the guildhall and quietly assess the room.

#### Dungeon Master

Dungeon MasterDM▶Generate ImageYou move quietly through the Frostbound Guildhall, letting your eyes adjust to the hearth's amber glow and the pale light leaking through the frosted windows. The benches, training dummies, eastern entrance, and sealed watch notice reveal no obvious threat. Kira remains motionless beside you, Thane watches the doors, and Elen studies the floor and rafters with practiced patience.

Please make a Perception check. Roll 1d20 and add your Wisdom (Perception) modifier (+3).

#### Player

⚔️YouI quietly verify the guildhall exits and return to my place.

#### Dungeon Master

--- Current Session ---

#### Dungeon Master

Welcome to NeverEndingQuest. Press the button at the top right to begin. New here? Open Settings (gear icon) to pick your AI provider -- Legacy (GPT-4.1) is the recommended default.

#### Dungeon Master

Dungeon MasterDM▶Generate ImageThe Frostbound Guildhall has fallen quiet after the snow rats' sudden assault. Frost and dust drift across the battered floor, while the hearth crackles beneath the echo of departing claws. Ranger Thane, Scout Elen, and Scout Kira stand alert among the overturned benches, watching you for direction. What do you do next?

#### Dungeon Master

Dungeon MasterDM▶Generate ImageEirik Hearthwise’s turn passes without a visible strike, spell, or other change. The battlefield holds its breath as the next turn approaches.

#### Dungeon Master

Game started! You can now enter commands. Try things like: "look around", "talk to the innkeeper", "check my inventory", or "head north".

#### Player

⚔️YouAs the snow rat, I spring at Eirik's shield side and bite. I rolled 17 to hit and 4 piercing damage.

#### Dungeon Master

Dungeon MasterDM▶Generate ImageThe snow rat darts through the swirling snow and lunges at Eirik’s shield side. Its teeth find a gap in his guard, and he staggers beneath the bite, still standing.


### React - pre-typed agentic

Raw evidence: `validation_evidence/agentic_combat/slice1/browser-react-openai-pretyped-r1/`

#### Dungeon Master

Dungeon MasterDM▶Generate ImageWelcome back! You stand in the Frostbound Guildhall, its hearth glowing against the chill of Frostmere Vale. Fresh slush tracks lead toward the eastern entrance, while a sealed watch notice rests on a nearby table. Scout Kira gives you a bright, knowing grin. "Back with us, Trouble Magnet?" Ranger Thane checks the hall in silence, and Scout Elen keeps her attention on the notice. The distant howls have not stopped, and the missing scout remains unaccounted for. What do you do next?

#### Player

⚔️YouI look around the guildhall and quietly assess the room.

#### Dungeon Master

Dungeon MasterDM▶Generate ImageYou quietly assess the Frostbound Guildhall. The hearth burns low but steady, throwing amber light across benches, training dummies, and frost-rimmed beams. Scout Kira keeps still beside you, while Thane watches the entrances and Elen studies the room's details. Near the eastern doorway, fresh slush tracks cross the floor and end beneath a bench. On the table nearby lies a sealed watch notice bearing the local guard mark. Nothing moves, and no immediate threat reveals itself, but the tracks and notice both feel recent.

Please make a Perception check. Roll 1d20 and add your Wisdom (Perception) modifier.

#### Player

⚔️YouI look around the guildhall and quietly assess the room.

#### Dungeon Master

Dungeon MasterDM▶Generate ImageYou move quietly through the Frostbound Guildhall, letting your eyes adjust to the hearth's amber glow and the pale light leaking through the frosted windows. The benches, training dummies, eastern entrance, and sealed watch notice reveal no obvious threat. Kira remains motionless beside you, Thane watches the doors, and Elen studies the floor and rafters with practiced patience.

Please make a Perception check. Roll 1d20 and add your Wisdom (Perception) modifier (+3).

#### Player

⚔️YouI quietly verify the guildhall exits and return to my place.

#### Dungeon Master

Dungeon MasterDM▶Generate ImageThe Frostbound Guildhall has fallen quiet after the brief clash. Three snow rats lie defeated among overturned benches and scattered tankards, while the hearth crackles against the cold pressing through the colored windows. Ranger Thane, Scout Elen, and Scout Kira remain alert, bows lowered but ready. You stand amid the aftermath, mace in hand, with the guildhall once again secure. What do you do next?

#### Dungeon Master

Dungeon MasterDM▶Generate ImageThe Snow Rat lunges at Scout Kira and its teeth find their mark. Kira remains standing, though blood darkens the bite. She answers with a swift shortbow shot, driving an arrow into the Snow Rat and leaving it wounded but alive.

Eirik Hearthwise, it is your turn.

#### Player

⚔️YouI step inside the rat's lunge and strike with my mace. I rolled 18 to hit and 3 bludgeoning damage.

#### Dungeon Master

Dungeon MasterDM▶Generate ImageEirik steps inside the Snow Rat’s lunge and crushes it with his mace. Ranger Thane follows with a longbow shot that drives the creature back, and Scout Elen’s arrow finishes it. The Snow Rat collapses, dead.


### Legacy UI - pre-typed agentic

Raw evidence: `validation_evidence/agentic_combat/slice1/browser-legacy-openai-pretyped-r1/`

#### Dungeon Master

--- Previous Session Messages ---

#### Dungeon Master

Dungeon MasterDM▶Generate ImageWelcome back! You stand in the Frostbound Guildhall, its hearth glowing against the chill of Frostmere Vale. Fresh slush tracks lead toward the eastern entrance, while a sealed watch notice rests on a nearby table. Scout Kira gives you a bright, knowing grin. "Back with us, Trouble Magnet?" Ranger Thane checks the hall in silence, and Scout Elen keeps her attention on the notice. The distant howls have not stopped, and the missing scout remains unaccounted for. What do you do next?

#### Player

⚔️YouI look around the guildhall and quietly assess the room.

#### Dungeon Master

Dungeon MasterDM▶Generate ImageYou quietly assess the Frostbound Guildhall. The hearth burns low but steady, throwing amber light across benches, training dummies, and frost-rimmed beams. Scout Kira keeps still beside you, while Thane watches the entrances and Elen studies the room's details. Near the eastern doorway, fresh slush tracks cross the floor and end beneath a bench. On the table nearby lies a sealed watch notice bearing the local guard mark. Nothing moves, and no immediate threat reveals itself, but the tracks and notice both feel recent.

Please make a Perception check. Roll 1d20 and add your Wisdom (Perception) modifier.

#### Player

⚔️YouI look around the guildhall and quietly assess the room.

#### Dungeon Master

Dungeon MasterDM▶Generate ImageYou move quietly through the Frostbound Guildhall, letting your eyes adjust to the hearth's amber glow and the pale light leaking through the frosted windows. The benches, training dummies, eastern entrance, and sealed watch notice reveal no obvious threat. Kira remains motionless beside you, Thane watches the doors, and Elen studies the floor and rafters with practiced patience.

Please make a Perception check. Roll 1d20 and add your Wisdom (Perception) modifier (+3).

#### Player

⚔️YouI quietly verify the guildhall exits and return to my place.

#### Dungeon Master

--- Current Session ---

#### Dungeon Master

Welcome to NeverEndingQuest. Press the button at the top right to begin. New here? Open Settings (gear icon) to pick your AI provider -- Legacy (GPT-4.1) is the recommended default.

#### Dungeon Master

Dungeon MasterDM▶Generate ImageThe Frostbound Guildhall has fallen quiet after the brief clash. Frost-dusted benches stand askew, scattered tankards glint near the hearth, and three defeated snow rats lie motionless on the floor. Ranger Thane, Scout Elen, and Scout Kira remain alert while you steady your mace and survey the room. What do you do next?

#### Dungeon Master

Game started! You can now enter commands. Try things like: "look around", "talk to the innkeeper", "check my inventory", or "head north".

#### Dungeon Master

Dungeon MasterDM▶Generate ImageThe Snow Rat lunges at Scout Kira, but its teeth snap shut short of her. Kira answers with a swift shortbow shot, the arrow striking the rat and leaving it wounded but still standing. Eirik Hearthwise, it is your turn.

#### Player

⚔️YouI step inside the rat's lunge and strike with my mace. I rolled 18 to hit and 3 bludgeoning damage.

#### Dungeon Master

Dungeon MasterDM▶Generate ImageEirik Hearthwise steps inside the Snow Rat’s lunge and brings his mace down hard, leaving the creature battered but still alive. Ranger Thane looses an arrow, but it misses the Snow Rat. Scout Elen’s arrow strikes true, driving deep into the rat and leaving it barely standing.


### React - legacy

Raw evidence: `validation_evidence/agentic_combat/slice1/browser-react-openai-legacy-r1/`

#### Dungeon Master

Dungeon MasterDM▶Generate ImageWelcome back! You stand in the Frostbound Guildhall, its hearth glowing against the chill of Frostmere Vale. Fresh slush tracks lead toward the eastern entrance, while a sealed watch notice rests on a nearby table. Scout Kira gives you a bright, knowing grin. "Back with us, Trouble Magnet?" Ranger Thane checks the hall in silence, and Scout Elen keeps her attention on the notice. The distant howls have not stopped, and the missing scout remains unaccounted for. What do you do next?

#### Player

⚔️YouI look around the guildhall and quietly assess the room.

#### Dungeon Master

Dungeon MasterDM▶Generate ImageYou quietly assess the Frostbound Guildhall. The hearth burns low but steady, throwing amber light across benches, training dummies, and frost-rimmed beams. Scout Kira keeps still beside you, while Thane watches the entrances and Elen studies the room's details. Near the eastern doorway, fresh slush tracks cross the floor and end beneath a bench. On the table nearby lies a sealed watch notice bearing the local guard mark. Nothing moves, and no immediate threat reveals itself, but the tracks and notice both feel recent.

Please make a Perception check. Roll 1d20 and add your Wisdom (Perception) modifier.

#### Player

⚔️YouI look around the guildhall and quietly assess the room.

#### Dungeon Master

Dungeon MasterDM▶Generate ImageYou move quietly through the Frostbound Guildhall, letting your eyes adjust to the hearth's amber glow and the pale light leaking through the frosted windows. The benches, training dummies, eastern entrance, and sealed watch notice reveal no obvious threat. Kira remains motionless beside you, Thane watches the doors, and Elen studies the floor and rafters with practiced patience.

Please make a Perception check. Roll 1d20 and add your Wisdom (Perception) modifier (+3).

#### Player

⚔️YouI quietly verify the guildhall exits and return to my place.

#### Dungeon Master

Dungeon MasterDM▶Generate ImageThe Frostbound Guildhall has fallen quiet after the brief clash. Frost dusts the overturned benches, the hearth crackles beneath the vaulted beams, and three defeated snow rats lie still across the scarred floor. Ranger Thane, Scout Elen, and Scout Kira remain alert nearby while you stand with mace in hand, the danger passed. What would you like to do next?

#### Player

⚔️YouI step inside the rat's lunge and strike with my mace. I rolled 18 to hit and 3 bludgeoning damage.

#### Dungeon Master

Dungeon MasterDM▶Generate ImageThe surviving rat bursts from beneath the bench and lunges straight for you. Its teeth tear through your guard, and pain flares hot beneath your armor as the guildhall fills with a sharp squeal. Kira answers instantly. Her bowstring cracks, and the arrow punches into the rat's side, driving it back across the frost-dusted boards. It staggers, bleeding, but refuses to fall. Kira keeps her bow trained on it. "Finish it, Eirik."


### Legacy UI - legacy

Raw evidence: `validation_evidence/agentic_combat/slice1/browser-legacy-openai-legacy-r1/`

#### Dungeon Master

--- Previous Session Messages ---

#### Dungeon Master

Dungeon MasterDM▶Generate ImageWelcome back! You stand in the Frostbound Guildhall, its hearth glowing against the chill of Frostmere Vale. Fresh slush tracks lead toward the eastern entrance, while a sealed watch notice rests on a nearby table. Scout Kira gives you a bright, knowing grin. "Back with us, Trouble Magnet?" Ranger Thane checks the hall in silence, and Scout Elen keeps her attention on the notice. The distant howls have not stopped, and the missing scout remains unaccounted for. What do you do next?

#### Player

⚔️YouI look around the guildhall and quietly assess the room.

#### Dungeon Master

Dungeon MasterDM▶Generate ImageYou quietly assess the Frostbound Guildhall. The hearth burns low but steady, throwing amber light across benches, training dummies, and frost-rimmed beams. Scout Kira keeps still beside you, while Thane watches the entrances and Elen studies the room's details. Near the eastern doorway, fresh slush tracks cross the floor and end beneath a bench. On the table nearby lies a sealed watch notice bearing the local guard mark. Nothing moves, and no immediate threat reveals itself, but the tracks and notice both feel recent.

Please make a Perception check. Roll 1d20 and add your Wisdom (Perception) modifier.

#### Player

⚔️YouI look around the guildhall and quietly assess the room.

#### Dungeon Master

Dungeon MasterDM▶Generate ImageYou move quietly through the Frostbound Guildhall, letting your eyes adjust to the hearth's amber glow and the pale light leaking through the frosted windows. The benches, training dummies, eastern entrance, and sealed watch notice reveal no obvious threat. Kira remains motionless beside you, Thane watches the doors, and Elen studies the floor and rafters with practiced patience.

Please make a Perception check. Roll 1d20 and add your Wisdom (Perception) modifier (+3).

#### Player

⚔️YouI quietly verify the guildhall exits and return to my place.

#### Dungeon Master

--- Current Session ---

#### Dungeon Master

Welcome to NeverEndingQuest. Press the button at the top right to begin. New here? Open Settings (gear icon) to pick your AI provider -- Legacy (GPT-4.1) is the recommended default.

#### Dungeon Master

Game started! You can now enter commands. Try things like: "look around", "talk to the innkeeper", "check my inventory", or "head north".

#### Dungeon Master

Dungeon MasterDM▶Generate ImageThe Frostbound Guildhall has fallen quiet again. Three snow rats lie defeated among overturned benches and scattered tankards, while the hearth crackles against the cold leaking through the frosted windows. Ranger Thane, Scout Elen, and Scout Kira regroup nearby, weapons lowered but eyes alert. You stand amid the aftermath, mace in hand, with the brief violence still echoing beneath the vaulted beams. What do you do next?

#### Player

⚔️YouI step inside the rat's lunge and strike with my mace. I rolled 18 to hit and 3 bludgeoning damage.

#### Dungeon Master

Dungeon MasterDM▶Generate ImageThe rat's teeth punch through your guard, and pain flashes beneath your armor. Kira's bowstring snaps across the guildhall; her arrow drives into the rat's flank, spraying dark blood across the frost-dusted boards. The wounded creature skitters beside the overturned bench, still snarling. Kira keeps her bow trained on it. Kira: Your opening.

## Verification

### Exact commands and observed outputs

- `python -m pytest .superpowers/local-tests/combat/test_web_prompt_readiness.py -q` before the fix -> `1 failed`; after the fix -> `1 passed`
- `python -m pytest .superpowers/local-tests/combat -q` -> `46 passed in 1.69s`
- `python -m pytest tests -q` -> `14 passed in 0.23s`
- `python -m py_compile web/web_interface.py .superpowers/local-tests/combat/test_web_prompt_readiness.py .superpowers/local-tests/combat/prepare_resume_fixture.py .superpowers/local-tests/combat/run_resume_acceptance.py` -> exit 0
- `.superpowers/local-tests/combat/run_resume_acceptance.py` against three fresh copied campaigns -> headless reversed, pre-typed, and legacy all PASS
- `.superpowers/local-tests/combat/run_browser_resume.ps1 -Port 8368` against six fresh copied campaigns -> React/legacy UI x reversed/pre-typed/legacy all PASS
- `git fetch origin design/agentic-combat` -> local/remote both `6784a6274d5c7cae979523fb0a8dab2ce1a03624` before commit
- `git fetch origin main`; `git merge-base --is-ancestor origin/main HEAD` -> exit 0
- `git diff --check 6784a627 -- web/web_interface.py docs/audits/2026-08-24-agentic-combat-provenance-controller-HANDOFF.md` -> exit 0
- credential-pattern scan of both intended tracked files -> `secret_pattern_hits=0`

### Files touched

- Tracked production: `web/web_interface.py`
- Tracked audit: `docs/audits/2026-08-24-agentic-combat-provenance-controller-HANDOFF.md`
- Ignored local acceptance: `prepare_resume_fixture.py`, `run_resume_acceptance.py`, `browser_resume_acceptance.mjs`, `run_browser_resume.ps1`, `test_web_prompt_readiness.py`, and the evidence trees named above
- Explicitly excluded unrelated pre-existing change: `web/frontend/src/components/party/party.test.tsx`

## Notes

- The final legacy/legacy run exercised real T017 compression validation
  exhaustion and continued through the original combat operation; it did not
  rewrite provenance or silently activate the typed route.
- The copied campaign lacks optional portrait/video assets. Browser traces record
  the known media 404/aborted requests; no combat, controller, or persistence
  request failed.
- This proves the controller/provenance acceptance subset only. Slice 1 still
  requires the activation mismatch, same-state claim, mechanics freshness/race,
  near-death, and free-form action controls before it can be called complete.
