"""Qualitative review tool for multi-model capture data.

Sends captured input+outputs to GPT and Gemini independently for qualitative
assessment, then prints both reviews for human assembly.

Usage:
    python tools/capture_quality_reviewer.py T067                    # Review latest entry
    python tools/capture_quality_reviewer.py T067 --entry -1         # Same (latest)
    python tools/capture_quality_reviewer.py T067 --entry 0          # First entry
    python tools/capture_quality_reviewer.py T067 --entry 2          # Third entry
    python tools/capture_quality_reviewer.py T067 --variants "gpt-5.2|effort=none,gemini-3-pro|thinking=low"
    python tools/capture_quality_reviewer.py T067 --source reports    # Use reports/details/ format
    python tools/capture_quality_reviewer.py T067 --source captures   # Use model_captures/ format (default)
"""
import argparse
import json
import os
import sys
import threading

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Review prompt template
# ---------------------------------------------------------------------------

REVIEW_PROMPT = """You are a qualitative reviewer for AI model outputs. You will receive:
1. The ORIGINAL INPUT (system prompts + conversation history + user message) that was sent to multiple AI models
2. The OUTPUTS from each model variant

Your job is to assess EACH output purely on quality, accuracy, and faithfulness to the input instructions.

DO NOT consider speed, cost, or token counts -- those are tracked separately. Focus ONLY on:

## Scoring Criteria (score each 1-5)

1. **Instruction Compliance**: Did the output follow ALL instructions from the system prompt? (JSON format, ASCII-only, action schema, etc.)
2. **Content Accuracy**: Is the narration/content accurate to the game state, character data, location details, and conversation history?
3. **Completeness**: Does the output include everything it should? Are required actions present? Is anything missing?
4. **Narrative Quality**: Is the narration engaging, immersive, and well-written? Does it maintain the right tone and perspective?
5. **Contextual Awareness**: Does the output demonstrate understanding of prior conversation, character state, plot status, and world context?
6. **Schema Correctness**: Are JSON actions properly structured with correct "action" and "parameters" keys? Are parameter values correct?

## Output Format

For EACH variant, provide:

```
### [variant label]
Instruction Compliance: [1-5] - [brief explanation]
Content Accuracy: [1-5] - [brief explanation]
Completeness: [1-5] - [brief explanation]
Narrative Quality: [1-5] - [brief explanation]
Contextual Awareness: [1-5] - [brief explanation]
Schema Correctness: [1-5] - [brief explanation]
Overall: [1-5]
Key Strengths: [bullet points]
Key Weaknesses: [bullet points]
```

After reviewing all variants, provide:

```
### RANKING
1. [label] - Overall [score] - [one-line reason]
2. [label] - Overall [score] - [one-line reason]
...
```

Be specific. Quote actual text from outputs when pointing out strengths or problems.
Do not favor any particular model brand -- judge purely on output quality.
"""


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_from_captures(task_id, entry_index=-1):
    """Load from model_captures/T0xx.json (CaptureFileWriter format)."""
    path = os.path.join("model_captures", f"{task_id}.json")
    if not os.path.exists(path):
        print(f"ERROR: {path} not found")
        sys.exit(1)

    with open(path, 'r', encoding='utf-8') as f:
        records = json.load(f)

    if not records:
        print(f"ERROR: {path} is empty")
        sys.exit(1)

    try:
        record = records[entry_index]
    except IndexError:
        print(f"ERROR: Entry index {entry_index} out of range (file has {len(records)} entries)")
        sys.exit(1)

    print(f"Loaded entry {entry_index} from {path} (timestamp: {record.get('timestamp', 'unknown')})")
    print(f"  Tier: {record.get('tier', 'unknown')}")
    print(f"  Variants: {len(record.get('outputs', {}))} outputs, {len(record.get('errors', {}))} errors")

    return {
        "input": record["input"],
        "outputs": record.get("outputs", {}),
        "errors": record.get("errors", {}),
        "timestamp": record.get("timestamp"),
        "tier": record.get("tier"),
    }


