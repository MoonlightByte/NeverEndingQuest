"""
Regenerate Validators with Correct Schemas
Based on audit results from 2026-02-22

This script regenerates all 10 validators with correct schemas
identified by parallel audit agents.
"""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Correct schemas from audit
CORRECTED_SCHEMAS = {
    "T051": {
        "description": "Character AC validation response with corrections",
        "type": "object",
        "required": ["validated_character_data", "corrections_made", "ac_calculation_breakdown"],
        "properties": {
            "validated_character_data": {"type": "object"},
            "corrections_made": {"type": "array", "items": {"type": "string"}},
            "ac_calculation_breakdown": {
                "type": "object",
                "required": ["base_armor", "dex_modifier", "shield_bonus", "fighting_style_bonus", "total_ac"],
                "properties": {
                    "base_armor": {"type": "string"},
                    "dex_modifier": {"type": "string"},
                    "shield_bonus": {"type": "string"},
                    "fighting_style_bonus": {"type": "string"},
                    "total_ac": {"type": ["integer", "number", "string"]}
                }
            }
        }
    },
    "T054": {
        "description": "Inventory consolidation response",
        "type": "object",
        "required": ["ammunition", "equipment", "consolidations_made"],
        "properties": {
            "inventory": {
                "type": "object",
                "properties": {
                    "currency": {
                        "type": "object",
                        "properties": {
                            "platinum": {"type": "number"},
                            "gold": {"type": "number"},
                            "electrum": {"type": "number"},
                            "silver": {"type": "number"},
                            "copper": {"type": "number"}
                        }
                    }
                }
            },
            "ammunition": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["name", "quantity", "description"],
                    "properties": {
                        "name": {"type": "string"},
                        "quantity": {"type": "number"},
                        "description": {"type": "string"}
                    }
                }
            },
            "equipment": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["item_name"],
                    "properties": {
                        "item_name": {"type": "string"},
                        "_remove": {"type": "boolean"},
                        "_update": {"type": "boolean"}
                    }
                }
            },
            "consolidations_made": {
                "type": "array",
                "items": {"type": "string"}
            }
        }
    },
    "T065": {
        "description": "DM validation response - checks AI DM compliance",
        "type": "object",
        "required": ["valid", "reason"],
        "properties": {
            "valid": {"type": "boolean"},
            "reason": {"type": "string"}
        }
    },
    "T067": {
        "description": "Main DM response - narration and actions",
        "type": "object",
        "required": ["narration", "actions"],
        "properties": {
            "narration": {"type": "string"},
            "actions": {
                "type": "array",
                "items": {"type": "string"}
            }
        }
    },
    "T077": {
        "description": "Plot update response - plot point status changes",
        "type": "object",
        "patternProperties": {
            "^(PP|SQ)\\d{3}$": {
                "oneOf": [
                    {
                        "type": "object",
                        "required": ["status", "plotImpact"],
                        "properties": {
                            "status": {
                                "type": "string",
                                "enum": ["not started", "in progress", "completed"]
                            },
                            "plotImpact": {"type": "string"}
                        }
                    },
                    {
                        "type": "object",
                        "required": ["sideQuests"],
                        "properties": {
                            "sideQuests": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["id", "status", "plotImpact"],
                                    "properties": {
                                        "id": {"type": "string", "pattern": "^SQ\\d{3}$"},
                                        "status": {"type": "string", "enum": ["not started", "in progress", "completed"]},
                                        "plotImpact": {"type": "string"}
                                    }
                                }
                            }
                        }
                    }
                ]
            }
        }
    },
    "T078": {
        "description": "Character effect tracking response",
        "type": "object",
        "required": ["should_track", "effect"],
        "properties": {
            "should_track": {"type": "boolean"},
            "effect": {
                "type": "object",
                "required": ["stat", "value", "source", "duration_type", "duration_value", "description", "affects_max"],
                "properties": {
                    "stat": {"type": "string"},
                    "value": {"type": ["number", "string"]},
                    "source": {"type": "string"},
                    "duration_type": {"type": "string"},
                    "duration_value": {"type": ["number", "string"]},
                    "description": {"type": "string"},
                    "affects_max": {"type": "boolean"}
                }
            }
        }
    },
    "T079": {
        "description": "Character info update response - delta changes only",
        "type": "object",
        "properties": {
            "currency": {
                "type": "object",
                "required": ["gold", "silver", "copper"],
                "properties": {
                    "gold": {"type": "integer"},
                    "silver": {"type": "integer"},
                    "copper": {"type": "integer"}
                }
            }
        }
    },
    "T082": {
        "description": "Action prediction response",
        "type": "object",
        "required": ["requires_actions", "reason"],
        "properties": {
            "requires_actions": {"type": "boolean"},
            "reason": {"type": "string"}
        }
    },
    "T090": {
        "description": "Quest reformatting response - dynamic quest IDs to descriptions",
        "type": "object",
        "patternProperties": {
            "^[A-Z]{2,3}\\d{3}$": {"type": "string"}
        },
        "additionalProperties": False,
        "minProperties": 1
    }
}


