Use this file as the builder execution scaffold for `tasks.md`.

---

## Execution Contract

- MUST execute in order: Prompt 1 -> Prompt 6.
- MUST keep existing `token_update` keys (`tpm`, `rpm`, `total_tokens`) unchanged.
- MUST keep new Python-visible text ASCII only.
- MUST keep provider wording generic (no OpenAI-only labels in new UI text).
- MUST mark required host-file hooks with `# TABLETOP MODE:` comments.
- SHOULD keep logic additive and merge-safe.

---

## Prompt 1 - Generic Tracker + Config Foundation (Revised)

Implement tasks 1.x and 2.x.

Scope:
- `model_config.py`
- `utils/llm_usage_tracker.py` (new)
- `utils/openai_usage_tracker.py`

Requirements:
- Add config constants for week window, USD->NZD conversion, and blended fallback USD-per-1M rate.
- Build thread-safe generic tracker with session + rolling-week rollups.
- Parse provider-reported per-call cost from usage metadata when available.
- Apply generic fallback estimate/default behavior when provider cost is missing.
- Preserve `utils/openai_usage_tracker.py` public function compatibility.
- Avoid nested lock acquisition in stats read path.

Verify before moving on:
- `python3 -m py_compile model_config.py utils/llm_usage_tracker.py utils/openai_usage_tracker.py`
- quick smoke: `get_usage_stats()` returns immediately after one mock track event

---

## Prompt 2 - Socket Payload Extension

Implement tasks 3.x.

Scope:
- `web/web_interface.py`

Requirements:
- Extend `token_update` payload with additive `session_*` and `week_*` fields.
- Include USD/NZD values, conversion rate, `cost_source`, and estimate metadata.
- Keep legacy payload keys untouched.

Verify before moving on:
- `python3 -m py_compile web/web_interface.py`

---

## Prompt 3 - Debug Tab Top Rollup UI

Implement tasks 4.x.

Scope:
- `web/templates/game_interface.html`

Requirements:
- Add top rollup row above current TPM/RPM/Total row.
- Update CSS sticky header behavior for two-row layout.
- Bind new payload fields with zero/default fallback when missing.

Verify before moving on:
- Manual smoke: Debug tab shows top rollup + existing token row.
- Manual smoke: existing debug output remains scrollable.

---

## Prompt 4 - Compatibility and Regression Hardening

Implement tasks 5.x.

Scope:
- `web/web_interface.py`
- `web/templates/game_interface.html`
- tracker modules as needed

Requirements:
- Confirm legacy payload path remains stable.
- Confirm missing provider cost does not break token updates.
- Confirm additive fields are safe when partially absent.

Verify before moving on:
- Manual smoke with legacy-only mock payload.
- Manual smoke with provider-cost-missing usage event.

---

## Prompt 5 - Automated Tests

Implement tasks 6.x.

Scope:
- `scripts/test_usage_rollups_debug_tab.py` (new or equivalent)
- any touched tracker files

Requirements:
- Add tests for session/week math, rolling-window filtering, malformed telemetry tolerance, and conversion math.
- Add tests for cost source states: provider_reported, estimated, unavailable.
- Add test for payload compatibility retaining legacy keys.

Verify before moving on:
- `python3 scripts/test_usage_rollups_debug_tab.py`

---

## Prompt 6 - Final Validation and Handoff

Implement tasks 7.x and 8.x.

Scope:
- all changed files in this change

Required final commands:
- `python3 -m py_compile model_config.py utils/llm_usage_tracker.py utils/openai_usage_tracker.py web/web_interface.py`
- `python3 scripts/test_usage_rollups_debug_tab.py`
- `openspec status --change debug-usage-session-week-nzd-rollup`

Manual final smoke checklist:
1. Session rollup increases during active gameplay.
2. Week rollup displays and does not reset on short idle periods.
3. Existing TPM/RPM/Total still updates.
4. Debug tab remains responsive while debug logs stream.
5. New labels and Python-visible messages remain provider-generic and ASCII-safe.
