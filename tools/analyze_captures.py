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
