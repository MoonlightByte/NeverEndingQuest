"""
Validator for T051: core/validation/character_validator.py:958
Regenerated with correct schema from audit 2026-02-22

Purpose: Character AC validation response with corrections
Expected output: See EXPECTED_SCHEMA below
"""
import json
import re
from typing import Dict, List, Tuple, Optional, Any

TASK_ID = "T051"
SOURCE_FILE = "core/validation/character_validator.py"
SOURCE_LINE = 958
MODEL_EXPR = "CHARACTER_VALIDATOR_MODEL=>gpt-5.2"
SCOPE = "runtime"

EXPECTED_SCHEMA = {'description': 'Character AC validation response with corrections', 'type': 'object', 'required': ['validated_character_data', 'corrections_made', 'ac_calculation_breakdown'], 'properties': {'validated_character_data': {'type': 'object'}, 'corrections_made': {'type': 'array', 'items': {'type': 'string'}}, 'ac_calculation_breakdown': {'type': 'object', 'required': ['base_armor', 'dex_modifier', 'shield_bonus', 'fighting_style_bonus', 'total_ac'], 'properties': {'base_armor': {'type': 'string'}, 'dex_modifier': {'type': 'string'}, 'shield_bonus': {'type': 'string'}, 'fighting_style_bonus': {'type': 'string'}, 'total_ac': {'type': ['integer', 'number', 'string']}}}}}


def validate_json_structure(output_text: str) -> Tuple[bool, List[str]]:
    """
    Validates JSON parsing and basic structure.
    Handles markdown code blocks and preamble text.
    """
    errors = []

    # Check for markdown code blocks
    if "```json" in output_text or "```" in output_text:
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', output_text, re.DOTALL)
        if match:
            output_text = match.group(1)
        else:
            errors.append("Failed to extract JSON from markdown code block")
            return (False, errors)
    # Check for preamble text before JSON
    elif not output_text.strip().startswith('{'):
        match = re.search(r'(\{.*\})', output_text, re.DOTALL)
        if match:
            output_text = match.group(1)
        else:
            errors.append("No JSON object found in output")
            return (False, errors)

    try:
        parsed = json.loads(output_text)
        if not isinstance(parsed, dict):
            errors.append(f"JSON root is not an object: {type(parsed)}")
            return (False, errors)
    except json.JSONDecodeError as e:
        errors.append(f"JSON parse error: {str(e)}")
        return (False, errors)

    return (True, errors)


def validate_schema_compliance(parsed_json: dict) -> Tuple[bool, List[str]]:
    """Validates against expected schema."""
    errors = []

    # Check required fields
    required_fields = EXPECTED_SCHEMA.get("required", [])
    for field in required_fields:
        if field not in parsed_json:
            errors.append(f"Missing required field: {field}")

    # Check field types for properties
    properties = EXPECTED_SCHEMA.get("properties", {})
    for field, type_def in properties.items():
        if field in parsed_json:
            expected_type = type_def.get("type")
            actual_value = parsed_json[field]

            # Handle type arrays (e.g., ["integer", "string"])
            if isinstance(expected_type, list):
                valid_type = False
                for t in expected_type:
                    if t == "string" and isinstance(actual_value, str):
                        valid_type = True
                        break
                    elif t == "number" and isinstance(actual_value, (int, float)):
                        valid_type = True
                        break
                    elif t == "integer" and isinstance(actual_value, int):
                        valid_type = True
                        break
                    elif t == "boolean" and isinstance(actual_value, bool):
                        valid_type = True
                        break
                    elif t == "array" and isinstance(actual_value, list):
                        valid_type = True
                        break
                    elif t == "object" and isinstance(actual_value, dict):
                        valid_type = True
                        break
                if not valid_type:
                    errors.append(f"Field '{field}' has wrong type: expected one of {expected_type}, got {type(actual_value).__name__}")
            else:
                # Single type
                if expected_type == "string" and not isinstance(actual_value, str):
                    errors.append(f"Field '{field}' should be string, got {type(actual_value).__name__}")
                elif expected_type == "number" and not isinstance(actual_value, (int, float)):
                    errors.append(f"Field '{field}' should be number, got {type(actual_value).__name__}")
                elif expected_type == "integer" and not isinstance(actual_value, int):
                    errors.append(f"Field '{field}' should be integer, got {type(actual_value).__name__}")
                elif expected_type == "boolean" and not isinstance(actual_value, bool):
                    errors.append(f"Field '{field}' should be boolean, got {type(actual_value).__name__}")
                elif expected_type == "array" and not isinstance(actual_value, list):
                    errors.append(f"Field '{field}' should be array, got {type(actual_value).__name__}")
                elif expected_type == "object" and not isinstance(actual_value, dict):
                    errors.append(f"Field '{field}' should be object, got {type(actual_value).__name__}")

    return (len(errors) == 0, errors)


