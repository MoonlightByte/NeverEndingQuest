"""
Validator for T079
Auto-generated stub validator

Source: updates/update_character_info.py:1453
Model: model
Scope: runtime

STUB_VALIDATOR = True
This is a Phase 1 stub. Phase 2 will generate intelligent validators via agent dispatch.
"""
import json
import re
from typing import Dict, List, Tuple, Optional, Any

# Task metadata
TASK_ID = "T079"
SOURCE_FILE = "updates/update_character_info.py"
SOURCE_LINE = 1453
MODEL_EXPR = "model"
SCOPE = "runtime"
FUNCTION_CONTEXT = "unknown_function (in update_character_info.py)"

# Expected schema (inferred - needs agent analysis)
EXPECTED_SCHEMA = {
    "description": "Generic response schema (placeholder)",
    "type": "object",
    "properties": {
        "status": {
            "type": "string"
        }
    }
}


def validate_json_structure(output_text: str) -> Tuple[bool, List[str]]:
    """
    Validates JSON parsing and basic structure.

    Args:
        output_text: Raw API output text

    Returns:
        (is_valid, errors): Tuple of validation status and error messages
    """
    errors = []

    # Check for markdown code blocks
    if "```json" in output_text or "```" in output_text:
        errors.append("Output contains markdown code blocks")
        # Try to extract JSON from code block
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', output_text, re.DOTALL)
        if match:
            output_text = match.group(1)
        else:
            return (False, errors)

    # Try to parse JSON
    try:
        parsed = json.loads(output_text)
        if not isinstance(parsed, (dict, list)):
            errors.append(f"JSON root is not dict or list: {type(parsed)}")
            return (False, errors)
    except json.JSONDecodeError as e:
        errors.append(f"JSON parse error: {str(e)}")
        return (False, errors)

    return (True, errors)


def validate_schema_compliance(parsed_json: dict, expected_schema: dict) -> Tuple[bool, List[str]]:
    """
    Validates against expected schema (required fields, types, etc.)

    Args:
        parsed_json: Parsed JSON object
        expected_schema: Expected schema structure

    Returns:
        (is_valid, errors): Tuple of validation status and error messages
    """
    errors = []

    # Check required fields
    required_fields = expected_schema.get("required", [])
    for field in required_fields:
        if field not in parsed_json:
            errors.append(f"Missing required field: {field}")

    # Check field types
    field_types = expected_schema.get("properties", {})
    for field, type_def in field_types.items():
        if field in parsed_json:
            expected_type = type_def.get("type")
            actual_value = parsed_json[field]

            if expected_type == "string" and not isinstance(actual_value, str):
                errors.append(f"Field '{field}' should be string, got {type(actual_value)}")
            elif expected_type == "number" and not isinstance(actual_value, (int, float)):
                errors.append(f"Field '{field}' should be number, got {type(actual_value)}")
            elif expected_type == "boolean" and not isinstance(actual_value, bool):
                errors.append(f"Field '{field}' should be boolean, got {type(actual_value)}")
            elif expected_type == "array" and not isinstance(actual_value, list):
                errors.append(f"Field '{field}' should be array, got {type(actual_value)}")
            elif expected_type == "object" and not isinstance(actual_value, dict):
                errors.append(f"Field '{field}' should be object, got {type(actual_value)}")

    return (len(errors) == 0, errors)


def validate_business_rules(parsed_json: dict, input_data: Optional[dict] = None) -> Tuple[bool, List[str]]:
    """
    Validates business logic specific to this API callsite.

    STUB: This function needs agent analysis to implement real business rules.

    Args:
        parsed_json: Parsed JSON object
        input_data: Input data sent to API (for context)

    Returns:
        (is_valid, errors): Tuple of validation status and error messages
    """
    # TODO: Implement real business rules via agent dispatch
    # For now, accept all outputs as valid (stub behavior)
    return (True, [])


