## 1. Seed contract generation

- [ ] 1.1 Add module NPC seed generation step in `core/generators/module_builder.py` after NPC reconciliation.
- [ ] 1.2 Write `modules/<module>/npc_profile_seeds.json` with canonical names, aliases, source refs, and optional profile hints.
- [ ] 1.3 Ensure seed generation is additive and non-fatal to module build completion.

## 2. NPC builder alignment

- [ ] 2.1 Extend `core/generators/npc_builder.py` to accept optional module/seed context inputs.
- [ ] 2.2 Implement merge precedence: explicit args > seed hints > defaults.
- [ ] 2.3 Add deterministic postprocessing in `npc_builder`:
  - role normalization (`type`, `character_type`, `character_role` => `npc`)
  - appearance key seeding (`age`, `height`, `weight`, `eyes`, `skin`, `hair`)
  - audit validation using shared creation audit pipeline.
- [ ] 2.4 Ensure schema-critical failures are explicit and surfaced.

## 3. Runtime callsite wiring

- [ ] 3.1 Update enlist path in `core/ai/action_handler.py` (`updatePartyNPCs` add flow) to pass module seed context into NPC materialization.
- [ ] 3.2 Update NPC creation fallback in `core/generators/combat_builder.py` to pass module seed context into NPC materialization.
- [ ] 3.3 Preserve existing behavior when seed file is unavailable.

## 4. Candidate classification guard

- [ ] 4.1 Tighten Add Existing candidate filtering in `web/routes/tabletop_party_routes.py`:
  - explicit NPC marker in `type`, `character_type`, or `character_role` excludes player candidate listing.
- [ ] 4.2 Preserve backward compatibility for legacy player files with missing marker fields.

## 5. Regression coverage

- [ ] 5.1 Add tests for module seed contract generation and structure.
- [ ] 5.2 Add tests for seed-aware NPC builder materialization and postprocessing.
- [ ] 5.3 Add tests for enlist/combat callsite context wiring and fallback behavior.
- [ ] 5.4 Add tests confirming NPC -> PC promotion remains viable with generated NPC files.

## 6. Verification

- [ ] 6.1 Run compile checks on modified files.
- [ ] 6.2 Run phase-focused regression tests.
- [ ] 6.3 Run manual smoke: generate module -> recruit NPC ally -> promote NPC to PC.
