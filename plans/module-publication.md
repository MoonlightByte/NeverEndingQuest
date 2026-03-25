# Module Publication Plan

## Problem

Current ingest and readiness tooling can produce modules that are structurally valid but not safely publishable for live play.

Today the pipeline mostly validates:
- source shape and metadata
- schema compliance
- monster/reference parity
- continuity metadata
- sidecar/registry state

It does not yet guarantee semantic runtime completeness.

That gap is why modules can pass validation while still failing at the table when players use natural language such as:
- "take us to Lintar's place"
- "bring Father Aldric to Brother Lintar"
- "we return to the priest's lodging"

These failures should be caught before publication, not discovered through manual bug testing across dozens of adventures.

## Root Cause

The current pipeline does not enforce a publishability standard for:
- named destination resolution
- hidden/revealable NPC authority
- natural-language room and destination aliases
- runtime-safe semantic travel validation

In practice:
- a location may exist topologically but lack canonical player-facing aliases
- an NPC may exist in hooks or seed data but not in scene-authority records
- prose may mention a destination or refuge that is not mapped to any canonical location ID
- readiness may return pass even though runtime DM play will still guess incorrectly

## Example: Night of the Restless Dead

Observed issue:
- Father Aldric is authored in location hooks and can be surfaced at runtime
- Brother Lintar / Lintar's place is referenced conceptually in play but is not canonically authored as a resolvable destination in the module
- the runtime therefore guesses a valid graph destination instead of the intended authored destination
- validation passes because the move is topologically legal, even though semantically wrong

This is not just a one-off module defect. It exposes a publication-gap in the pipeline.

## Goal

Define a stronger module-publication workflow so a module is only publishable when it is:
- structurally valid
- reference complete
- semantically grounded for runtime play
- safe for natural-language travel and NPC interactions

## Publication Standard

A module should be considered publishable only if all of the following are true:

1. Schema-valid
- All module files pass validation.

2. Reference-complete
- Monster references resolve.
- Required authored data exists.
- Runtime hydration does not depend on guesswork.

3. Semantic destination-complete
- Every authored named refuge, hall, abode, camp, shrine, chapel, inn, lodge, watchtower, etc. either:
  - maps to exactly one canonical location ID, or
  - fails publication.

4. NPC authority-complete
- Every visible NPC and every hidden/revealable NPC has a canonical scene-authority path.
- If the module allows the NPC to be discovered in a location, runtime must be able to validate and move that NPC deterministically.

5. Natural-language alias-complete
- Common destination and room aliases are deterministic.
- Stripped room titles, authored location nicknames, and key named destinations resolve safely.

6. Probe-safe for live play
- Deterministic test prompts for travel, discovery, and NPC escort behavior resolve to the expected authored targets.

## Required Pipeline Changes

### 1. Add Semantic Enrichment During Ingest

Ingest should build a deterministic semantic layer, not just emit baseline JSON files.

New enrichment outputs should include:
- location alias map
- destination phrase map
- npc scene-authority map
- hidden/revealable NPC bindings
- authored destination mentions resolved to canonical location IDs

Examples:
- "Priest's Lodging" -> `NIG04`
- "Lintar's place" -> intended location ID
- `Father Aldric` -> scene authority at `NIG04`

This enrichment must be deterministic and traceable.

### 2. Add Publishability Semantic Audit

A new audit phase should fail publication when:
- a named destination is mentioned in authored content but cannot resolve uniquely
- a hidden/revealable NPC can appear in scene but lacks canonical authority mapping
- a likely player phrase could resolve to the wrong valid location
- runtime would need to guess instead of apply deterministic module truth

### 3. Add Probe-Based Validation

Publication auditing should run synthetic gameplay probes against authored module semantics.

Examples:
- "take us to Lintar's place"
- "return to the priest's lodging"
- "bring Father Aldric to Brother Lintar"
- "show us the hidden priest"

Expected result:
- each probe resolves to one canonical authored target
- ambiguity or drift blocks publication

### 4. Upgrade Readiness -> Publishability

Current readiness pass is not enough.

We need two levels:
- `ready`: structurally valid
- `publishable`: structurally valid + semantically safe for runtime play

A module should not be released to testers or players unless it passes `publishable`.

## Policy Recommendation

Unresolved semantic references should hard-fail publication.

Recommended policy:
- if a destination like "Brother Lintar's place" is not canonically resolvable, publication fails
- do not silently guess
- do not rely on runtime heuristics to save missing authored structure

Rationale:
- matches the requirement that validated modules should be publishable
- scales better than manual bug testing across 50+ adventures
- forces missing semantics to be fixed once in the pipeline rather than repeatedly in runtime patches

## Proposed OpenSpec Change

Suggested change name:
- `module-publishability-semantic-readiness`

Suggested scope:
- deterministic destination alias extraction
- hidden/revealable NPC authority enrichment
- semantic publishability audit
- readiness gate upgrade from pass to publishable
- synthetic probe coverage for live-play travel/NPC semantics

## Expected Outcome

After this work:
- modules that pass publication validation should be safe to ship
- destination and NPC authority bugs should be caught during ingest/readiness
- runtime should stop carrying the burden of repairing missing authored semantics
- manual bug testing should become confirmation, not discovery