def compare_to_baseline(parsed_json: dict, baseline_json: dict) -> Tuple[bool, List[str]]:
    """
    Compares output to baseline for functional equivalence.

    Args:
        parsed_json: Variant output
        baseline_json: Baseline output

    Returns:
        (is_equivalent, differences): Tuple of equivalence status and differences
    """
    differences = []

    # Check if keys match
    variant_keys = set(parsed_json.keys())
    baseline_keys = set(baseline_json.keys())

    missing_keys = baseline_keys - variant_keys
    extra_keys = variant_keys - baseline_keys

    if missing_keys:
        differences.append(f"Missing keys: {missing_keys}")
    if extra_keys:
        differences.append(f"Extra keys: {extra_keys}")

    # Check common keys for value equality
    for key in variant_keys & baseline_keys:
        variant_val = parsed_json[key]
        baseline_val = baseline_json[key]

        if variant_val != baseline_val:
            differences.append(f"Value mismatch for '{key}': {variant_val} != {baseline_val}")

    return (len(differences) == 0, differences)


def validate_output(output_text: str,
                   input_data: Optional[dict] = None,
                   baseline_output: Optional[str] = None,
                   expected_schema: Optional[dict] = None) -> Dict[str, Any]:
    """
    Main validation entry point.

    Args:
        output_text: Raw API output text
        input_data: Input data sent to API
        baseline_output: Baseline output for comparison
        expected_schema: Expected JSON schema (uses EXPECTED_SCHEMA if not provided)

    Returns:
        {
            "valid": bool,
            "errors": [...],
            "warnings": [...],
            "checks": {
                "json_valid": bool,
                "schema_compliant": bool,
                "business_rules_pass": bool,
                "matches_baseline": bool  # if baseline provided
            },
            "details": {...}  # Additional context
        }
    """
    result = {
        "valid": True,
        "errors": [],
        "warnings": ["STUB_VALIDATOR: Using inferred schema, not real analysis"],
        "checks": {},
        "details": {}
    }

    # Use provided schema or default to EXPECTED_SCHEMA
    schema_to_use = expected_schema or EXPECTED_SCHEMA

    # 1. Validate JSON structure
    json_valid, json_errors = validate_json_structure(output_text)
    result["checks"]["json_valid"] = json_valid
    result["errors"].extend(json_errors)

    if not json_valid:
        result["valid"] = False
        return result

    # Extract clean JSON
    clean_json_text = output_text
    if "```json" in output_text or "```" in output_text:
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', output_text, re.DOTALL)
        if match:
            clean_json_text = match.group(1)
            result["warnings"].append("Extracted JSON from markdown code block")

    parsed_json = json.loads(clean_json_text)
    result["details"]["parsed_json"] = parsed_json

    # 2. Validate schema compliance
    schema_valid, schema_errors = validate_schema_compliance(parsed_json, schema_to_use)
    result["checks"]["schema_compliant"] = schema_valid
    result["errors"].extend(schema_errors)
    if not schema_valid:
        result["valid"] = False

    # 3. Validate business rules
    business_valid, business_errors = validate_business_rules(parsed_json, input_data)
    result["checks"]["business_rules_pass"] = business_valid
    result["errors"].extend(business_errors)
    if not business_valid:
        result["valid"] = False

    # 4. Compare to baseline (if provided)
    if baseline_output:
        baseline_valid, _ = validate_json_structure(baseline_output)
        if baseline_valid:
            baseline_clean = baseline_output
            if "```json" in baseline_output or "```" in baseline_output:
                match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', baseline_output, re.DOTALL)
                if match:
                    baseline_clean = match.group(1)

            baseline_json = json.loads(baseline_clean)
            matches_baseline, differences = compare_to_baseline(parsed_json, baseline_json)
            result["checks"]["matches_baseline"] = matches_baseline
            result["details"]["baseline_differences"] = differences
            if not matches_baseline:
                result["warnings"].extend([f"Baseline difference: {diff}" for diff in differences])
        else:
            result["checks"]["matches_baseline"] = None
            result["warnings"].append("Baseline output is invalid JSON, cannot compare")
    else:
        result["checks"]["matches_baseline"] = None

    return result


# Convenience function for testing
def test_validator():
    """Test validator with sample data."""
    sample_output = json.dumps({"status": "success", "data": "test"})
    result = validate_output(sample_output)
    print(f"Validation result: {result['valid']}")
    print(f"Checks: {result['checks']}")
    if result['warnings']:
        print(f"Warnings: {result['warnings']}")
    return result


if __name__ == "__main__":
    print(f"Validator for {TASK_ID}")
    print(f"Source: {SOURCE_FILE}:{SOURCE_LINE}")
    print(f"Model: {MODEL_EXPR}")
    print(f"Scope: {SCOPE}")
    print()
    test_validator()
