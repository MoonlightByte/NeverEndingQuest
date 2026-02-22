# Multi-Model Capture Validation System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an automated validation system that analyzes multi-model capture data from 95 API callsites using agent-generated deterministic validators.

**Architecture:** Two-phase system: (1) Discovery phase dispatches 95 parallel agents to generate validator modules by analyzing system prompts, callsite code, and existing validators; (2) Analysis phase runs deterministic Python validation on all captured outputs and produces HTML/JSON reports.

**Tech Stack:** Python 3.10+, standard library (json, glob, importlib), Jinja2 (HTML reports), optional jsonschema

---

## Task 1: Create Directory Structure

**Files:**
- Create: `validators/__init__.py`
- Create: `reports/.gitkeep`
- Create: `reports/details/.gitkeep`
- Create: `tools/__init__.py`

**Step 1: Create validators directory with __init__.py**

```bash
mkdir -p validators
touch validators/__init__.py
```

Expected: `validators/` directory exists with empty `__init__.py`

**Step 2: Create reports directory structure**

```bash
mkdir -p reports/details
touch reports/.gitkeep reports/details/.gitkeep
```

Expected: `reports/` and `reports/details/` directories exist

**Step 3: Create tools directory with __init__.py**

```bash
mkdir -p tools
touch tools/__init__.py
```

Expected: `tools/` directory exists with empty `__init__.py`

**Step 4: Verify directory structure**

```bash
ls -la validators/ reports/ reports/details/ tools/
```

Expected: All directories exist with correct permissions

**Step 5: Commit directory structure**

```bash
git add validators/__init__.py reports/.gitkeep reports/details/.gitkeep tools/__init__.py
git commit -m "feat(validation): add directory structure for validator system"
```

---

## Task 2: Create Validator Template Module

**Files:**
- Create: `validators/validator_template.py`

**Step 1: Write validator template with complete structure**

```python
"""
Validator Template
Auto-generated validators follow this structure.
"""
import json
import re
from typing import Dict, List, Tuple, Optional, Any


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
    Validates business logic (e.g., gold=14 after removing 1 from 15)

    Args:
        parsed_json: Parsed JSON object
        input_data: Input data sent to API (for context)

    Returns:
        (is_valid, errors): Tuple of validation status and error messages
    """
    # Override this in generated validators with specific business rules
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
        expected_schema: Expected JSON schema

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
        "warnings": [],
        "checks": {},
        "details": {}
    }

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

    # 2. Validate schema compliance (if schema provided)
    if expected_schema:
        schema_valid, schema_errors = validate_schema_compliance(parsed_json, expected_schema)
        result["checks"]["schema_compliant"] = schema_valid
        result["errors"].extend(schema_errors)
        if not schema_valid:
            result["valid"] = False
    else:
        result["checks"]["schema_compliant"] = None  # No schema to check

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
```

Expected: `validators/validator_template.py` created with complete validation logic

**Step 2: Test template functions with sample data**

Create `test_validator_template.py`:

```python
import sys
sys.path.insert(0, '/mnt/c/dungeon_master_v1_testing')
from validators.validator_template import validate_output

# Test 1: Valid JSON
output1 = '{"action": "move", "direction": "north"}'
result1 = validate_output(output1)
print(f"Test 1 - Valid JSON: {result1['valid']}")
assert result1['valid'] == True
assert result1['checks']['json_valid'] == True

# Test 2: JSON in code block
output2 = '```json\n{"action": "attack", "target": "goblin"}\n```'
result2 = validate_output(output2)
print(f"Test 2 - JSON in code block: {result2['valid']}, warnings: {len(result2['warnings'])}")
assert result2['valid'] == True
assert len(result2['warnings']) == 1

# Test 3: Invalid JSON
output3 = 'This is not JSON'
result3 = validate_output(output3)
print(f"Test 3 - Invalid JSON: {result3['valid']}, errors: {result3['errors']}")
assert result3['valid'] == False
assert result3['checks']['json_valid'] == False

print("All template tests passed!")
```

Run: `python test_validator_template.py`
Expected: All assertions pass

**Step 3: Commit validator template**

```bash
git add validators/validator_template.py
git commit -m "feat(validation): add validator template with JSON/schema/business rule validation"
```

---

## Task 3: Create Discovery Script (Phase 1)

**Files:**
- Create: `tools/discover_validators.py`

**Step 1: Write discovery script with agent dispatch logic**

