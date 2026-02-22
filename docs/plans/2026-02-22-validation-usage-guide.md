# Multi-Model Capture Validation System - Usage Guide

## Quick Start

### Initial Setup (One-Time)

Generate validators for all 95 API callsites:

```bash
cd /mnt/c/dungeon_master_v1_testing
python tools/discover_validators.py
```

Expected output:
- `validators/task_T001.py` through `validators/task_T095.py` created
- Progress messages showing completion: "Generated 95/95 validators"

### Running Analysis

After playing the game and collecting capture data:

```bash
# Analyze all captures
python tools/analyze_captures.py

# Analyze specific tasks
python tools/analyze_captures.py --tasks T079,T082

# Generate only HTML report
python tools/analyze_captures.py --format html

# Generate only JSON reports
python tools/analyze_captures.py --format json
```

### Viewing Results

**HTML Dashboard:**
Open `reports/validation_summary.html` in a browser for interactive overview.

**JSON Summary:**
Read `reports/validation_summary.json` for machine-readable summary.

**Detailed Per-Task Reports:**
Drill into `reports/details/T079_validation.json` for specific task analysis.

## Command Reference

### discover_validators.py

```bash
# Generate all validators
python tools/discover_validators.py

# Generate specific validators
python tools/discover_validators.py --tasks T079,T082,T067

# Retry failed validators from previous run
python tools/discover_validators.py --retry-failed

# Specify custom inventory location
python tools/discover_validators.py --inventory /path/to/inventory.json
```

### analyze_captures.py

```bash
# Analyze all captures with both HTML and JSON reports
python tools/analyze_captures.py

# Analyze specific tasks
python tools/analyze_captures.py --tasks T079,T082

# Generate only HTML report
python tools/analyze_captures.py --format html

# Generate only JSON reports
python tools/analyze_captures.py --format json

# Specify custom directories
python tools/analyze_captures.py --capture-dir /path/to/captures --output-dir /path/to/reports
```

## Report Structure

### HTML Dashboard

Shows:
- Total tasks analyzed
- Total captures processed
- Overall pass/fail rates
- API error counts
- Per-task drill-down links

### JSON Summary (validation_summary.json)

```json
{
  "generated_at": "2026-02-22T10:30:00",
  "total_tasks": 95,
  "total_captures": 285,
  "total_variants": 4275,
  "variants_passed": 4100,
  "variants_failed": 133,
  "api_errors": 42,
  "tasks": [...]
}
```

### Detailed Task Report (details/T079_validation.json)

```json
{
  "task_id": "T079",
  "total_captures": 3,
  "captures": [
    {
      "timestamp": "2026-02-22T07:44:52Z",
      "baseline": {
        "validation": {"valid": true, "checks": {...}}
      },
      "variants": {
        "gpt-5-mini|minimal": {
          "latency_s": 1.502,
          "validation": {
            "valid": true,
            "matches_baseline": true,
            "errors": [],
            "warnings": []
          }
        }
      }
    }
  ]
}
```

## Workflow Examples

### Example 1: Initial Validation Run

```bash
# 1. Generate validators (first time only)
python tools/discover_validators.py

# 2. Play game to collect captures
python run_web.py
# ... interact with game ...

# 3. Run analysis
python tools/analyze_captures.py

# 4. View results
open reports/validation_summary.html
```

### Example 2: Investigating Failures

```bash
# 1. Identify failing task from HTML dashboard (e.g., T079)

# 2. Read detailed report
cat reports/details/T079_validation.json

# 3. Check specific variant output
python -c "
import json
with open('reports/details/T079_validation.json') as f:
    data = json.load(f)
    variant = data['captures'][0]['variants']['gemini-3-flash|high']
    print(variant['validation']['errors'])
"

# 4. Re-run analysis for just this task
python tools/analyze_captures.py --tasks T079
```

### Example 3: Regenerating Validators After Code Changes

```bash
# 1. Make code changes to API callsite

# 2. Regenerate affected validators
python tools/discover_validators.py --tasks T079,T082

# 3. Re-run analysis
python tools/analyze_captures.py --tasks T079,T082

# 4. Compare results
open reports/validation_summary.html
```

## Troubleshooting

### No validators found

**Error:** `No validator found for T079`

**Solution:**
```bash
python tools/discover_validators.py --tasks T079
```

### Import errors

**Error:** `ImportError: cannot import name 'task_T079'`

**Solution:** Regenerate validators and check `validators/__init__.py` is updated.

### Malformed captures

**Error:** `Failed to parse T079.json`

**Solution:** Check capture file is valid JSON. Delete corrupt file and recapture.

### Missing capture files

**Warning:** `No capture file found: T079.json`

**Solution:** Play game to generate captures for that callsite, or exclude with `--tasks`.

## Testing

Run integration tests:

```bash
python test_validation_system.py
```

Expected: All tests pass or skip gracefully.
