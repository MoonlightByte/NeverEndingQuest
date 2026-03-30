## Problem
Currently, the ingest pipeline creates a naive linear map (`X0Y0`, `X1Y0`...) ignoring module text descriptions. Legacy modules have either missing or manually authored coordinates that conflict with the narrative text. To fully enable the 3x3 phenomenological "DM Local Grid", modules must possess semantically accurate `X#Y#` coordinates where connected rooms are physically adjacent, and their relative placement matches the narrative descriptions (e.g., North, South, East, West).

## Objective
Implement an LLM-driven "Spatial Resolution Pass" during module ingestion to generate semantically accurate 2D coordinates from narrative descriptions. Provide developer tooling to backfill legacy modules with accurate coordinates based on their existing connectivity.

## Non-goals
- Runtime dynamic coordinate generation (coordinates must be generated at ingest/backfill time and committed).
- Changes to the existing Python movement validator (which continues to rely purely on `connectivity`).

## Rollout Risk and Fallback
- Risk: The LLM cartographer might generate invalid coordinate strings or disconnected map components.
- Fallback: The pipeline MUST fall back to the existing naive linear placement if the LLM output is malformed or invalid JSON.

## Merge-Safety and Compatibility
- MUST preserve the current `connectivity` arrays in legacy modules; only `coordinates` and `layout` should be modified.
- MUST not break single-player mode, as `map_<AREA>.json` rendering relies on valid coordinate strings.