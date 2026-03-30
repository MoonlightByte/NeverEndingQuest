# NeverEndingQuest v2 Mapping Architecture

This directory contains the comprehensive planning documents for the Version 2 Mapping System. The system is designed to provide infinite scalability, zero external engine lock-in, and token-efficient spatial reasoning for the LLM.

It is divided into two conceptual halves: the **Presentation Layer** (what the user sees) and the **Data & Cognitive Layer** (how the LLM understands space).

## Synthesis

The Data Layer feeds the Presentation Layer directly:
1. **Topological Relativity** (Local/Regional Grids) naturally formats the data required by the `AsciiRenderer` defined in the World Mapping plan.
2. **Engagement Roster and Threat Radar** (Combat Grid) provide the exact token-efficient payload needed to render the tactical overlays described in the Combat Mapping plan.

---

## 1. The Presentation Layer (UX & UI Architecture)

These documents define the player-facing map experience, architectural constraints, and visual styling (e.g., PlaySCII-inspired ASCII renderers).

* **[World Mapping v2 Plan](./world-mapping.md)**: Defines the fail-open, topology-driven architecture for local, module, and world-level maps.
* **[Combat Mapping UX Plan](./combat-mapping.md)**: Defines the tactical combat interface, focusing on readability, range, and line-of-sight without heavy 2D grid lock-in.

---

## 2. The Data & Cognitive Layer (DM Sensory Grids)

These documents define the underlying data structures. They translate traditional rigid maps into "phenomenological" relative grids that the LLM can easily understand and narrate.

* **[DM Regional Grid](./dm-regional-grid.md)**: The macro world map. Pins isolated modules to a global coordinate system, creating a procedural "Fog of War" horizon for organic travel.
* **[DM Local Grid](./dm-local-grid.md)**: The 3x3 topological dungeon view. Translates connected rooms into immediate relative directions (North, South, East, West) based on the graph edges.
* **[DM Combat Grid & Engagement Roster](./dm-combat-grid.md)**: The micro tactical view. Separates the environment (The Stage) from the combatants (The Actors), tracking entities via Relational Geometry (Melee Clusters vs. Ranged) to generate a 16-point "Relative Threat Radar".
