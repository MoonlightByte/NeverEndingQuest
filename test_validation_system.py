#!/usr/bin/env python3
"""
Integration Tests for Multi-Model Validation System

Tests the complete validation pipeline:
1. Validator template functions
2. Validator discovery and generation
3. Capture analysis

Usage:
    python test_validation_system.py
"""
import sys
import json
import subprocess
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from validators.validator_template import (
    validate_json_structure,
    validate_schema_compliance,
    validate_business_rules,
    compare_to_baseline,
    validate_output
)


def test_validator_functionality():
    """Test validator template functions."""
    print("\n" + "=" * 60)
    print("TEST SUITE 1: Validator Template Functionality")
    print("=" * 60)

    tests_passed = 0
    tests_failed = 0

    # Test 1: Valid JSON parsing
    print("\n[TEST 1.1] Valid JSON parsing")
    output1 = '{"action": "move", "direction": "north"}'
    valid, errors = validate_json_structure(output1)
    if valid and len(errors) == 0:
        print("[PASS] Valid JSON accepted")
        tests_passed += 1
    else:
        print(f"[FAIL] Valid JSON rejected: {errors}")
        tests_failed += 1

    # Test 2: JSON in code block (should extract with warning)
    print("\n[TEST 1.2] JSON in markdown code block")
    output2 = '```json\n{"action": "attack", "target": "goblin"}\n```'
    valid, errors = validate_json_structure(output2)
    if valid and "markdown code blocks" in errors[0]:
        print("[PASS] Code block detected with warning")
        tests_passed += 1
    else:
        print(f"[FAIL] Code block not handled correctly: {errors}")
        tests_failed += 1

    # Test 3: Invalid JSON
    print("\n[TEST 1.3] Invalid JSON rejection")
    output3 = 'This is not JSON at all'
    valid, errors = validate_json_structure(output3)
    if not valid and len(errors) > 0:
        print("[PASS] Invalid JSON rejected")
        tests_passed += 1
    else:
        print("[FAIL] Invalid JSON accepted")
        tests_failed += 1

    # Test 4: Schema validation - required fields
    print("\n[TEST 1.4] Schema validation - required fields")
    schema = {
        "required": ["action", "target"],
        "properties": {
            "action": {"type": "string"},
            "target": {"type": "string"}
        }
    }
    valid_json = {"action": "attack", "target": "goblin"}
    valid, errors = validate_schema_compliance(valid_json, schema)
    if valid:
        print("[PASS] Valid schema accepted")
        tests_passed += 1
    else:
        print(f"[FAIL] Valid schema rejected: {errors}")
        tests_failed += 1

    # Test 5: Schema validation - missing required field
    print("\n[TEST 1.5] Schema validation - missing field")
    invalid_json = {"action": "attack"}  # missing "target"
    valid, errors = validate_schema_compliance(invalid_json, schema)
    if not valid and any("target" in err for err in errors):
        print("[PASS] Missing required field detected")
        tests_passed += 1
    else:
        print(f"[FAIL] Missing field not detected: {errors}")
        tests_failed += 1

    # Test 6: Baseline comparison - identical
    print("\n[TEST 1.6] Baseline comparison - identical")
    variant = {"action": "move", "direction": "north"}
    baseline = {"action": "move", "direction": "north"}
    equivalent, diffs = compare_to_baseline(variant, baseline)
    if equivalent:
        print("[PASS] Identical outputs matched")
        tests_passed += 1
    else:
        print(f"[FAIL] Identical outputs not matched: {diffs}")
        tests_failed += 1

    # Test 7: Baseline comparison - different
    print("\n[TEST 1.7] Baseline comparison - different")
    variant = {"action": "move", "direction": "south"}
    baseline = {"action": "move", "direction": "north"}
    equivalent, diffs = compare_to_baseline(variant, baseline)
    if not equivalent and len(diffs) > 0:
        print("[PASS] Different outputs detected")
        tests_passed += 1
    else:
        print("[FAIL] Different outputs not detected")
        tests_failed += 1

    # Test 8: Full validation pipeline
    print("\n[TEST 1.8] Full validation pipeline")
    output = '{"action": "cast_spell", "spell": "fireball"}'
    result = validate_output(output)
    if result['valid'] and result['checks']['json_valid']:
        print("[PASS] Full validation pipeline works")
        tests_passed += 1
    else:
        print(f"[FAIL] Full validation failed: {result}")
        tests_failed += 1

    print("\n" + "-" * 60)
    print(f"Suite 1 Results: {tests_passed} passed, {tests_failed} failed")
    return tests_passed, tests_failed


