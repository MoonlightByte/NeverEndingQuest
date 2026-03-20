# Capture Analysis Report Template

**Purpose:** Standardized format for per-callsite model comparison reports. Used after
running `tools/capture_quality_reviewer.py` across multiple entries and collecting cost data.

---

## Report Structure

### Header

```
## T0XX: [Callsite Description] -- Combined Report ([N] entries)

**File:** `path/to/file.py:LINE`
**Model Variable:** `CONFIG_VARIABLE_NAME`
**Legacy Model:** `gpt-4.1-2025-04-14` or `gpt-4.1-mini-2025-04-14`
**Temperature:** [value from callsite]
**Tier:** full or mini
```

### Combined Grid

Every report must include ALL of these columns:

| Column | Description |
|---|---|
| Rank | Sorted by quality avg descending |
| Model | Model variant label from capture config |
| Quality Avg | Average of GPT reviewer Overall scores across all entries (1-5 scale) |
| Correct | X/Y where X = entries the model produced a correct output, Y = total number of test runs (always the full count, never a subset). Determined by live testing (replaying captured prompts through the model) or GPT reviewer analysis. The denominator is ALWAYS the number of actual test executions, not a sample. |
| Avg Cost | Average USD cost per call across entries |
| Avg Latency | Average seconds per call across entries |
| vs Baseline | Percentage cost difference vs the legacy baseline model |
| Notes | Key observations -- failure modes, strengths, patterns |

### Example Row

```
| 1 | gemini-3-flash|medium | 4.9 | 5/5 | $0.0035 | 6.9s | -73% | Top quality, all correct |
```

### Footer Sections

**Correctness failures:** List every entry where a model produced an incorrect output.
Include the entry number, what the model got wrong, and what the correct answer was.

**Model selection:** After reviewing the grid, identify the recommended model per provider:
- OpenAI full: [model + params]
- OpenAI mini: [model + params] (if applicable)
- Gemini full: [model + params]
- Gemini mini: [model + params] (if applicable)
- Legacy: unchanged

**Rationale:** Brief explanation of why each model was selected, referencing
quality, correctness, cost, and latency tradeoffs.

---

## Rules

1. Correctness is the PRIMARY criterion -- a cheaper/faster model that gives wrong answers is worthless
2. Among correct models, prefer lower cost then lower latency
3. The GPT reviewer determines correctness -- read its per-entry analysis carefully
4. A model scoring 2/5 or below on any entry is flagged as incorrect for that entry
5. A model with any incorrect entries should be flagged with a warning in Notes
6. Temperature stays at the callsite -- do not include it in model selection recommendations
