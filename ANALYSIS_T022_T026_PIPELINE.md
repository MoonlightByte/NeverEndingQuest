# T022-T026: Area and Location Generation Pipeline Analysis

## Overview

The area and location generation pipeline consists of **5 API callsites** working in sequence:
- **T022**: Generate thematic location names within an area (via MapLayoutGenerator)
- **T023**: Generate area name + description refinement
- **T024**: Generate area-level description (fallback/alternate to T023)
- **T025**: Generate individual location field by field (rarely used, legacy)
- **T026**: Generate ALL locations in batch (primary method, replaces T025)

Data flow:
```
Module Metadata
     ↓
T023 (area name + description)
     ↓
MapLayoutGenerator creates room layout
     ↓
T022 (thematic names for rooms)
     ↓
Location stubs extracted from map
     ↓
T026 (batch generate all location details)
     ↓
Location data saved + linked to area
```

---

## T022: generate_thematic_names() - Line 74

**File**: `/mnt/c/dungeon_master_v1/core/generators/area_generator.py:74-171`

### Purpose
Generate immersive, thematic names for locations within an area instead of generic "Room 1" identifiers.

### Input
```python
room_data: List[Dict]  # Rooms from MapLayoutGenerator with id, type, connections
area_context: Dict[str, Any]  # {module_name, area_name, area_type, theme, danger_level, recommended_level}
```

### Prompts

**System message (line 131)**:
```
"You are an expert at creating immersive 5th edition of the world's most popular
roleplaying game location names that enhance storytelling and world-building."
```

**User message (lines 99-128)** - Example for a medium dungeon:
```
You are creating thematic location names for a 5th edition of the world's most popular
roleplaying game module called "[module_name]".

AREA CONTEXT:
- Area Name: [area_name]
- Area Type: [area_type]  # e.g., "dungeon"
- Theme: [theme]
- Total Locations: [count]

ROOM LIST TO NAME:
1. Entrance (A01) - connects to 2 other rooms
2. Corridor (A02) - connects to 3 other rooms
... [all rooms]

NAMING REQUIREMENTS:
1. Create unique, memorable names that fit the module's theme
2. Names should be 2-4 words maximum
3. Avoid generic terms like "Room 1" or including IDs
4. Consider the room's function and connections
5. Names should feel immersive and atmospheric
6. Use evocative adjectives (Ancient, Forgotten, Shattered, etc.)

EXAMPLES OF GOOD NAMES:
- entrance → "Weathered Gate Chamber"
- throne room → "Sunken Crown Hall"
- corridor → "Whispering Passage"
- shrine → "Altar of Lost Hopes"
- marketplace → "Merchant's Circle"

Please respond with ONLY a JSON array of names in the exact order listed above:
["Name 1", "Name 2", "Name 3", ...]

No explanations, just the JSON array of thematic location names.
```

### JSON Schema (Output)
```json
[
  "string (2-4 words, evocative, thematic)",
  "string (matches module/area theme)",
  ...
]
```
**Must be**:
- Valid JSON array
- Length == len(room_data)
- Order matches room list in prompt

### Processing (lines 135-150)

1. **Parse JSON** (line 140)
   ```python
   names = json.loads(response_text)
   ```

2. **Validate** (line 141)
   - Must be list type
   - Must have exact same count as input rooms

3. **Success path** (line 143)
   - Returns names list
   - Applied to room_data in generate_layout() at line 287

4. **Failure handling** (lines 144-150)
   - JSON parse fails → catches JSONDecodeError + ValueError
   - Prints debug message with actual response
   - **Raises exception** (no fallback)
   - Caller catches at line 288 in generate_layout()

### Fallback in generate_layout() (lines 288-296)

If T022 fails:
```python
except Exception as e:
    print(f"DEBUG: [Area Generator] Failed to generate thematic names: {e}")
    # Fallback: Enhanced generic names
    for room in room_data:
        room["name"] = f"{room['type'].title()} {room['id']}"
```
Falls back to format like "Entrance A01", "Corridor A02"

### API Call Details (lines 130-133)