```python
"""
Validator Discovery Script
Dispatches agents to generate validator modules for all 95 API callsites.

Usage:
    python tools/discover_validators.py              # Generate all validators
    python tools/discover_validators.py --tasks T079,T082  # Specific tasks
    python tools/discover_validators.py --retry-failed     # Retry failed
"""
import argparse
import json
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def load_inventory(inventory_path: str) -> list:
    """Load API call inventory from JSON file."""
    with open(inventory_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_task_ids_to_process(args, inventory: list) -> list:
    """Determine which tasks to process based on arguments."""
    all_task_ids = [task['task_id'] for task in inventory]

    if args.tasks:
        # Specific tasks requested
        requested = [t.strip() for t in args.tasks.split(',')]
        return [t for t in requested if t in all_task_ids]

    if args.retry_failed:
        # Find tasks without validators
        validator_dir = PROJECT_ROOT / 'validators'
        existing = set()
        if validator_dir.exists():
            for file in validator_dir.glob('task_T*.py'):
                task_id = file.stem.replace('task_', '')
                existing.add(task_id)
        return [t for t in all_task_ids if t not in existing]

    # All tasks
    return all_task_ids


def generate_agent_prompt(task: dict) -> str:
    """Generate prompt for agent to create validator."""
    return f"""Analyze API callsite and generate validator module:

Task ID: {task['task_id']}
File: {task['path']}
Line: {task['line']}
Scope: {task['scope']}

Your task:
1. Read the file at {task['path']} around line {task['line']} to understand the API call
2. Look for capture file at model_captures/{task['task_id']}.json
3. Search for existing validators in core/validation/ that might be related
4. Extract:
   - Expected JSON schema from system prompt in capture file
   - Validation rules from callsite code (how response is used)
   - Business logic constraints from code context
5. Generate validators/task_{task['task_id']}.py using this template:

```python
\"\"\"
Validator for {task['task_id']}: {task['path']}:{task['line']}
Auto-generated by discover_validators.py

Purpose: [Describe what this API call does]
Expected output: [Describe expected JSON structure]
\"\"\"
import json
import re
from typing import Dict, List, Tuple, Optional, Any

TASK_ID = "{task['task_id']}"
FILE_PATH = "{task['path']}"
LINE_NUMBER = {task['line']}
TIER = "{'mini' if 'mini' in task.get('model_expr', '').lower() else 'full'}"

EXPECTED_SCHEMA = {{
    "type": "object",
    "required": [...],  # Extract from system prompt
    "properties": {{
        # Extract field definitions from system prompt
    }}
}}


def validate_json_structure(output_text: str) -> Tuple[bool, List[str]]:
    \"\"\"Validates JSON parsing and basic structure.\"\"\"
    errors = []

    # Check for markdown code blocks
    if "```json" in output_text or "```" in output_text:
        errors.append("Output contains markdown code blocks")
        match = re.search(r'```(?:json)?\\s*(\\{{.*?\\}})\\s*```', output_text, re.DOTALL)
        if match:
            output_text = match.group(1)
        else:
            return (False, errors)

    try:
        parsed = json.loads(output_text)
        if not isinstance(parsed, (dict, list)):
            errors.append(f"JSON root is not dict or list: {{type(parsed)}}")
            return (False, errors)
    except json.JSONDecodeError as e:
        errors.append(f"JSON parse error: {{str(e)}}")
        return (False, errors)

    return (True, errors)


def validate_schema_compliance(parsed_json: dict) -> Tuple[bool, List[str]]:
    \"\"\"Validates against expected schema.\"\"\"
    errors = []

    # Check required fields
    for field in EXPECTED_SCHEMA.get("required", []):
        if field not in parsed_json:
            errors.append(f"Missing required field: {{field}}")

    # Add specific field type checks based on EXPECTED_SCHEMA

    return (len(errors) == 0, errors)


def validate_business_rules(parsed_json: dict, input_data: Optional[dict] = None) -> Tuple[bool, List[str]]:
    \"\"\"Validates business logic specific to this API call.\"\"\"
    errors = []

    # Add specific business rule checks based on callsite code analysis
    # Example: if updating gold, check that math is correct

    return (len(errors) == 0, errors)


def validate_output(output_text: str,
                   input_data: Optional[dict] = None,
                   baseline_output: Optional[str] = None) -> Dict[str, Any]:
    \"\"\"Main validation entry point.\"\"\"
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

            try:
                baseline_json = json.loads(baseline_clean)

                # Compare keys
                variant_keys = set(parsed_json.keys())
                baseline_keys = set(baseline_json.keys())

                differences = []
                missing = baseline_keys - variant_keys
                extra = variant_keys - baseline_keys

                if missing:
                    differences.append(f"Missing keys: {{missing}}")
                if extra:
                    differences.append(f"Extra keys: {{extra}}")

                # Compare values
                for key in variant_keys & baseline_keys:
                    if parsed_json[key] != baseline_json[key]:
                        differences.append(f"Value mismatch for '{{key}}': {{parsed_json[key]}} != {{baseline_json[key]}}")

                result["checks"]["matches_baseline"] = (len(differences) == 0)
                result["details"]["baseline_differences"] = differences

                if differences:
                    result["warnings"].extend([f"Baseline difference: {{d}}" for d in differences])
            except Exception as e:
                result["checks"]["matches_baseline"] = None
                result["warnings"].append(f"Baseline comparison failed: {{str(e)}}")
        else:
            result["checks"]["matches_baseline"] = None
            result["warnings"].append("Baseline output is invalid JSON")
    else:
        result["checks"]["matches_baseline"] = None

    return result
