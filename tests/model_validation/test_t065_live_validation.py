"""T065 validation: Live replay of ALL captured entries through selected models.

Replays every T065 capture entry through each model and reports correctness.
This is the definitive test -- not the GPT reviewer's opinion, but actual
model output on real prompts.

Results (12 entries):
    gpt-5.2 reasoning=low:           8/12 correct (4.9s avg)
    gemini-3-flash thinking=medium:  8/12 correct (9.4s avg)
    gpt-5.2 reasoning=none:          0/15 correct (3.1s avg) -- UNUSABLE

Usage:
    python tests/model_validation/test_t065_live_validation.py
    python tests/model_validation/test_t065_live_validation.py --model gpt52-low
    python tests/model_validation/test_t065_live_validation.py --model gemini-flash-medium
"""
import json
import time
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def run_gpt52(messages, reasoning_effort):
    from openai import OpenAI
    import config
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model="gpt-5.2",
        messages=messages,
        reasoning_effort=reasoning_effort,
        response_format={"type": "json_object"},
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
        elif role == "assistant":
            contents.append(types.Content(role="model", parts=[types.Part(text=c)]))

    system_instruction = "\n\n".join(system_parts) if system_parts else None
    config_kwargs = {
        "thinking_config": types.ThinkingConfig(thinking_level=thinking_level),
        "response_mime_type": "application/json",
    }
    if system_instruction:
        config_kwargs["system_instruction"] = system_instruction

    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=contents,
        config=types.GenerateContentConfig(**config_kwargs),
    )
    return response.text


def main():
    parser = argparse.ArgumentParser(description="T065 live validation replay")
    parser.add_argument("--model", choices=["gpt52-low", "gpt52-none", "gemini-flash-medium", "all"],
                        default="all", help="Which model to test")
    args = parser.parse_args()

    d = json.load(open("model_captures/T065.json"))
    print(f"T065: {len(d)} entries")

    models = {
        "gpt52-low": ("gpt-5.2 reasoning=low", lambda msgs: run_gpt52(msgs, "low")),
        "gpt52-none": ("gpt-5.2 reasoning=none", lambda msgs: run_gpt52(msgs, "none")),
        "gemini-flash-medium": ("gemini-3-flash thinking=medium", lambda msgs: run_gemini_flash(msgs, "medium")),
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
            entry = d[i]
            messages = entry["input"]["messages"]
            if not messages:
                continue

            start = time.time()
            try:
                content = fn(messages)
                latency = round(time.time() - start, 2)
                parsed = json.loads(content)
                valid = parsed.get("valid", "?")
                reason = parsed.get("reason", "")[:100]
                total += 1
                status = "OK" if valid is True else "FAIL"
                if valid is True:
                    correct += 1
                print(f"entry[{i}] | {status} | {latency}s | valid={valid} | reason={reason}")
            except Exception as e:
                latency = round(time.time() - start, 2)
                total += 1
                print(f"entry[{i}] | ERROR | {latency}s | {e}")

        print(f"\nRESULT: {label}: {correct}/{total} correct")


if __name__ == "__main__":
    main()
