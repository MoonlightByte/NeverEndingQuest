# OpenAI callsite optimization: final recommendation

Date: 2026-08-16  
Rebased integration tip: `362996004e4bf26ba9242eaccb8cdbdd715d48e5`  
Decision coverage: 76/76 call IDs

## T104 is enabled and remains enabled

The old plan said to preserve a "default-off" state for T104. That statement
was stale and wrong for the reviewed tip. `config_template.py` sets
`ENABLE_NPC_COHERENCE_REPAIR = True`, so the branch owner's selected behavior
is ON. This change preserves that setting and changes the runtime fallback to
`True`, preventing an older local `config.py` that lacks the new key from
silently turning the feature off.

T104 is the classic module builder's fail-closed NPC-coherence postprocessor.
It runs after T088 when a classic build has repeated NPC occurrences that need
identity reconciliation. Story-first builds use T101 instead. A malformed T104
response leaves the already generated module unchanged rather than aborting
publication.

The rebased mainline also wraps T104 in a hard 120-second timeout. That shipped
guard is preserved: timeout, malformed output, provider failure, and unsupported
local-model output remain heal-forward no-ops over the already reconciled module.
The wrapper does not alter the OpenAI request or the Luna-none selection.

The final exact-request classic acceptance build invoked T104 and published
with zero validation issues. Its final `module_context.json` contains one
`kira_vale` identity with appearances at `BGF001/A01` and `EAE001/B01`. The
exact comparison was:

| Profile | Latency | Prompt + completion | Cost | Result |
|---|---:|---:|---:|---|
| Luna-none | 5.128s | 6,334 + 802 | $0.002229 | Pass; selected |
| Terra-none | 13.708s | 6,334 + 2,286 | $0.040100 | Pass, but 18.0x the cost |
| Luna-high incumbent | 42.148s | 6,334 + 6,912 | $0.009561 | Pass, 8.2x slower and 4.3x dearer |

T104 therefore stays enabled and moves from Luna-high to Luna-none.

## Recommendation

The canonical production registry contains an explicit decision for every ID:

- 68 callsites: Luna-none.
- T065, T083, and T101: Luna-low.
- T017: Luna-medium.
- T026: Luna-high.
- T099: Terra-low.
- T040: retain `gpt-5.4` none.
- T046: retain `gpt-5.2` none.
- T097 starts at Luna-none and escalates only on its existing bounded retry
  ladder to Luna-low, then Luna-medium.

This distribution is deliberately not a blanket Luna switch. The broad
production-shaped scaffolds overturned several early provisional choices:

- T017: Luna-none passed 1/6 source-aware compression cases; Luna-medium passed
  6/6, beat the incumbent's 5/6, and was much faster than the incumbent.
- T040: the incumbent passed 4/4 broad combat-referee cases. No Luna or Terra
  profile through high matched that result, so it stays on `gpt-5.4` none.
- T046: both Terra-none and the incumbent passed 4/4 initiative cases. Terra
  was only about 0.12s faster and offered no material accepted-result saving,
  so the incumbent remains.
- T065: Luna-low passed 11/13 full validation cases versus 7/13 for both
  Luna-none and the incumbent. Luna-low was also faster than the incumbent.
- T083: Luna-none changed an explicitly supplied Beast into a Monstrosity.
  Luna-low preserved all four expected taxonomy values.
- T099: Luna-none and Luna-low failed the story-first area-binding semantic
  gates. Terra-low passed the graph, reachability, reciprocity, schema, compile,
  and map checks.
- T101: Luna-none left a duplicate NPC placement; Luna-low conserved identity
  and removed the duplicate.

## Pricing and speed rule

Official prices recorded on 2026-08-16 are:

| Model | Input / 1M | Cached input / 1M | Output / 1M |
|---|---:|---:|---:|
| GPT-5.6 Luna | $0.20 | $0.02 | $1.20 |
| GPT-5.6 Terra | $2.00 | $0.20 | $12.00 |

Terra is 10x Luna at equal token counts. Luna-none wins whenever it clears the
same production contract because it normally reduces both latency and accepted-
result cost. More effort, Terra, or an incumbent is selected only where the
observed quality/retry evidence requires it. Sol and the unsuffixed `gpt-5.6`
alias are excluded.

Examples from exact current requests:

- T013: Luna-none 1.848s / $0.000539 versus incumbent 9.242s / $0.001625.
- T049 storage extraction: Luna-none 1.366-2.340s / $0.000390 or less versus
  incumbent 5.515-7.141s / $0.001130 or more; both operations passed.
- T053 batched validation: Luna-none 2.135s / $0.001700 versus incumbent
  2.942s / $0.015281, with the same authoritative no-change result.
- T086 NPC level-up: Luna-none 1.318s / $0.000993 versus incumbent 1.892s /
  $0.009513, with the required state delta validated.

Observed-frequency projections use the exact number of calls made by the
headless/build runs and sum model request time (not total wall time):