```

Write the complete validator module to validators/task_{task['task_id']}.py

IMPORTANT:
- Read the callsite code carefully to understand what the API call does
- Extract the EXACT expected schema from the system prompt in the capture file
- Identify specific business rules from how the response is used in code
- Make the validator as specific as possible to this API call
"""


def create_stub_validator(task: dict, output_path: Path):
    """Create a minimal stub validator if agent fails."""
    stub_content = f'''"""
Validator for {task['task_id']}: {task['path']}:{task['line']}
STUB - Auto-generated by discover_validators.py (agent failed)

Purpose: Unknown (agent generation failed)
Expected output: JSON object
"""
import json
from typing import Dict, Optional, Any

TASK_ID = "{task['task_id']}"
FILE_PATH = "{task['path']}"
LINE_NUMBER = {task['line']}
TIER = "unknown"
EXPECTED_SCHEMA = {{}}


def validate_output(output_text: str,
                   input_data: Optional[dict] = None,
                   baseline_output: Optional[str] = None) -> Dict[str, Any]:
    """Minimal validation - JSON parsing only."""
    result = {{
        "valid": True,
        "errors": [],
        "warnings": ["STUB validator - limited validation"],
        "checks": {{}},
        "details": {{}}
    }}

    try:
        parsed = json.loads(output_text)
        result["checks"]["json_valid"] = True
        result["details"]["parsed_json"] = parsed
    except json.JSONDecodeError as e:
        result["valid"] = False
        result["errors"].append(f"JSON parse error: {{str(e)}}")
        result["checks"]["json_valid"] = False

    return result
'''

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(stub_content)


def main():
    parser = argparse.ArgumentParser(description='Generate validator modules for API callsites')
    parser.add_argument('--tasks', help='Comma-separated task IDs (e.g., T079,T082)')
    parser.add_argument('--retry-failed', action='store_true', help='Retry failed validators')
    parser.add_argument('--inventory', default='../dungeon_master_v1/docs/audit/2026-02-12-openai-api-call-inventory.json',
                       help='Path to API call inventory JSON')
    args = parser.parse_args()

    # Load inventory
    inventory_path = Path(args.inventory)
    if not inventory_path.exists():
        print(f"[ERROR] Inventory file not found: {inventory_path}")
        print("Checking alternate location...")
        inventory_path = Path('/mnt/c/dungeon_master_v1/docs/audit/2026-02-12-openai-api-call-inventory.json')
        if not inventory_path.exists():
            print(f"[ERROR] Inventory file not found at: {inventory_path}")
            return 1

    inventory = load_inventory(inventory_path)
    print(f"[OK] Loaded {len(inventory)} tasks from inventory")

    # Determine tasks to process
    task_ids = get_task_ids_to_process(args, inventory)
    print(f"[OK] Processing {len(task_ids)} tasks: {', '.join(task_ids[:10])}{'...' if len(task_ids) > 10 else ''}")

    # Create validators directory
    validator_dir = PROJECT_ROOT / 'validators'
    validator_dir.mkdir(exist_ok=True)

    # THIS IS WHERE WE DISPATCH AGENTS
    # For now, this is a placeholder - actual agent dispatch will be implemented
    # using Claude Code's Task tool in the real implementation

    print("\n" + "="*80)
    print("AGENT DISPATCH PLACEHOLDER")
    print("="*80)
    print("\nTo implement actual agent dispatch:")
    print("1. Use Claude Code's Task tool with subagent_type='general-purpose'")
    print("2. Dispatch all agents in parallel (single message with multiple Task calls)")
    print("3. Each agent receives the prompt from generate_agent_prompt()")
    print("4. Agents write output directly to validators/task_TXXX.py")
    print("5. Track completion and create stubs for failures")
    print("\nFor manual testing, create validators manually or use stub generation.")
    print("="*80 + "\n")

    # For now, just create stub validators for testing infrastructure
    success_count = 0
    for task_id in task_ids:
        task = next((t for t in inventory if t['task_id'] == task_id), None)
        if not task:
            print(f"[ERROR] Task {task_id} not found in inventory")
            continue

        output_path = validator_dir / f"task_{task_id}.py"

        # Create stub (in real implementation, agents would create these)
        create_stub_validator(task, output_path)
        print(f"[STUB] Created stub validator: {output_path.name}")
        success_count += 1

    print(f"\n[OK] Generated {success_count}/{len(task_ids)} validators")

    # Update validators/__init__.py
    init_file = validator_dir / '__init__.py'
    init_content = '"""Auto-generated validator imports"""\n\n'

    for task_id in task_ids:
        task = next((t for t in inventory if t['task_id'] == task_id), None)
        if task:
            init_content += f"from . import task_{task_id}\n"

    with open(init_file, 'w', encoding='utf-8') as f:
        f.write(init_content)

    print(f"[OK] Updated {init_file}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
```

Expected: `tools/discover_validators.py` created

**Step 2: Test discovery script with --tasks argument**

Run: `python tools/discover_validators.py --tasks T079,T082`
Expected: Creates stub validators for T079 and T082, updates __init__.py

**Step 3: Verify stub validators are importable**

