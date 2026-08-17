# Module-Builder Model Hand-off Brief (Luna / Terra) — 2026-08-16

What we learned selecting a model for the T026 location-generation callsite, for reuse across the
module-builder callsites. Source: blind 3-reviewer quality eval + real cost/latency capture
(`docs/audits/2026-08-15-t026-model-quality-eval.md`; raw capture was local/ignored
and is not present in this checkout).

## Pricing snapshot

The optimization registry uses the direct official model-page prices fetched on
2026-08-16. These are per 1M tokens:

| Model | Input | Cached in | Output | Notes |
|---|---|---|---|---|
| gpt-5.6-luna | $0.20 | $0.02 | $1.20 | direct model page, fetched 2026-08-16 |
| gpt-5.6-terra | $2.00 | $0.20 | $12.00 | direct model page, fetched 2026-08-16 |
| gpt-5.2 | $1.75 | $0.175 | $14.00 | previous frontier |
| gpt-4.1 (legacy) | $2.00 | — | $8.00 | current prod baseline |

Sol and the unsuffixed `gpt-5.6` alias are excluded from eligibility. Newly
discovered model IDs are also ineligible until explicitly evaluated.

## T026 historical eval results (6 locations/run, real callsite)

The dollar column below is the original 2026-08-15 run record and uses the
pricing then recorded; it is retained as historical evidence, not as the current
projection. Current cost accounting uses the direct model-page snapshot above.
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

**Selected for T026 OpenAI branch: gpt-5.6-luna|high**. It beat the old
gpt-5.2 incumbent in the blind quality review and was materially faster in that
run. The earlier $0.027094 projection used a superseded conservative
snapshot and produced zero module-validation issues.

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
from model_config import get_provider, resolve_callsite_config
provider = get_provider()
cfg = resolve_callsite_config("T0xx", provider, attempt=0)
response = capture_and_fanout("T0xx", api_client.create_completion,
    _request_provider=provider, messages=[...],
    model=cfg["model"], temperature=<fixed>, **{k:v for k,v in cfg.items() if k!="model"})
```
- create_completion is a THIN router (no retry/param injection beyond provider constraints).
- For a NEW structured callsite prefer `execute_structured_stage`/`production_completion_gateway`
  (story_first/execution.py) — bounded correction + strict schema + provider-neutral, `max_attempts=2`.
- lmstudio sends no schema; the prompt is the effective lever. OpenAI strict rejects unknown keys.

## Module-builder callsite status

- T022-T025 and T027-T038: Luna-none, except T026 on Luna-high.
- Story-first: T098 Luna-none, T099 Terra-low, T100 Luna-none, T101 Luna-low,
  T102 Luna-none, T103 Luna-none.
- T104: enabled and Luna-none. A complete classic build exercised it on the
  recurring Kira Vale identity and published with zero validation issues. The
  final evaluated context has one `kira_vale` with appearances at
  `BGF001/A01` and `EAE001/B01`.
- Mainline's 120-second T104 timeout remains intact after the rebase. Timeout,
  failure, malformed output, or unusable local-model output is a heal-forward
  no-op and cannot block module publication.
- Each callsite retains its own binding; this is not an alias-based blanket swap.

## Before/after projection from live build frequencies

The seven observed story-first stage calls project from $0.155699 and 101.577
seconds of serial model time on the incumbents to $0.026564 and 45.903 seconds
on the selected bindings. The complete build published with zero validation
issues. T099 accounts for most of the selected cost because Terra is 10x Luna,
but Luna none/low failed that stage's semantic gates.

The 27 observed classic-builder calls project from $0.333929 and 331.298 seconds
of serial model time to $0.041894 and 198.792 seconds. T026 is unchanged at
Luna-high in both sides of that comparison; T104 is compared against its
Luna-high incumbent.

The final exact enabled T104 comparison used 6,334 prompt tokens. Luna-none
completed in 5.128 seconds with 802 output tokens for $0.002229. Terra-none took
13.708 seconds and cost $0.040100; the Luna-high incumbent took 42.148 seconds
and cost $0.009561. T026 remains the main creative-generation latency component.
The older whole-build table is superseded because it assumed only T026 changed
and therefore cannot project the new 76-callsite registry.

## Availability check

`GET /v1/models` confirmed both explicit eligible IDs on 2026-08-16:
`gpt-5.6-luna` (created 2026-06-23 15:30:58 UTC) and
`gpt-5.6-terra` (created 2026-06-23 15:27:39 UTC). Availability alone does not
promote either model to a callsite.
