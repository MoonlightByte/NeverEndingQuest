## Context

Current module state is strong on baseline progression and mechanics but lighter on origin depth and branch consequences. Existing plot flow already supports staged escalation:

- PP001-PP002: village setup and outskirts clues
- PP003-PP005: maze and ritual artifact discovery
- PP006-PP007: graveyard judgment and final confrontation

The expansion must preserve this structure while adding occult narrative pressure and multiple parity endings.

## Goals / Non-Goals

**Goals**
- Introduce restrained occult dread inspired by August Underground mood (psychological pressure, ritual unease, moral decay) without explicit gore focus.
- Deliver multiple endings with equal viability and distinct consequences.
- Ensure clue discovery rewards reasoning, not random guesswork.
- Constrain challenge checks to DC 12-18.
- Keep all JSON edits additive and LLM DM contract-safe.

**Non-Goals**
- Any schema-breaking JSON changes.
- Any replacement of the existing PP001-PP007 route.
- Runtime code or UI system changes.

## Decision Lock (User Inputs)

- Tone: restrained August Underground influence.
- Endings: equal viability.
- Puzzle style: reason-first interpretation and deduction.
- DC policy: 12-18 only.
- Integration: additive-only JSON updates to preserve LLM DM contract.

## Narrative Architecture

### 1) Occult Escalation Arc

Escalation is staged by area:
- HFG001: subtle unease and social denial.
- VO001: pact-era artifacts and witness records.
- CMS001: distorted memory, child-loss echoes, failed prior intervention evidence.
- BOO001: ritual and bargain mechanics become explicit.
- GRV001: legal/moral judgment and pact interpretation pressure.
- HLF001: culmination and ending branch resolution.

### 2) Branching Ending Parity Model

Four endings are maintained as equal-viability outcomes by balancing entry requirements and final-scene pressure:

1. **Bramble Sacrifice Ending**
   - Requires legacy-line reveal + voluntary cost acceptance.
   - Lower final combat pressure, higher moral cost.

2. **Contract Void Ending**
   - Requires multi-clue legal/ritual reasoning.
   - Medium final combat pressure, high investigation demand.

3. **Kingslayer Ending**
   - Requires minimal clue completion.
   - High final combat pressure, low investigation demand.

4. **Dark Bargain Ending**
   - Requires direct occult negotiation path.
   - Medium combat pressure plus severe world consequence.

Parity rule: each ending MUST be reachable through in-world clues and decisions without hidden out-of-band requirements.

### 3) Reason-First Clue Graph

Clues are distributed so at least two independent threads can reveal each major truth:

- Origin truth (who formed pact and why)
- Contract weakness (what can void or reshape it)
- Ritual completion requirements (what final scene needs)

All gates use explicit logic with DC checks constrained to 12-18.

## Data Mapping (Implementation Targets)

- `module_plot.json`
  - Add branch outcome notes to PP006/PP007 narrative handling.
  - Add side-quest references for ending unlock parity.
- `module_context.json`
  - Add NPC placement/description fill-ins where currently sparse.
  - Add references for new evidence-bearing NPCs or spirits.
- `areas/HFG001.json`
  - Add early occult foreshadowing and social contradiction hooks.
- `areas/VO001.json`
  - Add origin evidence location and contract witness artifacts.
- `areas/CMS001.json`
  - Add failed-intervention evidence and child-loss clue thread.
- `areas/BOO001.json`
  - Add ritual grammar and contract interpretation clues.
- `areas/GRV001.json`
  - Add judgment records and pact legal-pressure choices.
- `areas/HLF001.json`
  - Add explicit branch-trigger end-scene options and consequence framing.

## Contract-Safe Rules

- MUST preserve existing top-level structures in each JSON file.
- MUST keep existing IDs for plot points, areas, and established locations.
- MUST only add fields/entries that existing schemas permit.
- MUST preserve LLM-DM action compatibility (`createEncounter`, `updateCharacterInfo`, `updatePlot`, `levelUp`, `updateTime`).
- SHOULD place new narrative text where existing `description`, `investigationNotes`, `storyHooks`, and quest-like structures already exist.

## Risks / Trade-offs

- Risk: over-branching can fragment pacing.
  - Mitigation: preserve linear PP backbone and attach branches at PP006-PP007 decision points.
- Risk: tone may drift into excess explicitness.
  - Mitigation: content rubric enforces restrained description and implication-first horror.
- Risk: ending parity may fail if one branch has substantially easier unlocks.
  - Mitigation: define per-ending requirement count and balancing pass in validation tasks.

## Verification Strategy

- Schema validation:
  - `python core/validation/validate_module_files.py`
- Branch parity checks:
  - Verify each ending has clear in-world unlock path and comparable effort profile.
- Contract checks:
  - Verify no key removals/renames in modified module JSON.
- Tone checks:
  - Verify language remains restrained occult horror (implication > explicit gore).
