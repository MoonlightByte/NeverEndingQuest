# Module Quality Audit Checklist

## Overview
This checklist ensures NeverEndingQuest modules are mechanically sound, narratively consistent, and compatible with the game engine's action handler system.

---

## ⚠️ CRITICAL AUDIT GUIDELINES - READ FIRST

### Common False Positives to Avoid

**1. Quest Reward Items "Missing" from Loot Tables**
- **NOT A BUG:** Quest rewards are mentioned in quest descriptions, awarded by AI when quest completes
- **Example:** "Reward: Maelo's Iron Charm" in side quest description
- **Validation:** Check if item mentioned with "Reward:" prefix → CORRECT (not missing)
- **See Section 8** for full explanation of Static Loot vs Dynamic Quest Rewards

**2. Plot Point "location" Field Using Area IDs**
- **CORRECT:** Plot points use area IDs (HFG001, RO001), NOT location IDs (A01, R01)
- **Schema description misleading:** Says "locationId" but actual implementation uses area IDs
- **Validation:** Check module_generator.py:908 confirms "use area ID, not specific room"
- **See Section 3** for plot point validation rules

**3. Monster "disposition" and "strategy" Fields**
- **ACCEPTABLE:** Not in schema but useful for DM guidance
- **Required:** `name` and `quantity: {min, max}`
- **Optional extras:** `disposition`, `strategy`, `description` enhance gameplay but aren't required
- **See Section 2** for monster schema details

---

## 1. CORE MECHANICS COMPLIANCE

### Action Handler Integration (per action_handler.py)
- [ ] All `dmInstructions` use valid action types only (from ACTION_* constants):
  - `createEncounter` - Combat initialization
  - `updateEncounter` - Modify active encounter
  - `updateCharacterInfo` - Stats/inventory changes
  - `updatePlot` - Story progression
  - `levelUp` - Character advancement
  - `transitionLocation` - Movement between locations
  - `updateTime` - Time advancement
  - `updatePartyNPCs` - Add/remove party members
  - `exitGame` - End session
  - `createNewModule` - Module transition
  - `establishHub` - Set hub location
  - `storageInteraction` - Access storage
  - `updatePartyTracker` - Modify party data
  - `moveBackgroundNPC` - NPC movement
  - `saveGame` / `restoreGame` / `listSaves` / `deleteSave` - Save system
- [ ] No invalid actions (e.g., `grantXP`, `awardItems`, `milestone`, `grantBuff`)
- [ ] XP rewards mentioned in context only (auto-awarded by combat system)
- [ ] Level-up triggers use `levelUp` action, not "milestone" or "advance to Level X" language
- [ ] Action calls follow format: "Call actionName with parameters"

### Area File Structure (per loca_schema.json)
- [ ] Required area-level fields: `areaName`, `areaId`, `locations`
- [ ] Recommended area fields: `areaType`, `areaDescription`, `dangerLevel`, `recommendedLevel`, `climate`, `terrain`, `map`, `randomEncounters`, `areaFeatures`, `notes`
- [ ] `areaId` follows same pattern as locationId for consistency
- [ ] Area file stored in `areas/` subdirectory as `{areaId}.json`

### Location System (per loca_schema.json)
- [ ] Required location fields: `name`, `type`, `description`, `dmInstructions`, `locationId`, `coordinates`, `accessibility`, `npcs`, `monsters`, `plotHooks`, `lootTable`, `dangerLevel`, `connectivity`, `areaConnectivity`, `areaConnectivityId`, `traps`, `features`, `dcChecks`, `encounters`, `adventureSummary`, `doors`
- [ ] `locationId` pattern: `^[A-Z]{1,3}[0-9]{2}$` (e.g., A01, BO01, HFG12)
- [ ] `coordinates` pattern: `^X[0-9]+Y[0-9]+$` (e.g., X2Y3)
- [ ] `dangerLevel` enum: "Low", "Medium", "High", "Very High"
- [ ] All location IDs are unique across the entire module
- [ ] Every location has valid `connectivity` array (location IDs within same area)
- [ ] Cross-area transitions have matching `areaConnectivity` (area names) and `areaConnectivityId` (location IDs)
- [ ] **CRITICAL:** `areaConnectivityId` contains **LOCATION IDs** only (e.g., "C01", "H01")
- [ ] **NEVER use area IDs** (e.g., "CMS001", "HFG001") in `areaConnectivityId` - these are location IDs only
- [ ] `transitionLocation` action uses location IDs - areaConnectivityId must match this format
- [ ] Bidirectional connectivity: If location A connects to area B via location B01, then B01 must connect back to A
- [ ] Starting location (first area, first location) is clearly accessible
- [ ] All arrays present even if empty (npcs: [], monsters: [], etc.)

