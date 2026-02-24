## 1. OpenSpec scaffold and contract

- [x] 1.1 Add proposal/design/spec/tasks artifacts for this change with explicit MUST and SHOULD sections.
- [x] 1.2 Validate artifact language is testable and aligned to merge-safe plugin rules.

## 2. Startup multi-PC reprompt hardening

- [x] 2.1 Update `utils/startup_wizard.py` add-more prompt emission to line-visible web output before input capture.
- [x] 2.2 Add strict yes/no parser for add-more flow (`y/yes`, `n/no`) and reprompt on blank/invalid input.
- [x] 2.3 Ensure blank/timeout web input cannot silently end multi-PC startup creation.
- [x] 2.4 Keep startup transition to gameplay gated until explicit `n/no` response.
- [x] 2.5 Preserve existing per-character creation retry behavior and failure messaging.

## 3. Character sheet stats loading resilience

- [x] 3.1 Fix null-guard order in `displayCharacterStats` in `web/templates/game_interface.html` so `data` is validated before `data.*` access.
- [x] 3.2 Add deterministic waiting/error render states when `player_data_response` stats payload is null.
- [x] 3.3 Ensure no JS exception blocks later successful stats render.
- [x] 3.4 Preserve existing polling refresh behavior as recovery path.

## 4. Regression tests and verification

- [x] 4.1 Add focused startup tests for explicit yes/no enforcement and blank/invalid reprompt behavior.
- [x] 4.2 Add focused UI source-contract tests for null-safe `displayCharacterStats` behavior.
- [x] 4.3 Run compile/syntax checks and targeted tests; capture pass/fail summary.

## 5. Builder handoff

- [x] 5.1 Keep `executor_prompts.md` aligned with task sequencing and verification gates.