```python
import sys
sys.path.insert(0, '/mnt/c/dungeon_master_v1_testing')
from validators import task_T079, task_T082

# Test import
print(f"T079 TASK_ID: {task_T079.TASK_ID}")
print(f"T082 TASK_ID: {task_T082.TASK_ID}")

# Test validation function
result = task_T079.validate_output('{"test": "data"}')
print(f"T079 validation result: {result['valid']}")
```

Expected: Both modules import successfully, validation runs

**Step 4: Commit discovery script**

```bash
git add tools/discover_validators.py
git commit -m "feat(validation): add validator discovery script with agent dispatch"
```

---

## Task 4: Create Analysis Script (Phase 2)

**Files:**
- Create: `tools/analyze_captures.py`

**Step 1: Write analysis script with validator execution**

```python
"""
Capture Analysis Script
Runs deterministic validation on all captured model outputs.

Usage:
    python tools/analyze_captures.py                    # Analyze all captures
    python tools/analyze_captures.py --tasks T079,T082  # Specific tasks
    python tools/analyze_captures.py --format html      # HTML report only
    python tools/analyze_captures.py --format json      # JSON report only
"""
import argparse
import importlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def load_capture_file(capture_path: Path) -> List[Dict]:
    """Load capture file and return list of capture entries."""
    try:
        with open(capture_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Capture files contain a list of capture entries
            if isinstance(data, list):
                return data
            else:
                return [data]  # Single entry
    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to parse {capture_path.name}: {e}")
        return []
    except Exception as e:
        print(f"[ERROR] Failed to load {capture_path.name}: {e}")
        return []


def get_validator_module(task_id: str):
    """Import validator module for task_id."""
    try:
        module_name = f"validators.task_{task_id}"
        return importlib.import_module(module_name)
    except ImportError:
        return None


def find_baseline_label(outputs: Dict) -> str:
    """Find baseline output label in outputs dict."""
    # Baseline is gpt-4.1 model
    for label in outputs.keys():
        if 'gpt-4.1' in label.lower() and 'baseline' in label.lower():
            return label
        if 'gpt-4.1' in label.lower():
            return label

    # Fallback: first output
    return list(outputs.keys())[0]


def analyze_capture_entry(validator_module, entry: Dict, task_id: str) -> Dict:
    """Analyze a single capture entry with all variants."""
    result = {
        "task_id": task_id,
        "timestamp": entry.get("timestamp", "unknown"),
        "input": entry.get("input", {}),
        "baseline": {},
        "variants": {}
    }

    outputs = entry.get("outputs", {})
    if not outputs:
        result["error"] = "No outputs in capture entry"
        return result

    # Find baseline
    baseline_label = find_baseline_label(outputs)
    baseline_data = outputs[baseline_label]

    # Validate baseline
    if "content" in baseline_data:
        baseline_validation = validator_module.validate_output(
            baseline_data["content"],
            entry.get("input")
        )
        result["baseline"] = {
            "label": baseline_label,
            "output": baseline_data["content"],
            "latency_s": baseline_data.get("latency_s"),
            "validation": baseline_validation
        }
    elif "error" in baseline_data:
        result["baseline"] = {
            "label": baseline_label,
            "error": baseline_data["error"]
        }

    # Validate each variant
    for variant_label, variant_data in outputs.items():
        if variant_label == baseline_label:
            continue

        if "content" in variant_data:
            validation = validator_module.validate_output(
                variant_data["content"],
                entry.get("input"),
                baseline_output=baseline_data.get("content")
            )
            result["variants"][variant_label] = {
                "output": variant_data["content"],
                "latency_s": variant_data.get("latency_s"),
                "validation": validation
            }
        elif "error" in variant_data:
            result["variants"][variant_label] = {
                "error": variant_data["error"]
            }

    return result


def analyze_task(task_id: str, capture_dir: Path) -> Dict:
    """Analyze all captures for a single task."""
    result = {
        "task_id": task_id,
        "captures": [],
        "summary": {
            "total_captures": 0,
            "total_variants": 0,
            "variants_passed": 0,
            "variants_failed": 0,
            "api_errors": 0
        }
    }

    # Load validator
    validator = get_validator_module(task_id)
    if not validator:
        result["error"] = f"No validator found for {task_id}"
        return result

    # Load capture file
    capture_file = capture_dir / f"{task_id}.json"
    if not capture_file.exists():
        result["error"] = f"No capture file found: {capture_file.name}"
        return result

    entries = load_capture_file(capture_file)
    if not entries:
        result["error"] = "No capture entries found"
        return result

    # Analyze each capture entry
    for entry in entries:
        capture_result = analyze_capture_entry(validator, entry, task_id)
        result["captures"].append(capture_result)

        # Update summary
        result["summary"]["total_captures"] += 1

        # Count variants
        for variant_data in capture_result.get("variants", {}).values():
            if "validation" in variant_data:
                result["summary"]["total_variants"] += 1
                if variant_data["validation"]["valid"]:
                    result["summary"]["variants_passed"] += 1
                else:
                    result["summary"]["variants_failed"] += 1
            elif "error" in variant_data:
                result["summary"]["api_errors"] += 1

    return result


def generate_json_reports(results: List[Dict], output_dir: Path):
    """Generate JSON reports."""
    details_dir = output_dir / 'details'
    details_dir.mkdir(parents=True, exist_ok=True)

    # Per-task detailed reports
    for task_result in results:
        task_id = task_result["task_id"]
        detail_file = details_dir / f"{task_id}_validation.json"

        with open(detail_file, 'w', encoding='utf-8') as f:
            json.dump(task_result, f, indent=2)

    # Summary report
    summary = {
        "generated_at": datetime.now().isoformat(),
        "total_tasks": len(results),
        "total_captures": sum(r["summary"]["total_captures"] for r in results if "summary" in r),
        "total_variants": sum(r["summary"]["total_variants"] for r in results if "summary" in r),
        "variants_passed": sum(r["summary"]["variants_passed"] for r in results if "summary" in r),
        "variants_failed": sum(r["summary"]["variants_failed"] for r in results if "summary" in r),
        "api_errors": sum(r["summary"]["api_errors"] for r in results if "summary" in r),
        "tasks": []
    }

    for task_result in results:
        summary["tasks"].append({
            "task_id": task_result["task_id"],
            "total_captures": task_result.get("summary", {}).get("total_captures", 0),
            "variants_passed": task_result.get("summary", {}).get("variants_passed", 0),
            "variants_failed": task_result.get("summary", {}).get("variants_failed", 0),
            "api_errors": task_result.get("summary", {}).get("api_errors", 0),
            "error": task_result.get("error")
        })

    summary_file = output_dir / 'validation_summary.json'
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)

    print(f"[OK] JSON reports written to {output_dir}")
    return summary


def generate_html_report(summary: Dict, output_dir: Path):
    """Generate HTML dashboard report."""
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Validation Report - {summary['generated_at']}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background-color: #2c3e50;
            color: white;
            padding: 20px;
            border-radius: 5px;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }}
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .stat-value {{
            font-size: 2em;
            font-weight: bold;
            color: #3498db;
        }}
        .stat-label {{
            color: #7f8c8d;
            margin-top: 5px;
        }}
        .pass {{ color: #27ae60; }}
        .fail {{ color: #e74c3c; }}
        .error {{ color: #f39c12; }}
        table {{
            width: 100%;
            background: white;
            border-collapse: collapse;
            margin-top: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ecf0f1;
        }}
        th {{
            background-color: #34495e;
            color: white;
        }}
        tr:hover {{
            background-color: #f8f9fa;
        }}
        .task-link {{
            color: #3498db;
            text-decoration: none;
        }}
        .task-link:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Multi-Model Capture Validation Report</h1>
        <p>Generated: {summary['generated_at']}</p>
    </div>

    <div class="summary">
        <div class="stat-card">
            <div class="stat-value">{summary['total_tasks']}</div>
            <div class="stat-label">Total Tasks</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{summary['total_captures']}</div>
            <div class="stat-label">Total Captures</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{summary['total_variants']}</div>
            <div class="stat-label">Total Variants Tested</div>
        </div>
        <div class="stat-card pass">
            <div class="stat-value pass">{summary['variants_passed']}</div>
            <div class="stat-label">Variants Passed</div>
        </div>
        <div class="stat-card fail">
            <div class="stat-value fail">{summary['variants_failed']}</div>
            <div class="stat-label">Variants Failed</div>
        </div>
        <div class="stat-card error">
            <div class="stat-value error">{summary['api_errors']}</div>
            <div class="stat-label">API Errors</div>
        </div>
    </div>

    <table>
        <thead>
            <tr>
                <th>Task ID</th>
                <th>Captures</th>
                <th>Passed</th>
                <th>Failed</th>
                <th>API Errors</th>
                <th>Status</th>
            </tr>
        </thead>
        <tbody>
"""

    for task in summary['tasks']:
        status = "ERROR" if task.get('error') else "OK"
        status_class = "error" if task.get('error') else ""

        html_content += f"""
            <tr>
                <td><a href="details/{task['task_id']}_validation.json" class="task-link">{task['task_id']}</a></td>
                <td>{task.get('total_captures', 0)}</td>
                <td class="pass">{task.get('variants_passed', 0)}</td>
                <td class="fail">{task.get('variants_failed', 0)}</td>
                <td class="error">{task.get('api_errors', 0)}</td>
                <td class="{status_class}">{status}</td>
            </tr>
"""

    html_content += """
        </tbody>
    </table>
</body>
</html>
"""

    html_file = output_dir / 'validation_summary.html'
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"[OK] HTML report written to {html_file}")


def main():
    parser = argparse.ArgumentParser(description='Analyze multi-model capture data')
    parser.add_argument('--tasks', help='Comma-separated task IDs (e.g., T079,T082)')
    parser.add_argument('--format', choices=['html', 'json', 'both'], default='both',
                       help='Report format')
    parser.add_argument('--capture-dir', default='model_captures',
                       help='Directory containing capture files')
    parser.add_argument('--output-dir', default='reports',
                       help='Output directory for reports')
    args = parser.parse_args()

    capture_dir = PROJECT_ROOT / args.capture_dir
    output_dir = PROJECT_ROOT / args.output_dir

    if not capture_dir.exists():
        print(f"[ERROR] Capture directory not found: {capture_dir}")
        return 1

    # Determine which tasks to process
    if args.tasks:
        task_ids = [t.strip() for t in args.tasks.split(',')]
    else:
        # Find all capture files
        task_ids = []
        for capture_file in capture_dir.glob('T*.json'):
            task_id = capture_file.stem
            task_ids.append(task_id)
        task_ids.sort()

    print(f"[OK] Analyzing {len(task_ids)} tasks")

    # Analyze each task
    results = []
    for task_id in task_ids:
        print(f"[ANALYZING] {task_id}...", end=' ')
        result = analyze_task(task_id, capture_dir)
        results.append(result)

        if "error" in result:
            print(f"[ERROR] {result['error']}")
        else:
            print(f"[OK] {result['summary']['total_captures']} captures, "
                  f"{result['summary']['variants_passed']} passed, "
                  f"{result['summary']['variants_failed']} failed")

    # Generate reports
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.format in ['json', 'both']:
        summary = generate_json_reports(results, output_dir)
    else:
        # Need summary for HTML
        summary = {
            "generated_at": datetime.now().isoformat(),
            "total_tasks": len(results),
            "total_captures": sum(r["summary"]["total_captures"] for r in results if "summary" in r),
            "total_variants": sum(r["summary"]["total_variants"] for r in results if "summary" in r),
            "variants_passed": sum(r["summary"]["variants_passed"] for r in results if "summary" in r),
            "variants_failed": sum(r["summary"]["variants_failed"] for r in results if "summary" in r),
            "api_errors": sum(r["summary"]["api_errors"] for r in results if "summary" in r),
            "tasks": [{"task_id": r["task_id"],
                       "total_captures": r.get("summary", {}).get("total_captures", 0),
                       "variants_passed": r.get("summary", {}).get("variants_passed", 0),
                       "variants_failed": r.get("summary", {}).get("variants_failed", 0),
                       "api_errors": r.get("summary", {}).get("api_errors", 0),
                       "error": r.get("error")} for r in results]
        }

    if args.format in ['html', 'both']:
        generate_html_report(summary, output_dir)

    print(f"\n[OK] Analysis complete!")
    print(f"[OK] Summary: {summary['variants_passed']}/{summary['total_variants']} variants passed")

    return 0


if __name__ == '__main__':
    sys.exit(main())
```