def load_from_reports(task_id, entry_index=-1):
    """Load from reports/details/T0xx_validation.json format."""
    path = os.path.join("reports", "details", f"{task_id}_validation.json")
    if not os.path.exists(path):
        print(f"ERROR: {path} not found")
        sys.exit(1)

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    captures = data.get("captures", [])
    if not captures:
        print(f"ERROR: No captures in {path}")
        sys.exit(1)

    try:
        capture = captures[entry_index]
    except IndexError:
        print(f"ERROR: Entry index {entry_index} out of range (file has {len(captures)} entries)")
        sys.exit(1)

    print(f"Loaded entry {entry_index} from {path} (timestamp: {capture.get('timestamp', 'unknown')})")

    # Convert reports format to unified format
    outputs = {}

    # Baseline
    baseline = capture.get("baseline", {})
    if baseline:
        label = baseline.get("label", "baseline")
        outputs[label] = {"content": baseline.get("output", "")}

    # Variants
    for label, variant_data in capture.get("variants", {}).items():
        outputs[label] = {"content": variant_data.get("output", "")}

    print(f"  Variants: {len(outputs)} outputs")

    return {
        "input": capture.get("input", {}),
        "outputs": outputs,
        "errors": {},
        "timestamp": capture.get("timestamp"),
        "tier": None,
    }


# ---------------------------------------------------------------------------
# Build the review payload
# ---------------------------------------------------------------------------

def build_review_message(data, variant_filter=None):
    """Build the message content for reviewers."""
    input_data = data["input"]
    outputs = data["outputs"]

    # Filter variants if requested
    if variant_filter:
        filter_set = {v.strip() for v in variant_filter.split(",")}
        filtered = {}
        for label, output in outputs.items():
            if label in filter_set or any(f in label for f in filter_set):
                filtered[label] = output
        if not filtered:
            print(f"WARNING: No variants matched filter '{variant_filter}'")
            print(f"  Available: {list(outputs.keys())}")
            sys.exit(1)
        outputs = filtered

    print(f"  Reviewing {len(outputs)} variants: {list(outputs.keys())}")

    # Build the content
    parts = []

    # Input section
    parts.append("=" * 60)
    parts.append("ORIGINAL INPUT (what was sent to all models)")
    parts.append("=" * 60)

    messages = input_data.get("messages", [])
    for i, msg in enumerate(messages):
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        # Truncate very long system prompts for readability but keep enough context
        if role == "system" and len(content) > 3000:
            parts.append(f"\n--- Message {i+1} (role: {role}) [truncated to 3000 chars] ---")
            parts.append(content[:3000] + "\n... [truncated] ...")
        else:
            parts.append(f"\n--- Message {i+1} (role: {role}) ---")
            parts.append(content)

    if "temperature" in input_data:
        parts.append(f"\n[Temperature: {input_data['temperature']}]")

    # Outputs section
    parts.append("\n" + "=" * 60)
    parts.append("MODEL OUTPUTS (review each one)")
    parts.append("=" * 60)

    for label, output_data in outputs.items():
        parts.append(f"\n--- Variant: {label} ---")
        content = output_data.get("content", "")
        if content:
            parts.append(content)
        else:
            parts.append("[NO OUTPUT / EMPTY]")

    # Errors section
    errors = data.get("errors", {})
    if errors:
        parts.append("\n" + "=" * 60)
        parts.append("ERRORS (models that failed)")
        parts.append("=" * 60)
        for label, error in errors.items():
            parts.append(f"\n--- {label} ---")
            parts.append(str(error))

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# API key helpers
# ---------------------------------------------------------------------------

def _get_openai_key():
    """Get OpenAI API key from env or config.py."""
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key
    try:
        import config
        return config.OPENAI_API_KEY
    except (ImportError, AttributeError):
        raise RuntimeError("OPENAI_API_KEY not found in env or config.py")


def _get_gemini_key():
    """Get Gemini API key from env or google_api.pi file."""
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if key:
        return key
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    api_key_file = os.path.join(project_root, "google_api.pi")
    if os.path.exists(api_key_file):
        with open(api_key_file, 'r') as f:
            content = f.read().strip()
            if 'api_key=' in content:
                return content.split('api_key=')[1].strip()
            return content
    raise RuntimeError("Gemini API key not found in env or google_api.pi")


# ---------------------------------------------------------------------------
# API callers
# ---------------------------------------------------------------------------