```python
response = capture_and_fanout("T022", client.chat.completions.create,
    messages=[
        {"role": "system", "content": "You are an expert at creating immersive..."},
        {"role": "user", "content": prompt}
    ],
    model=DM_MAIN_MODEL,  # From config.py
    temperature=0.8)
```

**Parameters**:
- `temperature=0.8` → Creative variation desired for names
- `DM_MAIN_MODEL` → Currently gpt-4.1-2025-04-14
- No `response_format` specified (plain text JSON in response)
- No `max_tokens` constraint

### Data Dependencies
- Input: room_data from MapLayoutGenerator (has id, type, connections)
- Output: room["name"] field populated in each room dict
- Feeds into: generate_layout() applies names to all rooms before returning

### Quality Requirements
1. Names must be atmosphere + thematic
2. Names must be 2-4 words (CRITICAL - longer names break UI)
3. No IDs in names
4. Must maintain order from prompt
5. Must escape special characters (already done by JSON)

---

## T023: generate_area_name_and_description() - Line 384

**File**: `/mnt/c/dungeon_master_v1/core/generators/area_generator.py:384-427`

### Purpose
Refine a coarse area name into a regional name + write atmospheric 1-2 sentence description.

### Input
```python
initial_name: str  # Rough area concept, e.g., "Forgotten Temple"
config: AreaConfig  # {area_type, danger_level, ...}
```

### Prompt (lines 389-409)

**System message (line 414)**:
```
"You are an expert fantasy world builder specializing in creating evocative names
and descriptions for 5th edition of the world's most popular roleplaying game areas."
```

**User message (lines 389-409)**:
```
You are an expert fantasy world builder. Your task is to refine an area name and
write a description for a 5th edition area.

**Initial Concept Name:** "[initial_name]"

**Area Details:**
- Type: [area_type]  # e.g., "dungeon"
- Danger Level: [danger_level]  # e.g., "medium"

**TASK:**
1. **Refine the Name:** If the initial name is too specific (like a single building
   or landmark), broaden it into a more general, evocative name for the entire
   region. For example, if the initial name is "The Old Lighthouse," a better
   regional name would be "The Shipwreck Coast" or "The Cursed Headlands."
   If the initial name is already good for a region, you can keep it or make
   minor improvements.

2. **Write a Description:** Write 1-2 atmospheric sentences for the refined area
   name. The description should capture the area's character, include sensory
   details, and match the danger level.

**CRITICAL RULES:**
- The refined name should describe a whole AREA/REGION, not a single location.
- The description must be for the refined name.

**Return ONLY a JSON object with this exact structure:**
{
  "refinedName": "Your New, More General Area Name",
  "description": "Your 1-2 sentence atmospheric description."
}
```

### JSON Schema (Output)
```json
{
  "refinedName": "string (2-5 words, regional scope, atmospheric)",
  "description": "string (1-2 sentences, sensory, matches danger level)"
}
```

**Must be**:
- Valid JSON object
- Both fields present
- refinedName: 2-5 words minimum
- description: at least 20 chars (validation would be in caller)

### Processing (lines 413-427)

1. **API call** (line 413)
   ```python
   response = capture_and_fanout("T023", self.client.chat.completions.create,
       messages=[...],
       model=DM_MAIN_MODEL,
       temperature=0.8,
       response_format={"type": "json_object"})
   ```

2. **Parse JSON** (line 418)
   ```python
   result = json.loads(response.choices[0].message.content)
   refined_name = result.get("refinedName", initial_name)
   description = result.get("description", f"A mysterious area known as {initial_name}.")
   ```

3. **Return** (line 422)
   ```python
   return refined_name, description
   ```

4. **Fallback on exception** (lines 424-427)
   ```python
   except Exception as e:
       print(f"DEBUG: [Area Generator] Warning: AI name/description generation failed: {e}")
       return initial_name, f"A {config.danger_level} {config.area_type} area known as {initial_name}."
   ```
   Falls back to: `"{danger_level} {area_type} area known as {initial_name}."`

### API Call Details (line 413-416)

