# Module-Builder Model Hand-off Brief (luna / terra / sol) — 2026-08-16

What we learned selecting a model for the T026 location-generation callsite, for reuse across the
module-builder callsites. Source: blind 3-reviewer quality eval + real cost/latency capture
(`docs/audits/2026-08-15-t026-model-quality-eval.md`, raw at `model_eval_captures/t026/2026-08-15/`).

## Pricing (per 1M tokens, short-context standard; from OpenAI model/pricing pages)
| Model | Input | Cached in | Output | Notes |
|---|---|---|---|---|
| gpt-5.6-luna | $0.20 | $0.02 | $1.20 | cheapest by far |
| gpt-5.6-terra | $2.00 | $0.20 | $12.00 | mid |
| gpt-5.6-sol | $5.00 | $0.50 | $30.00 | = Codex's own model (daybreak-blue-latest) |
| gpt-5.2 | $1.75 | $0.175 | $14.00 | previous frontier |
| gpt-4.1 (legacy) | $2.00 | — | $8.00 | current prod baseline |

## T026 eval results (6 locations/run, real callsite)
Adherence (valid JSON, 6/6 locations, zero encounters): ALL pass. Quality (blind avg /30), latency,
and cost/build:

| Model | Quality /30 | Latency | $/build |
|---|---|---|---|
| sol \| high | 30.0 | 182s | $0.308 |
| sol \| none | 29.3 | 128s | $0.198 |
| terra \| none | 28.7 | 66s | $0.074 |
| **luna \| high** | **28.3** | 58s | **$0.0091** |
| gpt-5.2 \| none | 26.3 | 138s | $0.114 |
| luna \| none | 25.3 | 43s | $0.0065 |
| gpt-4.1 | 18.3 | 20-25s | $0.030 |

**Selected for T026 OpenAI branch: gpt-5.6-luna|high** (`DM_MAIN_T026_GPT56LUNA_HIGH` in
model_config.py). Beats the old gpt-5.2 on quality at ~1/12th the cost and ~2.4x faster. gpt-4.1 is
fastest but worst quality (terse == under-built: empty doors, "use Ghost statblock" shorthand).

## Model-parameter rules (important for calls)
- `reasoning_effort="none"` = cheapest/fastest for 5.x; higher effort raises quality (luna none 25.3 ->
  high 28.3). Effort ladder: none < low < medium < high < xhigh.
- **HIGH effort requires temperature = default (1).** These models return HTTP 400 on temperature=0.8
  at high effort. BUT `create_completion._enforce_provider_constraints` (api_client.py:390-392)
  STRIPS temperature automatically for gpt-5.x (non-mini) at reasoning>none — so callsites pass
  temperature uniformly and the router handles it. Do NOT add callsite-level temperature gating (I
  tried; reverted it as redundant, commit dbc93723).
- gpt-5-mini NEVER supports temperature; gpt-5.4-mini only with reasoning=none (both handled centrally
  by _enforce_provider_constraints).
- OpenAI strict `json_schema` NOW accepts `maxItems:0` (the old "strict rejects maxItems" note is stale
  for 5.2+). Verified live.

## Call pattern (all module-builder callsites)
```python
from model_config import MODEL_PROVIDER
if MODEL_PROVIDER == "openai":   cfg = config.<TASK>_<MODEL>_<EFFORT>
elif MODEL_PROVIDER == "gemini": cfg = config.<TASK>_GEMINI_...
elif MODEL_PROVIDER == "lmstudio": cfg = config.<TASK>_LMSTUDIO   # sends NO schema (response_format=None)
else:                            cfg = config.<TASK>_LEGACY
response = capture_and_fanout("T0xx", api_client.create_completion,
    _request_provider=MODEL_PROVIDER, messages=[...],
    model=cfg["model"], temperature=<fixed>, **{k:v for k,v in cfg.items() if k!="model"})
```
- create_completion is a THIN router (no retry/param injection beyond provider constraints).
- For a NEW structured callsite prefer `execute_structured_stage`/`production_completion_gateway`
  (story_first/execution.py) — bounded correction + strict schema + provider-neutral, `max_attempts=2`.
- lmstudio sends no schema; the prompt is the effective lever. OpenAI strict rejects unknown keys.

## Module-builder callsite status
- T026 (location generation): OpenAI -> gpt-5.6-luna|high (changed from gpt-5.2). Others per provider.
- T028 (unify_plots): OpenAI still `DM_MAIN_GPT52_NONE`. Candidate to re-eval on luna|high if desired.
- Other DM_MAIN callsites: still gpt-5.2|none; not separately evaluated. Per-callsite doctrine: eval +
  select individually; each callsite names its own config, no blanket swap.

## Available model IDs on this key
gpt-5.2, gpt-5.4(+mini/nano/pro), gpt-5.5(+pro), gpt-5.6-luna, gpt-5.6-terra, gpt-5.6-sol, gpt-5.6-cyber.
