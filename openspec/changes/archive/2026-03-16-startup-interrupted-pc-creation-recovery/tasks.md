## 1. Startup resume contract

- [x] 1.1 Add explicit startup-incomplete lifecycle handling in `utils/startup_wizard.py` so first-PC persistence remains immediate but interrupted onboarding is still resumable.
- [x] 1.2 Update startup detection paths to require wizard resume when persisted startup state is incomplete, while preserving normal single-player completion behavior.
- [x] 1.3 Add focused regression coverage for interrupted startup after first-PC creation and resumed preservation of existing party members.

## 2. One-PC tabletop UI recovery access

- [x] 2.1 Expose tabletop/startup-recovery visibility context from `web/web_interface.py` and add `MULTIPLAYER_MODE` coverage to `config_template.py`.
- [x] 2.2 Update `web/templates/game_interface.html` and `web/templates/partials/character_tabs.html` so `Manage Party` remains visible in valid one-PC tabletop recovery states without widening normal single-player UI.
- [x] 2.3 Add focused UI/source-contract regression tests for one-PC tabletop recovery visibility.

## 3. New-PC request fail-closed routing

- [x] 3.1 Add deterministic runtime handling in `main.py` for brand-new player-character creation requests made outside dedicated creation mode.
- [x] 3.2 Ensure the normal gameplay path does not use `updatePartyNPCs` for novel player identities and instead returns explicit creation-flow guidance.
- [x] 3.3 Add regression coverage for the failed `Xorn`-style request path so it cannot re-enter the same validation loop.

## 4. Verification

- [x] 4.1 Run targeted Python compile checks for touched backend files.
- [x] 4.2 Run targeted regression suites covering startup resume, one-PC UI recovery visibility, and new-PC request routing.
- [x] 4.3 Capture a concise pass/fail verification summary in the builder report before proceeding to broader implementation.