| Workload | Calls | Before cost / model time | Selected cost / model time | Change |
|---|---:|---:|---:|---:|
| Paired ordinary-play slice | 30 | $0.154319 / 124.203s | $0.033590 / 81.519s | 78.2% cheaper, 34.4% less model time |
| Classic build slice | 27 | $0.333929 / 331.298s | $0.041894 / 198.792s | 87.5% cheaper, 40.0% less model time |
| Story-first build | 7 | $0.155699 / 101.577s | $0.026564 / 45.903s | 82.9% cheaper, 54.8% less model time |

The ordinary-play projection stops at the last identical paired turn; later
candidate/incumbent scripts diverged, so their unmatched calls are not mixed
into the comparison. The classic projection keeps T026 on Luna-high because
that is both its incumbent and final selection, and compares T104 against its
Luna-high incumbent. These are workload samples, not a promise that every game
session has the same call frequency.

## What was implemented

- An immutable eligible-model catalog containing explicit Luna and Terra IDs,
  supported efforts, availability metadata, official prices, and source dates.
- One canonical 76-ID binding registry with startup validation for missing or
  duplicate IDs, unknown profiles, unsupported effort, and malformed retry
  ladders. T024 alone is marked dormant because its helper is unreferenced.
- A detached `(task_id, provider, attempt)` resolver. Compatibility aliases
  remain while callers transition.
- Production selection and capture selection now come from the same registry.
  Prompts, schemas, response formats, callsite temperatures, and token ceilings
  remain callsite-owned and unchanged.
- Provider isolation remains intact: Gemini, LM Studio, and legacy selections
  do not inherit OpenAI model or reasoning fields.
- Exact request capture records source fingerprints, token use, latency, cost,
  and incumbent/candidate outputs. Raw prompts and responses remain ignored and
  outside Git.

## Headless acceptance results

Real headless play and production builders were used, with results judged from
files rather than narration:

- Final exact-request classic build (`Final_Classic_Evidence`): published two
  areas and four locations with zero validation issues; enabled T104 ran.
- Final exact-request story-first build (`Final_Story_Evidence`): published two
  areas, four locations, two compiled creatures, and zero validation issues;
  T099 and T101 also received their focused semantic/compile comparisons.
- Agentic combat: identical-state Luna-none T067 entered combat after one
  validation retry, matching the incumbent; encounter state persisted.
- Level-up: Lux advanced from Wizard 1 to 2; disk shows max HP 55, XP 300,
  next threshold 900, School of Evocation/Sculpt Spells, Alarm and Burning
  Hands, and three first-level slots. An interrupted interview first proved the
  update is atomic: no partial level-up was saved.
- Save/resume: the disposable game resumed the saved character and module state.
- Module completion/transition: the classic module was archived and summarized,
  campaign completion was recorded, and party state moved to the story-first
  module at `AR001/A01` with character state preserved.

The transition also exposed a pre-existing state-context defect that is not a
model-selection win: after the party tracker moved to the new module, the
validator continued using the old module's A01 name. It rejected correct Luna
and incumbent responses, and the accepted narration eventually repeated the
old name even though the authoritative party tracker correctly says Moonfall
Starting Square. The campaign file also retained the old `currentModule` while
the party tracker contained the new one. This must be fixed separately; it is
not hidden as a successful truthfulness gate.

Likewise, a storage command in paired headless play left an item in character
equipment instead of creating storage. The same disk-state failure occurred for
candidate and incumbent and belongs to the T109/storage reconciliation path,
not to the T049 extraction comparison. T049 itself passed two production calls.

T039 has an existing prompt/consumer mismatch: its prompt does not state that
four fields must be objects, so both Luna-none and the incumbent returned arrays
and code used the same safe local fallback. Luna reached the accepted fallback
in 1.615s versus 15.638s on the focused case. The recommendation is Luna-none,
but the raw provider contract is recorded as a shared failure, not a pass.

## Evidence locations

The per-ID rationale, incumbent, tested candidates, retries, cost/latency, and
evidence class are in
`docs/audits/2026-08-16-openai-callsite-evaluation-ledger.md`. Pricing and model
availability are in `docs/audits/2026-08-16-openai-model-catalog.md`. Raw local
evidence is ignored under `model_eval_captures/openai-callsite-optimization/`.

The repository-referenced
`validation_evidence/headless_acceptance/run_acceptance.py` is absent from this
checkout. Acceptance therefore drove the unmodified `core/headless/client.py`
directly; it did not monkeypatch gameplay functions. Verification also ran
`python -m pytest -q tests` (44 passed), Python compilation of all changed
runtime modules, registry/source inventory checks (76/76, with T078's two live
implementations intentional), provider-resolution checks, and `git diff
--check`.

## Layman summary

T104 was not supposed to be turned off. The branch says it is on, so it remains
on. I ran it in a real module build and found that the cheapest Luna setting
does the job correctly and costs far less than Terra.

For most calls, use Luna with no extra thinking: it is usually fastest and is
one tenth Terra's price. A few calls genuinely need more care, so T017 uses
Luna-medium; T065, T083, and T101 use Luna-low; T026 stays Luna-high; and T099
uses Terra-low. Do not change T040 or T046 because the proposed replacements did
not beat their current models without losing confidence. Every one of the 76
call IDs has an explicit recommendation in the ledger.