Expected: `tools/analyze_captures.py` created

**Step 2: Test analysis script with existing captures**

Run: `python tools/analyze_captures.py --tasks T079,T082 --format json`
Expected: Creates validation_summary.json and details/T079_validation.json, details/T082_validation.json

**Step 3: Test HTML report generation**

Run: `python tools/analyze_captures.py --tasks T079,T082 --format html`
Expected: Creates validation_summary.html with dashboard

**Step 4: Commit analysis script**

```bash
git add tools/analyze_captures.py
git commit -m "feat(validation): add capture analysis script with HTML/JSON reporting"
```

---

## Task 5: Integration Testing

**Files:**
- Create: `test_validation_system.py`

**Step 1: Write integration test**

```python
"""Integration test for validation system."""
import sys
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_discovery_phase():
    """Test validator discovery and generation."""
    print("\n=== Testing Discovery Phase ===")

    # Run discovery for small subset
    result = subprocess.run(
        ["python", "tools/discover_validators.py", "--tasks", "T079,T082"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True
    )

    print(result.stdout)
    if result.returncode != 0:
        print(f"[FAIL] Discovery failed: {result.stderr}")
        return False

    # Check validators were created
    validator_dir = PROJECT_ROOT / 'validators'
    if not (validator_dir / 'task_T079.py').exists():
        print("[FAIL] task_T079.py not created")
        return False
    if not (validator_dir / 'task_T082.py').exists():
        print("[FAIL] task_T082.py not created")
        return False

    # Test import
    try:
        from validators import task_T079, task_T082
        print(f"[PASS] Validators importable: T079={task_T079.TASK_ID}, T082={task_T082.TASK_ID}")
    except ImportError as e:
        print(f"[FAIL] Import failed: {e}")
        return False

    return True


def test_analysis_phase():
    """Test capture analysis."""
    print("\n=== Testing Analysis Phase ===")

    # Check if captures exist
    capture_dir = PROJECT_ROOT / 'model_captures'
    if not capture_dir.exists():
        print("[SKIP] No model_captures/ directory, skipping analysis test")
        return True

    capture_files = list(capture_dir.glob('T*.json'))
    if not capture_files:
        print("[SKIP] No capture files found, skipping analysis test")
        return True

    # Run analysis
    result = subprocess.run(
        ["python", "tools/analyze_captures.py", "--format", "both"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True
    )

    print(result.stdout)
    if result.returncode != 0:
        print(f"[FAIL] Analysis failed: {result.stderr}")
        return False

    # Check reports were created
    reports_dir = PROJECT_ROOT / 'reports'
    if not (reports_dir / 'validation_summary.json').exists():
        print("[FAIL] validation_summary.json not created")
        return False
    if not (reports_dir / 'validation_summary.html').exists():
        print("[FAIL] validation_summary.html not created")
        return False

    print("[PASS] Reports generated successfully")
    return True


def test_validator_functionality():
    """Test validator functions work correctly."""
    print("\n=== Testing Validator Functionality ===")

    from validators.validator_template import validate_output

    # Test 1: Valid JSON
    result = validate_output('{"action": "test"}')
    if not result['valid'] or not result['checks']['json_valid']:
        print(f"[FAIL] Valid JSON test failed: {result}")
        return False
    print("[PASS] Valid JSON test")

    # Test 2: JSON in code block with warning
    result = validate_output('```json\n{"action": "test"}\n```')
    if not result['valid'] or len(result['warnings']) == 0:
        print(f"[FAIL] Code block test failed: {result}")
        return False
    print("[PASS] Code block extraction test")

    # Test 3: Invalid JSON
    result = validate_output('This is not JSON')
    if result['valid'] or result['checks']['json_valid']:
        print(f"[FAIL] Invalid JSON test failed: {result}")
        return False
    print("[PASS] Invalid JSON test")

    return True


def main():
    """Run all integration tests."""
    print("="*80)
    print("Multi-Model Capture Validation System - Integration Tests")
    print("="*80)

    tests = [
        ("Validator Functionality", test_validator_functionality),
        ("Discovery Phase", test_discovery_phase),
        ("Analysis Phase", test_analysis_phase),
    ]

    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n[ERROR] {name} crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} {name}")

    total_passed = sum(1 for _, p in results if p)
    print(f"\n{total_passed}/{len(results)} test suites passed")

    return 0 if total_passed == len(results) else 1


if __name__ == '__main__':
    sys.exit(main())
```

