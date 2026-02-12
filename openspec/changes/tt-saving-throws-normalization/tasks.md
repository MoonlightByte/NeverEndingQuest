## 1. Shared Normalization and Fallback Logic

- [x] 1.1 Add helper(s) to normalize `savingThrows` into canonical ability keys (case-insensitive, abbreviation-aware) (verify: unit-style checks for `Strength/strength/STR` equivalence).
- [x] 1.2 Add class-based fallback helper for empty savingThrows with alias handling (`thief` -> rogue) (verify: expected defaults for wizard/cleric/barbarian/rogue).

## 2. GUI Character Sheet Consistency

- [x] 2.1 Update `web/templates/game_interface.html` to always render the Saving Throws panel with all six abilities (verify: panel visible even when `savingThrows` is empty).
- [x] 2.2 Replace direct `data.savingThrows.includes(...)` usage with normalized/fallback proficiency lookup (verify: proficiency markers correct for mixed-case values).

## 3. PDF Export Consistency

- [x] 3.1 Update saving throw proficiency checks in `web/routes/character_sheet_routes.py` to use normalized/fallback source (verify: checkbox mapping works for title-case and lowercase values).
- [x] 3.2 Ensure PDF save bonuses match GUI computed bonuses for same character (verify: compare one empty-savingThrows character and one populated-savingThrows character).

## 4. Optional Data Backfill Utility

- [x] 4.1 Add optional one-time script to populate missing `savingThrows` in existing character files using class fallback (verify: dry-run/report mode and explicit apply mode).
- [x] 4.2 Ensure backfill script skips characters that already have explicit savingThrows (verify: unchanged files reported correctly).

## 5. Verification and Regression Checks

- [x] 5.1 Run `python3 -m py_compile` on modified Python files (verify: no syntax errors).
- [x] 5.2 Validate affected PCs (Tester, Xerxes, Cyrius) now show Saving Throws in GUI and consistent PDF values.
- [x] 5.3 Regression-check valid PCs (Acheron, Claris) remain correct in GUI and PDF.