def validate_business_rules(parsed_json: dict, input_data: Optional[dict] = None) -> Tuple[bool, List[str]]:
    """Validates business logic (task-specific rules can be added here)."""
    errors = []
    # Default: pass
    # Override this in specific validators as needed
    return (len(errors) == 0, errors)


def validate_output(output_text: str,
                   input_data: Optional[dict] = None,
                   baseline_output: Optional[str] = None) -> Dict[str, Any]:
    """Main validation entry point."""
    result = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "checks": {},
        "details": {}
    }

    # 1. JSON structure validation
    json_valid, json_errors = validate_json_structure(output_text)
    result["checks"]["json_valid"] = json_valid
    result["errors"].extend(json_errors)

    if not json_valid:
        result["valid"] = False
        return result

    # Extract clean JSON
    clean_json_text = output_text
    if "```" in output_text:
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', output_text, re.DOTALL)
        if match:
            clean_json_text = match.group(1)
            result["warnings"].append("Extracted JSON from markdown code block")
    elif not output_text.strip().startswith('{'):
        match = re.search(r'(\{.*\})', output_text, re.DOTALL)
        if match:
            clean_json_text = match.group(1)
            result["warnings"].append("Extracted JSON from preamble text")

    parsed_json = json.loads(clean_json_text)
    result["details"]["parsed_json"] = parsed_json

    # 2. Schema compliance
    schema_valid, schema_errors = validate_schema_compliance(parsed_json)
    result["checks"]["schema_compliant"] = schema_valid
    result["errors"].extend(schema_errors)
    if not schema_valid:
        result["valid"] = False

    # 3. Business rules
    business_valid, business_errors = validate_business_rules(parsed_json, input_data)
    result["checks"]["business_rules_pass"] = business_valid
    result["errors"].extend(business_errors)
    if not business_valid:
        result["valid"] = False

    # 4. Baseline comparison
    if baseline_output:
        baseline_valid, _ = validate_json_structure(baseline_output)
        if baseline_valid:
            baseline_clean = baseline_output
            if "```" in baseline_output:
                match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', baseline_output, re.DOTALL)
                if match:
                    baseline_clean = match.group(1)
            elif not baseline_output.strip().startswith('{'):
                match = re.search(r'(\{.*\})', baseline_output, re.DOTALL)
                if match:
                    baseline_clean = match.group(1)

            try:
                baseline_json = json.loads(baseline_clean)

                # Simple key/value comparison
                variant_keys = set(parsed_json.keys())
                baseline_keys = set(baseline_json.keys())

                differences = []
                missing = baseline_keys - variant_keys
                extra = variant_keys - baseline_keys

                if missing:
                    differences.append(f"Missing keys: {missing}")
                if extra:
                    differences.append(f"Extra keys: {extra}")

                for key in variant_keys & baseline_keys:
                    if parsed_json[key] != baseline_json[key]:
                        differences.append(f"Value mismatch for '{key}'")

                result["checks"]["matches_baseline"] = (len(differences) == 0)
                result["details"]["baseline_differences"] = differences

                if differences:
                    result["warnings"].extend([f"Baseline difference: {d}" for d in differences[:5]])
            except Exception as e:
                result["checks"]["matches_baseline"] = None
                result["warnings"].append(f"Baseline comparison failed: {str(e)}")
        else:
            result["checks"]["matches_baseline"] = None
            result["warnings"].append("Baseline output is invalid JSON")
    else:
        result["checks"]["matches_baseline"] = None

    return result