def call_gpt_review(review_content):
    """Send to GPT for qualitative review. Returns review text."""
    from openai import OpenAI

    client = OpenAI(api_key=_get_openai_key())

    print("\n[GPT] Sending review request...")
    response = client.chat.completions.create(
        model="gpt-5.4",
        messages=[
            {"role": "system", "content": REVIEW_PROMPT},
            {"role": "user", "content": review_content},
        ],
        reasoning_effort="medium",
    )

    result = response.choices[0].message.content
    tokens = getattr(response, 'usage', None)
    if tokens:
        print(f"[GPT] Done. Tokens: {tokens.prompt_tokens} in, {tokens.completion_tokens} out")
    return result


def call_gemini_review(review_content):
    """Send to Gemini for qualitative review. Returns review text."""
    from google import genai
    from google.genai import types

    api_key = _get_gemini_key()
    os.environ['GEMINI_API_KEY'] = api_key
    client = genai.Client()

    print("\n[Gemini] Sending review request...")
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            types.Content(
                role="user",
                parts=[types.Part(text=REVIEW_PROMPT + "\n\n" + review_content)]
            )
        ],
        config=types.GenerateContentConfig(
            temperature=0.1,
        ),
    )

    usage = getattr(response, 'usage_metadata', None)
    if usage:
        print(f"[Gemini] Done. Tokens: {getattr(usage, 'prompt_token_count', '?')} in, {getattr(usage, 'candidates_token_count', '?')} out")
    return response.text


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Qualitative review tool for multi-model capture data"
    )
    parser.add_argument("task_id", help="Task ID to review (e.g., T067)")
    parser.add_argument("--entry", type=int, default=-1,
                        help="Entry index within the capture file (-1 = latest, 0 = first)")
    parser.add_argument("--variants", type=str, default=None,
                        help="Comma-separated variant labels to review (default: all)")
    parser.add_argument("--source", choices=["captures", "reports"], default="captures",
                        help="Data source: 'captures' (model_captures/) or 'reports' (reports/details/)")
    parser.add_argument("--reviewer", choices=["both", "gpt", "gemini"], default="both",
                        help="Which reviewer to use (default: both)")
    parser.add_argument("--output", type=str, default=None,
                        help="Save reviews to this file (default: print to stdout)")

    args = parser.parse_args()

    # Load data
    if args.source == "captures":
        data = load_from_captures(args.task_id, args.entry)
    else:
        data = load_from_reports(args.task_id, args.entry)

    # Build review content
    review_content = build_review_message(data, args.variants)

    # Show review content size
    print(f"\nReview payload: {len(review_content):,} characters")

    # Run reviews
    results = {}

    if args.reviewer in ("both", "gpt"):
        gpt_thread = threading.Thread(target=lambda: results.update({"gpt": call_gpt_review(review_content)}))
        gpt_thread.start()
    if args.reviewer in ("both", "gemini"):
        gemini_thread = threading.Thread(target=lambda: results.update({"gemini": call_gemini_review(review_content)}))
        gemini_thread.start()

    # Wait for completion
    if args.reviewer in ("both", "gpt"):
        gpt_thread.join()
    if args.reviewer in ("both", "gemini"):
        gemini_thread.join()

    # Assemble output
    output_parts = []
    output_parts.append("=" * 70)
    output_parts.append(f"QUALITATIVE REVIEW: {args.task_id} (entry {args.entry})")
    output_parts.append(f"Timestamp: {data.get('timestamp', 'unknown')}")
    output_parts.append(f"Tier: {data.get('tier', 'unknown')}")
    output_parts.append("=" * 70)

    if "gpt" in results:
        output_parts.append("\n" + "#" * 70)
        output_parts.append("# GPT REVIEWER")
        output_parts.append("#" * 70)
        output_parts.append(results["gpt"])

    if "gemini" in results:
        output_parts.append("\n" + "#" * 70)
        output_parts.append("# GEMINI REVIEWER")
        output_parts.append("#" * 70)
        output_parts.append(results["gemini"])

    final_output = "\n".join(output_parts)

    # Output
    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(final_output)
        print(f"\nReview saved to: {args.output}")
    else:
        print("\n" + final_output)


if __name__ == "__main__":
    main()