```python
response = capture_and_fanout("T023", self.client.chat.completions.create,
    messages=[...],
    model=DM_MAIN_MODEL,
    temperature=0.8,
    response_format={"type": "json_object"})  # ENFORCES JSON output
```

**Parameters**:
- `temperature=0.8` → Balanced creativity + consistency
- `response_format={"type": "json_object"}` → **CRITICAL** - forces structured output
- No `max_tokens` constraint
- Returns: Promise of valid JSON (mode enforces it)

### Data Dependencies
- Input: initial_name from module builder
- Output: (refined_area_name, area_description) tuple
- Feeds into:
  - Stored in area_data["areaName"] (line 516)
  - Stored in area_data["areaDescription"] (line 518)
  - Used as context for T022 (area_context["area_name"] = refined_area_name, line 457)

### Quality Requirements
1. Regional scope (not single landmark)
2. 2-5 words for name
3. 1-2 sentences for description
4. Sensory details (sights, sounds, smells)
5. Matches danger level tone
6. No cliches ("where civilization meets frontier")

---

## T024: generate_area_description() - Line 532

**File**: `/mnt/c/dungeon_master_v1/core/generators/area_generator.py:532-578`

### Purpose
Alternate/fallback method to generate area description. **Currently unused in generate_area()** - T023 is preferred since it does name + description together.

### Input
```python
area_name: str  # Already refined name
config: AreaConfig  # {area_type, size, complexity, danger_level, recommended_level}
```

### Prompt (lines 534-550)

**System message (line 554)**:
```
"You are an expert fantasy world builder. Create unique, atmospheric descriptions
for 5th edition of the world's most popular roleplaying game areas that avoid
cliches and generic phrases."
```

**User message (lines 534-550)**:
```
Generate a unique, atmospheric description for a 5th edition area named "[area_name]".

Area Details:
- Type: [area_type]
- Size: [size]
- Complexity: [complexity]
- Danger Level: [danger_level]
- Recommended Level: [recommended_level]

Requirements:
- Write 1-2 sentences that capture the area's atmosphere and character
- Make it unique and evocative, not generic
- Include sensory details appropriate to the area type
- Avoid using the exact phrase "where civilization meets the frontier"
- Match the danger level and complexity in the description

Return ONLY the area description text, no additional formatting or labels.
```

### Output Schema
```
Plain text string (1-2 sentences, 50-200 chars)
```

### Processing (lines 552-578)

1. **API call** (line 553)
   ```python
   response = capture_and_fanout("T024", client.chat.completions.create,
       messages=[...],
       model=DM_MAIN_MODEL,
       temperature=0.8)
   ```
   Note: **NO response_format** - plain text output

2. **Extract + validate** (lines 558-562)
   ```python
   description = response.choices[0].message.content.strip()
   if description and len(description) > 10:
       return description
   else:
       return f"{area_name} presents unique challenges and opportunities for adventurers."
   ```

3. **Fallback on exception** (lines 567-578)
   ```python
   except Exception as e:
       area_adjectives = {
           "dungeon": ["ancient", "forgotten", "mysterious", "treacherous"],
           ...
       }
       adjective = random.choice(area_adjectives.get(config.area_type, ["mysterious"]))
       return f"{area_name} is a {adjective} {config.area_type} area with {config.complexity} challenges suitable for level {config.recommended_level} adventurers."
   ```

### API Call Details (line 553-556)

```python
response = capture_and_fanout("T024", client.chat.completions.create,
    messages=[...],
    model=DM_MAIN_MODEL,
    temperature=0.8)
```

**Parameters**:
- `temperature=0.8`
- NO `response_format` (plain text)
- Expects natural language response

### Data Dependencies
- Input: area_name (already refined)
- Output: description string (1-2 sentences)
- **Current usage**: NOT used in generate_area() - could be legacy
- **Better practice**: Use T023 instead (combines name + description)

### Quality Requirements
1. 1-2 sentences only
2. Atmospheric + unique
3. Include sensory details
4. Avoid generic phrases
5. Match danger level
6. Min 10 chars (validation check)

