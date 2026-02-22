#!/usr/bin/env python3
"""
Validator Discovery Script - Phase 1

Generates validator modules for API callsites from the audit inventory.
Phase 1: Stub validators (agent dispatch placeholder)
Phase 2: Agent dispatch for intelligent validator generation

Usage:
    python tools/discover_validators.py --tasks T079,T082
    python tools/discover_validators.py --retry-failed
    python tools/discover_validators.py  # All tasks
"""
import json
import os
import re
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Paths
AUDIT_INVENTORY = PROJECT_ROOT.parent / "dungeon_master_v1" / "docs" / "audit" / "2026-02-12-openai-api-call-inventory.json"
VALIDATORS_DIR = PROJECT_ROOT / "validators"
INIT_FILE = VALIDATORS_DIR / "__init__.py"


def load_audit_inventory() -> List[Dict[str, Any]]:
    """Load API call inventory from audit file."""
    if not AUDIT_INVENTORY.exists():
        raise FileNotFoundError(f"Audit inventory not found: {AUDIT_INVENTORY}")

    with open(AUDIT_INVENTORY, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"[OK] Loaded {len(data)} tasks from audit inventory")
    return data


def filter_tasks(inventory: List[Dict[str, Any]], args: argparse.Namespace) -> List[Dict[str, Any]]:
    """Filter tasks based on command-line arguments."""
    if args.tasks:
        # Specific tasks requested
        requested = set(args.tasks.split(','))
        filtered = [task for task in inventory if task['task_id'] in requested]
        print(f"[OK] Filtered to {len(filtered)} requested tasks: {', '.join(sorted(requested))}")
        return filtered

    if args.retry_failed:
        # Retry failed tasks (check for existing validators with errors)
        failed_tasks = []
        for task in inventory:
            validator_file = VALIDATORS_DIR / f"task_{task['task_id']}.py"
            if validator_file.exists():
                # Check if validator has errors or is a stub
                with open(validator_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if 'STUB_VALIDATOR = True' in content or 'ERROR' in content:
                        failed_tasks.append(task)

        print(f"[OK] Found {len(failed_tasks)} failed/stub validators to retry")
        return failed_tasks

    # All tasks
    print(f"[OK] Processing all {len(inventory)} tasks")
    return inventory


def extract_function_signature(task: Dict[str, Any]) -> str:
    """
    Extract likely function/method name from path and line context.
    This is a placeholder - in Phase 2, agent will analyze source code.
    """
    path = task['path']

    # Extract module/class hints from path
    parts = path.split('/')
    filename = parts[-1].replace('.py', '')

    # Common patterns
    if 'combat' in path.lower():
        return f"combat_related_function (in {filename}.py)"
    elif 'generator' in path.lower():
        return f"generation_function (in {filename}.py)"
    elif 'manager' in path.lower():
        return f"manager_function (in {filename}.py)"
    elif 'utils' in path.lower():
        return f"utility_function (in {filename}.py)"
    else:
        return f"unknown_function (in {filename}.py)"


def infer_response_schema(task: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Infer expected response schema from task context.
    This is a placeholder - in Phase 2, agent will analyze code and prompts.
    """
    path = task['path'].lower()

    # Common patterns based on path
    if 'combat' in path:
        return {
            "description": "Combat-related response (inferred)",
            "type": "object",
            "properties": {
                "action": {"type": "string"},
                "result": {"type": "string"},
                "success": {"type": "boolean"}
            },
            "required": ["action", "result"]
        }
    elif 'generator' in path or 'builder' in path:
        return {
            "description": "Generation response (inferred)",
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "metadata": {"type": "object"}
            },
            "required": ["content"]
        }
    elif 'validation' in path:
        return {
            "description": "Validation response (inferred)",
            "type": "object",
            "properties": {
                "valid": {"type": "boolean"},
                "errors": {"type": "array"}
            },
            "required": ["valid"]
        }

    # Default generic schema
    return {
        "description": "Generic response schema (placeholder)",
        "type": "object",
        "properties": {
            "status": {"type": "string"}
        }
    }


def generate_stub_validator(task: Dict[str, Any]) -> str:
    """
    Generate a stub validator module.
    Phase 1: Returns stub with placeholders
    Phase 2: Will dispatch to agent for intelligent generation
    """
    task_id = task['task_id']
    path = task['path']
    line = task['line']
    model_expr = task['model_expr']
    scope = task['scope']

    # Extract basic metadata
    function_sig = extract_function_signature(task)
    schema = infer_response_schema(task)

    # Generate validator code
    code = f'''"""
Validator for {task_id}
Auto-generated stub validator

Source: {path}:{line}
Model: {model_expr}
Scope: {scope}

STUB_VALIDATOR = True
This is a Phase 1 stub. Phase 2 will generate intelligent validators via agent dispatch.
"""
import json
import re
from typing import Dict, List, Tuple, Optional, Any

# Task metadata
TASK_ID = "{task_id}"
SOURCE_FILE = "{path}"
SOURCE_LINE = {line}
MODEL_EXPR = "{model_expr}"
SCOPE = "{scope}"
FUNCTION_CONTEXT = "{function_sig}"

# Expected schema (inferred - needs agent analysis)
EXPECTED_SCHEMA = {json.dumps(schema, indent=4)}


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
        match = re.search(r'```(?:json)?\\s*(\\{{.*?\\}})\\s*```', output_text, re.DOTALL)
        if match:
            output_text = match.group(1)
        else:
            return (False, errors)

    # Try to parse JSON
    try:
        parsed = json.loads(output_text)
        if not isinstance(parsed, (dict, list)):
            errors.append(f"JSON root is not dict or list: {{type(parsed)}}")
            return (False, errors)
    except json.JSONDecodeError as e:
        errors.append(f"JSON parse error: {{str(e)}}")
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
            errors.append(f"Missing required field: {{field}}")

    # Check field types
    field_types = expected_schema.get("properties", {{}})
    for field, type_def in field_types.items():
        if field in parsed_json:
            expected_type = type_def.get("type")
            actual_value = parsed_json[field]

            if expected_type == "string" and not isinstance(actual_value, str):
                errors.append(f"Field '{{field}}' should be string, got {{type(actual_value)}}")
            elif expected_type == "number" and not isinstance(actual_value, (int, float)):
                errors.append(f"Field '{{field}}' should be number, got {{type(actual_value)}}")
            elif expected_type == "boolean" and not isinstance(actual_value, bool):
                errors.append(f"Field '{{field}}' should be boolean, got {{type(actual_value)}}")
            elif expected_type == "array" and not isinstance(actual_value, list):
                errors.append(f"Field '{{field}}' should be array, got {{type(actual_value)}}")
            elif expected_type == "object" and not isinstance(actual_value, dict):
                errors.append(f"Field '{{field}}' should be object, got {{type(actual_value)}}")

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
        differences.append(f"Missing keys: {{missing_keys}}")
    if extra_keys:
        differences.append(f"Extra keys: {{extra_keys}}")

    # Check common keys for value equality
    for key in variant_keys & baseline_keys:
        variant_val = parsed_json[key]
        baseline_val = baseline_json[key]

        if variant_val != baseline_val:
            differences.append(f"Value mismatch for '{{key}}': {{variant_val}} != {{baseline_val}}")

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
        {{
            "valid": bool,
            "errors": [...],
            "warnings": [...],
            "checks": {{
                "json_valid": bool,
                "schema_compliant": bool,
                "business_rules_pass": bool,
                "matches_baseline": bool  # if baseline provided
            }},
            "details": {{...}}  # Additional context
        }}
    """
    result = {{
        "valid": True,
        "errors": [],
        "warnings": ["STUB_VALIDATOR: Using inferred schema, not real analysis"],
        "checks": {{}},
        "details": {{}}
    }}

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
        match = re.search(r'```(?:json)?\\s*(\\{{.*?\\}})\\s*```', output_text, re.DOTALL)
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
                match = re.search(r'```(?:json)?\\s*(\\{{.*?\\}})\\s*```', baseline_output, re.DOTALL)
                if match:
                    baseline_clean = match.group(1)

            baseline_json = json.loads(baseline_clean)
            matches_baseline, differences = compare_to_baseline(parsed_json, baseline_json)
            result["checks"]["matches_baseline"] = matches_baseline
            result["details"]["baseline_differences"] = differences
            if not matches_baseline:
                result["warnings"].extend([f"Baseline difference: {{diff}}" for diff in differences])
        else:
            result["checks"]["matches_baseline"] = None
            result["warnings"].append("Baseline output is invalid JSON, cannot compare")
    else:
        result["checks"]["matches_baseline"] = None

    return result


# Convenience function for testing
def test_validator():
    """Test validator with sample data."""
    sample_output = json.dumps({{"status": "success", "data": "test"}})
    result = validate_output(sample_output)
    print(f"Validation result: {{result['valid']}}")
    print(f"Checks: {{result['checks']}}")
    if result['warnings']:
        print(f"Warnings: {{result['warnings']}}")
    return result


if __name__ == "__main__":
    print(f"Validator for {{TASK_ID}}")
    print(f"Source: {{SOURCE_FILE}}:{{SOURCE_LINE}}")
    print(f"Model: {{MODEL_EXPR}}")
    print(f"Scope: {{SCOPE}}")
    print()
    test_validator()
'''

    return code


def create_validator_file(task: Dict[str, Any]) -> Path:
    """Create validator file for a task."""
    task_id = task['task_id']
    validator_file = VALIDATORS_DIR / f"task_{task_id}.py"

    # Generate validator code
    code = generate_stub_validator(task)

    # Write file
    with open(validator_file, 'w', encoding='utf-8') as f:
        f.write(code)

    return validator_file


def update_init_file(task_ids: List[str]):
    """Update validators/__init__.py with imports."""
    imports = []
    for task_id in sorted(task_ids):
        imports.append(f"from validators import task_{task_id}")

    init_content = '''"""
Validator modules for API callsite validation.
Auto-generated by tools/discover_validators.py
"""

# Auto-generated imports
'''
    init_content += '\n'.join(imports)
    init_content += '\n\n__all__ = [\n'
    init_content += ',\n'.join([f'    "task_{tid}"' for tid in sorted(task_ids)])
    init_content += '\n]\n'

    with open(INIT_FILE, 'w', encoding='utf-8') as f:
        f.write(init_content)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate validator modules for API callsites",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/discover_validators.py --tasks T079,T082
  python tools/discover_validators.py --retry-failed
  python tools/discover_validators.py  # All tasks
        """
    )
    parser.add_argument(
        '--tasks',
        help='Comma-separated list of task IDs (e.g., T079,T082)'
    )
    parser.add_argument(
        '--retry-failed',
        action='store_true',
        help='Retry failed/stub validators only'
    )

    args = parser.parse_args()

    print("=" * 70)
    print("Validator Discovery Script - Phase 1")
    print("=" * 70)
    print()

    # Load inventory
    try:
        inventory = load_audit_inventory()
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    # Filter tasks
    tasks = filter_tasks(inventory, args)
    if not tasks:
        print("[WARNING] No tasks to process")
        sys.exit(0)

    print()
    print(f"Generating validators for {len(tasks)} tasks...")
    print()

    # Generate validators
    created_files = []
    task_ids = []

    for task in tasks:
        task_id = task['task_id']
        print(f"  [{task_id}] {task['path']}:{task['line']}")

        try:
            validator_file = create_validator_file(task)
            created_files.append(validator_file)
            task_ids.append(task_id)
            print(f"        -> Created {validator_file.name}")
        except Exception as e:
            print(f"        -> [ERROR] Failed to create validator: {e}")

    print()
    print(f"[OK] Created {len(created_files)} validator files")

    # Update __init__.py
    if task_ids:
        # Get all existing validators
        all_task_ids = set(task_ids)
        for validator_file in VALIDATORS_DIR.glob("task_*.py"):
            match = re.match(r'task_(T\d+)\.py', validator_file.name)
            if match:
                all_task_ids.add(match.group(1))

        update_init_file(sorted(all_task_ids))
        print(f"[OK] Updated {INIT_FILE.name} with {len(all_task_ids)} imports")

    print()
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"Total tasks processed: {len(tasks)}")
    print(f"Validators created: {len(created_files)}")
    print(f"Total validators: {len(all_task_ids)}")
    print()
    print("Next steps:")
    print("  1. Test imports: python -c 'from validators import task_T079; print(task_T079.TASK_ID)'")
    print("  2. Run validation: result = task_T079.validate_output('{\"test\": \"data\"}')")
    print("  3. Phase 2: Implement agent dispatch for intelligent validator generation")
    print()


if __name__ == "__main__":
    main()
