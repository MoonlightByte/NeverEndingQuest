#!/usr/bin/env python3
"""
OpenRouter Migration Script - Phase 1B (FIXED)
Automatically migrates model references to use 3-tier OpenRouter system

USAGE:
    python scripts/migrate_to_openrouter.py [--dry-run] [--file FILE]
    python scripts/migrate_to_openrouter.py --dry-run          # Preview all changes
    python scripts/migrate_to_openrouter.py --file main.py     # Migrate single file
    python scripts/migrate_to_openrouter.py --test            # Run unit tests

FEATURES:
    - Surgical line replacement (preserves all other parameters)
    - Preserves explicit temperature settings
    - AST-based detection (preserves formatting)
    - Upstream merge compatible
    - Creates .bak backups
    - Validates Python syntax after migration
    - Marked with # OPENROUTER: comments for easy identification
    - Prevents duplicate migration

SAFETY:
    - Always use --dry-run first to preview changes
    - Creates backups before modifying files
    - Validates Python syntax after migration
    - Auto-restores backup on validation failure
    - Preserves all original constants and structure
    - Never migrates already-migrated files

MERGE COMPATIBILITY:
    - Original OpenAI constants remain unchanged
    - Added lines marked with # OPENROUTER: comments
    - Easy conflict resolution during upstream merges
    - 100% backward compatible (non-migrated files still work)

FIXED BUGS (from v1):
    - Surgical line replacement instead of full function replacement
    - Preserves explicit temperature settings
    - Fixed task ID mappings to match THINKING_ENABLED_TASKS
    - Removed Unicode characters (Windows console compatible)
    - Prevents duplicate migration
"""

import ast
import sys
import os
import argparse
import shutil
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# Model constant to task_id mapping (matches THINKING_ENABLED_TASKS in model_config.py)
MODEL_TASK_MAP = {
    # Full models (complex reasoning) - thinking: enabled
    'DM_MAIN_MODEL': 'dm_main',
    'DM_VALIDATION_MODEL': 'dm_validation',
    'COMBAT_MAIN_MODEL': 'combat_main',
    'ACTION_PREDICTION_MODEL': 'action_prediction',
    'CHARACTER_VALIDATOR_MODEL': 'character_validator',
    'NPC_BUILDER_MODEL': 'npc_builder',
    'MONSTER_BUILDER_MODEL': 'monster_builder',
    'LEVEL_UP_MODEL': 'level_up',
    'DM_FULL_MODEL': 'dm_full',
    'LOCATION_COMPRESSION_MODEL': 'location_compression',

    # Mini models (simple tasks) - thinking: disabled
    'DM_SUMMARIZATION_MODEL': 'summaries',
    'COMBAT_DIALOGUE_SUMMARY_MODEL': 'combat_dialogue_summary',
    'ADVENTURE_SUMMARY_MODEL': 'adventure_summary',
    'PLOT_UPDATE_MODEL': 'plot_update',
    'PLAYER_INFO_UPDATE_MODEL': 'player_update',
    'NPC_INFO_UPDATE_MODEL': 'npc_update',
    'ENCOUNTER_UPDATE_MODEL': 'encounter_update',
    'TRANSITION_VALIDATOR_MODEL': 'transition_validation',
    'DM_MINI_MODEL': 'dm_mini',
    'NARRATIVE_COMPRESSION_MODEL': 'compression',
}


class ModelUsageFinder(ast.NodeVisitor):
    """AST visitor to find model constant usages in function calls."""

    def __init__(self):
        self.usages = []
        self.imported_names = set()

    def visit_ImportFrom(self, node):
        """Track which model constants are imported."""
        for alias in node.names:
            name = alias.asname if alias.asname else alias.name
            self.imported_names.add(name)
        self.generic_visit(node)

    def visit_Call(self, node):
        """Find model=CONSTANT in function calls."""
        for keyword in node.keywords:
            if keyword.arg == 'model':
                if isinstance(keyword.value, ast.Name):
                    const_name = keyword.value.id
                    if const_name in MODEL_TASK_MAP:
                        self.usages.append({
                            'line': keyword.value.lineno,
                            'col': keyword.value.col_offset,
                            'constant': const_name,
                            'task_id': MODEL_TASK_MAP[const_name],
                            'complexity': 'full' if 'MINI' not in const_name else 'mini',
                            'node': keyword.value
                        })
        self.generic_visit(node)