---

## T025: generate_field() - Line 393

**File**: `/mnt/c/dungeon_master_v1/core/generators/location_generator.py:393-436`

### Purpose
Generate a **single field** of a location (description, npcs, traps, etc.) in isolation.

### Input
```python
field_path: str  # e.g., "description", "doors", "plotHooks"
schema_info: Dict[str, Any]  # JSON schema for that field
context: Dict[str, Any]  # Area, module, plot context
```

### Prompt (lines 405-420)

**System message (line 423)**:
```
"You are an expert 5e location designer. Return only the requested data in the exact format needed."
```

**User message (lines 405-420)**:
```
Generate content for the '[field_path]' field of a 5e location.

Field Schema:
[schema_info as JSON]

Detailed Guidelines:
[LocationPromptGuide.[field_name] text, e.g., for "description"]:
    "The main description paints a vivid picture for players.
     Include sensory details and atmosphere.

     Structure (3-5 sentences):
     1. Overall impression and size
     2. Key visual features
     3. Atmospheric details (sounds, smells, temperature)
     4. Notable objects or areas of interest
     5. Hints at danger or opportunity
     ..."

Context:
[area, module, plot data as JSON]

Return ONLY the value for this field in the correct format.
For strings, return just the string.
For arrays, return just the array.
For objects, return just the object.
```

### Output Schema
Varies by field (string, array, or object):
- `description`: Plain string
- `npcs`: Array of {name, description, attitude}
- `traps`: Array of trap objects
- `doors`: Array of door objects

### Processing (lines 422-436)

1. **API call** (line 422)
   ```python
   response = capture_and_fanout("T025", client.chat.completions.create,
       messages=[...],
       model=DM_MAIN_MODEL,
       temperature=0.7)  # Lower temp for consistency
   ```
   Note: **NO response_format** - must handle both text and JSON

2. **Extract content** (line 427)
   ```python
   content = response.choices[0].message.content.strip()
   ```

3. **Try JSON parse if looks like JSON** (lines 430-434)
   ```python
   if content.startswith(('[', '{')):
       try:
           return json.loads(content)
       except json.JSONDecodeError:
           pass
   ```

4. **Return as-is** (line 436)
   ```python
   return content
   ```

5. **NO exception handling** - returns whatever AI produces

### API Call Details (line 422-425)

```python
response = capture_and_fanout("T025", client.chat.completions.create,
    messages=[...],
    model=DM_MAIN_MODEL,
    temperature=0.7)  # Lower creativity for field-level generation
```

**Parameters**:
- `temperature=0.7` → More consistent than 0.8
- NO `response_format`
- Flexible output (text or JSON)

### Data Dependencies
- Input: field_path, schema, context
- Output: Single field value (type varies)
- **Current usage**: **NOT USED** in generate_locations()
- **Better practice**: Use T026 instead (batch generation)

### Quality Requirements
1. Correct format (string/array/object)
2. Matches schema validation
3. Follows LocationPromptGuide rules
4. Fits context

### Why T025 is Rarely Used

T026 (batch) is preferred because:
- Single field generation lacks coherence (fields generated in isolation)
- No cross-field consistency (one location's description doesn't inform its npcs/traps)
- Slower (N API calls per location)
- Higher cost
- T026 generates all locations + all fields in one smart prompt

---

## T026: generate_location_batch() - Line 438

**File**: `/mnt/c/dungeon_master_v1/core/generators/location_generator.py:438-546`

### Purpose
**PRIMARY method** - Generate ALL locations for an area + ALL their fields in a single batch API call.

### Input
```python
area_data: Dict[str, Any]  # Refined area with map + metadata
plot_data: Dict[str, Any]  # Plot points with locations
module_data: Dict[str, Any]  # Module metadata
location_stubs: List[Dict[str, Any]]  # Room layouts from map
context: Optional  # Validation context (optional)
excluded_names: List[str]  # Party member names to avoid for NPCs
context_header: str  # Additional context
```

### Prompt (lines 485-539)

