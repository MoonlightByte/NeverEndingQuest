"""T065 validation: Test gpt-5.2 at varying reasoning_effort levels.

Tests whether gpt-5.2 produces correct validation output (valid=true for
a known-good DM response) at different reasoning_effort settings.

Result: reasoning_effort="none" produces 100% false negatives (0/15 correct).
        reasoning_effort="low" produces 100% correct (9/9).
        Temperature is irrelevant -- failure is in reasoning capacity.

Usage:
    python tests/model_validation/test_t065_gpt52_reasoning.py
"""
import json
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from openai import OpenAI
import config

client = OpenAI(api_key=config.OPENAI_API_KEY)

# Load prompt from T065 capture entry 7
d = json.load(open("model_captures/T065.json"))
messages = d[7]["input"]["messages"]

# Test configurations
tests = [
    {"reasoning_effort": "none", "temperatures": [0.0, 0.1, 0.3], "runs": 3},
    {"reasoning_effort": "low", "temperatures": [None], "runs": 3},  # temp stripped by API
]

for test in tests:
    effort = test["reasoning_effort"]
    for temp in test["temperatures"]:
        for run in range(test["runs"]):
            start = time.time()
            kwargs = {
                "model": "gpt-5.2",
                "messages": messages,
                "reasoning_effort": effort,
                "response_format": {"type": "json_object"},
            }
            if temp is not None:
                kwargs["temperature"] = temp

            response = client.chat.completions.create(**kwargs)
            latency = round(time.time() - start, 2)
            content = response.choices[0].message.content
            parsed = json.loads(content)
            valid = parsed.get("valid", "?")
            reason = parsed.get("reason", "")[:100]
            usage = response.usage

            temp_str = f"temp={temp}" if temp is not None else "temp=N/A"
            print(f"effort={effort} {temp_str} run={run+1} | {latency}s | valid={valid} | "
                  f"in={usage.prompt_tokens} out={usage.completion_tokens} | reason={reason}")
        print("-" * 90)