def find_model_usages(file_path: str) -> Tuple[List[Dict], str]:
    """
    Parse Python file and find all model constant usages.
    Returns list of locations where models are used.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return [], f"Error reading file: {e}"

    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        return [], f"Syntax error in file: {e}"

    finder = ModelUsageFinder()
    finder.visit(tree)

    return finder.usages, content


def get_call_block(lines: List[str], line_idx: int) -> str:
    """
    Extract the complete function call block starting around line_idx.
    Returns the multi-line string of the call.
    """
    # Look backwards to find 'chat.completions.create'
    start_idx = line_idx
    for i in range(line_idx, max(0, line_idx - 10), -1):
        if 'chat.completions.create' in lines[i] or 'completions.create' in lines[i]:
            start_idx = i
            break
    
    # Look forwards to find closing paren
    end_idx = line_idx
    paren_count = 0
    found_start = False
    
    for i in range(start_idx, min(len(lines), start_idx + 50)):
        for char in lines[i]:
            if char == '(':
                paren_count += 1
                found_start = True
            elif char == ')':
                paren_count -= 1
                if found_start and paren_count == 0:
                    end_idx = i
                    return '\n'.join(lines[start_idx:end_idx + 1])
    
    # Fallback: return context around the line
    return '\n'.join(lines[max(0, line_idx - 2):min(len(lines), line_idx + 3)])


def has_explicit_parameter(call_block: str, param_name: str) -> bool:
    """Check if a parameter is explicitly set in the function call."""
    # Match param_name= followed by something (not just whitespace or newline)
    pattern = rf'{param_name}\s*=\s*[^\s,)\n]'
    return bool(re.search(pattern, call_block))


def get_indentation(line: str) -> str:
    """Extract leading whitespace from a line."""
    return line[:len(line) - len(line.lstrip())]


def find_function_call_start(lines: List[str], line_idx: int) -> int:
    """
    Find the line index where the function call starts.
    Looks backwards for the line containing 'chat.completions.create'.
    """
    for i in range(line_idx, max(0, line_idx - 20), -1):
        if 'chat.completions.create' in lines[i] or 'completions.create' in lines[i]:
            return i
    return line_idx  # Fallback to current line


def inject_config_surgically(file_path: str, usages: List[Dict], content: str) -> Tuple[str, List[str]]:
    """
    Surgically inject get_model_config calls while preserving all other code.
    
    Key improvements over v1:
    - Only replaces the model= line, not the entire function call
    - Preserves explicit temperature settings
    - Preserves all other parameters (messages, max_tokens, etc.)
    - Adds config line right before the function call
    """
    lines = content.split('\n')
    changes_log = []
    
    # Track if we need to add import
    has_import = False
    import_line_idx = -1
    existing_import_line = None
    in_ai_factory_import = False
    ai_factory_import_start = -1
    ai_factory_import_end = -1
    
    for i, line in enumerate(lines):
        if line.startswith('from ') or line.startswith('import '):
            import_line_idx = i + 1
        
        # Detect multi-line imports from ai_client_factory
        if 'from utils.ai_client_factory import' in line:
            existing_import_line = i
            if 'get_model_config' in line:
                has_import = True
            # Check if this is a multi-line import (ends with opening paren or no items on same line)
            if '(' in line and ')' not in line:
                in_ai_factory_import = True
                ai_factory_import_start = i
            elif '(' not in line:
                # Single line import - check if get_model_config is already there
                pass
        
        # Track end of multi-line import
        if in_ai_factory_import:
            if ')' in line:
                ai_factory_import_end = i
                in_ai_factory_import = False
                # Check if get_model_config is in the multi-line block
                for j in range(ai_factory_import_start, ai_factory_import_end + 1):
                    if 'get_model_config' in lines[j]:
                        has_import = True
                        break
    
    # Process usages in reverse order (to preserve line numbers)
    
    # Process usages in reverse order (to preserve line numbers)
    for usage in sorted(usages, key=lambda x: x['line'], reverse=True):
        line_idx = usage['line'] - 1
        original_line = lines[line_idx]
        
        # Get indentation level from the model= line
        model_indent = get_indentation(original_line)
        
        # Find the start of the function call to get its indentation
        func_start_idx = find_function_call_start(lines, line_idx)
        func_indent = get_indentation(lines[func_start_idx])
        
        # Extract the call block to check for explicit parameters
        call_block = get_call_block(lines, line_idx)
        has_temp = has_explicit_parameter(call_block, 'temperature')
        
        # Build the replacement
        task_id = usage['task_id']
        const_name = usage['constant']
        
        # Config assignment line (at function call indentation level, before the call)
        config_line = f'{func_indent}config = get_model_config("{task_id}", {const_name})  # OPENROUTER: 3-tier model selection'
        
        # Model replacement line
        # Replace model=CONSTANT with model=config["model"], **config.get("extra_body", {})
        old_pattern = rf'model\s*=\s*{re.escape(const_name)}'
        new_model = 'model=config["model"], **config.get("extra_body", {})'
        
        # Check if line has trailing comma or more content after model
        remaining = re.sub(old_pattern, '', original_line, count=1).strip()
        if remaining and remaining != ',':
            # There's more content on this line (unlikely but possible)
            new_line = f'{model_indent}{new_model}, {remaining.lstrip(", ")}'
        else:
            new_line = f'{model_indent}{new_model},'
        
        # If no explicit temperature, add it from config after model line
        if not has_temp:
            temp_line = f'{model_indent}temperature=config["temperature"],'
            # Replace model line with model + temp
            lines[line_idx] = new_line + '\n' + temp_line
        else:
            # Just replace model line
            lines[line_idx] = new_line
        
        # Insert config line BEFORE the function call start
        lines[func_start_idx] = config_line + '\n' + lines[func_start_idx]
        
        changes_log.append(f"Line {usage['line']}: {const_name} -> {task_id} (temp_explicit={has_temp})")
    
    # Add import if needed (do this once at the end)
    if not has_import:
        if existing_import_line is not None and ai_factory_import_start >= 0:
            # Multi-line import - add get_model_config before the closing paren
            for i in range(ai_factory_import_start, ai_factory_import_end + 1):
                stripped = lines[i].strip()
                if stripped == ')' or stripped.startswith(')'):
                    # This is the closing line - insert before it
                    # First, ensure the line before ends with a comma
                    prev_line_idx = i - 1
                    if prev_line_idx >= ai_factory_import_start:
                        prev_line = lines[prev_line_idx]
                        if not prev_line.rstrip().endswith(','):
                            lines[prev_line_idx] = prev_line.rstrip() + ','
                    # Ensure proper indentation (match the line above)
                    indent = '    '  # Standard 4-space indent for imports
                    lines.insert(i, f'{indent}get_model_config,  # OPENROUTER: Multi-provider support')
                    changes_log.append(f"Updated multi-line import at lines {ai_factory_import_start + 1}-{i + 1}")
                    break
        elif existing_import_line is not None:
            # Single line import - add to existing line
            old_import = lines[existing_import_line]
            # Insert get_model_config before the comment if there is one
            if '#' in old_import:
                before_comment, comment = old_import.rsplit('#', 1)
                new_import = before_comment.rstrip() + ', get_model_config  #' + comment
            else:
                new_import = old_import.rstrip() + ', get_model_config  # OPENROUTER: Multi-provider support'
            lines[existing_import_line] = new_import
            changes_log.append(f"Updated existing import at line {existing_import_line + 1}")
        else:
            # Add new import line
            import_stmt = "from utils.ai_client_factory import get_model_config  # OPENROUTER: Multi-provider support"
            lines.insert(import_line_idx, import_stmt)
            changes_log.append(f"Added import at line {import_line_idx + 1}")
    
    return '\n'.join(lines), changes_log


def is_already_migrated(content: str) -> bool:
    """Check if file has already been migrated."""
    # Check if get_model_config is imported from utils.ai_client_factory
    return 'from utils.ai_client_factory import' in content and 'get_model_config' in content


def validate_migration(file_path: str) -> Tuple[bool, str]:
    """
    Validate that migrated file compiles and has correct structure.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Try to parse
        ast.parse(content)

        # Check for required import - be flexible about what else is imported
        if 'from utils.ai_client_factory import' not in content or 'get_model_config' not in content:
            return False, "Missing required import"

        # Check for our markers
        if '# OPENROUTER:' not in content:
            return False, "Missing OPENROUTER markers"
        
        # Check for v1 bug: hardcoded 'messages=messages' in our generated code
        # This happens when the old template was used that hardcoded 'messages'
        # Look for the specific pattern: model=config... followed immediately by messages=messages
        v1_bug_pattern = r'model=config\["model"\], \*\*config\.get\("extra_body", \{\}\),?\s*\n\s*messages=messages'
        if re.search(v1_bug_pattern, content):
            return False, "Hardcoded 'messages' variable detected - v1 bug pattern"

        return True, "OK"

    except SyntaxError as e:
        return False, f"Syntax error: {e}"
    except Exception as e:
        return False, str(e)