def test_discovery_phase():
    """Test validator discovery and generation."""
    print("\n" + "=" * 60)
    print("TEST SUITE 2: Validator Discovery Phase")
    print("=" * 60)

    tests_passed = 0
    tests_failed = 0

    # Test 1: Run discovery for specific tasks
    print("\n[TEST 2.1] Validator generation for T079,T082")
    try:
        result = subprocess.run(
            [sys.executable, "tools/discover_validators.py", "--tasks", "T079,T082"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            print("[PASS] Discovery script executed successfully")
            tests_passed += 1

            # Check if validators were created
            validators_created = True
            for task_id in ["T079", "T082"]:
                validator_path = PROJECT_ROOT / "validators" / f"task_{task_id}.py"
                if not validator_path.exists():
                    print(f"[WARN] Validator not found: task_{task_id}.py")
                    validators_created = False

            if validators_created:
                print("[PASS] Validators created for both tasks")
                tests_passed += 1
            else:
                print("[FAIL] Some validators were not created")
                tests_failed += 1
        else:
            print(f"[FAIL] Discovery script failed: {result.stderr}")
            tests_failed += 2
    except subprocess.TimeoutExpired:
        print("[FAIL] Discovery script timed out")
        tests_failed += 2
    except Exception as e:
        print(f"[FAIL] Discovery test error: {e}")
        tests_failed += 2

    # Test 2: Verify validator imports work
    print("\n[TEST 2.2] Validator imports")
    try:
        import importlib
        for task_id in ["T079", "T082"]:
            validator_path = PROJECT_ROOT / "validators" / f"task_{task_id}.py"
            if validator_path.exists():
                module = importlib.import_module(f"validators.task_{task_id}")
                if hasattr(module, 'validate_output'):
                    print(f"[PASS] task_{task_id} imports and has validate_output")
                    tests_passed += 1
                else:
                    print(f"[FAIL] task_{task_id} missing validate_output function")
                    tests_failed += 1
            else:
                print(f"[SKIP] task_{task_id} not found, skipping import test")
    except Exception as e:
        print(f"[FAIL] Import test error: {e}")
        tests_failed += 1

    print("\n" + "-" * 60)
    print(f"Suite 2 Results: {tests_passed} passed, {tests_failed} failed")
    return tests_passed, tests_failed


def test_analysis_phase():
    """Test capture analysis."""
    print("\n" + "=" * 60)
    print("TEST SUITE 3: Capture Analysis Phase")
    print("=" * 60)

    tests_passed = 0
    tests_failed = 0

    # Check if captures exist
    captures_dir = PROJECT_ROOT / "model_captures"
    if not captures_dir.exists():
        print("[SKIP] No model_captures directory, skipping analysis tests")
        return 0, 0

    capture_files = list(captures_dir.glob("T*.json"))
    if not capture_files:
        print("[SKIP] No capture files found, skipping analysis tests")
        return 0, 0

    print(f"[OK] Found {len(capture_files)} capture files")

    # Test 1: Run analysis on all captures
    print("\n[TEST 3.1] Analyze all captures (JSON format)")
    try:
        result = subprocess.run(
            [sys.executable, "tools/analyze_captures.py", "--format", "json"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0:
            print("[PASS] Analysis script executed successfully")
            tests_passed += 1

            # Check if JSON report was created
            json_report_path = PROJECT_ROOT / "reports" / "validation_summary.json"
            if json_report_path.exists():
                print("[PASS] JSON report created")
                tests_passed += 1

                # Verify report structure
                with open(json_report_path, 'r') as f:
                    report = json.load(f)
                    if "generated_at" in report and "tasks" in report and "total_tasks" in report:
                        print("[PASS] Report has correct structure")
                        tests_passed += 1
                    else:
                        print(f"[FAIL] Report missing required fields: {list(report.keys())}")
                        tests_failed += 1
            else:
                print("[FAIL] JSON report not created")
                tests_failed += 1
        else:
            print(f"[FAIL] Analysis script failed: {result.stderr}")
            tests_failed += 3
    except subprocess.TimeoutExpired:
        print("[FAIL] Analysis script timed out")
        tests_failed += 3
    except Exception as e:
        print(f"[FAIL] Analysis test error: {e}")
        tests_failed += 3

    # Test 2: Run analysis with HTML format
    print("\n[TEST 3.2] Analyze captures (HTML format)")
    try:
        result = subprocess.run(
            [sys.executable, "tools/analyze_captures.py", "--format", "html"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0:
            print("[PASS] HTML analysis executed successfully")
            tests_passed += 1

            # Check if HTML report was created
            html_report_path = PROJECT_ROOT / "reports" / "validation_summary.html"
            if html_report_path.exists():
                print("[PASS] HTML report created")
                tests_passed += 1
            else:
                print("[FAIL] HTML report not created")
                tests_failed += 1
        else:
            print(f"[FAIL] HTML analysis failed: {result.stderr}")
            tests_failed += 2
    except subprocess.TimeoutExpired:
        print("[FAIL] HTML analysis timed out")
        tests_failed += 2
    except Exception as e:
        print(f"[FAIL] HTML analysis error: {e}")
        tests_failed += 2

    # Test 3: Analyze specific tasks
    print("\n[TEST 3.3] Analyze specific tasks")
    try:
        result = subprocess.run(
            [sys.executable, "tools/analyze_captures.py", "--tasks", "T079,T082", "--format", "json"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            print("[PASS] Task-specific analysis executed successfully")
            tests_passed += 1
        else:
            print(f"[FAIL] Task-specific analysis failed: {result.stderr}")
            tests_failed += 1
    except subprocess.TimeoutExpired:
        print("[FAIL] Task-specific analysis timed out")
        tests_failed += 1
    except Exception as e:
        print(f"[FAIL] Task-specific analysis error: {e}")
        tests_failed += 1

    print("\n" + "-" * 60)
    print(f"Suite 3 Results: {tests_passed} passed, {tests_failed} failed")
    return tests_passed, tests_failed


def main():
    """Run all integration tests."""
    print("=" * 60)
    print("MULTI-MODEL VALIDATION SYSTEM - INTEGRATION TESTS")
    print("=" * 60)

    total_passed = 0
    total_failed = 0

    # Suite 1: Template functionality
    passed, failed = test_validator_functionality()
    total_passed += passed
    total_failed += failed

    # Suite 2: Discovery phase
    passed, failed = test_discovery_phase()
    total_passed += passed
    total_failed += failed

    # Suite 3: Analysis phase
    passed, failed = test_analysis_phase()
    total_passed += passed
    total_failed += failed

    # Final summary
    print("\n" + "=" * 60)
    print("FINAL TEST RESULTS")
    print("=" * 60)
    print(f"Total Passed: {total_passed}")
    print(f"Total Failed: {total_failed}")
    print(f"Success Rate: {total_passed}/{total_passed + total_failed} " +
          f"({100 * total_passed / (total_passed + total_failed) if (total_passed + total_failed) > 0 else 0:.1f}%)")

    if total_failed == 0:
        print("\n[SUCCESS] All integration tests passed!")
        return 0
    else:
        print(f"\n[FAILURE] {total_failed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
