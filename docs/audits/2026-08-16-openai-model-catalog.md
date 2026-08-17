# OpenAI candidate model catalog — 2026-08-16

The optimization eligibility catalog contains exactly two explicit IDs:

| Model | Efforts supported | Evaluation ceiling | Input / cached / output per 1M | Account availability | Created | Shutdown |
|---|---|---|---|---|---|---|
| `gpt-5.6-luna` | none, low, medium, high, xhigh, max | high | $0.20 / $0.02 / $1.20 | yes | 2026-06-23 15:30:58 UTC | none reported |
| `gpt-5.6-terra` | none, low, medium, high, xhigh, max | high | $2.00 / $0.20 / $12.00 | yes | 2026-06-23 15:27:39 UTC | none reported |

The account results came from [`GET /v1/models`](https://developers.openai.com/api/reference/resources/models).
The endpoint establishes availability and metadata, not price or suitability.
The immutable catalog uses the direct official model-page rates fetched on the
source date. The source URLs are stored with each catalog
entry in `model_registry.py`: [Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
and [Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra).

`gpt-5.6-sol`, the unsuffixed `gpt-5.6` alias, pro variants, `xhigh`, and `max`
are excluded. Discovery never changes eligibility or production bindings.

## Selection state

All 76 callsites now have explicit selections. T017 uses Luna-medium; T026 uses
Luna-high; T065, T083, and T101 use Luna-low; T099 uses Terra-low; T040 retains
GPT-5.4 none; and T046 retains GPT-5.2 none. The other 68 primary bindings use
Luna-none (T097 may retry at Luna low/medium). T104 remains enabled, matching
the reviewed tip, and passed a complete classic build that conserved Kira Vale
as one identity across two areas.

The companion 76-row ledger records each decision and its evidence status.