### Map Data (per map_schema.json)
- [ ] Required map fields: `mapName`, `mapId`, `totalRooms`, `rooms`, `layout`
- [ ] Optional map fields: `startRoom`, `version`, `notes`
- [ ] Every area file contains embedded `map` object
- [ ] Map `totalRooms` integer matches actual number of rooms in array
- [ ] Each room requires: `id`, `name`, `connections`, `coordinates`
- [ ] Optional room fields: `type`, `directions`, `tags`, `purpose`, `landmark`, `dangerLevel`
- [ ] Map `rooms` array IDs match `locations` array location IDs exactly
- [ ] Map room `connections` match location `connectivity` (bidirectional)
- [ ] Map `layout` is 2D array visually representing room positions
- [ ] Room coordinates follow `XnYn` pattern and are unique per area
- [ ] `directions` object uses cardinal directions: "north", "south", "east", "west"

---

## 2. NPC & MONSTER INTEGRITY

### NPC Structure (per loca_schema.json)
- [ ] All NPCs have required fields: `name`, `description`, `attitude` (all required)
- [ ] No invalid fields (e.g., `isRecruitableNPC`, `class`, `race`, `level`, `recruitCondition`)
- [ ] Recruitable NPCs have recruitment conditions embedded in `description` text
- [ ] Key NPCs mentioned in plot actually exist in area files
- [ ] NPC names are consistent across all references
- [ ] No monsters accidentally placed in `npcs` array
- [ ] **Named NPCs in dmInstructions exist in that location's NPCs array** (specific names like "Elric", not generic "guards")
  - Partial name matches OK: "Hedra" acceptable if "Mistress Hedra Lanternwise" in array
  - Monsters in monsters array, not NPCs, are OK to reference
  - Generic NPCs ("a villager", "guards") don't need array entry
  - **Use AI review for accuracy** - keyword search produces false positives

### Monster Structure (In Location Files)
- [ ] Each monster appears in `monsters` array (not `npcs`)
- [ ] Monster objects have: `name` (required), `description` (optional), `stats` (optional)
- [ ] Monster `quantity` field: `{min: integer, max: integer}` (required per schema)
- [ ] No duplicate monster names unless intentionally different variants
- [ ] Boss/mini-boss monsters clearly labeled in name (e.g., "Name (Mini-boss)")
- [ ] Monster stat blocks in `stats` field for complex encounters
- [ ] XP values mentioned in `dmInstructions` for DM reference
- [ ] NOTE: Full monster stat blocks (mon_schema.json) are for compendium only, not location files

### Location Sub-Structures (per loca_schema.json)

#### Traps
- [ ] Each trap has required fields: `name`, `description`, `detectDC`, `disableDC`, `triggerDC`, `damage`
- [ ] DC values are integers appropriate for level
- [ ] Damage format: "XdY damage_type" (e.g., "2d6 necrotic")

#### Doors
- [ ] Each door has required fields: `name`, `description`, `type`, `locked`, `lockDC`, `breakDC`, `keyname`, `trapped`, `trap`
- [ ] `locked` is boolean
- [ ] `trapped` is boolean
- [ ] If `trapped: true`, the `trap` field should describe the trap
- [ ] DC values are integers

#### Features
- [ ] Each feature has required fields: `name`, `description`
- [ ] Features describe notable environmental elements
- [ ] No gameplay mechanics in features (use traps or encounters instead)

#### DC Checks
- [ ] Format pattern: `^[A-Z][a-z]+ DC [0-9]+: .+$`
- [ ] Examples: "Perception DC 15: Notice signs...", "Investigation DC 12: Find..."
- [ ] Skill names are properly capitalized (Perception, Investigation, Arcana, etc.)
- [ ] DC values appropriate for level (10-13 Low, 13-15 Medium, 15-18 High)

#### Encounters
- [ ] Encounters in location files can be objects OR strings (schema allows both)
- [ ] If object: requires `encounterId`, `summary`, `impact`, `worldConditions`
- [ ] `encounterId` pattern: `^[A-Za-z0-9]+-E[0-9]+$`
- [ ] `worldConditions` requires: `year`, `month`, `day`, `time`

