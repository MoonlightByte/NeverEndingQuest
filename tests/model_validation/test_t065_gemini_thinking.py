"""T065 validation: Test Gemini models at varying thinking_level settings.

Tests whether gemini-3-flash and gemini-3.1-flash-lite produce correct
validation output (valid=true for a known-good DM response).

Result: Both models produce 100% correct output at thinking_level="medium".
        gemini-3.1-flash-lite is dramatically faster (1.6s vs 9.0s avg).

Usage:
    python tests/model_validation/test_t065_gemini_thinking.py
"""
import json
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Load Gemini API key
api_key_file = "google_api.pi"
if os.path.exists(api_key_file):
    with open(api_key_file, "r") as f:
        content = f.read().strip()
        if "api_key=" in content:
            api_key = content.split("api_key=")[1].strip()
        else:
            api_key = content
    os.environ["GEMINI_API_KEY"] = api_key

from google import genai
from google.genai import types

client = genai.Client()

# Load prompt from T065 capture entry 7
d = json.load(open("model_captures/T065.json"))
entry = d[7]
messages = entry["input"]["messages"]

# Convert to Gemini format
system_parts = []
contents = []
for m in messages:
    role = m.get("role", "")
    content = m.get("content", "")
    if role == "system":
        system_parts.append(content)
    elif role == "user":
        contents.append(types.Content(role="user", parts=[types.Part(text=content)]))
    elif role == "assistant":
        contents.append(types.Content(role="model", parts=[types.Part(text=content)]))

system_instruction = "\n\n".join(system_parts) if system_parts else None

# Test configurations
models = [
    "gemini-3-flash-preview",
    "gemini-3.1-flash-lite-preview",
]
thinking_level = "medium"
runs = 3

for model_name in models:
    print(f"\nTesting {model_name} | thinking_level={thinking_level} | {runs} runs")
    print("=" * 90)

    for run in range(runs):
        start = time.time()
        config_kwargs = {
            "thinking_config": types.ThinkingConfig(thinking_level=thinking_level),
            "response_mime_type": "application/json",
        }
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction

        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=types.GenerateContentConfig(**config_kwargs),
        )
        latency = round(time.time() - start, 2)
        content_text = response.text
        usage = getattr(response, "usage_metadata", None)
        in_tok = getattr(usage, "prompt_token_count", "?") if usage else "?"
        out_tok = getattr(usage, "candidates_token_count", "?") if usage else "?"

        try:
            parsed = json.loads(content_text)
            valid = parsed.get("valid", "?")
            reason = parsed.get("reason", "")[:120]
        except json.JSONDecodeError:
            valid = "PARSE_ERROR"
            reason = content_text[:120]

        print(f"run={run+1} | {latency}s | valid={valid} | in={in_tok} out={out_tok} | reason={reason}")
    print("-" * 90)
