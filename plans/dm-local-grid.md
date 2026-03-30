# DM Local Sensory Grid (3x3 Bounded Map)

## 1. Objective
Enhance the LLM's spatial reasoning and narrative consistency by providing a token-efficient, 3x3 ASCII grid of the party's immediate surroundings. This grid represents the "phenomenological" view—what the characters and the DM can immediately sense (the "here" and the "over there")—without requiring mathematically perfect global maps.

## 2. Core Philosophy: Topological Relativity
* **Python Enforces Reality:** Movement validation relies strictly on the `connectivity` array (the graph edges). If Room A is connected to Room B, the transition is legal.
* **The LLM Interprets Space:** The LLM receives a 3x3 ASCII representation of the connected rooms based on their relative `coordinates` (e.g., "X2Y2"). This gives the LLM directional context (North, South, East, West) to narrate the transition naturally.
* **Fog of War:** The LLM only sees the immediate adjacent rooms. It does not see the entire 50-room dungeon, which saves massive amounts of tokens and focuses attention on the immediate scene.
* **Wacky Coordinate Tolerance:** If module authors create geometrically impossible spaces (e.g., overlapping coordinates or vast gaps), the system normalizes them into immediate relative directions (1 step North, 1 step East) based solely on the fact that they are connected.

## 3. Implementation Plan

### Step 3.1: Coordinate Parsing and Direction Mapping
Create a utility function to parse coordinates like `"X2Y2"` into integer tuples `(2, 2)`. 
Calculate the relative delta `(dx, dy)` between the current location and its connected neighbors.
* `dx < 0` -> West, `dx > 0` -> East
* `dy < 0` -> North, `dy > 0` -> South

### Step 3.2: Grid Construction (`build_local_sensory_grid`)
Create a helper function (likely in `utils/spatial_grid.py` or within `core/managers/location_manager.py`) that:
1. Takes the `current_location_id` and the `location_graph` (or area data).
2. Retrieves the current coordinates.
3. Retrieves the coordinates of all IDs in the `connectivity` list.
4. Places the connected locations into a 3x3 matrix based on their relative direction.
5. Handles edge cases:
   * **Missing/Malformed Coordinates:** Fallback to an "Unmapped" list.
   * **Coordinate Collisions:** If two connected rooms resolve to the same directional slot, append them or place them in an "Other Exits" list.
   * **Z-Axis (Up/Down):** If a module uses Z coordinates or descriptive text (e.g., "trapdoor"), list them explicitly as Up/Down.

### Step 3.3: Timescale and Distance-to-Time Hinting
1. **Manhattan Distance Calculation:** During grid construction, calculate the simple Manhattan distance (`|dx| + |dy|`) to adjacent connected rooms.
2. **Terrain Multiplier:** Apply a contextual scale multiplier based on the module's `areaType` (e.g., `wilderness` = 15 mins/unit, `dungeon` = 2 mins/unit, `city` = 5 mins/unit).
3. **Time Hint Injection:** Append this calculated time estimation directly to the Valid Exits list for the LLM to process naturally.

### Step 3.4: Output Formatting
The function will output a concise string optimized for the LLM. 

**Example Output:**
```text
Immediate Surroundings (3x3 Grid):
[ NC05 ] [  --  ] [  --  ]
[ NC02 ]-[ HERE ]-[  --  ]
[ NC04 ] [ NC03 ] [  --  ]

Your Location: [HERE] Corrupted Entry Cave (NC01) [Terrain: Wilderness]
Valid Exits:
- West: Twisted Briar Grove (NC02) [Est. Travel: ~15 mins]
- South: Hollow Shade Den (NC03) [Est. Travel: ~15 mins]
- North-West: Shrouded Sentinel Rise (NC05) [Est. Travel: ~45 mins]
```

### Step 3.5: DM Note Injection (`main.py`)
Locate the DM note construction block in `main.py` (around line 5510-5870, where `connected_locations_display_str` is built).
Replace or augment the flat list of connected locations with the output of `build_local_sensory_grid()`.

## 4. Phase Rollout

* **Phase 1: Proof of Concept & Utility Creation**
  * Write `utils/spatial_grid.py` with the coordinate parser and 3x3 ASCII renderer.
  * Add unit tests (`scripts/test_spatial_grid.py`) to ensure it gracefully handles missing coordinates, negative coordinates, and overlapping rooms.
* **Phase 2: Integration**
  * Hook the utility into `main.py`'s `dm_note` generation.
  * Ensure it only triggers for areas with valid coordinate data, falling back to the legacy flat list if coordinates are entirely absent.
* **Phase 3: Prompt Tuning**
  * Verify the LLM correctly interprets the grid in testing (e.g., navigating *The Thornwood Watch*).
  * Adjust the system prompt slightly if necessary to instruct the LLM to use the "Immediate Surroundings" grid for directional flavor.

## 5. Files to Modify/Create
* **`utils/spatial_grid.py`** (NEW): Core logic for generating the ASCII grid.
* **`main.py`**: Integration point for the DM note.
* **`scripts/test_spatial_grid.py`** (NEW): Regression tests for coordinate math and formatting.