def regenerate_validator(task_id: str, schema: dict):
    """Regenerate a single validator with correct schema."""
    validator_path = PROJECT_ROOT / f"validators/task_{task_id}.py"

    if not validator_path.exists():
        print(f"[SKIP] {task_id}: Validator file not found")
        return False

    # Read existing validator to preserve metadata
    with open(validator_path, 'r', encoding='utf-8') as f:
        existing_content = f.read()

    # Extract metadata lines (SOURCE_FILE, SOURCE_LINE, etc.)
    import re
    source_file_match = re.search(r'SOURCE_FILE = "(.*?)"', existing_content)
    source_line_match = re.search(r'SOURCE_LINE = (\d+)', existing_content)
    model_expr_match = re.search(r'MODEL_EXPR = "(.*?)"', existing_content)
    scope_match = re.search(r'SCOPE = "(.*?)"', existing_content)

    source_file = source_file_match.group(1) if source_file_match else "unknown"
    source_line = source_line_match.group(1) if source_line_match else "0"
    model_expr = model_expr_match.group(1) if model_expr_match else "unknown"
    scope = scope_match.group(1) if scope_match else "unknown"

    # Generate new validator content
    new_content = f'''"""
Validator for {task_id}: {source_file}:{source_line}
Regenerated with correct schema from audit 2026-02-22

Purpose: {schema.get("description", "Unknown")}
Expected output: See EXPECTED_SCHEMA below
"""
import json
import re
from typing import Dict, List, Tuple, Optional, Any

TASK_ID = "{task_id}"
SOURCE_FILE = "{source_file}"
SOURCE_LINE = {source_line}
MODEL_EXPR = "{model_expr}"
SCOPE = "{scope}"

EXPECTED_SCHEMA = {repr(schema)}


def validate_json_structure(output_text: str) -> Tuple[bool, List[str]]:
    """
    Validates JSON parsing and basic structure.
    Handles markdown code blocks and preamble text.
    """
    errors = []

    # Check for markdown code blocks
    if "```json" in output_text or "```" in output_text:
        match = re.search(r'```(?:json)?\\s*(\\{{.*?\\}})\\s*```', output_text, re.DOTALL)
        if match:
            output_text = match.group(1)
        else:
            errors.append("Failed to extract JSON from markdown code block")
            return (False, errors)
    # Check for preamble text before JSON
    elif not output_text.strip().startswith('{{'):
        match = re.search(r'(\\{{.*\\}})', output_text, re.DOTALL)
        if match:
            output_text = match.group(1)
        else:
            errors.append("No JSON object found in output")
            return (False, errors)

    try:
        parsed = json.loads(output_text)
        if not isinstance(parsed, dict):
            errors.append(f"JSON root is not an object: {{type(parsed)}}")
            return (False, errors)
    except json.JSONDecodeError as e:
        errors.append(f"JSON parse error: {{str(e)}}")
        return (False, errors)

    return (True, errors)


def validate_schema_compliance(parsed_json: dict) -> Tuple[bool, List[str]]:
    """Validates against expected schema."""
    errors = []

    # Check required fields
    required_fields = EXPECTED_SCHEMA.get("required", [])
    for field in required_fields:
        if field not in parsed_json:
            errors.append(f"Missing required field: {{field}}")

    # Check field types for properties
    properties = EXPECTED_SCHEMA.get("properties", {{}})
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
                    errors.append(f"Field '{{field}}' has wrong type: expected one of {{expected_type}}, got {{type(actual_value).__name__}}")
            else:
                # Single type
                if expected_type == "string" and not isinstance(actual_value, str):
                    errors.append(f"Field '{{field}}' should be string, got {{type(actual_value).__name__}}")
                elif expected_type == "number" and not isinstance(actual_value, (int, float)):
                    errors.append(f"Field '{{field}}' should be number, got {{type(actual_value).__name__}}")
                elif expected_type == "integer" and not isinstance(actual_value, int):
                    errors.append(f"Field '{{field}}' should be integer, got {{type(actual_value).__name__}}")
                elif expected_type == "boolean" and not isinstance(actual_value, bool):
                    errors.append(f"Field '{{field}}' should be boolean, got {{type(actual_value).__name__}}")
                elif expected_type == "array" and not isinstance(actual_value, list):
                    errors.append(f"Field '{{field}}' should be array, got {{type(actual_value).__name__}}")
                elif expected_type == "object" and not isinstance(actual_value, dict):
                    errors.append(f"Field '{{field}}' should be object, got {{type(actual_value).__name__}}")

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
    result = {{
        "valid": True,
        "errors": [],
        "warnings": [],
        "checks": {{}},
        "details": {{}}
    }}

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
        match = re.search(r'```(?:json)?\\s*(\\{{.*?\\}})\\s*```', output_text, re.DOTALL)
        if match:
            clean_json_text = match.group(1)
            result["warnings"].append("Extracted JSON from markdown code block")
    elif not output_text.strip().startswith('{{'):
        match = re.search(r'(\\{{.*\\}})', output_text, re.DOTALL)
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
                match = re.search(r'```(?:json)?\\s*(\\{{.*?\\}})\\s*```', baseline_output, re.DOTALL)
                if match:
                    baseline_clean = match.group(1)
            elif not baseline_output.strip().startswith('{{'):
                match = re.search(r'(\\{{.*\\}})', baseline_output, re.DOTALL)
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
                    differences.append(f"Missing keys: {{missing}}")
                if extra:
                    differences.append(f"Extra keys: {{extra}}")

                for key in variant_keys & baseline_keys:
                    if parsed_json[key] != baseline_json[key]:
                        differences.append(f"Value mismatch for '{{key}}'")

                result["checks"]["matches_baseline"] = (len(differences) == 0)
                result["details"]["baseline_differences"] = differences

                if differences:
                    result["warnings"].extend([f"Baseline difference: {{d}}" for d in differences[:5]])
            except Exception as e:
                result["checks"]["matches_baseline"] = None
                result["warnings"].append(f"Baseline comparison failed: {{str(e)}}")
        else:
            result["checks"]["matches_baseline"] = None
            result["warnings"].append("Baseline output is invalid JSON")
    else:
        result["checks"]["matches_baseline"] = None

    return result
'''

    # Write new validator
    with open(validator_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"[REGENERATED] {task_id}: {validator_path.name}")
    return True


def main():
    """Regenerate all validators with correct schemas."""
    print("="*80)
    print("Validator Regeneration from Audit Results")
    print("="*80)
    print()

    regenerated = 0
    skipped = 0

    for task_id, schema in CORRECTED_SCHEMAS.items():
        if regenerate_validator(task_id, schema):
            regenerated += 1
        else:
            skipped += 1

    print()
    print("="*80)
    print(f"Summary: {regenerated} regenerated, {skipped} skipped")
    print("="*80)

    # Note about remaining validators
    print()
    print("Note: T035 not included (NPC schema too complex for auto-generation)")
    print("      Run discover_validators.py --tasks T035 for full NPC validation")

    return 0


if __name__ == '__main__':
    sys.exit(main())
