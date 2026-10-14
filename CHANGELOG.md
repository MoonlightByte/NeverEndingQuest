# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- In a fight, after a character swings a weapon, the fight event now records the engine's view of that character's hands, and a carried weapon that fits a free hand in its default grip is drawn, so it is in hand for the next turn (NUM-B, Refs #193). The swing itself is never refused or changed. A thrown weapon, a stack such as eight javelins, a grip other than the default, or hands that are full is recorded but not drawn. When a weapon is drawn this way, the fight narration now says so ("draws the dagger and attacks"); nothing else about the hands reaches the narration (NUM-B2).

### Changed
- The game's OpenAI model profiles now name `gpt-6-luna` in place of `gpt-5.6-luna`, so the 84 tasks on luna, the main DM response included, move together with the same reasoning efforts; the five tasks on other models are unchanged. `gpt-6-luna` lists $0.10 input and $0.50 output per million tokens, against $0.20 and $1.20.
- At startup the game no longer builds companion memories by matching keywords in the journal (#855). For an older game opened for the first time, that build set each companion's starting relationship with the player from those matches. Companion memory now comes only from the episodic memory upgrade, which reads the same journal. Memory files a game already has are kept and read as before.
- The Thornwood Watch's Bandit Stronghold keeps every fight closed (#852). An alarm brings the whole camp into the fight from its first round instead of the warriors arriving two rounds later. A quiet fight out at the lookout posts stays as it started, and a loud one wakes the camp, which comes out together as a new fight. The DM is told to suggest picking the bandits off one at a time, and Bandit Captain Gorvek is back to 27 HP. The DM prompts now say that responders are in a fight from its start and nobody joins a fight already under way.
- Simplified the end of a location move in the action handler: removed three checks that could never fail (the move's transition record always exists at that point), joined three back-to-back blocks with the same condition into one, and deleted stray comments after a return. No behavior change (#773 follow-up).
- Removed `core/ai/conversation_compression.py`, a module that could not be imported (it imported two modules missing from the repository) and that nothing used. The README's compression section now names the live `utils/compression/conversation_compressor_parallel.py`, and `model_config.py` for the `COMPRESSION_ENABLED` switch (#811).
- Unused summary code in `core/ai/cumulative_summary.py`, seven functions left from an older summary pipeline that nothing called, was removed, and the registered source lines of its two remaining AI calls (T018, T019) were corrected (#798). Gameplay, summaries and saves are unchanged.

### Fixed
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