---

## 3. PLOT COHERENCE

### Plot Point Validation (per plot_schema.json)
- [ ] Required root fields: `plotTitle`, `mainObjective`, `plotPoints`
- [ ] Each plot point has: `id`, `title`, `description`, `location`, `nextPoints`, `status`, `plotImpact`
- [ ] Plot point `location` values reference existing area IDs (NOT location IDs)
- [ ] Plot point `status` uses valid enum: "not started", "in progress", "completed"
- [ ] Plot progression: Each `nextPoints` references valid plot IDs
- [ ] Final plot point has `"nextPoints": []`
- [ ] Side quest `involvedLocations` reference existing area IDs
- [ ] Side quests have: `id`, `title`, `description`, `involvedLocations`, `status`, `plotImpact` (all required)
- [ ] No references to removed/archived areas

### Narrative Flow
- [ ] Plot progression matches actual area progression
- [ ] Key items mentioned in plot exist in area loot tables
- [ ] Boss encounters in plot match monsters in area files
- [ ] Level requirements: PP001-PP002 (Level 1), PP003-PP005 (Level 2), PP006-PP007 (Level 3)
- [ ] `dmNotes` contain gameplay mechanics, not story spoilers

### Side Quest Cleanup
- [ ] No side quests referencing NPCs in wrong locations
- [ ] No duplicate quests across different plot points
- [ ] Quest rewards are achievable with items/NPCs that exist

---

## 4. CONNECTIVITY & PATHFINDING

### Area Flow
- [ ] Linear progression: Starting area → Intermediate areas → Boss area
- [ ] All areas reachable from starting location
- [ ] No orphaned areas (disconnected from main path)
- [ ] Cross-area transitions make narrative sense
- [ ] At least one path exists between any two locations

### Connectivity IDs
- [ ] `areaConnectivity` contains area NAMES (strings)
- [ ] `areaConnectivityId` contains location IDs (not area IDs)
- [ ] No dict objects in connectivity arrays
- [ ] Reciprocal connections: If location A → area B, then area B has location → A

### Narrative-Location Consistency
- [ ] All locations mentioned in plot hooks actually exist as locations
- [ ] All locations mentioned in NPC descriptions actually exist as locations
- [ ] All locations mentioned in dmInstructions actually exist as locations
- [ ] No references to "the old barn", "the tower", "the cave" without corresponding location names
- [ ] Quest destinations in plot/side quests reference actual location IDs or names
- [ ] Area descriptions don't reference locations that don't exist in the area
- [ ] **CRITICAL:** Grep all area files for quoted location references in plotHooks/descriptions - verify each one exists as a location name
- [ ] **Example issue:** "last seen near the old barn" but no location named "Old Barn" or "Barn of Offerings"
- [ ] **Fix:** Either add the missing location OR change narrative to reference existing location names

### Plot Hook Sequential Progression ⚠️ CRITICAL
**Plot hooks must guide players through areas in sequential order matching plot point progression.**

#### The Core Issue
When plot hooks in early areas reference late-game locations, level 1 players skip critical narrative progression and arrive unprepared at high-level content.

#### Validation Rules
- [ ] Plot hooks in PP001-PP002 areas reference ONLY next 1-2 plot point areas
- [ ] Plot hooks in starting areas do NOT mention: final boss lairs, endgame artifacts, climax locations
- [ ] Plot hooks in mid-game areas do NOT point backward to starting areas
- [ ] Each area's plot hooks create breadcrumb trail to the NEXT sequential area
- [ ] No plot hook skips more than 1 plot point ahead
- [ ] Area danger escalation matches plot hook references (low→medium→high→boss)

#### Sequential Progression Pattern
```
Area for PP001 (Starting)
  └─> Plot hooks mention: PP002 areas (immediate next step)
  └─> Do NOT mention: PP005+ areas (endgame locations)

Area for PP002 (Early Investigation)
  └─> Plot hooks mention: PP003 areas (next investigation site)
  └─> Do NOT mention: PP001 areas (backward) or PP006+ (too far ahead)

Area for PP003-PP004 (Mid-game)
  └─> Plot hooks mention: PP005 areas (major discovery site)
  └─> Do NOT mention: PP001-PP002 (backward) or PP007 (finale)

Area for PP005 (Major Discovery)
  └─> Plot hooks mention: PP006 areas (penultimate challenge)
  └─> Do NOT mention: Earlier areas (backward references)

Area for PP006 (Penultimate)
  └─> Plot hooks mention: PP007 areas (final confrontation)
  └─> May reference key items/knowledge from PP005

Area for PP007 (Finale)
  └─> Plot hooks describe final challenge mechanics
  └─> May reference all previous plot progression
```