def preview_changes(file_path: str, usages: List[Dict], content: str):
    """Display preview of changes without applying."""
    print(f"\n{'='*70}")
    print(f"Preview: {file_path}")
    print('='*70)

    if not usages:
        print("  No model references found to migrate.")
        return
    
    if is_already_migrated(content):
        print("  [SKIP] File already migrated (import found)")
        return

    for usage in usages:
        line_idx = usage['line'] - 1
        lines = content.split('\n')
        call_block = get_call_block(lines, line_idx)
        has_temp = has_explicit_parameter(call_block, 'temperature')
        
        print(f"\n  Line {usage['line']}: {usage['constant']}")
        print(f"    Task ID: {usage['task_id']}")
        print(f"    Complexity: {usage['complexity']}")
        print(f"    Explicit temperature: {has_temp}")
        print(f"    Change: model={usage['constant']} -> model=config['model']")
        if not has_temp:
            print(f"    Added: temperature=config['temperature']")

    print(f"\n  Total changes: {len(usages)}")


def run_unit_tests():
    """Run unit tests for the migration logic."""
    print("="*70)
    print("Running Unit Tests")
    print("="*70)
    
    tests_passed = 0
    tests_failed = 0
    
    # Test 1: Basic model replacement
    print("\n[Test 1] Basic model replacement")
    test_input = '''def test():
    response = client.chat.completions.create(
        model=DM_MAIN_MODEL,
        messages=narration_request_messages,
        temperature=0.7
    )'''
    
    # Simulate migration
    usages = [{'line': 3, 'constant': 'DM_MAIN_MODEL', 'task_id': 'dm_main', 'complexity': 'full'}]
    result, _ = inject_config_surgically("test.py", usages, test_input)
    
    checks = [
        ('get_model_config import' in result or 'config = get_model_config' in result, "Has config assignment"),
        ('model=config["model"]' in result, "Uses config model"),
        ('narration_request_messages' in result, "Preserves messages variable"),
        ('temperature=0.7' in result, "Preserves explicit temperature"),
    ]
    
    for passed, desc in checks:
        if passed:
            print(f"  [PASS] {desc}")
            tests_passed += 1
        else:
            print(f"  [FAIL] {desc}")
            tests_failed += 1
    
    # Test 2: No explicit temperature - should add from config
    print("\n[Test 2] No explicit temperature")
    test_input = '''def test():
    response = client.chat.completions.create(
        model=DM_MINI_MODEL,
        messages=messages
    )'''
    
    usages = [{'line': 3, 'constant': 'DM_MINI_MODEL', 'task_id': 'dm_mini', 'complexity': 'mini'}]
    result, _ = inject_config_surgically("test.py", usages, test_input)
    
    checks = [
        ('config = get_model_config' in result, "Has config assignment"),
        ('model=config["model"]' in result, "Uses config model"),
        ('temperature=config["temperature"]' in result, "Adds temperature from config"),
    ]
    
    for passed, desc in checks:
        if passed:
            print(f"  [PASS] {desc}")
            tests_passed += 1
        else:
            print(f"  [FAIL] {desc}")
            tests_failed += 1
    
    # Test 3: Already migrated detection
    print("\n[Test 3] Already migrated detection")
    test_input = '''from utils.ai_client_factory import get_model_config

def test():
    config = get_model_config("dm_main", DM_MAIN_MODEL)
    response = client.chat.completions.create(
        model=config["model"],
        messages=messages
    )'''
    
    if is_already_migrated(test_input):
        print("  [PASS] Correctly detects migrated file")
        tests_passed += 1
    else:
        print("  [FAIL] Failed to detect migrated file")
        tests_failed += 1
    
    # Test 4: Task ID mapping
    print("\n[Test 4] Task ID mappings")
    expected_mappings = [
        ('DM_MAIN_MODEL', 'dm_main'),
        ('DM_SUMMARIZATION_MODEL', 'summaries'),
        ('COMBAT_DIALOGUE_SUMMARY_MODEL', 'combat_dialogue_summary'),
    ]
    
    for const, expected_id in expected_mappings:
        actual_id = MODEL_TASK_MAP.get(const)
        if actual_id == expected_id:
            print(f"  [PASS] {const} -> {actual_id}")
            tests_passed += 1
        else:
            print(f"  [FAIL] {const} -> {actual_id} (expected {expected_id})")
            tests_failed += 1
    
    # Summary
    print("\n" + "="*70)
    print(f"Test Results: {tests_passed} passed, {tests_failed} failed")
    print("="*70)
    
    return tests_failed == 0