Expected: `test_validation_system.py` created

**Step 2: Run integration tests**

Run: `python test_validation_system.py`
Expected: All tests pass or skip gracefully if no captures exist

**Step 3: Commit integration test**

```bash
git add test_validation_system.py
git commit -m "test(validation): add integration tests for validation system"
```

---

## Task 6: Documentation and Usage Guide

**Files:**
- Create: `docs/plans/2026-02-22-validation-usage-guide.md`

**Step 1: Write usage guide**

```markdown
# Multi-Model Capture Validation System - Usage Guide

## Quick Start

### Initial Setup (One-Time)

Generate validators for all 95 API callsites:

\`\`\`bash
cd /mnt/c/dungeon_master_v1_testing
python tools/discover_validators.py
\`\`\`

Expected output:
- `validators/task_T001.py` through `validators/task_T095.py` created
- Progress messages showing completion: "Generated 95/95 validators"

### Running Analysis

After playing the game and collecting capture data:

\`\`\`bash
# Analyze all captures
python tools/analyze_captures.py

# Analyze specific tasks
python tools/analyze_captures.py --tasks T079,T082

# Generate only HTML report
python tools/analyze_captures.py --format html

# Generate only JSON reports
python tools/analyze_captures.py --format json
\`\`\`

### Viewing Results

**HTML Dashboard:**
Open `reports/validation_summary.html` in a browser for interactive overview.

**JSON Summary:**
Read `reports/validation_summary.json` for machine-readable summary.

**Detailed Per-Task Reports:**
Drill into `reports/details/T079_validation.json` for specific task analysis.

## Command Reference

### discover_validators.py

\`\`\`bash
# Generate all validators
python tools/discover_validators.py

# Generate specific validators
python tools/discover_validators.py --tasks T079,T082,T067

# Retry failed validators from previous run
python tools/discover_validators.py --retry-failed

# Specify custom inventory location
python tools/discover_validators.py --inventory /path/to/inventory.json
\`\`\`

### analyze_captures.py

\`\`\`bash
# Analyze all captures with both HTML and JSON reports
python tools/analyze_captures.py

# Analyze specific tasks
python tools/analyze_captures.py --tasks T079,T082

# Generate only HTML report
python tools/analyze_captures.py --format html

# Generate only JSON reports
python tools/analyze_captures.py --format json

# Specify custom directories
python tools/analyze_captures.py --capture-dir /path/to/captures --output-dir /path/to/reports
\`\`\`

## Report Structure

### HTML Dashboard

Shows:
- Total tasks analyzed
- Total captures processed
- Overall pass/fail rates
- API error counts
- Per-task drill-down links

### JSON Summary (validation_summary.json)

\`\`\`json
{
  "generated_at": "2026-02-22T10:30:00",
  "total_tasks": 95,
  "total_captures": 285,
  "total_variants": 4275,
  "variants_passed": 4100,
  "variants_failed": 133,
  "api_errors": 42,
  "tasks": [...]
}
\`\`\`

### Detailed Task Report (details/T079_validation.json)

\`\`\`json
{
  "task_id": "T079",
  "total_captures": 3,
  "captures": [
    {
      "timestamp": "2026-02-22T07:44:52Z",
      "baseline": {
        "validation": {"valid": true, "checks": {...}}
      },
      "variants": {
        "gpt-5-mini|minimal": {
          "latency_s": 1.502,
          "validation": {
            "valid": true,
            "matches_baseline": true,
            "errors": [],
            "warnings": []
          }
        }
      }
    }
  ]
}
\`\`\`

## Workflow Examples

### Example 1: Initial Validation Run

\`\`\`bash
# 1. Generate validators (first time only)
python tools/discover_validators.py

# 2. Play game to collect captures
python run_web.py
# ... interact with game ...

# 3. Run analysis
python tools/analyze_captures.py

# 4. View results
open reports/validation_summary.html
\`\`\`

### Example 2: Investigating Failures

\`\`\`bash
# 1. Identify failing task from HTML dashboard (e.g., T079)

# 2. Read detailed report
cat reports/details/T079_validation.json

# 3. Check specific variant output
python -c "
import json
with open('reports/details/T079_validation.json') as f:
    data = json.load(f)
    variant = data['captures'][0]['variants']['gemini-3-flash|high']
    print(variant['validation']['errors'])
"

# 4. Re-run analysis for just this task
python tools/analyze_captures.py --tasks T079
\`\`\`

### Example 3: Regenerating Validators After Code Changes

\`\`\`bash
# 1. Make code changes to API callsite

# 2. Regenerate affected validators
python tools/discover_validators.py --tasks T079,T082

# 3. Re-run analysis
python tools/analyze_captures.py --tasks T079,T082

# 4. Compare results
open reports/validation_summary.html
\`\`\`

## Troubleshooting

### No validators found

**Error:** `No validator found for T079`

**Solution:**
\`\`\`bash
python tools/discover_validators.py --tasks T079
\`\`\`

### Import errors

**Error:** `ImportError: cannot import name 'task_T079'`

**Solution:** Regenerate validators and check `validators/__init__.py` is updated.

### Malformed captures

**Error:** `Failed to parse T079.json`

**Solution:** Check capture file is valid JSON. Delete corrupt file and recapture.

### Missing capture files

**Warning:** `No capture file found: T079.json`

**Solution:** Play game to generate captures for that callsite, or exclude with `--tasks`.

## Testing

Run integration tests:

\`\`\`bash
python test_validation_system.py
\`\`\`

Expected: All tests pass or skip gracefully.
\`\`\`

Expected: Usage guide created

**Step 2: Commit documentation**

```bash
git add docs/plans/2026-02-22-validation-usage-guide.md
git commit -m "docs(validation): add usage guide for validation system"
```

---

## Final Task: Verification and Handoff

**Step 1: Run full integration test**

```bash
python test_validation_system.py
```

Expected: All tests pass

**Step 2: Verify directory structure**

```bash
ls -R validators/ tools/ reports/
```

Expected: All directories and key files exist

**Step 3: Create final summary commit**

```bash
git add -A
git commit -m "feat(validation): complete multi-model capture validation system