**System message (line 542)**:
```
"You are an expert 5e dungeon designer creating cohesive, interconnected locations."
```

**User message (lines 485-539)** - Comprehensive batch prompt:
```
[context_header optional]

Generate detailed 5e locations for [area_name].

[Party exclusion if provided]
CRITICAL: Do NOT use these names for NPCs: [excluded_names]

Context:
{
  "module": {
    "name": "[module_name]",
    "description": "[description]",
    "theme": "[theme]",
    "magicLevel": "[magic_prevalence]"
  },
  "area": {
    "name": "[refined_area_name from T023]",
    "type": "[dungeon|wilderness|town|mixed]",
    "description": "[description from T023]",
    "dangerLevel": "[medium|high|...]",
    "recommendedLevel": [level]
  },
  "plot": {
    "title": "[plot_title]",
    "objective": "[main_objective]",
    "currentStage": "[first_plot_point_description]"
  },
  "locationStubs": [
    {
      "locationId": "A01",
      "name": "[thematic_name from T022]",
      "type": "entrance",
      "connections": ["A02", "A03"],
      "coordinates": "X0Y0"
    },
    ...
  ]
}

[validation_prompt if context provided]

For each location stub provided, generate complete location data following the schema.
Ensure locations:
1. Connect logically based on the map layout
2. Support the plot's needs (place key items, NPCs, and clues appropriately)
3. If a location stub already has an NPC entry (like a pre-placed antagonist),
   you MUST include that NPC. You can enhance their description, but their name
   and presence are mandatory
4. Vary in purpose and challenge
5. Include a mix of combat, exploration, and roleplay opportunities
6. Feel cohesive as part of the same [area_type]

Return a JSON object with a 'locations' array containing all complete location objects.
Each location must include ALL required fields from the location schema.

CRITICAL: Field names must match the schema EXACTLY:
- Use "npcs" NOT "notableNPCs" (must be array of objects with name, description, attitude)
- Use "monsters" NOT "creatures"
- Use "lootTable" NOT "items" (must be array of strings, not objects)
- Use "connectivity" for room connections
- Use "areaConnectivity" for connections to other areas
- Use "areaConnectivityId" for area connection IDs (empty array [] if no connections
  to other areas, NEVER include current area ID)
- Use "plotHooks" NOT "clues"
- Use "dmInstructions" for DM-specific notes
- Use "doors" for door information (ALL fields required: name, description, type,
  locked, lockDC, breakDC, keyname, trapped, trap)
- Use "traps" for trap details (must include detectDC, disableDC, triggerDC, damage)
- Use "dcChecks" in format "SkillName DC XX: Description"
- Include "accessibility" (describe how easily the location can be accessed)
- Include "dangerLevel" (must be "Low", "Medium", "High", or "Very High")
- Include "features" (array of objects with name and description)

DOOR STRUCTURE: Every door must have ALL these fields:
- name (string): e.g., "North Door", "Secret Panel"
- description (string): physical appearance
- type (string): e.g., "regular", "secret", "heavy"
- locked (boolean): true or false
- lockDC (integer): difficulty to pick (0 if not locked)
- breakDC (integer): difficulty to force open
- keyname (string): what opens it (empty string if none)
- trapped (boolean): true or false
- trap (string): trap description (empty string if not trapped)

AREA CONNECTIVITY RULES:
- areaConnectivityId should be [] for locations that don't connect to other areas
- Only include other area IDs when location explicitly connects to different areas
- NEVER include the location's own area ID in areaConnectivityId

Check the location schema carefully for all required fields.
```

### JSON Schema (Output)

