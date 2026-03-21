# Model Validation Test Scripts

Test scripts for validating model behavior at specific callsites. Each script
replays a captured prompt through different model+param combinations and reports
correctness, latency, and token usage.

These are NOT unit tests -- they make real API calls and cost real money.

## Scripts

| Script | Callsite | What it tests | Key finding |
|---|---|---|---|
| `test_t065_gpt52_reasoning.py` | T065 (validation) | gpt-5.2 at reasoning_effort none vs low, varying temperatures | none=0/15 correct, low=9/9 correct. Temperature irrelevant. |
| `test_t065_gemini_thinking.py` | T065 (validation) | gemini-3-flash and gemini-3.1-flash-lite at thinking=medium | Both correct. 3.1-flash-lite is 5x faster (1.6s vs 9.0s). |
| `test_t065_live_validation.py` | T065 (validation) | Full replay of ALL entries through selected models | gpt-5.2 low=8/12, gemini-3-flash medium=8/12, gpt-5.2 none=0/15 |

## Usage

Run from project root:
```bash
python tests/model_validation/test_t065_gpt52_reasoning.py
python tests/model_validation/test_t065_gemini_thinking.py
python tests/model_validation/test_t065_live_validation.py                        # all models
python tests/model_validation/test_t065_live_validation.py --model gpt52-low      # single model
python tests/model_validation/test_t065_live_validation.py --model gemini-flash-medium
```

Requires:
- `config.py` with OPENAI_API_KEY
- `google_api.pi` with Gemini API key
- `model_captures/T065.json` with capture data

## Adding New Scripts

When testing a new callsite:
1. Create `test_tXXX_[description].py` following the existing pattern
2. Load the prompt from the capture file
3. Run through the candidate models
4. Report correctness + latency per entry
5. Update this README with the new script and its key finding

## Callsite Migration Status

| Callsite | Description | OpenAI Model | Gemini Model | Status |
|---|---|---|---|---|
| T013 | Transition narration | gpt-5-mini (via CALLSITE_MODEL_MAP) | gemini-3.1-flash-lite (via CALLSITE_MODEL_MAP) | Done |
| T067 | Main DM loop | gpt-5.2 none / gpt-5-mini low | gemini-3.1-pro low / gemini-3.1-flash-lite minimal | Done |
| T065 | AI response validation | gpt-5.2 low | gemini-3-flash medium | Done |
| T082 | Action predictor (router) | gpt-5-mini low | gemini-3-flash minimal | Done |
