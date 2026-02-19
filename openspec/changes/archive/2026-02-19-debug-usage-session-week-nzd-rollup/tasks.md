## 1. Baseline and compatibility setup

- [x] 1.1 Confirm current `token_update` producer/consumer paths in `web/web_interface.py` and `web/templates/game_interface.html` and record baseline payload keys for regression checks.
- [x] 1.2 Add additive config defaults in `model_config.py` for `USD_TO_NZD_RATE`, `USAGE_WEEK_WINDOW_DAYS`, and `USD_PER_1M_TOKENS_BLEND` with safe fallback semantics.
- [x] 1.3 Verify baseline compile for unchanged startup path: `python3 -m py_compile model_config.py web/web_interface.py`.

## 2. Provider-agnostic usage tracker foundation

- [x] 2.1 Create `utils/llm_usage_tracker.py` with thread-safe session counters, rolling 60-second TPM/RPM, and rolling-week event aggregation.
- [x] 2.2 Implement provider-reported cost parsing from usage metadata (`usage.cost`) with generic fallback estimate/default behavior when missing.
- [x] 2.3 Implement safe historical bootstrap from telemetry log (skip malformed lines, continue on errors).
- [x] 2.4 Add compatibility wrapper behavior in `utils/openai_usage_tracker.py` so existing function signatures remain stable while delegating to generic tracker.
- [x] 2.5 Ensure stats path does not use nested lock acquisition and verify non-blocking reads.
- [x] 2.6 Verify compile: `python3 -m py_compile utils/llm_usage_tracker.py utils/openai_usage_tracker.py`.

## 3. Web socket payload extension

- [x] 3.1 Update `web/web_interface.py` token emitter to include additive rollup fields (`session_*`, `week_*`, USD/NZD, `cost_source`, estimate metadata, conversion rate) while preserving existing keys.
- [x] 3.2 Ensure failure path emits safe defaults for new fields without interrupting existing output queue processing.
- [x] 3.3 Verify compile: `python3 -m py_compile web/web_interface.py`.

## 4. Debug tab top rollup bar UI

- [x] 4.1 Update `web/templates/game_interface.html` Debug tab markup to add a top rollup row above existing TPM/RPM/Total stats.
- [x] 4.2 Update Debug header CSS so sticky layout supports two rows without clipping and keeps debug output scroll behavior intact.
- [x] 4.3 Extend `token_update` client handler in `web/templates/game_interface.html` to bind new rollup fields with safe defaults when fields are absent.
- [x] 4.4 Manual smoke: open Debug tab and verify new row renders above existing token stats row.

## 5. Regression-safe compatibility checks

- [x] 5.1 Verify existing TPM/RPM/Total updates still function in Debug tab with active gameplay outputs.
- [x] 5.2 Verify no runtime exceptions when `token_update` payload contains only legacy fields.
- [x] 5.3 Verify missing provider cost still increments token counters and emits estimated/unavailable metadata without crashes.

## 6. Focused tests

- [x] 6.1 Add test coverage script (for example `scripts/test_usage_rollups_debug_tab.py`) for session/week token math, rolling-window boundaries, and malformed telemetry tolerance.
- [x] 6.2 Add tests for cost source behavior: provider-reported cost, fallback estimated cost, and unavailable cost.
- [x] 6.3 Add tests for conversion rate handling and payload shape compatibility (legacy keys retained, additive keys present when available).
- [x] 6.4 Run tests added in this change and capture results.

## 7. Final verification

- [x] 7.1 Run compile checks: `python3 -m py_compile utils/llm_usage_tracker.py utils/openai_usage_tracker.py web/web_interface.py`.
- [x] 7.2 Run UI compile/sanity checks for template edits (load app and open Debug tab).
- [ ] 7.3 Manual smoke checklist:
- [ ] 7.3.1 Session tokens/cost values increase during play.
- [ ] 7.3.2 Week values show rolling aggregate and remain stable across short idle periods.
- [ ] 7.3.3 Existing TPM/RPM/Total row still updates.
- [ ] 7.3.4 No OpenAI-only wording appears in new Debug rollup labels.

## 8. Builder handoff artifacts

- [x] 8.1 Create `openspec/changes/debug-usage-session-week-nzd-rollup/executor_prompts.md` with phase-by-phase Kimi builder prompts and verification commands.
- [x] 8.2 Ensure all host edits are minimal and mark required host hooks with `# TABLETOP MODE:` comments.

SHOULD guidance (non-blocking): keep rollup labels concise to avoid wrapping in narrow debug panel widths.
