# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- In a fight, after a character swings a weapon, the fight event now records the engine's view of that character's hands, and a carried weapon that fits a free hand in its default grip is drawn, so it is in hand for the next turn (NUM-B, Refs #193). The swing itself is never refused or changed. A thrown weapon, a stack such as eight javelins, a grip other than the default, or hands that are full is recorded but not drawn. When a weapon is drawn this way, the fight narration now says so ("draws the dagger and attacks"); nothing else about the hands reaches the narration (NUM-B2).

### Changed
- Code-issued combat roll requests now store their phase beside the die, so the die check no longer reads the request's wording (#1008).
- The turn validator now also names which of its rules a rejected DM answer broke, from a fixed list written to the validation diagnostics only, so rejections can be counted by rule; verdicts and the feedback the DM sees are unchanged.
- The game's OpenAI model profiles now name `gpt-6-luna` in place of `gpt-5.6-luna`, so the 84 tasks on luna, the main DM response included, move together with the same reasoning efforts; the five tasks on other models are unchanged. `gpt-6-luna` lists $0.10 input and $0.50 output per million tokens, against $0.20 and $1.20.
- At startup the game no longer builds companion memories by matching keywords in the journal (#855). For an older game opened for the first time, that build set each companion's starting relationship with the player from those matches. Companion memory now comes only from the episodic memory upgrade, which reads the same journal. Memory files a game already has are kept and read as before.
- The Thornwood Watch's Bandit Stronghold keeps every fight closed (#852). An alarm brings the whole camp into the fight from its first round instead of the warriors arriving two rounds later. A quiet fight out at the lookout posts stays as it started, and a loud one wakes the camp, which comes out together as a new fight. The DM is told to suggest picking the bandits off one at a time, and Bandit Captain Gorvek is back to 27 HP. The DM prompts now say that responders are in a fight from its start and nobody joins a fight already under way.
- Simplified the end of a location move in the action handler: removed three checks that could never fail (the move's transition record always exists at that point), joined three back-to-back blocks with the same condition into one, and deleted stray comments after a return. No behavior change (#773 follow-up).
- Removed `core/ai/conversation_compression.py`, a module that could not be imported (it imported two modules missing from the repository) and that nothing used. The README's compression section now names the live `utils/compression/conversation_compressor_parallel.py`, and `model_config.py` for the `COMPRESSION_ENABLED` switch (#811).
- Unused summary code in `core/ai/cumulative_summary.py`, seven functions left from an older summary pipeline that nothing called, was removed, and the registered source lines of its two remaining AI calls (T018, T019) were corrected (#798). Gameplay, summaries and saves are unchanged.
- Removed two unreachable code paths (#444). The DM-response validator in main.py no longer has a branch that normalized a draft itself: its only caller always passes the draft already normalized, and now has to. `core/validation/dm_response_validator.py` no longer has its own createEncounter shape check, a second copy of the live check in `core/combat/scene.py` that no game code ran. No game behaviour changes.
- Removed `updates/update_party_tracker.py`, a module that nothing called: it read a `party` list and an armor/weapons/other equipment shape that no party tracker or character sheet has used for a long time, so any call would have failed. Its unused import in `core/managers/combat_manager.py` and the lines naming it in `module_debugger.py` and `ARCHITECTURE.md` went with it (#470).
- Removed `merge_updates` from `core/managers/combat_manager.py`, a helper that nothing called; had anything called it, it would have replaced a character's whole equipment list with the update's list instead of changing single items (#471).
- Removed `update_json_schema` from `core/managers/combat_manager.py`, a deprecated function that nothing called; it only logged a warning and returned its input unchanged (#1002).

### Fixed
- A character with a very long name no longer makes the rules engine refuse the whole party world; the name part of its engine ids is shortened so every derived id fits, and every shorter name keeps its ids (#1022).
- If a file cannot be copied while saving, the game now says the save failed instead of reporting success, so loading that save can no longer silently drop your chests, journey record, effects or a character; a save that did not finish is no longer offered in the Load list (#1003).
- In a long fight, an earlier round whose log names no initiative is now compressed like the others instead of being kept in full after its summary is refused (#1008).
- In a fight, an answer that names your weapon (for example "I attack the spiders with my mace", or "I rolled 15" with the mace) is no longer refused with "That die does not match this action" because of the weapon notes the game adds to your words (#1008).
- If saving the welcome-back hits a brief lock wait, a line you type in that moment again replaces the welcome instead of waiting behind it (#990 follow-up).
- A DM reply that repeats a key (two "actions" lists) is sent back for a corrected draft instead of silently keeping only the last list, which dropped the fight a welcome-back had started (#1018).
- A very long ammunition name or storage container id no longer makes the rules engine refuse the whole party world; over-long engine ids are shortened, and every id that already worked is unchanged (#1004).
- Arrows taken out of a chest now join the sheet's quiver even when it is named the older way (Arrow), and a chest holding arrows from several deposits gives back up to the full amount stored (#971).
- The concentration save after damage now shows the Bless die the game rolled, for example "rolled 13 +2 +2 (Bless 1d4, the game rolled) = 17"; before, the die was counted but not shown, so the numbers did not add up (#1014).
- When your own action calls for a check (reading someone, searching, climbing), the game now always asks you for the roll and shows the result, instead of the DM rolling it in secret while telling you to roll (#1009).
- A companion recruited with `"level": null` (or an empty level) is built at the party's level, as when the level is left out, not at level 1-3 (#1007).
- A campaign whose characters folder holds a second sheet with a character's name (for example a leftover test copy) now converts its temporary effects, using the file the game itself opens for that name and leaving the copy untouched, instead of refusing at every start (#1005).
- Generated modules keep quest ids out of place and feature names (#989). The location writer is told that names are what the player sees, so ids such as SQ004 stay in the DM's notes.
- A fight started by the welcome-back scene no longer ends silently when you type your first action (#990). Your input waits for the fight instead of cancelling the scene, and a combat turn stopped for an unknown reason now pauses and keeps your turn.
- In the web player, a requested check now shows the extra die the game adds, for example "+ 1d4 Guidance (the game rolls)" when Guidance or Bless is on you (#984).
- In a fight, when the DM corrects one combatant's action, the actions already approved earlier in the same round now stay as approved, so the round no longer loops on two companions taking turns being refused (#435).
- The storage helper now sees a character's ammunition, so asking to store arrows no longer fails with 'Character does not have Arrows' (#366).
- In a fight, when you use a potion or other item you have none of left, or shoot with no arrows or bolts left, the DM now tells you and asks what you do instead, instead of picking another action for you (#968). This extends the same rule for spell slots and class features (#671) to items and ammunition; nothing is spent.
- After you roll a check the DM asked for, the result (your roll, bonus, total and the difficulty, success or failure) now shows right away under your dice, before the DM narrates what happens (#530).
- A character update that names no character is now sent back to the DM to name one, instead of being written to the first party member's sheet (#914).
- A hero saved before Fighting Styles were recorded as "Fighting Style: <name>" (for example "Fighting Style (Defense)" or "Fighting Style (Archery)") now gets the style's effect at their next level-up, which records it the new way and says so; until then the game log notes it (#760).
- A companion speaking in character now knows how much ammunition it carries: its in-character voice sees each ammunition stock with its count (for example "Arrow x19") after its equipment, so it no longer says its arrow count is not recorded (#359).
- A Fighter with the Defense Fighting Style now sees its +1 Armor Class listed as "Fighting Style: Defense" in the armor class breakdown, not as a bonus from their armor (#759).
- A character sheet that lists proficiencies the way the rules print them ("Martial weapons", "Light armor", "all armor") now has those proficiencies counted by the rules engine, the same as "Martial" or "Light" (#896).
- A recruited NPC is now built from the adventure's own description of that person, so the companion matches the character the players met even when the recruit action leaves race or class blank or names others; the recruit build also runs inside the game instead of a separate command, so a cancelled turn stops it cleanly (#534).
- The Thornwood Watch no longer shows a quest id in a place or feature name: the cave is now just "Wolf's Den Cave" and the watchtower bells are "East Tower Bell" and "West Tower Bell" (#989).
- When you attack in a fight, the DM now describes your swing or spell in its own words before asking for the dice; the exact dice to roll and the option to type roll stay the same (#860).
- An item with a very long name no longer stops the rules engine from loading the whole party (#566). Its engine id is now kept within the engine's size limit by shortening the name part, so every engine step for that party works again; ids already on a sheet stay as they are.
- A turn no longer fails with "the AI provider call could not be completed" when the response checker's debug file cannot be written (a file held by another program, a read-only or full disk); the debug copy is skipped and the turn goes on (#342).
- Choosing an existing character whose file has gone missing, is empty or is broken no longer ends setup; the game says the file is unavailable and asks again, and a file another program holds is waited for (#338).
- Spending or adding ammunition by a plural or older name (Arrows for a sheet row named Arrow) now changes that row instead of being refused or starting a second row (#358).
- Bless now adds a d4 to attack rolls, saving throws and the saves the rules engine rolls, instead of a flat +1, and Guidance adds its 1d4 to every check with the skill the caster chose (#889). An effect modifier could only hold a whole number, so Bless was stored as +1 every time and Guidance was not tracked; a modifier can now hold a die ("die": "1d4"), and the rules engine holds it too (engine 9771de5). In a fight the game takes the die from the fight's dice, so a replayed fight rolls the same, and shows it beside the d20; outside a fight the engine rolls it. This covers blessed attacks, a party member's saves in a fight, spell saves, concentration saves, and checks and saves outside a fight. The roll prompt names the die the game adds; the player still types only the d20. Two casts of the same spell add one die. Guidance is tracked as a concentration effect (up to 1 minute). A die on a plain ability check (such as "abilityCheck.wisdom") is not rolled yet: the effect applies without it and the game logs a warning.
- Loading a save made before any storage container existed now removes the current game's `player_storage.json`, so chests and their contents from a later point in the game no longer survive into the loaded game. Saves that include storage load it as before (#468).
- An empty or broken JSON file in a characters folder (for example an old 0-byte `ranger_thane_temp.json` that saves carry) no longer stops the game at startup: the effects conversion skips it and records it in its report. If the broken file is a party member's own sheet, the conversion waits instead, so that member's older effect bonuses are not dropped (#408).
- On Windows, a hero or companion whose name uses Korean, Chinese, Japanese, Cyrillic, Greek or other non-Western letters can now start a fight, and a new monster whose description holds such letters or math symbols no longer fails to build (#895).
- A hero or companion whose name has no Latin letters (Korean, Chinese, Japanese, Cyrillic, Greek...) now gets their own character file; two such characters no longer share one sheet or block each other (#894).
- When rebuilding companion memories at startup stops on a journal entry it cannot finish, the other entries still being read in parallel are now cancelled, so startup no longer waits on work it is going to discard (#429).
- Second Wind now restores 1d10 plus the fighter's level. Before, the fight sometimes healed only the die roll, so a level 1 fighter got 1 hit point too few (#881).
- In a fight, when you ask for a spell or class feature you have no slot or use left for, the DM now tells you and asks what you do instead, instead of picking another action for you (#671).
- With the Local/Custom provider, changing the custom model in Settings now rebuilds compressed chronicle sections with the new model instead of reusing ones the previous model wrote (#402).
- A module added to your world in the background no longer reads like a story event (#795). The notice uses the module's own title (apostrophes included), says it is a new adventure you can travel to, and appears as a system card once the opening scene has settled instead of as Dungeon Master narration.
- Character creation is easier to read (#792). The Dungeon Master now puts each open decision on its own "- " line with its options, asks three or four decisions per turn (background, then species, then class), and shows the final build as labelled sections ending with "Approve this build, or tell me what to change.". The web client lays out such lists, labels and bold text line by line; ordinary narration displays exactly as before.
- A night's sleep no longer counts as two long rests (#892). The game leaves 16 hours between long rests, a sleep "until morning" keeps the morning the DM narrates instead of being stretched to a full 8 hours, and a rest only lands when the story shows the party resting.
- On Windows, a chronicle compression that finds the compression cache held by another game process now waits for it, instead of giving up after ten seconds and sending the full history for that turn (#403).
- Arrows, bolts and other ammunition can now be put in a chest or other storage and taken back out: stored ammunition leaves the character's ammunition count and comes back to it (#366).
- Recruiting a companion whose character sheet could not be built no longer reads as a successful join: the DM is told the companion has not joined and the rest of that response does not run (#534).
- A newly generated NPC is built from the game's SRD 5.2.1 class tables: the builder is given each class's current features and numbers instead of the older edition's lists, and the new sheet starts with its class's spell slots and feature uses (a level-1 Ranger is now described with Favored Enemy and Weapon Mastery instead of the older edition's Natural Explorer, and starts with two level-1 slots and its Favored Enemy uses) (#533).
- The DM now sees how much ammunition a companion carries: the shortened companion sheet lists ammunition the way the full sheet does, so the DM no longer says a companion's arrow count is not recorded (#359).
- A character sheet change that tries to remove ammunition under a name the sheet does not list (Arrows when the sheet says Arrow) is now refused with the sheet's own names, so the DM can say it again, instead of being reported as done while nothing changed (#358).
- GPT-6 models that stream a short "commentary" message before their answer no longer break the reply: only the message labelled as the final answer is read, so the game no longer gets two JSON objects back to back ("Extra data"). Output without labels is read whole, as before (#961).
- A new character whose armor or shield was written without its armor numbers (for example Chain Mail with no base armor class) now gets them from that item's SRD entry when its name is exact, so the rules engine works out its armor class, initiative and passive Perception before it is saved (#573). Before, such a hero was saved with the armor class as written, initiative and passive Perception as the author wrote them, and armor the engine could not read. Saved characters are unchanged.
- Saves now keep a check that waits for the player's roll, and Load and Reset no longer carry over the current game's pending checks or unreported check results (`modules/checks_state.json`, #940).
- In a fight, when the DM tries to end an effect your character does not have (such as tearing free of webbing that never caught you), your action now resolves after one more try instead of the DM re-ruling it over and over (#725).
- Ammunition bought from a merchant now joins the stock a character already carries under an older name (20 Bolts bought with 60 "Crossbow bolt" make one stock of 80) instead of starting a second stock of the same ammunition, and new ammunition rows are named as the catalog names them. Saved sheets are not changed (#552).
- The shortened character sheet the DM reads for companions no longer folds Perception, Persuasion and Performance into one "per" skill: skills and expertise are listed by their full names (#553).
- During character creation, a follow-up question the reviewer accepts is now shown to the player even when the reviewer also marks it as needing the player's answer, instead of being refused as an invalid review and costing the turn until the build was handed back (#887). An accepted final character that still needs the player is refused as before. The reviewer is also told that this mark is for a rejection the author cannot correct without the player.
- Fifteen Keep of Doom loot items (potions, antitoxin, scrolls and two vials) now name a standard item or state what they do, so they can be used in play (#913).
- Three Thornwood Watch loot items now say what they do: the explorers' two healing potions and the Hart's tears state how many hit points they restore, and the vial of alchemical fire is the standard Alchemist's Fire, so they can be used (#913).
- An NPC named in an encounter, a combat turn, an encounter update or a party change is now matched to its own sheet only: the sheet recorded when the encounter was built, else the exact name. A name that only shares a word ("Scout", "Kira", "Captain Bryn") no longer loads, syncs or writes another NPC's sheet or an old backup file; an unreadable sheet is skipped instead of failing the lookup (#855).
- When the player's message that starts a fight declares their own first action (for example "I hurl my javelin at the nearest wolf"), that action is now kept and offered back at the player's first turn in the fight, instead of being lost when combat begins (#882). The game shows "Your declared action: ..." and puts the text in the input box (web and React clients) or sends it on Enter (terminal); the player can send it as is or type another action. It is offered once, and a resumed fight does not offer it again.
- A new Cleric who chooses the Protector Divine Order, or a Druid who chooses the Warden Primal Order, now gets the armor training (Heavy or Medium) and Martial weapons proficiency the order grants (#888). An order the character creator records under another name is sent back to it with the exact name to use.
- The React player builds again after PR #915 (#919): the app's TypeScript config no longer compiles the test files, which import Node modules.
- Magic Initiate's free level 1 spell is now a tracked use (#891). The feat's "cast it once without a spell slot" had no field, so the free cast was never spent or was paid with a slot; a feat can now carry its own use pool (feats[].usage), which the game spends, refuses at 0 and refills on a Long Rest. New characters and level-ups get it full; a character who already has the feat gets it on the next Long Rest.
- Typing "roll" now answers a roll the DM asked for in combat, not only the game's own attack prompts (#877). The game rolls the requested dice (all of them, such as 1d8+1d6) and the DM receives the result, and every such request says that "roll" is accepted. Before, "roll" was sent to the DM as text and the DM asked again.
- A player's bonus-action roll that comes before an attack is no longer dropped (#880). "I use Second Wind, then attack" opened the game's own attack roll and threw away the DM's request for the 1d10 heal, so Second Wind was never used; now the game takes over the swing only when the DM's request is for that swing (its attack or damage roll), and any other roll or choice is asked for first.
- Typed spell rules no longer switch off on a Windows checkout (#890). A clone made with Git's line-ending conversion stores data/spell_repository.json with CRLF endings, its byte hash then differed from the one the typed spell tables record, and every spell save, spell attack and roll check fell back to the model's own numbers. The recorded hash is now compared with line endings read as LF and a mismatch is logged once instead of turning the typed tables off, and .gitattributes keeps that file LF in new checkouts.
- A travel turn whose side changes could not be prepared no longer stops the game: a sheet change the rules refuse, a storage change or a new companion whose sheet cannot be made is dropped and the move goes on, with one notice on arrival; any other failure ends that turn cleanly and the game goes on (#855).
- A spell cast with a slot is scored at the level of the slot it spends (#855). A reply that spent a 1st-level slot but claimed slotLevel 3 had Guiding Bolt deal 3rd-level damage, and another creature's slot record could set the level; now the caster's own spent slot decides, a slotLevel that disagrees with it goes back to the DM to correct, and only slot names of the sheet's form (level1 to level9) are read.
- Giving ammunition to a companion now moves the ammunition count the game uses, so both characters' Character panels and shots show what each one holds (#902).
- A roll prompt for a requested check no longer gives away what the roll is meant to find (#883): the DM is told to name only the attempt in the check's reason, the turn validator rejects a reason that names the hidden thing, and an NPC being read or pressed holds back the answer until the roll is in.
- Great Weapon Fighting now works: on a melee weapon held in two hands (a Two-Handed weapon, or a Versatile one used two-handed), a 1 or 2 on a damage die counts as a 3, for dice typed or rolled with the dice tray, for "roll", on a critical hit and for companions (#879). For such a swing of two or more dice the game asks for each die, and the fight record keeps each die and what it counted as.
- A new character whose name has accents can now be created: the startup DM is no longer told to write ASCII, it sees its own earlier answers with their real letters, and a sheet that comes back with a broken letter (a control character) is sent back to the DM to correct before review instead of costing a full review each time (#874). When a build is handed back, the notice now says "I could not finish that build yet." instead of naming a rules question that may not exist.
- Equipping a stack (Javelin x8) is no longer sent to the rules engine as a one-unit equip (#876). The engine wears exactly one unit, so the swap "Greatsword off, Javelins on" was refused as "cannot use or lose 0 (not enough stock)" and nothing changed. The stack now stays carried and unworn while the rest of the change is kept, the DM is told in one line that it is carried, and unequipping or using up an older sheet's "equipped" stack is no longer refused. A refusal of an equip now names the engine's rule instead of a shortage.
- A monster or NPC whose generated stat block fails the schema is now retried with the validation error and its own previous answer, instead of the same request again, and the monster prompt states that skills and senses are objects; a fight no longer fails to start because a creature listed its skills as [] twice (#886).
- A character named in an action is now matched exactly: updateCharacterInfo, item and coin transfers, removeEffect, awardExperience, rollCheck, expendCharges, acquireItem and combat updates no longer go to a different character whose name only shares a word or part of a word ("Scout Elen" was written to Scout Kira, "Brother Tomas" to Brotherhood Guide Ana). A name that is not exact is refused before anything is written, and the DM is shown the exact names to use (#855).
- A change dropped on the road is no longer described by the journey narration (#855).
- A monster lying in wait to ambush the party is no longer marked surprised when the party spots it first (#882). Spotting the ambush cancels it, but the monster had already noticed the party, so by the rules it is not surprised and keeps its first turn. The DM's and the reviewer's instructions now say so.
- When the player readies gear, drinks a potion or pays before setting off and asks to move in the same message, the DM now does the step first and invites the move as the next action on its first try (#875). Before, the DM's instructions did not say this, so its first replies tried to do both and were rejected, which cost several extra model calls before the same result.
- A purchase the DM names wrongly (an item name the catalog does not have, such as "Trail Rations" for Rations, or a quantity that is not a whole lot) is now corrected before the DM's reply is shown, instead of being shown and then refused (#878). And when a change is still refused after its narration was shown (for example a purchase the character cannot pay for), the DM is told the player has already read that narration and continues it instead of retelling the scene.
- The Thornwood Watch hermit's healing potion is now a standard Potion of Healing that states what it restores, so it can be drunk (#903).
- A fight no longer fails to start when the DM picks a monster count inside a location's listed range, and a challenge the player makes of an NPC (a duel, a surrender, a parley term) is answered before any fight starts (#885). Before, the reviewer rejected a count such as two bandits from a "2-4" group as invented, and treated a duel offered with a drawn weapon as the start of combat, so the turn was rejected until it was dropped. The DM's and the reviewer's instructions now say both, in their full and compressed forms.
- Monsters and NPCs created for a fight are now built for the party's real level: the party level is read from each character's sheet file instead of a path made from the display name, which fell back to level 1 for any multi-word name (#873).
- A travel turn that adds an NPC who has no character sheet yet now creates the sheet and moves the party; before, it raised a TypeError that ended the game session, and the next start discarded the planned move (#893).
- A turn whose chronicle sections were all already compressed no longer leaves the compression progress banner on screen; such a pass is silent again (#901).
- A fight with a named NPC whose name carries a status word (for example "Wounded Ranger Gareth") now starts: the combat builder gives the NPC builder the NPC's name and loads the sheet it saved, and an NPC sheet already saved under the cleaned name is reused (#884).
- A travel turn that also asked for a character sheet or storage change no longer waits forever when the model never gives a usable answer: after 3 tries the change is dropped, the travel goes on, and the player is told once that it was not made and can say so again in the next message. Before, the model was asked again without end and the turn never returned (#855).
- A character update no longer guesses from the wording of its change which sheet fields it must return (#855). Before, eight word patterns forced fields the change did not touch (for example "Traded the old map for news" forced coins and gear), and an update that could not supply them was dropped after three tries; other wordings let half a change through ("Kira drinks a potion of healing, HP 6 -> 13" healed without using up the potion). The DM now lists the fields a change touches in a new "affects" list on updateCharacterInfo, and the update must return every one; a malformed list goes back to the DM as a correction before anything runs. On Gemini, a listed hit point, coin or spell slot change is asked for as the signed change the game accepts, never as a total. Rest-bound effects now end only through the rest action: an update that merely mentions a long or short rest ("cannot take a long rest here") no longer ends them. Updates without the list, older saves and fights from before the current combat system require no particular field.
- In a fight, the DM's request for a player roll now states what the roll is for (attack, damage, healing, save, check, or the spell's own phase) beside its die, and the game checks the two against each other instead of reading the request's wording (Refs #855; #853). Before, a damage request that mentioned the attack roll before it was stored as a d20 request, so the player's correct damage die was refused, and a spell's damage request that mentioned the spell attack was checked as a d20 and sent back as wrong. A request without its phase, or with a die that does not fit it (an attack not on a d20, damage or healing on a d20), goes back to the DM to correct. A roll already asked for in a saved game is answered as it was asked.
- Four fixes to new-character creation (#855). A sheet that writes Defense as "Defense Fighting Style" is no longer refused over and over for an armor class the engine never grants. A Fighter whose sheet does not record its Fighting Style in the exact form level-up writes is sent back with the exact form and the valid styles, instead of committing without the style. A Dwarf's level-1 Dwarven Toughness now comes from the species, so "Dwarven Toughness (Hill)" or a missing trait entry no longer leaves the hero one hit point low, and a doubled entry no longer adds 2. Names written in Chinese, Japanese or Korean are no longer stripped from the sheet; only emoji are.
- After a fight, when the automatic follow-up tried to change a character sheet, the player's notice no longer says the fight settled gear and rewards: it names what combat applies (damage, ammunition, combat XP) and invites loot or other changes in the next message. In a fight, the engine now records the weapon each character last used for each kind of attack (melee, shot, thrown), and the DM is told to pick that weapon for a bare "shoot", "throw" or "swing" instead of guessing, which could spend the wrong ammunition (#851).
- A player turn that contains words the game uses for its own history markers, such as "Module transition:", "Location transition:" or "=== LOCATION SUMMARY ===", is no longer taken for one of those markers. Before, such a turn could be dropped from the saved conversation, left out of a compressed summary, or cut the history in the wrong place when the party travelled. Markers the game writes now carry a field naming their kind, and markers in existing saves are still recognized by their exact wording, so saved games read as before.
- In a fight, whether the game rolls the player's weapon attack itself or leaves it to the DM now depends only on the die the turn already asked for and got an answer to (a d20), as the game recorded it. Before, a d20 named anywhere in the DM's question text (for example beside a damage roll, or in a choice) also counted, and the game's own scored swing was skipped for that turn (#852, follow-up to #830).
- On a short rest the game now rolls the hit dice a character spends and shows the roll; the DM names how many in the rest action instead of asking the player to roll (#840, #847).
- After a won fight, an area file that cannot be read cleanly (for example one invalid byte) is no longer written back with the bad bytes silently replaced; the fight's record is kept and one line names the file and the cause (#850). Travel now finds the location being left by its id, through the same reader as the DM note and combat start (#448), instead of by its name. A healthy area file is written exactly as before.
- When looking up a module's starting location fails with an unexpected error, the log now has one line naming the error and the start used, with its traceback, instead of a "Could not get starting location" line that read as a crash. That start, taken from the module's area files, is now checked against the module like the other fallbacks (#821), so the entry is no longer refused when that location is invalid: the party enters at the module's first valid location instead.
- Two fixes to the automatic save before a fight (#845, follow-up to #836). A Load or Exit pressed while that save is being written now takes effect at once, and a read-only save stop it meets now ends the session as other saves do (#654); before, both were logged as "checkpoint not saved" and the fight was built anyway. Old automatic saves are now pruned only by a marker the game writes into their save data, never by their name, so a save the player or DM names "Auto-save before combat..." is never deleted. Automatic saves made before this change carry no marker and are kept.
- The party's current location is now read in one way for the DM note, the location context, the DM-response check, the conversation history and combat start: by the location's id, as strict UTF-8, with a briefly locked file retried (#448). An area file that is missing, unreadable or without that location now leaves one warning naming the file and the cause, and each place shows what it showed before; before, one invalid byte made combat start and the DM-response check stop with an error while the DM note silently replaced it. The DM note and the location context now find the location by its id rather than its name, as the other readers already did. Other readers of the area file are unchanged.
- On a plain look-around turn the DM no longer hints at loot that the location's record calls hidden or concealed (#629). Both DM prompts (the full one and the compressed one the game uses) now say such an entry stays unnoticed until the party searches that spot or succeeds on a check that matches it. Nothing else in the prompts or the code changes.
- When a module is entered without a named destination and the model's start cannot be used, the game's own fallback start (the first location of the first area) is now checked against the module before the party is sent there (#821). A fallback the module would refuse no longer blocks the entry: the party enters at the module's first valid location instead, or at the same location with its area corrected. It is still used only for that entry and not saved.
- A bow, crossbow or sling now shoots the ammunition that matches it: a sling no longer spends arrows when the arrows are listed first (#822). The match uses the ammunition's catalog id, which ammunition bought from the catalog now keeps. When no carried stock matches, the shot uses the first stock as before; ammunition already on a sheet, including starting ammunition, keeps the old rule. Saved characters get the weapon side at their next level-up or weapon purchase.
- The NPC character sheets and NPC inspect now offer the people the game says are at the party's place, as the party panel does, instead of the module's original list; after an NPC moves, they no longer offer it at the old place or refuse it at the new one. The original list is still used while the game cannot say who is present (#537).
- When another program holds a file the game needs, the waiting messages are now right (#826). On first launch the "Waiting for the browser files" line shows once and then every 10 seconds, instead of four times a second; and Save, Load and history recovery now say they are waiting for a file another program is using, instead of "waiting for a safe campaign boundary".
- In the web interface, when the active module cannot be read (or an interrupted journey finishes but the game cannot reload, or the party's location cannot be read after a resumed fight), the page now pauses with "Gameplay is paused. Choose Load, Reset, or Exit." instead of the session ending after that line, where typed input went nowhere and Start ran into the same error. The terminal already paused (#806).
- A fight the DM starts no longer fails to start when the terminal forces colored output (FORCE_COLOR) (#812): the game now reads the combat builder's typed result instead of its printed text. Running core/generators/combat_builder.py by hand now exits with code 1 when it does not save an encounter.
- Model-evaluation capture records for the effects classifier (T078) could name the wrong source file: its two callsites shared one registry entry, so after the legacy effects path ran in a session, later records from `core/ai/effects_agent.py` named `updates/update_character_effects.py`. Each record now names the file that made the call (#816).
- A character holding two of the same weapon (two daggers, or a javelin bought while carrying a stack of javelins) no longer gets two identical sets of attacks on the sheet: there is one per weapon and grip, described as in hand when either one is (#814). Saved characters are tidied at their next level-up or weapon purchase.
- A campaign reset's backup no longer includes leftover module-refresh rollback files from older builds (`modules/.commit_backups`, `modules/commit_state.json`) (#813). Before, copying such a backup back by hand could make the next start roll module files back to stale copies.
- After a level-up, a character's attacks built by the rules engine now show the new numbers (a higher to-hit as proficiency grows, a Monk's larger Martial Arts die), and a weapon bought in a shop gets its attacks at once. Before, only character creation wrote these attacks, so they kept their level-1 numbers and a bought weapon had none. Characters made before the thrown-weapon fix (#801) also get it this way, at their next level-up or weapon purchase. Attacks written by hand under other names are left as they are; one named after an owned weapon is replaced by the engine's at the first refresh, as at character creation; an engine-built attack that the DM model edited is rewritten with the engine's numbers at the next refresh.
- Two follow-ups to #448 for a game that has no party_tracker.json yet. The character-effects validator no longer looks up the active module it never used, so it can be built before the first save (this fixes tests/test_startup_review_provenance.py). In the web version, the storage panel shows empty storage before setup finishes, instead of "An internal error occurred".
- When the game starts and finishes a journey that was interrupted, but then cannot reload the game afterwards, it no longer closes without a word (#211). It says so in one line; the terminal pauses on the load / reset / quit menu and the web pauses on Load / Reset / Exit. If the cause is that the active module cannot be read, the #448 line names it instead.
- When another part of the game, or a second copy of the game open on the same game folder, holds a file the game is about to save, the save no longer waits silently (#803). It still waits and never gives up the save, but after a couple of seconds it says so: during a turn the status line shows "Waiting to save <file>: another part of the game is still saving it.", Save and Load show their own waiting line, and the log gets a warning every 10 seconds. If the game has already stopped because a save file is read-only, an ordinary file save waiting this way stops too.
- When a fight the DM starts cannot be set up, the DM is now told and answers again, instead of the game silently doing nothing (#444). If it fails again in the same turn, or a fight stops partway or is left at a combat prompt, you see one line; a fight left unfinished stays saved and resumes at the next start. A finished fight's record is now always that fight's own summary, never an earlier one. Resuming a fight no longer crashes when the party's location cannot be read: the fight's record is kept, and the game says so; the terminal pauses on the load / reset / quit menu and the web pauses on Load / Reset / Exit.
- In a fight, a character whose turn the game plays (a companion, or your own character while the game controls it) no longer spends one of its arrows when it throws a weapon (a javelin, or a dagger or handaxe thrown), and is no longer refused the throw when it has no arrows left (#801). Your own turns, which the DM rules, are unchanged. This applies to attacks the game builds from the engine at character creation; a hand-written attack can opt in with "thrown": true. Characters made before this update keep their old attacks until those are rebuilt.
- A headless start with a character file (`run_headless.py new-game --character FILE`) no longer refuses a character whose written armor class the starting engine projection would correct. Headless now checks the starting mechanics after the projection, as the interactive setup does; a sheet still wrong after it is refused, naming which check failed (#797).
- When another program on your computer (an antivirus scan, a sync client such as OneDrive, or a program that locks files) holds a game file the game is saving, the game no longer waits in silence: after two seconds it says which file it is waiting for and that closing that program lets it continue, and it still never gives up the save. If another save has already stopped the game because a file is read-only, a waiting save now stops too instead of waiting forever (#653).
- When the game cannot read which module the party is in (party_tracker.json missing, unreadable, or without a module), it no longer silently uses Keep_of_Doom, which could read another adventure's files and write game files into its folder (#448). It waits briefly if another process has the file locked; if the file still cannot be read, it shows one line naming the cause: the terminal pauses on the load / reset / quit menu, and the web pauses on Load / Reset / Exit.
- A new module's plot themes are no longer limited to 40 words (#347). Before, when the DM wrote a longer theme for a module the player had accepted, the module failed to build with a generic "failed validation" message. Themes still need at least 3 words and 1-3 comma-separated goals.
- When the DM model fails to pick where a module starts, the game no longer remembers its fallback (the first location of the first area) as the model's choice for every later visit (#308). The party still enters at the fallback that time, and the model is asked again on the next entry. A start the model names that does not exist in the module is no longer saved either, so it can no longer block every later entry; a start with the right location but the wrong area is corrected before it is saved.
- When the party finishes a new module whose areas have long ids (over 7 characters, which a module can get from a region with a long name), the DM now gets the usual prompt about what comes next (#310). Before, the game did not count that module at all, so it never showed as finished.
- Model-call capture records now name `main.py` as the source of the travel departure narration (T013) instead of `core/ai/action_handler.py` (#773). Older travel-narration code that could no longer run was removed with it; moves, their narration and saves are unchanged.
- A new module now keeps every alias the DM gave an NPC in its saved module file (#647). The game engine takes at most 16 per NPC; it still gets the first 16 usable ones, and the conversion report and the build log now say how many were left out, instead of the extras being cut silently.
- When the game cannot read a new module's files at startup because of a problem on your computer (a read error, a missing library), it no longer says the module's files did not pass the checks (#639). It now says the module's checks could not be finished and that it will be tried again at the next start. A module whose own files are broken is still reported as failing the checks.
- Creating a new adventure no longer shows the DM's narration of it before the module is built (#182). The DM could narrate the party's arrival somewhere that did not exist yet, and when the build failed that narration stayed on screen and in the story. Now a published module is narrated once it exists, and a failed build shows only its notice.
- Level-up no longer crashes, or drops skills, for a hero whose skills are stored as a list, as a new character's are: for example a Bard reaching level 2 and choosing Expertise (#769). Level-up now reads the proficient skills and Expertise from that list and adds a newly learned skill to it, instead of replacing it.
- Campaign `availableModules` no longer changes order from one start to the next (#761). The module refresh rebuilt the list from a set whenever it had a module to add, so the order followed Python's hash seed; it now keeps the listed order and appends new modules in sorted order, as startup reconciliation does.
- Leaving a module no longer takes it off campaign `availableModules` while it is still joined to the world (#747). Every crossing completes the module the party leaves, to write the visit summary, and that removed it until the next start, so the DM lost the "Other installed modules" line for the place the party had just left. Now only a module the world registry does not join is removed, and an unreadable registry removes nothing. `completedModules` still means visited and summarized.
- A start no longer keeps a module in campaign `availableModules` twice under two spellings, such as `The Thornwood Watch` next to `The_Thornwood_Watch` (#754). Each offered module is written once, by its registry id, and a joined module spelled with spaces is kept under its id instead of being dropped.
- Completing a module no longer adds module names that are not joined to the world to campaign `availableModules` (#746). The names come from the module summary (or the party tracker when that export fails) and are written by the model; now only a joined module is added, by its id ("The Thornwood Watch" counts as `The_Thornwood_Watch`). The summary still records the names as written.
- A module that is installed but not joined to the world, for example because its files did not pass the checks, is no longer offered to the DM or reachable by travel (#720). Campaign `availableModules` lists only joined modules and the party's own module, and each start removes other names an older save still lists. The DM's installed-module references leave such a module out. A move into it is refused before anything changes: the party stays where it is and the DM is told that place cannot be reached yet.
- Legacy character, item, quest, spell and save text now displays literally, including quoted names in NPC and saved-game buttons. Tooltips preserve descriptions without interpreting embedded HTML.
- A campaign reset no longer copies `modules/.integration_backups` into its safety backup. That folder, and any copy of it under `modules/backups/campaign_backup_*/modules/`, is left over from older builds, is never read by the game, and can be deleted by hand (#614).
- A native Windows start no longer freezes when `modules/world_registry.json` is read-only. The game shows one line saying the file is read-only and that a module cannot join until its Read-only setting is cleared and the game is started again; play continues meanwhile.
- A native Windows start no longer freezes when `modules/conversation_history/conversation_history.json` is read-only. The game shows one line naming the file and how to clear its Read-only setting, and does not start until it is cleared, because it cannot save the story while that file is read-only.
- A native Windows game no longer freezes when a save during play meets a read-only file. The game shows one line naming the file and how to clear its Read-only setting, and ends the session without saving anything more, so the next start, once the file is cleared, picks up from the last save.
- When a save during play meets a read-only file, the game now stops right there: it makes no further model calls, writes no further files, and no longer goes on with travel summaries, combat, a level-up or a Save first. A terminal combat or level-up ends at its next question instead of waiting for an answer it could not save.
- Leaving a location no longer ends the session when other module work, such as a module build, keeps the module-refresh lock busy for more than 5 seconds. The game shows "Waiting for module work to finish before recording your journey (N seconds)." and records the departure once that work finishes. The same applies when an interrupted journey is finished at the next start (#637).
- A start no longer skips a dropped-in module without a word when the game cannot safely read the state of its modules folder, for example after an interrupted module build. The game still leaves the module unjoined, and now shows one line naming it, saying it could not be checked this time and will be tried again at the next start. A start with no module waiting shows nothing (#638).
- A move the DM had already proposed and checked no longer calls the AI over and over when it keeps failing just before it happens, for example because the destination's records changed. The move is checked again at most twice; then the game shows "You remain where you are. That move could not be completed, so it hasn't happened. You can take another action here or Load a saved game." and nothing moves.
- Building a module no longer makes the game wait for the whole build. A Save, a Load or travel during a build used to wait until the build finished, and a second build could not start. Now a build holds the module lock only to reserve its name and to publish, so generation no longer blocks play. Publishing still holds the lock across up to three AI calls for a module built during play (one for a module built in the toolkit), so play can still wait briefly while a module is added. A build that has to wait for the lock now waits instead of failing, showing "Waiting for other game work to finish before continuing your module (N seconds)." Two builds of the same name get distinct names, and a crashed build keeps its name reserved, so the next build of that name gets a _v2 suffix.
- The first time an older game builds its roster record from the fights on record, one record that cannot be read (an odd encounter or roster entry, or a report that cannot be written) no longer brings back every monster the party already beat. That record is left out and listed in the conversion report, and every other fight on record is kept (#741).
- On a start or Load with a journal.json that cannot be read, the game now says once that companion memories could not be rebuilt from the journey chronicle this time, and play continues (#623). Before, the memory build was skipped silently.
- A one-time companion-memory upgrade that had stopped partway no longer resumes against a new journey chronicle after an unreadable journal.json was set aside, where it could overwrite an older companion memory (#653). The upgrade now skips the rest of that chronicle, logs a warning, and finishes with the campaign summaries.

## [0.2.0] - 2025-08-11

### Major UI and Media Update

This release brings significant improvements to the user interface, combat experience, and visual feedback systems.

#### Added
- **Combat Initiative Tracker**: Visual real-time combat tracker with animated portraits
  - Hover-activated video previews for monsters and NPCs
  - Dynamic HP display with color-coded health status
  - Automatic round tracking
  - Support for 30+ monster animations

- **Party Display System**: Persistent party member display outside combat
  - Real-time HP tracking for all party members
  - Character portraits with class-based defaults
  - NPC companion tracking

- **Time-of-Day System**: Dynamic environment visualization
  - Four time periods (sunrise, midday, sunset, nightfall)
  - Automatic image updates based on in-game time
  - Clean 60x60 adventure box display

- **Media Assets**: Comprehensive animation library
  - 30+ compressed monster video animations
  - NPC character animations
  - Thumbnail generation for all creatures
  - Class-based portrait defaults

- **Token Usage Tracking**: OpenAI API monitoring
  - Real-time tokens per minute (TPM) display
  - Requests per minute (RPM) tracking
  - Total token consumption monitoring

#### Changed
- **Skill System Refactor**: Improved skill handling with backward compatibility
  - Skills now stored as arrays for better AI interaction
  - Automatic proficiency bonus calculations
  - Support for both legacy and new formats

- **Combat Flow**: Fixed turn fragmentation issues
  - Improved prompt system for seamless multi-turn processing
  - Better handling of NPC and monster turns
  - Clearer player turn prompts

#### Fixed
- The Thornwood Watch: Bandit Captain Gorvek is now sized for the module's level 1 party. The module had no stat block for him, so the game generated the full-strength bandit captain (65 hit points, three attacks a turn), who could defeat a level 1 party in a round or two. The module now ships his stat block: 27 hit points, AC 15 with Parry, and two attacks a turn (scimitar and dagger). Campaigns that already generated Gorvek keep their copy; a new campaign uses the module's.
- Video reset issues during 5-second refresh cycles
- Vertical scrollbar problems in initiative tracker
- Portrait upload and positioning system
- Combat conversation compression for character formatting
- Saving throws layout optimization

#### Technical
- Added comprehensive video compression utility
- Improved .gitignore for proper media tracking
- GPT-5 model integration with reasoning effort levels
- Enhanced file organization and import patterns

## [0.1.0] - 2025-01-20

### Initial Alpha Release

This is the first public alpha release of NeverEndingQuest, an AI-powered Dungeon Master for tabletop roleplaying using the world's most popular 5th edition system.

#### Features
- **Core Gameplay**
  - Complete 5th edition rules implementation with automated combat
  - Character creation wizard with class, race, and background selection
  - Persistent character progression with XP and leveling
  - Inventory management and equipment tracking
  - Spell slot tracking and magical effects
  - SRD 5.2.1 compliant content under CC BY 4.0

- **AI Dungeon Master**
  - Natural language processing for player actions
  - Dynamic narration and scene descriptions
  - NPC dialogue and personality management
  - Quest and plot progression tracking
  - Intelligent combat encounter management
  - Validation system to ensure consistent gameplay

- **Module System**
  - Two starter modules included:
    - The Thornwood Watch (Level 1-3): Stop a sorcerer corrupting the wilderness
    - Keep of Doom (Level 3-5): Lift the curse from an ancient keep
  - Hub-and-spoke architecture for infinite adventures
  - Module transition with context preservation
  - Dynamic area and location management
  - AI can create new modules when adventures complete

- **Innovation: Context Management**
  - Conversation compression to overcome AI memory limits
  - Persistent world state across sessions
  - NPC memory and relationship tracking
  - Adventure chronicle generation

- **Web Interface**
  - Real-time character sheet display
  - Interactive command interface
  - Combat tracker with initiative order
  - Visual dice rolling
  - Auto-scrolling adventure log
  - Tabbed character data viewer

#### Known Limitations
- Alpha release - expect bugs and rough edges
- Limited to two modules currently (AI can generate more)
- Requires OpenAI API key (Claude support coming)
- Web interface required for optimal experience
- Some combat edge cases may need refinement

#### Requirements
- Python 3.8+
- OpenAI API key with GPT-4 access
- Modern web browser
- ~100MB disk space

#### Legal
- Uses content from SRD 5.2.1 under Creative Commons Attribution 4.0
- Fair Source License for codebase
- No affiliation with Wizards of the Coast

## [Unreleased] - 2025-01-20

### Changed
- **Major Codebase Reorganization** for better maintainability:
  - All Python modules organized into logical directories:
    - `core/` - Core game engine (ai, generators, managers, validation)
    - `utils/` - Utility functions and helpers
    - `updates/` - State update modules
    - `web/` - Web interface
  - Module builder moved to `core/generators/module_builder.py`
  - Conversation history files moved to `modules/conversation_history/`
  - Updated all import paths throughout the codebase (100% import success)
  - Fixed 47+ import issues across 22 files
  - Added comprehensive import testing tools

### Added
- AI Autonomous Module Creation system:
  - AI DM can create new modules when current adventures are complete
  - Narrative-driven module generation from rich text descriptions
  - AI parsing of embedded parameters (areas, locations, level ranges)
  - Fully agentic system - AI controls all aspects of module creation
  - Conditional prompt injection only when module completion detected
- New `createNewModule` action for AI DM
- Enhanced `module_builder.py` with `ai_driven_module_creation` function
- AI narrative parser for extracting module parameters from prose
- Module creation prompt that guides contextual adventure generation
- Interactive tabs in the web interface for viewing player data:
  - Inventory tab showing equipment, weapons, and currency
  - Character Stats tab displaying basic info, combat stats, and abilities
  - NPCs tab listing party NPCs with their current status
- Auto-refresh of tab data every 5 seconds
- Socket.IO handlers for fetching character data from JSON files
- Responsive styling for tabbed interface with dark theme

### Fixed
- Web interface output routing to properly separate game narration and debug information
- Only "Dungeon Master:" messages appear in the game output panel
- All other output (DEBUG, ERROR, system messages, etc.) now goes to the debug panel
- Fixed issue where DM dialogue containing quotes or colons was incorrectly split between panels
- Improved detection of player status lines vs. DM content to prevent incorrect panel routing

## [0.1.0] - 2025-01-17

### Added
- New `generate_prerolls.py` module that pre-generates dice rolls for all combat actions, preventing the LLM from deciding roll outcomes
- Explicit character type labeling in combat (PLAYER, NPC, ENEMY) for clearer differentiation
- Import for `generate_prerolls` function in `combat_manager.py`
- Preroll text generation before each combat round with:
  - Attack rolls
  - Damage rolls (using proper damage dice from creature stats)
  - Saving throw rolls
  - Ability check rolls
  - Clear labeling of creature types and relationships
- Web-based interface for the game with Flask and SocketIO:
  - Separate panels for game output and debug information
  - Real-time updates using WebSockets
  - Automatic browser launch when starting the game
  - Professional dark theme UI
  - Input handling through web interface
- `web_interface.py` - Flask server with SocketIO for real-time communication
- `templates/game_interface.html` - Modern web UI with split panel design
- `run_web.py` - Simple launcher script that starts the web interface

### Changed
- Combat AI no longer determines dice roll outcomes - all rolls are pre-generated
- Enhanced creature type identification with explicit labels:
  - PLAYER CHARACTER: Controlled by the human player
  - NPC: Friendly non-player character allied with the player
  - ENEMY: Hostile monster fighting against the player
- Updated combat prompts to include pre-generated rolls for each round
- Updated `requirements.txt` to include Flask and SocketIO dependencies

### Improved
- Fairness of combat by removing AI bias in dice rolling
- Transparency of combat mechanics with explicit pre-rolled values
- Clarity of character roles and allegiances in combat encounters
- User experience with a modern web interface instead of terminal-only output

### Fixed
- Previously fixed XP calculation path issue for monster files
- Previously fixed .gitignore to exclude runtime and debug files