#### Common Violations
**❌ Starting Area References:**
- Mentioning graveyards/crypts when those are in PP006
- Referencing ritual altars when those are in PP005
- Naming endgame artifacts before players should know they exist
- Pointing to boss lair locations

**❌ Mid-game Area References:**
- Pointing back to starting town/village
- Referencing early NPCs who aren't present
- Directing players to already-completed areas

#### How to Validate
```bash
# 1. Map plot points to areas from module_plot.json
# Identify which areas correspond to which plot points

# 2. For each area, check plot hooks reference appropriate progression
grep -h "plotHooks" modules/[Module]/areas/[StartingArea].json -A5

# 3. Look for danger mismatches (safe area mentioning deadly locations)
# 4. Check for backward progression (mid-game pointing to start)
# 5. Verify endgame locations only mentioned in late-game areas
```

#### Fix Pattern
When plot hook violates sequential progression:

1. **Identify current plot point** for the area
2. **Find next plot point** in sequence
3. **Replace reference** with location from next plot point's area
4. **Maintain narrative tone** while fixing geography

**Generic Fix Examples:**
```diff
Starting Area (PP001):
- "Visit the [endgame location]"
+ "Investigate the [PP002 location]"

- "Seek the [key artifact from PP005]"
+ "Strange reports from [PP002 area]"

Mid-game Area (PP004):
- "Return to [starting village]"
+ "Trail leads to [PP005 area]"
```

#### Why This Matters
- **Narrative:** Preserves mystery, pacing, and story revelation order
- **Mechanical:** Ensures level-appropriate challenges (no level 1 at boss)
- **Player Experience:** Clear progression, proper difficulty curve, earned victories

---

## 5. ENCOUNTER BALANCE

### XP Progression
- [ ] Level 1→2 requires ~300 XP (available in first 2-3 areas)
- [ ] Level 2→3 requires ~600 XP (available in remaining areas)
- [ ] Total module XP: 900-3000 range
- [ ] Boss encounters: 400-700 XP
- [ ] Mini-bosses: 300-500 XP
- [ ] Regular encounters: 25-150 XP

### Combat Mechanics
- [ ] Skill challenges use format: "3 successes before 2 failures"
- [ ] DC checks appropriate for level (DC 10-13 Level 1, DC 13-15 Level 2, DC 15-18 Level 3)
- [ ] Boss phases clearly marked with HP thresholds (e.g., "at 70% HP")
- [ ] Lair actions on Initiative 20 with clear triggers
- [ ] Destructible objects have AC, HP, vulnerabilities

---

## 6. TECHNICAL COMPLIANCE

### File Structure
- [ ] Module folder name matches registry entries (no apostrophe mismatches)
- [ ] All area files in `areas/` subdirectory
- [ ] `module_plot.json` in module root
- [ ] `module_context.json` exists and is valid
- [ ] No orphaned map files (maps should be embedded in area files)
- [ ] BU (backup) files exist for all critical files
- [ ] Old backup files moved to `old_backups/` or `archived_areas_*/`

### Template File Integrity (BU Files) ⚠️ CRITICAL
**BU files are clean templates and MUST NOT contain pre-populated gameplay data.**

- [ ] ALL locations in BU files have `"encounters": []` (empty array)
- [ ] ALL locations in BU files have `"adventureSummary": ""` (empty string)
- [ ] No encounter objects with encounterId/summary in BU files
- [ ] No pre-written adventureSummary text in BU files

**Why This Matters:**
- encounters array: Populated when player visits location (records what happened)
- adventureSummary: AI-generated summary when player leaves location after events
- Empty = unexplored/template, Has entries = visited/gameplay occurred
- Transition intelligence system uses this to detect visited vs unexplored locations