Implements two-phase validation system:
- Phase 1: Agent-generated validator discovery
- Phase 2: On-demand deterministic analysis

Components:
- validators/: Auto-generated validation modules
- tools/discover_validators.py: Agent dispatch script
- tools/analyze_captures.py: Analysis and reporting
- reports/: HTML and JSON output

See docs/plans/2026-02-22-validation-usage-guide.md for usage."
```

**Step 4: Verification checklist**

- [ ] `validators/` directory exists with `__init__.py`
- [ ] `validators/validator_template.py` has complete validation logic
- [ ] `tools/discover_validators.py` can generate stub validators
- [ ] `tools/analyze_captures.py` can analyze captures and generate reports
- [ ] `test_validation_system.py` runs successfully
- [ ] `docs/plans/2026-02-22-validation-usage-guide.md` exists
- [ ] All commits follow conventional commit format
- [ ] No Unicode characters in Python code

---

## Notes

### Agent Dispatch Implementation (Task 3)

The `discover_validators.py` script contains a placeholder for agent dispatch. To implement real agent dispatch:

1. Use Claude Code's `Task` tool with `subagent_type="general-purpose"`
2. Dispatch all 95 agents in parallel (single message with multiple Task calls)
3. Each agent receives prompt from `generate_agent_prompt(task)`
4. Agents write output directly to `validators/task_TXXX.py`

For now, the script creates stub validators for testing infrastructure.

### Dependencies

- Python 3.10+
- Standard library only (json, glob, importlib, argparse, pathlib, re, datetime)
- Optional: Jinja2 for enhanced HTML templates (current implementation uses plain HTML)

### Performance Expectations

- **Discovery Phase:** ~5-10 minutes for 95 validators (with real agents)
- **Analysis Phase:** <1 second per capture entry
- **Total Analysis:** <30 seconds for 95 tasks with 3 captures each

### Success Criteria

✅ All directories created
✅ Validator template functional
✅ Discovery script creates validators
✅ Analysis script generates reports
✅ Integration tests pass
✅ Documentation complete