```json
{
  "locations": [
    {
      "locationId": "A01",
      "name": "Weathered Gate Chamber",
      "type": "entrance",
      "description": "3-5 sentences, immersive, sensory details",
      "dmInstructions": "3-5 sentences, mechanical, DCs, secrets",
      "coordinates": "X0Y0",
      "accessibility": "Describe how to access, DCs if needed",
      "npcs": [
        {
          "name": "string",
          "description": "string",
          "attitude": "string (hostile|friendly|neutral|etc)"
        }
      ],
      "monsters": [
        {
          "name": "string (SINGULAR, e.g., 'goblin' not 'goblins')",
          "quantity": {"min": 0, "max": 5}
        }
      ],
      "plotHooks": ["string", ...],
      "lootTable": ["string (item descriptions)", ...],
      "dangerLevel": "Low|Medium|High|Very High",
      "connectivity": ["A02", "A03", ...],
      "areaConnectivity": [],
      "areaConnectivityId": [],
      "traps": [
        {
          "name": "string",
          "description": "string",
          "detectDC": 15,
          "disableDC": 13,
          "triggerDC": 14,
          "damage": "string (e.g., '3d6 fire damage')"
        }
      ],
      "features": [
        {
          "name": "string",
          "description": "string"
        }
      ],
      "dcChecks": [
        "Perception DC 15: Notice the secret door",
        ...
      ],
      "encounters": [],
      "adventureSummary": "",
      "doors": [
        {
          "name": "string",
          "description": "string",
          "type": "string",
          "locked": true/false,
          "lockDC": 15,
          "breakDC": 20,
          "keyname": "string",
          "trapped": false,
          "trap": ""
        }
      ]
    },
    ...all other locations...
  ]
}
```

### Processing (lines 541-546)

1. **API call** (line 541)
   ```python
   response = capture_and_fanout("T026", client.chat.completions.create,
       messages=[
           {"role": "system", "content": "You are an expert 5e dungeon designer..."},
           {"role": "user", "content": batch_prompt}
       ],
       model=DM_MAIN_MODEL,
       temperature=0.8,
       response_format={"type": "json_object"})  # ENFORCES JSON
   ```

2. **Parse JSON** (line 546)
   ```python
   return json.loads(response.choices[0].message.content)
   ```

3. **NO exception handling** in this function

### Post-Processing in generate_locations() (lines 548-659)

After T026 returns, extensive post-processing happens:

1. **Extract locations** (line 584)
   ```python
   locations = location_data.get("locations", [])
   ```

2. **Validate connectivity** (lines 593-606)
   - Ensure all connections reference valid location IDs
   - Remove references to non-existent locations
   - Handles both string and dict formats

3. **Register NPCs with context** (lines 608-624)
   ```python
   if context:
       for npc in location.get("npcs", []):
           context.add_npc(npc_name=..., area_id=..., location_id=..., description=...)
   ```

4. **Enhance with plot data** (lines 626-639)
   - Adds plot hooks to plot-critical locations
   - Ensures plot points have supporting content

5. **Set defaults** (lines 641-645)
   - encounters = []
   - adventureSummary = ""

6. **Name consistency sync** (lines 647-657)
   - Updates map room names to match location names if they differ

### API Call Details (line 541-544)

```python
response = capture_and_fanout("T026", client.chat.completions.create,
    messages=[
        {"role": "system", "content": "You are an expert 5e dungeon designer..."},
        {"role": "user", "content": batch_prompt}
    ],
    model=DM_MAIN_MODEL,
    temperature=0.8,
    response_format={"type": "json_object"})  # ENFORCES VALID JSON OUTPUT
```

**Parameters**:
- `temperature=0.8` → Creative but consistent
- `response_format={"type": "json_object"}` → **CRITICAL** - API enforces valid JSON
- No `max_tokens` (could be issue if output too large)
- Model commitment: Must return valid JSON or API error

### Data Dependencies

**Inputs**:
- area_data: (from T023) refined area name + description, map with rooms from T022
- plot_data: plot points with location assignments
- location_stubs: from area_data["map"]["rooms"] or explicitly passed
- excluded_names: party member names to avoid in NPC generation

**Outputs**:
- locations[]: Full location objects with all required fields
- Feeds into:
  - save_locations() writes to area file (line 705)
  - Module builder completes area definition
  - Game runtime reads locations for encounters

**Storage Flow**:
```
LocationGenerator.generate_locations()
    → T026 generates locations
    → Post-processing validates + registers NPCs
    → save_locations()
        → reads existing area file
        → merges location data
        → writes back to modules/[module]/areas/[areaId].json
```