**Validation Commands:**
```bash
# Detect non-empty encounters in BU files
grep -h '"encounters"' modules/[Module]/areas/*_BU.json | grep -v '\[\]'

# Detect non-empty adventureSummary in BU files
grep -h '"adventureSummary"' modules/[Module]/areas/*_BU.json | grep -v '""'
```

**If violations found:** BU files were incorrectly generated with pre-populated data. Fix with:
```python
for location in area_data['locations']:
    location['encounters'] = []
    location['adventureSummary'] = ""
```

### Schema Compliance
- [ ] All NPCs follow: `{name, description, attitude}` (all required)
- [ ] All monsters follow: `{name, quantity: {min, max}}` (quantity required per schema)
- [ ] All traps follow: `{name, description, detectDC, disableDC, triggerDC, damage}` (all required)
- [ ] All doors follow: `{name, description, type, locked, lockDC, breakDC, keyname, trapped, trap}` (all required)
- [ ] All features follow: `{name, description}` (both required)
- [ ] All locations have ALL required fields per `loca_schema.json` (20 required fields)
- [ ] No Unicode characters in JSON (ASCII only for Windows compatibility)
- [ ] All JSON files valid (no syntax errors)
- [ ] No extra fields outside schema (e.g., `isRecruitableNPC`, `recruitCondition`)

### Registry Integration
- [ ] Module name in `campaign.json` matches folder name
- [ ] Module entry in `world_registry.json` matches folder name
- [ ] No apostrophes in module folder names (use "Kings" not "King's")

---

## 7. NARRATIVE QUALITY

### Thematic Consistency
- [ ] Area descriptions match stated danger levels
- [ ] NPC attitudes align with their situations
- [ ] Monster types fit area themes (undead in graveyards, plant creatures in fields)
- [ ] Loot tables contain thematically appropriate items
- [ ] Plot hooks connect to actual gameplay locations

### DM Guidance
- [ ] `dmInstructions` are actionable and specific
- [ ] DC checks listed for all skill challenges
- [ ] Combat triggers clearly stated
- [ ] Roleplay guidance provided for key NPCs
- [ ] `dmNotes` in plot file explain complex mechanics

### Spawn Loop Prevention ⚠️ CRITICAL
**Prevent infinite monster spawning by identifying unconditional spawn instructions**

- [ ] **HIGH RISK ONLY:** Check for unconditional "Use the [Monster Name]" pattern without nearby "if/when" conditional
- [ ] Locations with vague progression ("drive deeper") should have specific destination if it's a required path

**What to Look For (HIGH RISK):**
- Pattern: "Use the [Monster]" or "spawn [Monster]" as unconditional instruction
- No "if", "when", or "after" conditional within 50 characters before the instruction
- Vague progression like "drive the party deeper" without naming destination location

**Example - HIGH RISK (causes spawn loops):**
```
"Use the Cornfield Shadow as a low-level ambush or to drive the party deeper."
→ Unconditional "Use the Shadow", vague "drive deeper", AI spawns infinitely
```

**Example - SAFE (acceptable patterns):**
```
"Call createEncounter with Shadow if party makes noise" ✓ (has "if")
"Animated Scarecrow defends its post if disturbed" ✓ (has "if")
"On combat encounter: Call createEncounter" ✓ (reactive, not prescriptive)
```

**Example - FIXED (best practice):**
```
"IF monsters array contains Cornfield Shadow: Use as ambush to build tension.
AFTER threats cleared (monsters array empty): Guide party to C03 (Widow Grella).
Do NOT spawn additional threats once area is cleared."
```

**Note:** Most locations naturally avoid this by using reactive language ("if disturbed", "on approach", "when party does X"). Only audit for the unconditional "Use the [Monster]" pattern which is the actual bug.

### Rare Encounter Triggers ⚠️ CRITICAL
**Avoid complex or rare conditions that can break game progression**

- [ ] No rare environmental triggers for essential NPCs or plot progression
- [ ] Avoid: "when moon appears", "during full moon", "at midnight", "if raining"
- [ ] Avoid: Time-based conditions that may never occur naturally
- [ ] Avoid: Complex multi-condition requirements for critical encounters

**Problematic Triggers (can break progression):**
```
"When moon appears: Present Widow Grella" ❌ (rare condition blocks key NPC)
"During full moon: Spawn quest-critical monster" ❌ (may never trigger)
"At midnight if party has X item: Reveal NPC" ❌ (too specific)
```

