# T026 Location Generation — Model Quality + Cost/Latency Evaluation (2026-08-15)

> Pricing note (2026-08-16): dollar figures below are the historical run record.
> The canonical catalog now uses the direct official model-page snapshot of Luna
> $0.20/$0.02/$1.20 and Terra $2.00/$0.20/$12.00 per 1M input/cached/output
> tokens. Historical quality and latency results remain valid; historical cost
> ratios must not be used as current projections.

Blind, three-reviewer quality evaluation of the T026 location-batch generator across
OpenAI models and reasoning-effort settings, run through the **new generation-schema**
strict wiring (`schemas/loca_generation_schema.json`). All raw outputs, the shared input,
and the de-anonymization key were written to the ignored local path
`model_eval_captures/t026/2026-08-15/`. Those raw artifacts are not present in
this checkout; the reviewed aggregate evidence below is retained.

## Method
- One location batch (6 rooms, area HWG001 "Haunted Watchtower") generated per variant.
- Every variant constrained by the clean generation schema (encounters stripped to empty-only).
- Adherence gate first (valid JSON, 6/6 locations, **zero** encounters authored, validates
  against the runtime `loca_schema.json`). **All 7 variants PASS adherence.**
- Quality judged by **3 independent blind reviewers** (general-purpose agents) who saw only
  anonymized outputs A-G + the task — never the model identities. 6 criteria, 1-5 each
  (richness, DM-usability, coherence, encounter/content design, playability, polish); /30.

## Results (de-anonymized)

| Rank | Model | Effort | R1/R2/R3 | Avg /30 | Latency | Out tok | $/build |
|---|---|---|---|---|---|---|---|
| 1 | gpt-5.6-sol | high | 30/30/30 | **30.0** | 182.5s | 9,980 | $0.3083 |
| 2 | gpt-5.6-sol | none | 29/30/29 | 29.3 | 127.7s | 6,317 | $0.1984 |
| 3 | gpt-5.6-terra | none | 27/30/29 | 28.7 | 66.6s | 5,869 | $0.0740 |
| 4 | **gpt-5.6-luna** | **high** | 28/29/28 | **28.3** | 58.6s | 7,254 | **$0.0091** |
| 5 | gpt-5.2 *(current)* | none | 27/24/28 | 26.3 | 138.2s | 7,924 | $0.1140 |
| 6 | gpt-5.6-luna | none | 25/25/26 | 25.3 | 43.6s | 5,134 | $0.0065 |
| 7 | gpt-4.1 *(legacy)* | n/a | 18/17/20 | 18.3 | 24.9s | 3,323 | $0.0301 |

## Findings

**1. gpt-4.1 is the worst quality by a wide margin (18.3/30).** Answers the terseness
question directly: 4.1 is fastest + cheap, but its brevity is *under-built*, not efficient —
`"doors": []` empty in 4 of 6 rooms, vague loot ("a relic or clue"), non-actionable
dmInstructions ("there is a chance it animates"), and generation shorthand left in monster
names (`"Restless Spirit (use Ghost statblock)"`). **Thin here = worse.** All three reviewers
independently ranked it last.

**2. The current choice, gpt-5.2|none, ranked 5th of 7 (26.3).** It is beaten on quality by
terra|none, luna|high, and both sol settings — while also being the 2nd-slowest (138s) and
2nd-most-expensive. It carries a real content defect: it left the climactic antagonist
*undefined* ("choose a suitable entity for your campaign") — scaffolding at the centerpiece —
plus non-ASCII smart quotes and the longest, hardest-to-parse dmInstructions. Weak on all three axes.

**3. Owner's high-effort-luna hypothesis is CONFIRMED.** luna|high (28.3) **beats the current
gpt-5.2 (26.3)** on quality and was **2.4x faster** (58.6s vs 138.2s). Under the
prices recorded for this historical run it was 1/12th the cost ($0.0091 vs
$0.1140); see the pricing note above for current projections. Effort clearly
lifts luna: none=25.3 -> high=28.3 (+3.0).

**4. sol is the quality ceiling** (none 29.3, high 30.0) but 20-34x the cost of luna|high.

**5. terse != worse as a rule.** luna|none (G) is tight-but-complete (proper trap DCs, named
loot) — reviewers called its brevity "efficient." Only gpt-4.1's terseness was "under-built."

**6. ASCII violations (cross-cutting, stochastic):** this run, gpt-4.1, terra, gpt-5.2, and
luna|high emitted non-ASCII smart quotes/em-dashes; sol (both) and luna|none were ASCII-clean.
This is per-run stochastic, not a clean model discriminator, but it confirms a **sanitization
pass is needed regardless of model** (Windows cp1252 crash risk). Verify the downstream
encoding_utils path catches generation output.

## Wiring implications
- **High reasoning effort requires `temperature=1` (default).** These models reject
  temperature=0.8 at high effort. The T026 callsite hardcodes `temperature=0.8`, so any
  high-effort selection (luna|high, sol|high) must DROP the temperature override on that branch.

## Recommendation
For the OpenAI T026 branch, **replace gpt-5.2|none with gpt-5.6-luna|high**:
higher quality than the incumbent and 2.4x faster in this paired sample. Current
production eligibility excludes Sol and uses the conservative pricing catalog.

## Caveat
N=1 generation per variant (a quality sample, per the "run 1" scope). The 3-reviewer consensus
is strong and the cost/quality gaps are large, but before finalizing the production binding,
The later 2026-08-16 complete classic and story-first builds retained Luna-high
and published with zero validation issues. Sol is no longer an eligible candidate.