### Quality Requirements

1. **Field completeness**: ALL required fields present
2. **Field naming**: EXACT match to schema (critical emphasis in prompt)
3. **Field format**:
   - Doors: ALL subfields required (name, description, type, locked, lockDC, breakDC, keyname, trapped, trap)
   - Traps: detectDC, disableDC, triggerDC, damage all required
   - Monsters: SINGULAR names only (e.g., "goblin" not "goblins")
   - dcChecks: Format "SkillName DC XX: Description"
   - dangerLevel: Must be exactly "Low", "Medium", "High", or "Very High"
4. **Connectivity**:
   - connectivity[] → only internal location IDs
   - areaConnectivityId[] → only external area IDs (never own area)
5. **NPC names**: Must not match excluded_names
6. **Plot integration**: Key items/NPCs/clues placed at plot locations
7. **Coherence**: All locations feel like part of same area/type
8. **Pre-placed NPCs**: If location stub had NPC, must be included (can enhance)

### Fallback Behavior

- **If API call fails**: Exception bubbles up (no try/catch in generate_location_batch)
- **If JSON invalid**: APIResponseFormatError from response_format enforcement
- **If post-processing fails**: Continues with invalid connectivity (cleaned in validation step)

### Validation

Post-response validation (lines 661-703):

```python
def validate_locations(self, location_data: Dict[str, Any]) -> List[str]:
    """Validate location data against schema and logical consistency"""

    # Schema validation per location
    for location in location_data.get("locations", []):
        jsonschema.validate({"locations": [location]}, self.schema)

    # Content validation:
    # - Connections reference valid location IDs
    # - Trap DCs in range 10-30
    # - Danger level matches threat count
```

---

## Data Pipeline Flow Diagram

```
Module Creation
      ↓
Module Metadata (moduleName, description, worldSettings, etc.)
      ↓
Area Builder calls AreaGenerator.generate_area()
      ↓
[T023] generate_area_name_and_description()
       Input: initial_name, config
       Output: (refined_area_name, area_description)
       Prompt: JSON request for name refinement + description
       Schema: {refinedName, description}
       Error handling: Fallback to "danger_level area_type area known as {name}"
      ↓
[MapLayoutGenerator.generate_layout()] creates room structure
       - Random placement of rooms on grid
       - Auto-tagging rooms by degree, type
       - Calculates directions (N/S/E/W connections)
      ↓
[T022] generate_thematic_names()
       Input: room_data[], area_context
       Output: ["Thematic Name 1", "Thematic Name 2", ...]
       Prompt: JSON array of evocative 2-4 word names
       Schema: [string, string, ...]
       Error handling: Exception raised, caught by caller, falls back to "Type ID" format
       Applied to: room["name"] for each room in map
      ↓
Area saved with refined name, description, map, location stubs
      ↓
Module Builder calls LocationGenerator.generate_locations()
      ↓
LocationGenerator extracts location stubs from area["map"]["rooms"]
       - Each stub: {locationId, name (from T022), type, connections, coordinates}
      ↓
[T026] generate_location_batch()
       Input: area_data, plot_data, module_data, location_stubs[], excluded_names[]
       Output: {locations: [{locationId, name, description, npcs, monsters, ...}]}
       Prompt: Comprehensive batch prompt with all context + field naming rules
       Schema: Location schema (loca_schema.json)
       Temperature: 0.8 (creative but consistent)
       response_format: {type: "json_object"} (API enforces valid JSON)
       Error handling: Exception bubbles up (API will error if JSON invalid)
      ↓
Post-processing in generate_locations():
  - Validate connectivity (clean dead references)
  - Register NPCs with context system
  - Enhance with plot data (add plot hooks)
  - Set defaults (encounters, adventureSummary)
  - Sync map room names with location names
      ↓
validate_locations() runs jsonschema validation + content checks
      ↓
save_locations() merges with area file and writes to:
      modules/[module_name]/areas/[areaId].json
      ↓
Game Runtime
      - Loads area file with complete location data
      - Renders descriptions, runs encounters
      - Tracks NPC placements via context system
```

