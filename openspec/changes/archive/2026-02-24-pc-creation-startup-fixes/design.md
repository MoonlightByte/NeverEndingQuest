## Context

Observed tabletop startup path uses:
- `utils/startup_wizard.py` for module selection and PC creation loop.
- `web/web_interface.py` output capture + web input bridge.
- `web/templates/game_interface.html` stats socket response rendering.

Current failure pattern:
- Add-more prompt visibility is unreliable in web mode when prompt text is inline to `input(...)`.
- Blank inputs can be interpreted as not-yes and prematurely exit multi-PC creation.
- Stats UI can crash on null response due to pre-guard property access.

## Goals / Non-Goals

**Goals:**
- Enforce explicit y/n loop for additional PC creation (reprompt-only policy).
- Ensure startup prompt is visible and actionable in web tabletop flow.
- Guarantee null-safe character sheet rendering during startup race windows.

**Non-Goals:**
- Rework startup interview prompts.
- Remove periodic polling model.
- Introduce asynchronous startup wizard redesign.

## Decisions

### 1) Explicit y/n decision gate for add-more flow (MUST)
Decision: Replace permissive branch logic with strict response parser (`yes`/`no` only) and reprompt on blank/invalid responses.

Rationale:
- Matches tabletop facilitator requirement: no silent one-PC fallthrough.
- Prevents timeout/blank inputs from being interpreted as negative confirmation.

### 2) Web-visible prompt emission pattern (MUST)
Decision: Emit add-more question as newline-terminated output before collecting input.

Rationale:
- Web output capture is line-oriented.
- Explicit line emission ensures facilitator sees the decision point.

### 3) Null-safe stats rendering contract (MUST)
Decision: In `displayCharacterStats`, validate `data` before any derived fields or DOM-dependent render logic.

Rationale:
- Removes race-driven JS exceptions.
- Allows eventual recovery when later socket payload includes valid stats.

### 4) Deterministic waiting/error UI states (SHOULD)
Decision: Render stable fallback states (`waiting`, `error`) instead of leaving stale spinner forever.

Rationale:
- Clear operator feedback during startup races.
- Lower support/debug burden.

## MUST / SHOULD Contract

MUST:
- MUST reprompt for add-more decision until explicit yes/no.
- MUST not auto-exit add-more loop on blank input.
- MUST not crash character sheet renderer on null stats payload.
- MUST preserve existing periodic stats refresh and successful late render behavior.

SHOULD:
- SHOULD keep prompt and error copy concise.
- SHOULD add focused tests covering blank input and null stats payload behavior.

## Risks / Trade-offs

- [Risk] Strict reprompt may hold flow if facilitator leaves prompt unattended.
  - [Mitigation] Keep prompt copy explicit; allow clear cancel wording only if explicitly entered.
- [Risk] Extra UI fallback states may mask real backend errors.
  - [Mitigation] Include backend error text when available.

## Migration Plan

1. Add OpenSpec artifacts and task sequence.
2. Implement startup reprompt gate + visible prompt emission.
3. Implement stats null-safe rendering + waiting/error fallback.
4. Add focused regression tests and run compile checks.

Rollback:
- Revert startup decision parser and null-safe UI changes in isolation.
- Keep prior polling behavior intact.

## Verification Strategy

- Compile checks:
  - `python3 -m py_compile utils/startup_wizard.py web/web_interface.py`
- JS syntax/source checks:
  - `node --check web/templates/game_interface.html` (or source-contract tests)
- Targeted tests:
  - startup blank/invalid input reprompt behavior
  - explicit no required to exit add-more loop
  - null stats payload no-throw + later valid payload render path
