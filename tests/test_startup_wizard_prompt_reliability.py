#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import ValidationError, validate

import model_config
from core.ai import api_client
from utils.startup_prompt_builder import build_character_creation_system_prompt


ROOT_DIR = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT_DIR / "tests" / "synthetic_data" / "startup_wizard_t092_smashing_jack_case.json"
RESULTS_PATH = ROOT_DIR / "debug" / "t092_prompt_iteration_results.json"


MODEL_RUNS = [
    {
        "label": "legacy",
        "provider": "legacy",
        "config_name": "DM_MAIN_LEGACY",
    },
    {
        "label": "gemini",
        "provider": "gemini",
        "config_name": "DM_MAIN_GEMINI_PRO_LOW",
    },
    {
        "label": "openai",
        "provider": "openai",
        "config_name": "DM_MAIN_GPT52_NONE",
    },
]


def _load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _extract_json_object(text):
    stripped = (text or "").strip()
    if not stripped:
        return None, "empty_output"

    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped, None

    code_fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
    if code_fence:
        return code_fence.group(1), None

    object_match = re.search(r"(\{.*\})", stripped, flags=re.DOTALL)
    if object_match:
        return object_match.group(1), None

    return None, "no_json_object_found"


def _resolve_capture_record(fixture):
    source_path = Path(fixture["source_capture_file"])
    capture = _load_json(source_path)
    ts = fixture["source_record_timestamp"]
    for record in capture:
        if record.get("timestamp") == ts and record.get("task_id", fixture.get("source_task_id")) == fixture.get("source_task_id", "T092"):
            return record
    raise ValueError(f"Could not find capture record timestamp: {ts}")


def _build_messages(record, mode):
    capture_messages = record["input"]["messages"]
    if mode == "exact_capture":
        return capture_messages, "capture"

    if mode == "current_prompt":
        current_system_prompt = build_character_creation_system_prompt()
        non_system_messages = [m for m in capture_messages if m.get("role") != "system"]
        messages = [{"role": "system", "content": current_system_prompt}] + non_system_messages
        return messages, "startup_wizard_current"

    raise ValueError(f"Unknown mode: {mode}")


def _resolve_schema(schema_path):
    schema_file = ROOT_DIR / schema_path
    return _load_json(schema_file)


def _evaluate_output(content, constraints, schema):
    json_blob, extraction_error = _extract_json_object(content)
    if extraction_error:
        return False, extraction_error

    try:
        payload = json.loads(json_blob)
    except json.JSONDecodeError:
        return False, "json_decode_error"

    required_fields = constraints.get("required_top_level_fields", [])
    for field in required_fields:
        if field not in payload:
            return False, f"missing_required_field:{field}"

    for field, expected_type in constraints.get("field_type_requirements", {}).items():
        value = payload.get(field)
        if expected_type == "array" and not isinstance(value, list):
            return False, f"invalid_field_type:{field}:expected_array"

    try:
        validate(payload, schema)
    except ValidationError as exc:
        return False, f"schema_validation_error:{exc.message}"

    return True, "pass"


def _run_single_completion(messages, provider, config_name):
    previous_provider = model_config.get_provider()
    model_config.set_provider(provider)
    try:
        config_dict = getattr(model_config, config_name)
        kwargs = {k: v for k, v in config_dict.items() if k != "model"}
        response = api_client.create_completion(
            messages=messages,
            model=config_dict["model"],
            temperature=0.7,
            response_format=None,
            **kwargs,
        )
        return response.choices[0].message.content or ""
    finally:
        model_config.set_provider(previous_provider)


def run_reliability_matrix(fixture_path, attempts, output_path, mode):
    fixture = _load_json(fixture_path)
    capture_record = _resolve_capture_record(fixture)
    messages, prompt_source = _build_messages(capture_record, mode)
    system_prompt_sha256 = hashlib.sha256(messages[0]["content"].encode("utf-8")).hexdigest()
    schema = _resolve_schema(fixture["constraints"]["must_validate_schema_file"])
    constraints = fixture["constraints"]

    output_path.parent.mkdir(parents=True, exist_ok=True)

    records = []
    for model_run in MODEL_RUNS:
        for attempt in range(1, attempts + 1):
            started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            try:
                content = _run_single_completion(
                    messages=messages,
                    provider=model_run["provider"],
                    config_name=model_run["config_name"],
                )
                passed, reason = _evaluate_output(content, constraints, schema)
            except Exception as exc:  # noqa: BLE001
                content = ""
                passed = False
                reason = f"completion_error:{type(exc).__name__}:{exc}"

            records.append(
                {
                    "timestamp": started_at,
                    "fixture": fixture["name"],
                    "model_label": model_run["label"],
                    "provider": model_run["provider"],
                    "config_name": model_run["config_name"],
                    "attempt": attempt,
                    "mode": mode,
                    "prompt_source": prompt_source,
                    "system_prompt_sha256": system_prompt_sha256,
                    "passed": passed,
                    "reason": reason,
                    "output_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest() if content else "",
                    "output_preview": content[:220],
                    "output_failure_sample": content[:6000] if not passed else "",
                }
            )

    total = len(records)
    passed = sum(1 for r in records if r["passed"])
    failed = total - passed

    report = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fixture": fixture["name"],
        "mode": mode,
        "prompt_source": prompt_source,
        "system_prompt_sha256": system_prompt_sha256,
        "attempts_per_model": attempts,
        "summary": {
            "total_runs": total,
            "passed": passed,
            "failed": failed,
        },
        "records": records,
    }

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)

    return report


def main():
    parser = argparse.ArgumentParser(description="Run startup wizard prompt reliability matrix for T092 replay.")
    parser.add_argument("--fixture", default=str(FIXTURE_PATH), help="Path to replay fixture JSON.")
    parser.add_argument("--attempts", type=int, default=5, help="Attempts per model.")
    parser.add_argument("--output", default=str(RESULTS_PATH), help="Output JSON report path.")
    parser.add_argument(
        "--mode",
        choices=["exact_capture", "current_prompt"],
        default="current_prompt",
        help="Use exact captured system prompt or rebuild messages with current startup prompt.",
    )
    args = parser.parse_args()

    report = run_reliability_matrix(
        fixture_path=Path(args.fixture),
        attempts=args.attempts,
        output_path=Path(args.output),
        mode=args.mode,
    )

    print(json.dumps(report["summary"], indent=2))
    if report["summary"]["failed"] > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
