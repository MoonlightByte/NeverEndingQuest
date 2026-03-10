## Meta-Source Rubric (World Narrative Seed)

## Purpose

Define how high-level "meta" sources (strategy, cosmology, existential horror) combine with fantasy-novel corpus priors.

This rubric confirms the target architecture:
- Meta sources provide governance-level priors.
- Fantasy novels provide setting-level and motif-level specifics.
- Campaign outputs are interpreted world models, not direct source transcriptions.

## Layering Model

1. **Layer A - Meta Governance Priors**
   - Strategy realism and power dynamics.
   - Realm topology and metaphysical structure.
   - Existential tone and unknown-pressure patterns.

2. **Layer B - Genre/Novel Specific Priors**
   - Faction flavors, motifs, scene templates, arc pressure.
   - Local world texture and narrative cadence.

3. **Layer C - Campaign Interpreted World Model**
   - Synthesized per campaign and per version.
   - Consumed by EGO/Ratio, Module Builder, and Narrator via scoped contracts.

## MUST Contract

- MUST treat meta sources as abstract priors only, never direct lore imports.
- MUST keep committable outputs source-anonymous even when source text is public domain.
- MUST reject direct named IP carryover and direct quotations in atom outputs.
- MUST keep one-book-at-a-time ingestion and profile assignment explicit per ingest run.
- MUST keep final campaign behavior driven by interpreted model snapshots, not raw source rows.

## SHOULD Guidance

- SHOULD maintain separate profile IDs for each meta source family.
- SHOULD apply influence caps so no single profile dominates world interpretation.
- SHOULD review top weighted atoms after each ingest for leakage and overfitting.

## Recommended Profile Taxonomy

- `profile.strategy_realpolitik`
  - Source class: governance/power treatises (for example, The Prince)
- `profile.cosmology_layered_realms`
  - Source class: layered afterlife/cosmos epics (for example, Inferno)
- `profile.horror_eldritch_pressure`
  - Source class: public-domain cosmic/unknown horror
- `profile.fantasy_novel_<series_or_batch>`
  - Source class: fantasy corpus priors

## Atom Type Targets by Profile

- `profile.strategy_realpolitik`
  - preferred: `decision_logic`, `faction_pattern`, `institution_pattern`, `arc_shape`
  - avoid: named ruler/place references

- `profile.cosmology_layered_realms`
  - preferred: `cosmology_layer`, `realm_transition_rule`, `moral_topology`, `scene_template`
  - avoid: direct canonical proper nouns

- `profile.horror_eldritch_pressure`
  - preferred: `tone`, `threat_pattern`, `knowledge_cost`, `arc_shape`
  - avoid: trademarked/non-public-domain named entities

- `profile.fantasy_novel_*`
  - preferred: `motif`, `scene_template`, `faction_pattern`, `archetype`
  - avoid: source-identifying metadata and quotes

## Influence Governance (Interpretation Stage)

- Meta priors SHOULD act as structural constraints, not complete generators.
- Suggested starting bounds:
  - `strategy_realpolitik`: 0.15-0.25
  - `cosmology_layered_realms`: 0.15-0.25
  - `horror_eldritch_pressure`: 0.10-0.20
  - combined fantasy-novel profiles: 0.35-0.60

Adjustments belong to interpreted model generation, not raw atom mutation.

## Entry-Point Binding

- **EGO/Ratio**
  - reads interpreted model priors for drift analysis and governance tuning
  - does not consume raw source uploads

- **Module Builder**
  - uses interpreted model plus selected atom packs for setting synthesis
  - should preserve profile diversity in world generation

- **Narrator Runtime**
  - uses campaign interpreted model snapshots
  - should not directly read source-anonymous atom tables per turn

## QA Checklist per Ingest Batch

- [ ] Profile ID selected intentionally for source class.
- [ ] Strict compliance checks pass (banned keys/terms).
- [ ] No direct quote/proper-noun leakage in atom labels/descriptions.
- [ ] Top 20 weighted atoms reviewed for abstraction quality.
- [ ] Atom statistics/relations updated without profile collapse.
