"""T017 combat compression: Test models on plain text tag compression.

Replays captured combat inputs through candidate models and validates
output format (@T=CS/v2 prefix, no JSON wrapping, no narration).

CRITICAL: This callsite outputs plain text tags, NOT JSON. Models must
NOT have JSON mode enabled (response_format=None).

Results (6 entries, v5 prompt):
    gpt-4.1-mini baseline:        6/6 correct, 3.2s avg (being sunset)
    gpt-5-mini|low:               5/6 correct, 15.5s avg (entry 4 @ROUND cosmetic)
    gemini-3-flash|low (no JSON): 6/6 correct, 2.0s avg (fastest, stable)
    gpt-5-mini|minimal:           4/6 correct, 4.5s avg
    gpt-5-mini|medium:            0/6 correct, 44.7s avg (worse with more reasoning)

Usage:
    python tests/model_validation/test_t017_compression.py
    python tests/model_validation/test_t017_compression.py --model gpt5mini-low
    python tests/model_validation/test_t017_compression.py --model gemini-flash-low
"""
import json
import time
import sys
import os
import argparse
import importlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def run_gpt5mini(messages, reasoning_effort):
    from openai import OpenAI
    import config
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=messages,
        reasoning_effort=reasoning_effort,
        # NO temperature -- stripped for mini
    )
    return response.choices[0].message.content


def run_gemini_flash(messages, thinking_level):
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
    system_parts = []
    contents = []
    for m in messages:
        role = m.get("role", "")
        c = m.get("content", "")
        if role == "system":
            system_parts.append(c)
        elif role == "user":
            contents.append(types.Content(role="user", parts=[types.Part(text=c)]))

    system_instruction = "\n\n".join(system_parts) if system_parts else None
    config_kwargs = {
        "thinking_config": types.ThinkingConfig(thinking_level=thinking_level),
        # NO response_mime_type -- plain text output
    }
    if system_instruction:
        config_kwargs["system_instruction"] = system_instruction

    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=contents,
        config=types.GenerateContentConfig(**config_kwargs),
    )
    return response.text


def run_baseline(messages):
    from openai import OpenAI
    import config
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model="gpt-4.1-mini-2025-04-14",
        messages=messages,
        temperature=0.3,
    )
    return response.choices[0].message.content


def main():
    parser = argparse.ArgumentParser(description="T017 compression test")
    parser.add_argument("--model", choices=["baseline", "gpt5mini-low", "gpt5mini-minimal",
                                            "gemini-flash-low", "gemini-flash-minimal", "all"],
                        default="all", help="Which model to test")
    args = parser.parse_args()

    # Load system prompt from the module
    import core.ai.combat_compression_engine as cce
    importlib.reload(cce)
    system_prompt = cce.COMBAT_COMPRESSION_PROMPT

    d = json.load(open("model_captures/T017.json"))
    print(f"T017: {len(d)} entries")

    models = {
        "baseline": ("gpt-4.1-mini baseline", lambda msgs: run_baseline(msgs)),
        "gpt5mini-low": ("gpt-5-mini|low", lambda msgs: run_gpt5mini(msgs, "low")),
        "gpt5mini-minimal": ("gpt-5-mini|minimal", lambda msgs: run_gpt5mini(msgs, "minimal")),
        "gemini-flash-low": ("gemini-3-flash|low (no JSON)", lambda msgs: run_gemini_flash(msgs, "low")),
        "gemini-flash-minimal": ("gemini-3-flash|minimal (no JSON)", lambda msgs: run_gemini_flash(msgs, "minimal")),
    }

    if args.model == "all":
        to_test = models
    else:
        to_test = {args.model: models[args.model]}

    for model_key, (label, fn) in to_test.items():
        print(f"\n{'=' * 80}")
        print(f"Testing: {label}")
        print(f"{'=' * 80}")

        correct = 0
        total = 0

        for i in range(len(d)):
            user_content = d[i]["input"]["messages"][1]["content"]
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ]

            start = time.time()
            try:
                output = fn(messages)
                latency = round(time.time() - start, 2)
                total += 1

                has_tag = output.strip().startswith("@T=CS/v2")
                has_json = output.strip().startswith("{") or output.strip().startswith("[")
                has_narration = '"narration"' in output

                if has_tag and not has_json and not has_narration:
                    correct += 1
                    status = "OK"
                elif has_json:
                    status = "JSON_WRAP"
                elif has_narration:
                    status = "NARRATION"
                else:
                    status = "BAD_FORMAT"

                first_line = output.strip().split("\n")[0][:60]
                print(f"  E[{i}] {latency}s | {status} | {first_line}")
            except Exception as e:
                total += 1
                print(f"  E[{i}] ERROR: {str(e)[:80]}")

        print(f"\n  RESULT: {correct}/{total} correct")


if __name__ == "__main__":
    main()
