## Context

The current startup wizard intentionally persists the first created PC immediately so the web UI can hydrate tabs and sheets during multi-PC onboarding. That early persistence fixed one race, but it also means an interrupted session can leave `party_tracker.json` with a valid module, one `partyMembers` entry, and an `active_character`, which makes `startup_required()` think the campaign is fully initialized.

At the same time, tabletop UI visibility is still gated by `MULTIPLAYER_MODE` or `party_members|length > 1`, so a one-PC partial bootstrap can hide the `Manage Party` affordance. The normal gameplay narrator path also has no safe contract for "create another player character," so it falls back to `updatePartyNPCs`, which the NPC name normalizer correctly rejects for novel names.

## Goals / Non-Goals

**Goals:**
- Preserve immediate first-PC persistence while making interrupted startup resumable.
- Keep party-management controls accessible in one-PC tabletop bootstrap states.
- Fail closed on brand-new PC creation requests during normal gameplay chat and route facilitators back to dedicated creation flows.
- Preserve existing single-player and dedicated tabletop creation paths.

**Non-Goals:**
- Rebuild startup as an asynchronous wizard.
- Allow arbitrary gameplay narration to fully author and save new PCs.
- Redesign character creation prompts, schema, or combat-state handling.

## Decisions

### 1) Persist an explicit startup completion marker (MUST)
Decision: add lightweight startup state metadata to persisted party state, with an explicit "incomplete" value set after first-PC persistence and cleared only after the startup loop exits normally.

Rationale:
- Preserves the March 12 immediate-persistence fix for frontend hydration.
- Avoids guessing from `partyMembers` length alone whether startup finished.
- Keeps resume detection deterministic across process exits, browser disconnects, and launcher restarts.

Alternatives considered:
- Remove early persistence: rejected because it would likely reintroduce the UI hydration race already fixed.
- Infer incompleteness from a single-PC party: rejected because valid single-player campaigns also have one PC.
- Use a separate marker file: possible, but less discoverable than colocating startup state with existing party bootstrap data.

### 2) Treat incomplete tabletop bootstrap as a UI-visible party-management state (MUST)
Decision: expose startup-incomplete status to the web template and treat it as a valid reason to show tabletop character tabs / `Manage Party`, even when only one PC exists.

Rationale:
- Prevents the facilitator from getting trapped in a one-PC state with no visible add-character entry.
- Preserves intentional single-player hiding behavior when neither tabletop mode nor startup recovery applies.

Alternatives considered:
- Always show tabletop tabs for all one-PC sessions: rejected because it changes single-player UI expectations more broadly than needed.
- Rely only on `MULTIPLAYER_MODE`: rejected because missing config/template coverage already caused one class of silent SP fallback.

### 3) Dedicated PC creation MUST stay separate from `updatePartyNPCs` (MUST)
Decision: normal gameplay chat requests to create a new PC will be intercepted or rejected with deterministic guidance to use the dedicated creation flows, rather than letting the narrator invent `updatePartyNPCs` actions for brand-new names.

Rationale:
- `updatePartyNPCs` is designed for known NPC companions, not novel player identities.
- The existing name-normalization layer is behaving correctly by rejecting unknown names; the routing contract is what is wrong.
- A fail-closed redirect is safer than speculative LLM-driven player creation during an active scene.

Alternatives considered:
- Broaden `updatePartyNPCs` to accept novel names: rejected because it blurs NPC/PC lifecycle boundaries and bypasses character audit requirements.
- Launch full character creation mode directly from arbitrary narration every time: deferred as a larger UX feature beyond this recovery change.

### 4) Config fallback MUST be explicit and observable (SHOULD)
Decision: define `MULTIPLAYER_MODE` in `config_template.py` and harden template-context loading so missing config values do not silently disable tabletop UI.

Rationale:
- The current fallback-to-False behavior makes installer/template drift hard to diagnose.
- Explicit config coverage reduces environment-specific one-PC UI regressions.

## Risks / Trade-offs

- [Risk] Persisted startup-incomplete metadata could be left behind after an unexpected failure and keep forcing startup resume.
  - [Mitigation] Clear it only on successful completion, and keep resume behavior idempotent and safe to rerun.
- [Risk] Showing tabletop controls in the wrong context could widen UI surface for single-player users.
  - [Mitigation] Gate visibility on `MULTIPLAYER_MODE` or explicit startup-incomplete state, not on one-PC presence alone.
- [Risk] New-PC chat guard may feel stricter than current freeform narration.
  - [Mitigation] Return explicit system guidance that points to the correct dedicated creation flow instead of generic failure text.

## Migration Plan

1. Extend startup persistence logic with explicit incomplete/complete lifecycle handling.
2. Update startup detection to resume onboarding whenever persisted state says startup is incomplete.
3. Surface startup-incomplete context to the web template and relax tabletop UI gating only for intended tabletop recovery states.
4. Add deterministic runtime interception or validation guard for "create another PC" requests outside dedicated creation mode.
5. Add targeted regression tests and run focused verification.

Rollback:
- Revert startup-incomplete metadata handling and UI gating changes together if resume behavior misfires.
- Keep dedicated creation endpoints untouched so manual recovery remains possible.

## Open Questions

- None for planning. The implementation can choose exact metadata naming, but it MUST remain lightweight, backward-compatible, and ignored safely by existing party tracker consumers.
