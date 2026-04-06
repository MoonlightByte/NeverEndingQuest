## 1. Checkpoint metadata foundation

- [x] 1.1 Add additive diary checkpoint metadata support for module/location stamps in the diary persistence path and memory DB migration layer.
- [x] 1.2 Update diary row serialization so draft and confirmed entries expose structured world date/time, module, and location fields through the existing diary route.
- [x] 1.3 Verify metadata persistence and serialization with focused diary service tests plus `python3 -m py_compile core/memory/session_diary.py core/memory/memory_db.py web/routes/memory_routes.py`.

## 2. Journal-first source hygiene

- [x] 2.1 Replace the diary checkpoint source selection so journal beats are primary and conversation/combat history is only used as sanitized fallback when no journal beats exist in the checkpoint window.
- [x] 2.2 Implement diary-specific source sanitization that strips JSON/action payloads, system notices, prompt scaffolding, and other out-of-world artifacts before summary generation.
- [x] 2.3 Implement checkpoint deduplication for repeated journal variants that describe the same scene/time/location beat.
- [x] 2.4 Add regression coverage proving diary summaries do not leak JSON/system text and do not duplicate the same journal beat.

## 3. Concise diary recap generation

- [x] 3.1 Replace the current placeholder first-entry/last-entry fallback recap builder with a bounded quick-reference recap generator optimized for player memory.
- [x] 3.2 Wire the existing diary prompt path to a sanitized, compact checkpoint packet using the provider-agnostic AI client stack while preserving fail-open behavior.
- [x] 3.3 Keep Start Game, Save, and explicit Exit hooks fail-open and verify degraded diary generation still leaves primary lifecycle actions successful.
- [x] 3.4 Add focused tests for concise recap shape, world-line emphasis, and deterministic fallback behavior.

## 4. Journal UI presentation

- [x] 4.1 Update the Diary tab rendering so each entry presents gameworld date/time and location like an in-world log entry while keeping the existing Journal modal structure intact.
- [x] 4.2 Ensure diary route/UI fallback labels remain safe when module or location metadata is missing.
- [x] 4.3 Verify diary UI behavior with targeted JS/source-contract coverage and `node --check web/templates/game_interface.html` if script extraction is required by existing test patterns.

## 5. Story PDF foundation and remediation

- [x] 5.1 Update confirmed diary consumption in the story compiler so cleaned recap text and checkpoint metadata improve chapter-beat quality without changing confirmed-only canon boundaries.
- [x] 5.2 Add deterministic remediation tooling or service support to rebuild legacy noisy diary rows from their stored source windows.
- [x] 5.3 Add regression coverage for confirmed-only story input quality and legacy diary remediation safety.

## 6. Final verification

- [x] 6.1 Run targeted compile checks for touched Python files and route/UI assets.
- [x] 6.2 Run focused diary, route, remediation, and Story PDF regression suites.
- [ ] 6.3 Perform a manual smoke pass covering Start Game draft refresh, Save/Exit confirmation, Diary tab readability, and Story PDF generation quality.

SHOULD: Implement the diary source cleaner as a narrowly scoped helper module or helper cluster so generic memory ingestion behavior remains stable for non-diary consumers.
SHOULD: Keep host-file edits additive and marked with `# TABLETOP MODE:` comments wherever the Journal modal or lifecycle hooks need changes.