**Safe Triggers (reliable and player-controlled):**
```
"On arrival: Present Widow Grella" ✓ (immediate, guaranteed)
"IF party disturbs effigy: Call createEncounter" ✓ (player action)
"When party investigates: Reveal NPC" ✓ (player-controlled)
"IF party makes noise: Trigger ambush" ✓ (player action)
```

**Rule:** Essential NPCs and plot progression should use **immediate** ("On arrival") or **player-controlled** ("IF party does X") triggers, never rare environmental conditions.

### Player Agency
- [ ] Multiple approaches available (combat, stealth, diplomacy)
- [ ] Choices have stated consequences in `plotImpact`
- [ ] Side quests are optional but rewarding
- [ ] No forced outcomes or railroad mechanics

---

## 8. ITEM & REWARD TRACKING

### Key Artifacts & Reward Design Patterns ⚠️ CRITICAL UNDERSTANDING

**NeverEndingQuest uses TWO different item distribution methods. Understanding this prevents false positives in audits.**

#### Method 1: Static Loot Tables (Search & Find Items)
**Location:** In area JSON files under `lootTable` array
**Distribution:** Player searches location, AI reads loot table, awards items
**Always Available:** Yes - items physically exist in the world

**Example from area file:**
```json
"lootTable": [
  "Herbal healing potion brewed by the hermit",
  "Ward stones that protect against supernatural influence",
  "Ancient tome describing the corruption from the north"
]
```

**When to use:**
- Environmental treasures (gold in chests, weapons on racks)
- Location-specific items (books in libraries, tools in workshops)
- Enemy drops (items bandits would carry)
- Generic loot that doesn't require player action to earn

#### Method 2: Dynamic Quest Rewards (Earned Through Quests)
**Location:** In `module_plot.json` quest descriptions (side quest or plot point text)
**Distribution:** Player completes quest → AI reads reward description → AI calls updateCharacterInfo → item added to inventory
**Always Available:** No - player must complete quest objectives

**Example from module_plot.json:**
```json
{
  "id": "SQ003",
  "title": "The Hermit's Warning",
  "description": "The party can find a hidden cabin belonging to Maelo, a hermit who studies the forest's energies. He will only help if the party first cleanses a nearby spring he uses for scrying, which has been tainted by Malarok's magic. He can then perform a ritual to learn more about the threat. Reward: Maelo's Iron Charm (grows cold in the presence of dark magic, can potentially break enchantments).",
  ...
}
```

**When to use:**
- Quest-specific rewards (NPC gives item after helping them)
- Earned artifacts (complete ritual to receive charm)
- Personal gifts from NPCs (hermit gives his personal item as thanks)
- Items that should feel earned, not randomly found

### Audit Checklist for Items

