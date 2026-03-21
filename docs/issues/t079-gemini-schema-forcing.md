# T079: Gemini Needs response_schema for Character Updates

**Status:** Open
**Callsite:** T079 (updates/update_character_info.py:1455)
**Priority:** Medium -- blocks Gemini provider support for this callsite

## Problem

Gemini flash models output the wrong JSON structure for character updates. With
`response_mime_type="application/json"` alone, they produce DM narration JSON
(`{"narration": "..."}`) instead of character update deltas (`{"equipment": [...]}`).

Testing with `response_schema` (passing the expected schema structure) fixes the
format issue -- Gemini outputs the correct structure. But values are still sometimes
wrong (e.g., quantity:1 instead of quantity:0).

## Root Cause

The Gemini API's `response_mime_type="application/json"` only guarantees valid JSON
output, not a specific JSON structure. Without `response_schema`, Gemini picks whatever
JSON structure it thinks is appropriate based on the prompt -- and it often defaults to
the DM narration schema it's seen in other calls.

## Required Work

1. Create a delta schema for character updates (subset of `schemas/char_schema.json`
   with no required fields) that can be passed as `response_schema`
2. Add `response_schema` handling to `_gemini_completion()` in `core/ai/api_client.py`
3. Store the schema in the Gemini config dict for T079:
   ```python
   T079_GEMINI = {"model": "...", "thinking_level": "...", "response_schema": DELTA_SCHEMA}
   ```
4. Collect more capture data (only 5 variant entries currently)

## References

- `schemas/char_schema.json` -- full character schema (43 required fields)
- `updates/update_character_info.py` lines 1140-1425 -- system prompt defines delta format
- Gemini structured output docs: https://ai.google.dev/gemini-api/docs/structured-output
