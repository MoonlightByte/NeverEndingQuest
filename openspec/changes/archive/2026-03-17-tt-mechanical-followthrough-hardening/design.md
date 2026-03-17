## Context

The current runtime has a productive new balance: narrator validation is lighter, response times are faster, and umpire-style direct answers feel much more like collaborative tabletop play. The remaining gap is not creative freedom; it is follow-through. The transcript shows four concrete drift classes:

1. Explicit narrated gifts from Hermit Maelo (ward stones, tome, healing potion) were never persisted.
2. Kira's potion use partially updated HP, but malformed structured ops and missing canonical inventory state prevented clean inventory removal.
3. Chronos's Rage narration and umpire answer recognized the correct depletion state, but no deterministic resource op updated JSON.
4. Pre-combat hostiles such as the Naiad and Captain Gorvek were present in the scene data but invisible in the top-strip until combat formally created encounter creatures.

Constraint layer (MUST):
- Python state MUST remain the source of truth for mechanics.
- Reconcile-first behavior MUST stay narrow, explicit, and ambiguity-safe.
- Structured ops MUST use a canonical, deterministic shape at runtime.
- Host-file edits MUST remain additive, minimal, and marked with `# TABLETOP MODE:` comments.
- New Python-visible strings MUST remain ASCII-only.
- Single-player behavior MUST remain compatible.

Guidance layer (SHOULD):
- Fix transcript-proven drift classes before broadening any general inference logic.
- Prefer compatibility shims over prompt-only retraining when malformed payloads already exist in logs.
- Keep UI semantics distinct: hostile scene presence is not party membership and not yet a formal encounter.
- Keep action-prediction hygiene scoped to raw-input observability rather than broader routing redesign.

## Goals / Non-Goals

**Goals:**
- Canonize explicit narrated scene gifts when recipients and items are safely clear.
- Normalize malformed legacy nested ops into canonical flat ops before deterministic application.
- Add deterministic class-feature usage ops for limited resources such as Rage.
- Ensure validator, combat truth packs, and DM Note summaries see live inventory/resource schema.
- Show current-location hostiles in the pre-combat top strip without waiting for encounter creation.

**Non-Goals:**
- Build a general natural-language inventory parser for all narrated loot.
- Infer item quantities, recipients, or resource depletion from ambiguous prose.
- Replace explicit `updatePartyNPCs`, `moveBackgroundNPC`, or encounter creation semantics.
- Redesign intelligent routing/model selection beyond raw-input observability hygiene.

## Decisions

### Decision: explicit scene gifts reconcile only when assignment is safe
- Runtime MUST add a narrow post-validation reconcile step for explicit gift/grant language from a known scene actor to named party recipients.
- It MUST only synthesize inventory updates when item identity and recipient assignment are both unambiguous from the candidate response or immediate transcript context.
- It MUST preserve explicit action precedence; if the response already contains matching inventory actions, reconcile-first logic SHALL not duplicate them.
- It MUST fail safe on ambiguity (for example, "Maelo shares supplies with the party" without clear allocation).
- Rationale: the drift came from clear, repeated gift narration without state follow-through, not from lack of general language understanding.

### Amendment: scene gift reconciliation MUST be generic, not module-NPC hard-wired
- The runtime implementation MUST NOT rely on specific module NPC names such as `Maelo` to decide whether scene-gift reconciliation is active.
- Instead, runtime SHALL derive a scene actor map from the current location and party context, then reconcile only explicit transfer language involving known scene actors and named recipients.
- The initial generic detector SHALL support only narrow explicit patterns, such as:
  - `X gives Y a Z`
  - `X hands Y the Z`
  - `Y takes the Z`
  - `Y receives the Z`
  - `A and B take a ward stone each`
- The detector MUST require all of the following before synthesizing actions:
  - actor resolves to a known current scene actor or party actor,
  - recipient resolves canonically to a party member or party NPC,
  - item phrase is concrete and unambiguous,
  - quantity is explicit or safely defaultable to `1`,
  - no matching explicit inventory action already exists.
- The detector MUST fail safe on vague reward language such as `the party receives supplies`, `you are rewarded`, or `someone tosses over gear`.
- Rationale: transcript-targeted hardwires solve one bug but age into dead code. The intended capability is reusable explicit transfer reconciliation across the game, not Thornwood residue.

### Decision: structured ops get a compatibility shim before deterministic application
- `updateCharacterInfo.parameters.ops` MUST use canonical flat op records with an explicit `op` field.
- Runtime MUST normalize legacy nested single-key shapes (for example `{"inventory_remove": {...}}`) into canonical flat ops when the intended op is unambiguous.
- Runtime MUST continue to reject unsupported or malformed ops that cannot be safely normalized.
- Rationale: logs already show malformed nested ops in real play, so prompt-only correction is not enough.

### Decision: class-feature depletion becomes deterministic
- Runtime MUST support deterministic class-feature usage ops against `classFeatures[].usage` for named limited-use features.
- The initial slice MUST support decrement/set semantics sufficient for Rage-style depletion.
- Ambiguous prose-only feature changes MAY still use fallback paths, but explicit structured feature ops MUST not depend on model interpretation.
- Rationale: feature usage is currently the clearest remaining "Python reality" gap for combat resources.

### Decision: truth surfaces align to the live character schema
- Validator truth packs MUST summarize nested `classFeatures[].usage` as well as legacy flat fields when present.
- Truth packs and DM Note mechanical summaries MUST source item visibility from live `equipment`, `ammunition`, and `currency` structures rather than deprecated `inventory.items` assumptions.
- DM Note output MUST stay compact; this change is visibility hardening, not prompt bloat.
- Rationale: the narrator cannot faithfully update or challenge reality it cannot see.

### Decision: pre-combat hostiles get a separate scene-presence channel
- `party_data_response` MUST expose current-location hostiles separately from party NPCs.
- The client MUST render those hostiles in the top strip only when no active combat encounter is controlling the strip.
- Scene hostiles MUST remain visually and semantically distinct from party members/NPC companions.
- Rationale: users need pre-combat situational awareness before initiative starts, but hostile scene presence is not yet encounter state.

## Risks / Trade-offs

- Narrow gift reconciliation could still over-commit if scene parsing is too loose -> Mitigation: require explicit gift verbs, known item identity, and named recipient resolution.
- Legacy ops normalization could accidentally bless unsupported payloads -> Mitigation: normalize only one-key known-op wrappers and log deterministic markers for every normalization.
- DM Note visibility expansion could bloat prompt size -> Mitigation: keep summaries compact and relevance-bounded.
- Pre-combat hostile thumbnails could confuse encounter state -> Mitigation: separate payload key and styling, and suppress it when combat UI is active.
- Resource ops could drift across schemas if feature matching is fuzzy -> Mitigation: exact or canonicalized feature-name matching only, fail safe on ambiguity.

## Migration Plan

1. Lock transcript-driven regression tests and spec deltas before runtime edits.
2. Implement ops contract updates and compatibility normalization.
3. Implement scene gift reconciliation with transcript-proven cases only.
4. Replace any transcript-specific or NPC-specific hardwire with a generic explicit scene-gift detector before archive.
5. Align truth-pack and DM Note schema visibility.
6. Add pre-combat hostile payload/rendering.
7. Run targeted regression suite plus `openspec validate tt-mechanical-followthrough-hardening`.

## Open Questions

- None for the generic detector slice. Broader routing/model-selection cleanup remains a SHOULD-level follow-up once state follow-through is stable.
