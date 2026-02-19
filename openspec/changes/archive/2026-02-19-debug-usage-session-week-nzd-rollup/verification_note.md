## Verification Note (2026-02-19)

### Commands Run
- `python3 -m py_compile utils/llm_usage_tracker.py utils/openai_usage_tracker.py web/web_interface.py`
- `python3 scripts/test_usage_rollups_debug_tab.py` (8/8 passed)
- Headless socket smoke against local server using `.venv/bin/python` + `python-socketio` client
- HTTP fetch smoke of `http://127.0.0.1:8357` for rendered Debug tab markup checks

### Manual Checklist Outcomes (7.3.x)
- `7.3.1` Session tokens/cost increase during play -> **PARTIAL**
  - Session counters and costs were present and non-zero in live `token_update` events.
  - Single headless `user_input` did not trigger a new LLM generation in this run, so no delta was observed during the short smoke window.
  - Regression suite validates increment logic and source tracking behavior.
- `7.3.2` Week values stable across short idle periods -> **PASS**
  - `week_tokens` remained stable across repeated `token_update` events.
- `7.3.3` Existing TPM/RPM/Total row still updates -> **PASS**
  - Legacy keys (`tpm`, `rpm`, `total_tokens`) were present in every `token_update` payload.
- `7.3.4` No OpenAI-specific wording in new rollup labels -> **PASS**
  - Rendered rollup section and handlers use provider-generic labels/fields.

### Live Payload Contract Check
- `token_update` included all required fields:
  - legacy: `tpm`, `rpm`, `total_tokens`
  - session: `session_tokens`, `session_cost_usd`, `session_cost_nzd`, `session_cost_source`, `session_cost_estimate`
  - week: `week_tokens`, `week_cost_usd`, `week_cost_nzd`, `week_cost_source`
  - metadata: `usd_to_nzd_rate`, `cost_estimate`