---

## Summary Table: T022-T026 API Callsites

| Callsite | Function | Input | Output Schema | Temperature | response_format | Error Handling |
|----------|----------|-------|---------------|-------------|-----------------|-----------------|
| **T022** | generate_thematic_names() | room_data[], area_context | [string[], ...] | 0.8 | None (JSON text) | Exception raised → Fallback generic names |
| **T023** | generate_area_name_and_description() | initial_name, config | {refinedName, description} | 0.8 | json_object | Exception caught → Fallback simple description |
| **T024** | generate_area_description() | area_name, config | Plain text (1-2 sentences) | 0.8 | None | Exception caught → Random fallback |
| **T025** | generate_field() | field_path, schema, context | Varies (string/array/object) | 0.7 | None (flexible) | No exception handling - returns whatever AI produces |
| **T026** | generate_location_batch() | area_data, plot_data, module_data, location_stubs[] | {locations: [...]} | 0.8 | json_object | Exception bubbles up (API enforces valid JSON) |

---

## Critical Constraints and Gotchas

### 1. Monster Naming (CRITICAL)
- **Rule**: Use SINGULAR names only ("goblin", "dire wolf", "stone guardian")
- **Why**: System expects singular names; quantity field handles plural count
- **Failure mode**: "goblins" breaks encounter generation downstream

### 2. Door Fields (REQUIRED)
Every door MUST have ALL 9 fields:
- name, description, type, locked, lockDC, breakDC, keyname, trapped, trap
- Missing even one field causes schema validation error

### 3. areaConnectivityId[] Rules
- Empty array [] if location doesn't connect to other areas (CRITICAL)
- Only include OTHER area IDs (never own area ID)
- Must match length of areaConnectivity[] array

### 4. Danger Level Enum
- Must be exactly: "Low", "Medium", "High", "Very High"
- No variations ("low", "MEDIUM", "med", etc.)
- Used for post-validation consistency checks

### 5. Party Name Exclusion
- excluded_names[] passed to T026 prompt
- T026 should NOT use these names for any NPCs
- No validation post-response - trust model compliance

### 6. Pre-placed NPCs
- If location stub already has an NPC in the plot data, MUST be included
- Can enhance description, but name/presence is mandatory
- Plot critical enforcement

### 7. Response Format Enforcement
- T023, T026 use `response_format={"type": "json_object"}`
- This makes the API enforce valid JSON - if model produces invalid JSON, API returns error
- NO fallback for these - exception propagates
- T022, T024, T025 do NOT use response_format - more lenient

### 8. Temperature Settings
- T026 = 0.8 (creative for location descriptions)
- T025 = 0.7 (lower for field-level consistency)
- T022, T023, T024 = 0.8 (thematic variation important)

### 9. Connectivity Validation
- T026 can produce invalid connections (references non-existent locations)
- Post-processing cleans these before saving
- validate_locations() checks for dead connections

### 10. Name Consistency
- T022 generates thematic names
- T026 receives these names in location stubs
- T026 can change names (generates new ones)
- Post-processing syncs map room names to location names if different

---

## Performance Notes

### Token Cost
- T022: ~1000 tokens per area (room count + context)
- T023: ~500 tokens (structured JSON)
- T024: ~400 tokens (fallback, rarely used)
- T025: ~300 tokens per field (not batch - expensive if called multiple times)
- T026: ~3000-5000 tokens (batch generation for 15-20 locations, single call)

**Optimization**: T026 is much cheaper than calling T025 per location per field.

### Latency
- T022: 2-3 seconds
- T023: 1-2 seconds
- T024: 1-2 seconds
- T025: 1-2 seconds per field
- T026: 8-15 seconds (single large batch, but fastest overall for full area)

### Parallel Execution Potential
- T023 + T022 can run in parallel (independent inputs)
- T026 depends on T023 + T022 (needs refined name, thematic names)
- T024 rarely used (legacy)
- T025 not used (inferior to T026)
