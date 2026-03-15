# A Developer's Guide to "Keep of Doom": Forging a Home from a Haunted Keep

Welcome, adventurers. This guide provides a detailed walkthrough of the "Keep of Doom" module, demonstrating the flexible design of the game engine and the various ways challenges can be overcome. It highlights how keen observation, creative problem-solving, and strategic use of character abilities can lead to unique and rewarding outcomes beyond simple combat.

## Part 1: The Cursed Woods - Mending a Broken Veil

The journey to Shadowfall Keep is not a simple trek; it is a test of the party's resolve and awareness. The Gloamwood is a character in itself, and interacting with its secrets is key to success.

### The Challenge: The Lost Ward Circle (B06)

The path to the keep is plagued by an unnatural darkness because the forest's ancient protective wards are failing. Keeper Morvath (B07) tasks the party with restoring the central ward circle. A direct path to the keep without this step is possible but significantly more dangerous, leading to more frequent and difficult spectral encounters.

**The Clever Solution: A Ritual of Sacrifice**

This is a multi-stage environmental puzzle, not a combat encounter. To restore the ward, players must follow the instructions in a ritual tome found at the site.

- **Item-Based Interaction**: The party must use the Carved Bone Talisman and Gloamwood Roots provided by Keeper Morvath.
- **Personal Cost**: The ritual requires a blood sacrifice. The Cleric can offer a drop of their own blood, taking a small amount of damage but demonstrating a personal connection to the land.
- **Resource Expenditure**: The final step requires an offering of value. Placing gold coins upon the central menhir completes the rite.

**Developer Insight**: This encounter is designed to reward players who engage with NPCs and explore. It shows that solutions can involve roleplaying, resource management, and interacting with the environment, not just combat. Successfully restoring the ward grants the party a tangible buff (Strengthened Lost Ward Circle), reducing the threat level in the surrounding area.

## Part 2: Breaching the Keep - A Fortress of Sorrow

Shadowfall Keep is a dungeon built on a foundation of tragedy. Its defenses are often memories and echoes rather than simple traps, rewarding players who piece together its history.

### The Challenge: The Animated Guardian (C02 - Gatehouse Ruins)

The path to the Fallen Barracks is blocked by a suit of spectral-infused armor. Its hollow visor glows with hostile energy, and it will attack any who try to force the door behind it. While it can be defeated in combat, it is a formidable foe.

**The Clever Solution: Bypassing with Lore**

This encounter is a direct test of observation. Throughout the keep, players can find clues about the old garrison's codes and loyalties, including a Captain's Badge.

- **Item Presentation**: The Cleric presents the Captain's Badge.
- **Password**: The party speaks the password found in a logbook: "Honor and Shadow are One."

**Developer Insight**: The game engine recognizes this combination of item and dialogue. The armor guardian stands down, granting passage without a single sword swing. This demonstrates how lore is not just flavor text but a key mechanical component for bypassing difficult encounters.

### The Challenge: The Collapsing Staircase (C06 - Broken Tower)

The main spiral staircase in the tower is rigged with a pressure plate trap designed to collapse the section, potentially separating the party or sending them plummeting.

**The Clever Solution: Skill and Spell Synergy**

A high passive Perception might notice something is off, but an active search is more reliable.

- **Active Investigation**: The party declares they are checking for traps.
- **Cantrip Assistance**: The Cleric casts Guidance on the character performing the check, adding a 1d4 bonus.
- **Successful Check**: A successful Investigation roll reveals the pressure plate and the frayed ropes holding the stairs. The party can then carefully disarm it or find a way to secure the staircase before proceeding.

**Developer Insight**: This highlights the utility of non-combat spells and the importance of active skill usage. The game rewards a cautious and prepared party by allowing them to neutralize a deadly threat.

## Part 3: The Heart of Darkness - Salvation and Ownership

The lower levels of the keep are where the curse is strongest. Here, the challenges become more esoteric, demanding empathy and intellect.

### The Challenge: The Bone Speaker's Riddles (E06 - Forgotten Ossuary)

The path to the final chamber is guarded by the Bone Speaker, a spectral entity who will not yield to force. It challenges the party with three riddles about the keep's curse.

**The Clever Solution: A Test of Knowledge**

The answers to the riddles are not random. They are found within the Chaplain's Journal, the Scribe's Pages, and the Echo Crystal discovered in earlier locations.

- **Riddle 1 (Sir Garran's Burden)**: The answer lies in understanding his grief and betrayal, as detailed in the journals.
- **Riddle 2 (The Relic's Weakness)**: The answer is the Knight's Heart Amulet, whose purpose as a ritual focus is hinted at in the lore.
- **Riddle 3 (Elen's Fate)**: The answer requires the party to declare their intent to save her, showing their personal investment in the quest.

**Developer Insight**: This encounter serves as a final "lore check," ensuring the party has engaged with the story. It provides a climactic, non-combat resolution before the final battle, making the players feel like their entire journey of discovery mattered.

### The Challenge: The Final Battle & Elen's Rescue (E07 - Relic Chamber)

The final encounter is a multi-stage fight against the Shadow Relic and its manifestations, with Scout Elen trapped in a Shadow Cage that drains her life.

**The Clever Solution: Tactical Prioritization**

A brute-force approach against the main relic will fail, as Elen will perish. The key is a split-focus strategy.

- **Objective 1: Free Elen**. The party must first focus their attacks on the Shadow Cage. This structure is vulnerable to radiant damage, making a Cleric's Sacred Flame or other holy attacks highly effective.
- **Objective 2: Destroy the Relic**. Once Elen is freed, the entire party can turn their attention to the Shadow Relic. Using the vulnerabilities noted on the Cryptic Map (found in the Ossuary) allows for targeted strikes that deal extra damage.

**Developer Insight**: This encounter is designed to test tactical decision-making under pressure. The game tracks the status of multiple objectives, and the party's success hinges on their ability to prioritize and adapt.

## A New Beginning: A Keep to Call Home

With the curse broken, the module's focus shifts from survival to legacy.

**Recruiting Elen**: Upon being freed, Elen is exhausted but resolute. A simple dialogue invitation from the player to join the party triggers the updatePartyNPCs action. This is a narrative reward that provides a powerful and loyal new ally for future adventures.

**Taking Ownership & Establishing a Hub**: The discovery of the Deed to Shadowfall Keep is a pivotal moment. When the party returns to Harrow's Hollow and declares their intention to claim the keep, the game engine processes this through the establishHub action.

- **Hub Name**: Shadowfall Keep
- **Ownership**: Party
- **Services**: Rest, Storage, Sanctuary

**Developer Insight**: This transforms a completed dungeon into a persistent, player-owned base. It provides a tangible reward for their efforts and a narrative anchor for all future modules, giving the party a true home in the world and a reason to invest in the region's safety.