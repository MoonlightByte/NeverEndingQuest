# DM Combat Grid & Engagement Roster

## 1. Objective
Solve Theater of the Mind (TotM) combat scaling and spatial hallucination for the LLM DM. By separating the environment (The Stage) from the combatants (The Actors), we provide a computationally light, infinitely scalable spatial system. It adapts its presentation dynamically: giving active PCs a 16-point "Relative Threat Radar" during their individual turns, and giving the LLM a macro "Global Roster" during the batch Enemy Phase.

## 2. Core Architecture: The Stage vs. The Actors

To prevent overcrowding (e.g., 10 goblins in one 5ft square) and handle off-grid combatants (e.g., a sniper in a tree 60ft away), we split combat spatial awareness into two distinct layers.

### 2.1 The Stage (Environment Grid)
A 3x3 tactical grid representing the physical room or clearing. It contains *no people*, only terrain, hazards, and features.
*   **Generation:** Created at module ingest or backfill (Option A). The LLM cartographer extracts a `tactical_grid` array from the location's prose description and saves it to the module's `areas/` JSON.
*   **Mutability:** Python copies this into the active `encounter.json` when combat starts. The LLM can alter it mid-combat (e.g., setting a wall on fire) using a new `modify_environment` op.

```text
Environment:
[ Bar/Kegs ] [ N. Door ] [ Tables   ]
[ W. Window]-[ CENTER  ]-[ E. Stairs]
[ Fireplace] [ S. Door ] [ Kitchen  ] 
```

### 2.2 The Actors (Engagement Roster)
Python tracks combatants using Relational Geometry rather than rigid X/Y grid coordinates. This scales infinitely and naturally groups combatants into logical melee clusters or ranged bands.
*   **Melee Clusters:** Groups of combatants actively engaged within 5ft of each other.
*   **Ranged/Unengaged:** Combatants standing apart, tracked by distance to specific clusters or terrain features.

```text
Engagement Roster:
- Melee Cluster 1 (at CENTER): Acheron, Goblin 1, Goblin 2
- Melee Cluster 2 (at E. STAIRS): Sylara, Hobgoblin Boss
- Ranged/Unengaged:
  - Scout Kira (Near, 30ft from Cluster 1, at BAR/KEGS)
  - Goblin Archer (Far, 60ft from Cluster 1, Off-Grid/Trees)
```

## 3. Dual Presentation (Micro vs. Macro)

Python holds the Engagement Roster as ground truth but formats it differently depending on the combat phase.

### 3.1 PC Turn: The Relative Threat Radar (Micro View)
When it is a single PC's turn, Python places that PC at the absolute center `(0,0)` of their own sensory map. It translates the Roster into a 16-point radar (representing the 16 vertices of a 3x3 grid) spanning 3 range bands: Melee (5ft), Near (15-30ft), and Far (30ft+).

**Example (Lidda's Turn):**
```text
[ Lidda's Tactical Radar ]
Environment: S. Door
Condition: Unengaged (Free to move/shoot)

[FAR NW]-----[FAR N]-----[FAR NE]   <-- 30ft+ (Necromancer at N. Door)
   |            |            |
[NEAR W]----[MELEE]------[NEAR E]   <-- 15ft-30ft (Acheron & Goblins at CENTER)
   |            |            |
[NEAR W]----[MELEE]------[NEAR E]   <-- 5ft (Empty - No Disadvantage on Ranged)
   |        (LIDDA)          |
[FAR SW]-----[FAR S]-----[FAR SE]   <-- 30ft (Fireplace/Wall)
```
*Why:* Provides perfect, constrained context. The LLM knows instantly who can hit whom, enabling an ironclad guardrail against spatial hallucinations (e.g., a goblin can't melee from FAR N).

### 3.2 Enemy Phase: The Global Roster (Macro View)
During the batch Enemy Phase (`/end`), a relative radar centered on one person breaks down. Instead, Python hands the LLM the flat Global Roster and the Environment Grid.

*Why:* The LLM sees the entire board at once. It can orchestrate 5 different goblins and a necromancer in a single batch output without doing complex relative math. It inherently understands that the Goblin Archer (60ft away) must shoot, while Goblin 1 (in Cluster 1) must melee.

## 4. The Hybrid Physics Engine (Python + LLM Ops)

Python maintains the spatial ground truth to prevent hallucination, but the LLM directs the cinematic flow.

1.  **Auto-Snapping (Python):** If the LLM narrates a valid melee attack (e.g., *"Goblin 1 stabs Lidda"*), Python reads the math, intercepts the action, and automatically merges Goblin 1 into Lidda's Melee Cluster.
2.  **Tactical Movement (LLM `position_shift` Op):** To handle movement *without* attacking (e.g., fleeing, repositioning), we add a new deterministic op. The LLM emits:
    `{"op": "position_shift", "target": "Goblin 1", "destination": "FAR N, N. Door"}`.
    Python reads this, removes Goblin 1 from the melee cluster, and updates the roster.
3.  **Environmental Changes (LLM `modify_environment` Op):** The LLM can emit:
    `{"op": "modify_environment", "target": "N. Door", "new_state": "Wall of Fire"}`.
    Python updates the active encounter's 3x3 tactical grid, which immediately alters the terrain context for the next turn.

## 5. Implementation Phases

### Phase 1: The Stage (Ingest & Remediation)
*   Update `homebrewery_importer.py` to extract a 3x3 `tactical_grid` array during the LLM spatial resolution pass.
*   Update `remediate_module_coordinates.py` to backfill the `tactical_grid` for legacy modules based on their descriptions.

### Phase 2: The Roster State (Python Core)
*   Update `core/managers/multi_pc_combat.py` (`CombatStateManager`) to initialize and track `engagements` (clusters and unengaged distances) in the `encounter_XYZ.json` state.
*   Implement the Python "Auto-Snapping" logic to merge combatants into clusters upon detecting valid melee attack rolls.

### Phase 3: The Hybrid Ops
*   Add `position_shift` and `modify_environment` to the structured ops parsers (`updateEncounter` and `updateCharacterInfo`).
*   Ensure these ops gracefully fail-open if the LLM attempts an impossible movement.

### Phase 4: Prompt Injection & Presentation
*   Update `core/managers/combat_manager.py` prompt formatting logic.
*   Inject the "Relative Threat Radar" during active PC turns.
*   Inject the "Global Roster + Environment Grid" during the Enemy Phase (`/end`).
*   Tune validation prompts to enforce spatial consistency (e.g., "Do not narrate a melee attack against a target in the FAR band without a position_shift op").