- [ ] **Static Loot Items** exist in appropriate location loot tables
- [ ] **Quest Reward Items** are mentioned in quest descriptions with "Reward:" prefix
- [ ] Quest reward items are **NOT in loot tables** (this is correct - don't flag as missing!)
- [ ] Quest rewards clearly stated in side quest `description` field
- [ ] Static loot artifact locations indicated in `dmInstructions`
- [ ] Special item mechanics documented in `dmNotes` or item description
- [ ] No duplicate artifacts across locations (same named item in multiple places)

### ⚠️ CRITICAL: How to Identify Quest Rewards vs Missing Items

**Quest Reward (CORRECT - Don't flag as bug):**
```
✓ Item mentioned in plot file with "Reward:" in description
✓ Item given by named NPC
✓ Item requires completing quest objectives
✓ NOT in any loot table
Example: "Reward: Maelo's Iron Charm" in SQ003
```

**Missing Item (INCORRECT - Flag as bug):**
```
✗ Item mentioned in plot as "use the ancient key"
✗ No indication it's a quest reward
✗ No NPC gives it
✗ NOT in any loot table
✗ Player has no way to obtain it
Example: Plot says "use the iron key to open the door" but key doesn't exist anywhere
```

**Validation Method:**
If item is mentioned in plot/quest:
1. Check if quest description says "Reward: [item name]" → QUEST REWARD (correct)
2. Check if item is in relevant location loot table → STATIC LOOT (correct)
3. If neither → MISSING ITEM (bug)

### Why This Design Is Correct

**Quest rewards should NOT be in loot tables because:**
- ✅ Rewards player agency and quest completion
- ✅ Prevents getting quest rewards without doing quests
- ✅ Gives AI DM narrative control over timing of award
- ✅ Makes quest completion feel meaningful and rewarding
- ✅ Allows NPC interaction to feel personal (gift, not finding item on ground)
- ✅ Quest descriptions serve as "virtual loot table" for earned items

**If quest rewards were in loot tables:**
- ❌ Player could get Maelo's personal charm without ever meeting Maelo
- ❌ Quest completion feels unrewarding (already have the item)
- ❌ Narrative disconnect (why is NPC's personal item lying around?)
- ❌ No incentive to complete optional quests

### Validation Examples

**✓ CORRECT Implementation (Thornwood Watch):**
- **Static Loot:** "Ward stones" in TW04 loot table
- **Quest Reward:** "Maelo's Iron Charm" in SQ003 description with "Reward:" prefix
- **Result:** Both systems working as intended

**✗ INCORRECT Implementation:**
- Item mentioned in PP004: "Use the sealed scroll to banish the demon"
- NOT in quest rewards
- NOT in loot tables
- **Result:** Missing item - player cannot progress

### Loot Balance
- [ ] Magic items appropriate for level range
- [ ] Currency rewards proportional to level (50-200 gp for Level 1-3)
- [ ] Consumables available for resource management
- [ ] Boss loot clearly superior to regular loot

---

## 9. FINAL POLISH

### Cleanup Checklist
- [ ] No references to deleted/archived areas
- [ ] All backup files (.bak, .backup_*) moved to `old_backups/`
- [ ] BU files contain latest stable versions
- [ ] Module folder contains only necessary files
- [ ] Standalone map files removed (if maps embedded in areas)

### Validation Tests
- [ ] Pathfinding test: All locations reachable from start
- [ ] Monster name check: No unintentional duplicates
- [ ] NPC audit: All plot NPCs exist in areas
- [ ] Connectivity test: No broken area transitions
- [ ] JSON syntax: All files parse correctly

---

## 10. COMMON SCHEMA VIOLATIONS (Quick Reference)

### NPCs - Frequently Added Invalid Fields
- ❌ `isRecruitableNPC` - Does not exist in schema
- ❌ `recruitCondition` - Does not exist in schema
- ❌ `class`, `race`, `level` - Does not exist in schema
- ✅ Put recruitment info IN the `description` field
- ✅ Only use: `name`, `description`, `attitude`

### Monsters - Schema vs Practice Mismatch
- ⚠️ Schema REQUIRES `quantity: {min, max}` but many modules omit it
- ⚠️ Actual practice: `{name, description, stats}` is commonly used
- ✅ For safety, include both: `name`, `description`, `stats`, `quantity`

### Connectivity - Most Common Errors ⚠️ CRITICAL
- ❌ **WRONG:** `areaConnectivityId: ["CMS001"]` - Using area ID
- ✅ **CORRECT:** `areaConnectivityId: ["C01"]` - Using location ID
- ❌ **WRONG:** `areaConnectivityId: ["HFG001"]` - This is an area ID
- ✅ **CORRECT:** `areaConnectivityId: ["A01"]` - This is a location ID
- **Rule:** `areaConnectivityId` MUST contain location IDs (2-4 chars: A01, C01, H01, BO01)
- **Never:** Area IDs (5+ chars: HFG001, CMS001, BOO001) in areaConnectivityId
- ❌ Dict objects in `areaConnectivity` arrays - should be strings only
- ❌ One-way connections - if A→B, then B must→A
- ✅ `areaConnectivity` = area names (strings like "The Wailing Cornfields")
- ✅ `areaConnectivityId` = location IDs (strings like "C01", NOT "CMS001")

### Plot Points - Common Mistakes
- ❌ `location` field using location ID instead of area ID
- ❌ Using "milestone" language instead of `levelUp` action
- ❌ Side quests referencing NPCs not in that area
- ✅ `location` should be area ID (HFG001, not A01)
- ✅ Use "Call levelUp" not "Milestone: advance to Level X"

### Traps - Schema Strictness
- ⚠️ Schema REQUIRES: `name`, `description`, `detectDC`, `disableDC`, `triggerDC`, `damage`
- ⚠️ Many modules use simplified format with just DC values
- ✅ For compliance, always include `name` and `description`

### Doors - Full Requirements
- ⚠️ Schema requires ALL 9 fields even if values are empty/false
- ✅ Always include: `name`, `description`, `type`, `locked`, `lockDC`, `breakDC`, `keyname`, `trapped`, `trap`
- ✅ Use empty string `""` for unused fields, not null

---

## USAGE NOTES

### When to Use This Checklist
- After creating a new module
- Before releasing a module to players
- After major structural changes
- When debugging gameplay issues
- During module review/QA process

### Priority Levels
- **CRITICAL** (Sections 1-4): Game-breaking if failed
- **IMPORTANT** (Sections 5-6): Impacts gameplay quality
- **POLISH** (Sections 7-9): Enhances player experience

### Automation Potential
Many items can be validated programmatically:
- JSON syntax validation
- Schema compliance checking
- Pathfinding validation
- Monster/NPC name deduplication
- Connectivity graph analysis

### Validation Commands

#### Schema Validation (Per-Module)
```bash
# Validate specific module by slug
python core/validation/validate_module_files.py --module The_Pumpkin_Kings_Curse

# Validate with JSON output
python core/validation/validate_module_files.py --module The_Pumpkin_Kings_Curse --json

# Validate all detected modules
python core/validation/validate_module_files.py --all-modules

# Validate with explicit path
python core/validation/validate_module_files.py --module-path /path/to/module

# Get help
python core/validation/validate_module_files.py --help
```

**Exit codes:**
- `0` - Validation passed
- `1` - Validation failed (schema errors or validation failures)
- `2` - Execution error (e.g., jsonschema not installed, module not found)

#### Bulk Validation (All Modules)
```bash
# Validate all modules with human-readable output
python scripts/validate_modules_bulk.py

# Validate all modules with JSON output
python scripts/validate_modules_bulk.py --json

# Validate specific module(s)
python scripts/validate_modules_bulk.py --module The_Pumpkin_Kings_Curse
python scripts/validate_modules_bulk.py --module Keep_of_Doom --module The_Thornwood_Watch

# Force all-modules scan
python scripts/validate_modules_bulk.py --all
```

**Exit codes:**
- `0` - All modules passed
- `1` - One or more modules failed validation
- `2` - Execution/config error (no modules found, modules dir missing)

#### Gameplay Audit (Monster Reference Parity)
```bash
# Audit specific module for monster reference parity
python scripts/audit_module_gameplay.py --module The_Pumpkin_Kings_Curse

# Audit with JSON output
python scripts/audit_module_gameplay.py --module The_Pumpkin_Kings_Curse --json

# Audit with strict instruction checking
python scripts/audit_module_gameplay.py --module The_Pumpkin_Kings_Curse --strict-instructions
```

**Exit codes:**
- `0` - No blocking errors
- `1` - Blocking errors found (missing monster JSON, missing media, etc.)

#### Manual Checks
```bash
# Test pathfinding
python -c "
from utils.location_path_finder import LocationGraph
graph = LocationGraph()
graph.load_module_data()
# Test paths between key locations
"

# Check for duplicate monsters
grep -h '"name":' modules/[ModuleName]/areas/*.json | grep -A1 monsters | sort | uniq -c | grep -v "1 "

# Verify area connectivity
grep -h 'areaConnectivityId' modules/[ModuleName]/areas/*.json

# List all NPCs
grep -h '"name":' modules/[ModuleName]/areas/*.json | grep -B2 '"attitude"' | grep name
```

---

## VERSION HISTORY
- v1.0 (2025-09-30): Initial checklist based on The Pumpkin Kings Curse cleanup
- v1.1 (2025-09-30): Added schema-specific requirements from loca_schema.json, plot_schema.json, map_schema.json, and action_handler.py validation
- v1.2 (2025-10-01): Added critical audit guidelines to prevent false positives
  - Added Static Loot vs Dynamic Quest Rewards pattern explanation (Section 8)
  - Clarified quest reward items should NOT be in loot tables
  - Added validation method to distinguish quest rewards from missing items
  - Added common false positives section with examples
  - Validated against Thornwood Watch actual playthrough data
- v1.3 (2025-10-06): Added Plot Hook Sequential Progression validation (Section 4)
  - Added critical check for plot hooks referencing areas in correct sequence
  - Prevents early areas from pointing to endgame locations
  - Ensures narrative progression follows PP001→PP002→...→PP007 pattern
  - Generic, module-agnostic validation rules and fix patterns
  - Prevents level 1 players from skipping to endgame content