def main():
    parser = argparse.ArgumentParser(
        description='Migrate to OpenRouter 3-tier system (FIXED VERSION)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run unit tests
    python scripts/migrate_to_openrouter.py --test

    # Preview changes for all files
    python scripts/migrate_to_openrouter.py --dry-run

    # Migrate single file
    python scripts/migrate_to_openrouter.py --file main.py

    # Migrate single file with dry-run
    python scripts/migrate_to_openrouter.py --file main.py --dry-run

    # Apply changes to all files
    python scripts/migrate_to_openrouter.py
        """
    )
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview changes without applying')
    parser.add_argument('--file', help='Migrate specific file only')
    parser.add_argument('--test', action='store_true',
                        help='Run unit tests')
    args = parser.parse_args()
    
    # Run tests if requested
    if args.test:
        success = run_unit_tests()
        sys.exit(0 if success else 1)

    # Default files to migrate (all core files)
    default_files = [
        'main.py',
        'core/managers/combat_manager.py',
        'core/ai/action_handler.py',
        'updates/update_character_info.py',
        'updates/update_npc_info.py',
        'updates/update_encounter.py',
        'updates/plot_update.py',
        'core/ai/transition_validator.py',
        'core/ai/combat_compression_engine.py',
        'core/ai/incremental_compression.py',
        'core/ai/cumulative_summary.py',
        'core/ai/adv_summary.py',
        'web/web_interface.py',
        'utils/startup_wizard.py',
    ]

    files_to_process = [args.file] if args.file else default_files

    print("=" * 70)
    print("OpenRouter Migration Script - Phase 1B (FIXED)")
    print("=" * 70)
    print(f"Mode: {'DRY RUN (preview only)' if args.dry_run else 'LIVE (will modify files)'}")
    print(f"Files to process: {len(files_to_process)}")
    print()

    report = []

    for file_path in files_to_process:
        full_path = os.path.join(os.getcwd(), file_path)

        print(f"Processing: {file_path}")

        if not os.path.exists(full_path):
            print(f"  [WARN] File not found, skipping\n")
            report.append({
                'file': file_path,
                'changes': 0,
                'status': 'not_found'
            })
            continue

        # Find usages
        usages, content = find_model_usages(full_path)

        if isinstance(usages, str):  # Error message
            print(f"  [FAIL] Error: {usages}\n")
            report.append({
                'file': file_path,
                'changes': 0,
                'status': 'error',
                'message': usages
            })
            continue

        # Check if already migrated
        if is_already_migrated(content):
            print(f"  [SKIP] Already migrated\n")
            report.append({
                'file': file_path,
                'changes': 0,
                'status': 'already_migrated'
            })
            continue

        print(f"  Found {len(usages)} model reference(s)")

        if not usages:
            report.append({
                'file': file_path,
                'changes': 0,
                'status': 'no_changes'
            })
            continue

        # Preview changes
        if args.dry_run:
            preview_changes(file_path, usages, content)
            report.append({
                'file': file_path,
                'changes': len(usages),
                'status': 'preview'
            })
        else:
            # Generate replacement
            new_content, changes_log = inject_config_surgically(full_path, usages, content)

            # Create backup
            backup_path = full_path + '.bak'
            shutil.copy2(full_path, backup_path)

            # Apply changes
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            # Validate
            valid, msg = validate_migration(full_path)

            if valid:
                print(f"  [OK] Migrated successfully ({len(usages)} change(s))")
                os.remove(backup_path)  # Remove backup on success
                report.append({
                    'file': file_path,
                    'changes': len(usages),
                    'status': 'success',
                    'details': changes_log
                })
            else:
                print(f"  [FAIL] Validation failed: {msg}")
                print(f"  [RESTORE] Restoring from backup...")
                shutil.copy2(backup_path, full_path)
                os.remove(backup_path)
                report.append({
                    'file': file_path,
                    'changes': 0,
                    'status': 'failed',
                    'message': msg
                })

        print()

    # Print summary
    print("=" * 70)
    print("MIGRATION REPORT")
    print("=" * 70)

    successful = sum(1 for r in report if r['status'] in ('success', 'preview'))
    failed = sum(1 for r in report if r['status'] == 'failed')
    not_found = sum(1 for r in report if r['status'] == 'not_found')
    no_changes = sum(1 for r in report if r['status'] == 'no_changes')
    already_migrated = sum(1 for r in report if r['status'] == 'already_migrated')

    print(f"Total files processed: {len(report)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Not found: {not_found}")
    print(f"No changes needed: {no_changes}")
    print(f"Already migrated: {already_migrated}")
    print()

    if failed > 0:
        print("Failed migrations:")
        for r in report:
            if r['status'] == 'failed':
                print(f"  - {r['file']}: {r.get('message', 'Unknown error')}")
        print()

    if args.dry_run:
        print("=" * 70)
        print("DRY RUN COMPLETE")
        print("=" * 70)
        print("No files were modified.")
        print()
        print("To apply these changes, run WITHOUT --dry-run:")
        print("  python scripts/migrate_to_openrouter.py")
    else:
        print("=" * 70)
        print("MIGRATION COMPLETE")
        print("=" * 70)
        print()
        print("Next steps:")
        print("1. Review changes: git diff")
        print("2. Test compilation: python -m py_compile <file>")
        print("3. Run game: python run_web.py")
        print("4. Verify: Check that OpenRouter is being used")
        print()
        print("To undo migration:")
        print("  - Restore from .bak files: cp file.py.bak file.py")
        print("  - Or use git: git checkout -- <file>")


if __name__ == '__main__':
    main()
