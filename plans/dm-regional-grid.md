# DM Regional Grid (Macro World Map & Procedural Discovery)

## 1. Objective
Scale the "phenomenological bounds" concept from the local room level to the macro world level. By placing isolated adventure modules onto a dynamic, procedurally generated `WorldX, WorldY` grid, we give the LLM DM awareness of neighboring regions. This enables organic travel, geographically consistent rumors, and a true "Fog of War" experience as the campaign expands endlessly.

## 2. Core Philosophy: Procedural Macro-Geography
* **Isolated but Spatially Aware:** Modules remain mechanically isolated JSON ecosystems (`"isolatedModules": True`). However, they are wrapped in a spatial metadata layer for the specific campaign.
* **Procedural Unfolding:** The world map is not hardcoded. As players pick a direction (e.g., "We ride North into the unknown"), the system dynamically selects a level-appropriate module from the `world_registry.json` and permanently pins it to that coordinate for the current campaign.
* **The Regional Horizon:** The LLM receives a 3x3 macro-grid showing the current module, discovered adjacent modules, and "Unexplored" wilderness.
* **Organic Rumors & Travel:** The LLM uses the themes of adjacent modules to organically generate rumors in taverns, and uses the macro-grid to narrate multi-day travel between regions.

## 3. Implementation Plan

### Step 3.1: Campaign World State (`party_tracker.json`)
The global `world_registry.json` contains *all* installed modules, but the specific layout of the world is unique to each campaign.
We will add a `worldMap` object to `party_tracker.json`:
```json
"worldMap": {
  "0,0": "Keep_of_Doom",
  "0,1": "The_Thornwood_Watch",
  "-1,0": "The_Pumpkin_Kings_Curse"
}
```
*   The starting module is always placed at `0,0`.
*   As players travel, new coordinates are populated.

### Step 3.2: Procedural Module Placement
Create a Python service (e.g., `core/managers/world_map_manager.py`) to handle exploration:
1. **Detect Exploration:** If the LLM issues a `transitionRegion(direction="North")` action, Python checks the coordinate `(X, Y+1)`.
2. **Assign Module:** If empty, Python scans `world_registry.json` for modules the party hasn't visited, filtering by `levelRange` matching the party's current level.
3. **Pin & Save:** It pins the selected module to `(X, Y+1)` in `party_tracker.json` and initiates the standard module transition sequence.

### Step 3.3: Regional Grid Construction
Similar to the local grid, build a 3x3 ASCII representation of the macro-world based on the party's current `WorldX, WorldY`.
*   Fetch adjacent coordinates.
*   If a coordinate has a mapped module, display its name and brief terrain type.
*   If empty, display `[ Unexplored ]`.

### Step 3.4: Output Formatting & Injection
Inject the Regional Grid into the `dm_note` *only* when appropriate (e.g., when outdoors, in a hub town, or when the player explicitly asks about the wider world/travel).

**Example Output:**
```text
Regional World Map (3x3 Macro Grid):
[ Thornwood ] [ Unexplored ] [ Unexplored ]
[ P.K. Curse]-[    HERE    ]-[ Greenfields]
[ Unexplored] [ Unexplored ] [ Unexplored ]

Your Region: [HERE] Harrow's Hollow (Keep of Doom) [Level 3-5]
Regional Horizons:
- North: The Thornwood Watch (Blighted Forest) [Est. Travel: 3 Days]
- West: The Pumpkin King's Curse (Cursed Farmland) [Est. Travel: 2 Days]
- East: Greenfields (Peaceful Plains) [Est. Travel: 1 Day]
- South: Unexplored Wilderness (Unknown dangers)

DM Instruction: Use these regions to provide rumors if asked. If players travel to an Unexplored region, narrate a journey into the unknown wilderness.
```

### Step 3.5: Linking with the Module Stitcher
Leverage the existing `module_stitcher.py` and its generated `travelNarration`. When the party travels to an adjacent module, the LLM can seamlessly use the stitcher's atmospheric text to describe the multi-day journey crossing the regional boundary.

## 4. Phase Rollout

* **Phase 1: Foundation**
  * Create `core/managers/world_map_manager.py`.
  * Add `worldMap` tracking to `party_tracker.json`.
  * Initialize the starting module at `0,0`.
* **Phase 2: The Horizon Prompt**
  * Build the 3x3 macro-grid renderer.
  * Inject it into the `dm_note` under specific conditions (e.g., `areaType == "hub"` or `areaType == "wilderness"`).
* **Phase 3: Procedural Expansion**
  * Add the new `transitionRegion` AI action.
  * Implement the logic that selects and pins new modules from the registry when an unexplored direction is chosen.
* **Phase 4: Ecosystem Integration**
  * As the massive Module Import pipeline (Homebrewery/DMsGuild) pulls in dozens of modules, the world map will organically expand outward infinitely based on player choice.

## 5. Why this works
This design requires **zero changes to existing modules**. It treats modules as isolated black boxes and simply arranges them on a campaign-specific pegboard. It gives the LLM massive contextual awareness of the "world" without overwhelming its token limit, perfectly mirroring human DM improvisation ("Let me check my notes to see what's North of here... ah, the Thornwood").