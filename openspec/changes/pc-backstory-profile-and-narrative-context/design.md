## Context

Background feature and backstory now have distinct jobs:
- `backgroundFeature` = practical social/mechanical access flavor (already mapped to PDF `Feat+Traits`)
- `backstory` = narrative identity history that should influence portrait mood and ongoing story responses

Current code has no top-level `backstory` in schema or profile contracts.

## Goals / Non-Goals

**Goals:**
- Add a first-class `backstory` field to character data contracts.
- Make `backstory` required for PC profile quality in creation + portrait create + readiness repair.
- Replace portrait modal background-feature inputs with backstory input.
- Thread `backstory` into narrative context providers and portrait prompt composition.
- Keep NPC->PC promotion safe and warning-first.

**Non-Goals:**
- Build full world-narrative interpretation logic in this change.
- Remove `backgroundFeature` from schema or existing flows.
- Block legacy NPC files from functioning when `backstory` is absent.

## Architecture Decisions

1. **Schema compatibility strategy (MUST)**
   - Add `backstory: string` in schema `properties`.
   - Keep `required` list unchanged for immediate backward compatibility.
   - Enforce PC-critical behavior in audit/readiness layers, not raw schema required list.

2. **Profile contract strategy (MUST)**
   - Portrait Create required profile fields swap:
     - remove `background_feature_name`, `background_feature_description`
     - add `backstory`
   - Persist backstory with profile save before portrait generation.

3. **Audit and repair strategy (MUST)**
   - Add `backstory` to completeness paths for creation audit.
   - Add `backstory` to profile readiness paths.
   - Add `backstory` to readiness repair writable whitelist and deterministic fallback text.
   - Preserve mechanical immutability invariants unchanged.

4. **Narrative injection strategy (SHOULD)**
   - Add bounded backstory snippets (sanitized/length-limited) to runtime character context blocks in:
     - conversation context builder
     - combat manager character formatters
     - multi-PC DM note summaries
     - character sheet compressor output
   - Purpose is flavor influence, not mechanical authority.

5. **NPC->PC promotion strategy (MUST)**
   - Promotion remains non-blocking on missing `backstory`.
   - Profile readiness warning payload includes `backstory` gaps.
   - Optional seeding behavior may initialize empty `backstory` key for consistency.

6. **PDF Backstory field strategy (SHOULD)**
   - Prefer `char_data.backstory` for page 2 `Backstory` field content.
   - Optionally append campaign summary snippets below authored backstory.
   - Keep `backgroundFeature` in `Feat+Traits` unchanged.

## Risks / Trade-offs

- **Risk:** adding `backstory` to completeness could break some creation paths.
  - **Mitigation:** update all creation entry points and defaults in same change.
- **Risk:** token growth in system context.
  - **Mitigation:** sanitize and cap backstory text before injection.
- **Risk:** specification conflict with background-feature-guided portrait modal.
  - **Mitigation:** update spec delta to reflect backstory replacement in portrait modal.

## Migration Plan

1. Schema + audit base (`schemas/char_schema.json`, `utils/character_creation_audit.py`).
2. Creation paths (`utils/startup_wizard.py`, `web/routes/tabletop_party_routes.py`, DM prompt template).
3. Portrait modal + API + prompt (`web/templates/game_interface.html`, `web/web_interface.py`, `core/toolkit/portrait_service.py`).
4. Narrative injection surfaces (`conversation_utils`, `combat_manager`, `multi_pc_dm_note`, compressor).
5. Promotion and PDF alignment.
6. Tests and verification.

Rollback:
- Keep schema addition additive.
- Revert profile-required contract changes if needed while preserving stored `backstory` field.

## Verification Strategy

- Compile checks on modified Python files.
- Run targeted tests:
  - `python3 scripts/test_character_creation_audit.py`
  - `python3 scripts/test_pc_image_create_mvp.py` (targeted profile suites)
- Manual checks:
  - Roll Your Own create with backstory
  - Create with DM finalization requiring backstory
  - Portrait Create modal enforces backstory and persists it
  - Promotion preview/apply warnings include missing backstory when absent
  - PDF page 2 `Backstory` field prefers authored backstory
