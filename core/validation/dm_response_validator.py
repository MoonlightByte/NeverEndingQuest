#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
DM Response Validator

Validates DM AI responses against expected format and game rules.
"""

import json
import re
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime

try:
    from core.ai.module_creation_contract import (
        ModuleCreationContractError,
        validate_create_new_module_actions,
        validate_create_new_module_parameters,
    )
except ModuleNotFoundError:
    # Preserve this file's documented direct CLI entry point.
    import os
    import sys

    sys.path.insert(
        0,
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    )
    from core.ai.module_creation_contract import (
        ModuleCreationContractError,
        validate_create_new_module_actions,
        validate_create_new_module_parameters,
    )


class DMResponseValidator:
    """Validates DM responses for format, content, and game rule compliance"""
    
    def __init__(self):
        self.valid_actions = [
            "updateCharacterInfo",
            "transitionLocation",
            "createEncounter",
            "updateEncounter",
            "updatePlot",
            "updateTime",
            "levelUp",
            "updatePartyNPCs",
            "updatePartyTracker",
            "createNewModule",
            "establishHub",
            "storageInteraction",
            "exitGame"
        ]
        
        self.validation_log = []
    
    def log_validation(self, check: str, passed: bool, details: str = ""):
        """Log validation result"""
        self.validation_log.append({
            "check": check,
            "passed": passed,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })
    
    def validate_response(self, response: str, scenario: Dict = None) -> Tuple[bool, List[str], Dict]:
        """
        Comprehensive response validation
        
        Args:
            response: Raw response string from DM
            scenario: Optional test scenario with expected values
            
        Returns:
            Tuple of (is_valid, errors, parsed_data)
        """
        errors = []
        parsed_data = {}
        self.validation_log = []
        
        # 1. JSON Format Validation
        try:
            parsed_data = json.loads(response)
            self.log_validation("JSON Parse", True)
        except json.JSONDecodeError as e:
            self.log_validation("JSON Parse", False, str(e))
            errors.append(f"Invalid JSON: {str(e)}")
            return False, errors, {}
        
        # 2. Required Fields Validation
        if "narration" not in parsed_data:
            self.log_validation("Narration Field", False, "Missing")
            errors.append("Missing required field: 'narration'")
        else:
            self.log_validation("Narration Field", True)
            
        if "actions" not in parsed_data:
            self.log_validation("Actions Field", False, "Missing")
            errors.append("Missing required field: 'actions'")
        else:
            self.log_validation("Actions Field", True)
        
        if errors:
            return False, errors, parsed_data
        
        # 3. Type Validation
        if not isinstance(parsed_data["narration"], str):
            self.log_validation("Narration Type", False, f"Got {type(parsed_data['narration'])}")
            errors.append("'narration' must be a string")
        else:
            self.log_validation("Narration Type", True)
            
        if not isinstance(parsed_data["actions"], list):
            self.log_validation("Actions Type", False, f"Got {type(parsed_data['actions'])}")
            errors.append("'actions' must be an array")
            return False, errors, parsed_data
        else:
            self.log_validation("Actions Type", True)

        # A module build is an atomic publication attempt.  It cannot share a
        # candidate response with another state-mutating action, and its
        # parameters have one exact narrative-only shape.
        try:
            validate_create_new_module_actions(parsed_data["actions"])
            self.log_validation("createNewModule Contract", True)
        except ModuleCreationContractError as exc:
            self.log_validation("createNewModule Contract", False, str(exc))
            errors.append(str(exc))
        
        # 4. Validate Each Action
        for i, action in enumerate(parsed_data["actions"]):
            action_errors = self.validate_action(action, i)
            errors.extend(action_errors)
        
        # 5. Content Validation
        content_errors = self.validate_content(parsed_data)
        errors.extend(content_errors)
        
        # 6. Scenario-Specific Validation (if provided)
        if scenario:
            scenario_errors = self.validate_against_scenario(parsed_data, scenario)
            errors.extend(scenario_errors)
        
        # 7. Game Rules Validation
        rule_errors = self.validate_game_rules(parsed_data)
        errors.extend(rule_errors)
        
        is_valid = len(errors) == 0
        return is_valid, errors, parsed_data
    
    def validate_action(self, action: Dict, index: int) -> List[str]:
        """Validate individual action structure and parameters"""
        errors = []
        action_desc = f"Action {index}"
        
        # Check required fields
        if not isinstance(action, dict):
            self.log_validation(f"{action_desc} Type", False, "Not a dictionary")
            errors.append(f"{action_desc}: Must be an object")
            return errors
        
        if "action" not in action:
            self.log_validation(f"{action_desc} 'action' field", False, "Missing")
            errors.append(f"{action_desc}: Missing 'action' field")
        else:
            # Validate action type
            action_type = action["action"]
            if action_type not in self.valid_actions:
                self.log_validation(f"{action_desc} Type Valid", False, f"Unknown: {action_type}")
                errors.append(f"{action_desc}: Unknown action type '{action_type}'")
            else:
                self.log_validation(f"{action_desc} Type Valid", True)
        
        if "parameters" not in action:
            self.log_validation(f"{action_desc} 'parameters' field", False, "Missing")
            errors.append(f"{action_desc}: Missing 'parameters' field")
        elif not isinstance(action["parameters"], dict):
            self.log_validation(f"{action_desc} 'parameters' type", False, "Not a dictionary")
            errors.append(f"{action_desc}: 'parameters' must be an object")
        else:
            # Validate specific action parameters
            param_errors = self.validate_action_parameters(action["action"], action["parameters"], index)
            errors.extend(param_errors)
        
        return errors
    
    def validate_action_parameters(self, action_type: str, params: Dict, index: int) -> List[str]:
        """Validate parameters for specific action types"""
        errors = []
        
        # Define required parameters for each action type
        required_params = {
            "updateCharacterInfo": ["characterName", "changes"],
            "transitionLocation": ["newLocation"],
            "updatePlot": ["plotPointId", "newStatus"],
            "updateTime": ["timeEstimate"],
            "levelUp": ["entityName", "newLevel"],
            "updatePartyNPCs": ["operation", "npc"],
            "establishHub": ["hubName"],
            "storageInteraction": ["description"],
            "createEncounter": [],  # Complex parameters handled by combat_builder
            "updateEncounter": ["encounterId", "changes"],
            "createNewModule": ["narrative"],
            "updatePartyTracker": [],  # Various fields allowed
            "exitGame": []  # No parameters required
        }
        
        if action_type in required_params:
            for param in required_params[action_type]:
                if param not in params:
                    self.log_validation(f"Action {index} param '{param}'", False, "Missing")
                    errors.append(f"Action {index} ({action_type}): Missing required parameter '{param}'")
                else:
                    self.log_validation(f"Action {index} param '{param}'", True)
        
        # Additional parameter validation
        if action_type == "updateCharacterInfo":
            if "changes" in params:
                # Validate changes can be parsed
                changes = params["changes"]
                if isinstance(changes, str):
                    try:
                        json.loads(changes)
                        self.log_validation(f"Action {index} changes JSON", True)
                    except json.JSONDecodeError:
                        self.log_validation(f"Action {index} changes JSON", False, "Invalid JSON")
                        errors.append(f"Action {index}: 'changes' contains invalid JSON")
        
        elif action_type == "transitionLocation":
            if "newLocation" in params:
                # Validate location ID format
                loc_id = params["newLocation"]
                if not re.match(r'^[A-Z]\d{2}$', str(loc_id)):
                    self.log_validation(f"Action {index} location format", False, f"Invalid: {loc_id}")
                    errors.append(f"Action {index}: Invalid location ID format '{loc_id}' (expected like 'A01')")
                else:
                    self.log_validation(f"Action {index} location format", True)
        
        elif action_type == "updateTime":
            if "timeEstimate" in params:
                # Validate time can be converted to number
                try:
                    time_val = int(str(params["timeEstimate"]))
                    if time_val < 0:
                        errors.append(f"Action {index}: Time cannot be negative")
                    self.log_validation(f"Action {index} time value", time_val >= 0)
                except ValueError:
                    self.log_validation(f"Action {index} time value", False, "Not numeric")
                    errors.append(f"Action {index}: 'timeEstimate' must be numeric")

        elif action_type == "createNewModule":
            try:
                validate_create_new_module_parameters(params)
                self.log_validation(
                    f"Action {index} createNewModule exact contract", True
                )
            except ModuleCreationContractError as exc:
                self.log_validation(
                    f"Action {index} createNewModule exact contract", False, str(exc)
                )
                errors.append(f"Action {index} (createNewModule): {exc}")
        
        return errors
    
    def validate_content(self, data: Dict) -> List[str]:
        """Validate content rules (no Unicode, etc.)"""
        errors = []
        
        # Check for Unicode characters in narration
        narration = data.get("narration", "")
        unicode_chars = self.find_unicode_characters(narration)
        if unicode_chars:
            self.log_validation("No Unicode in narration", False, f"Found: {unicode_chars}")
            errors.append(f"Narration contains forbidden Unicode characters: {unicode_chars}")
        else:
            self.log_validation("No Unicode in narration", True)
        
        # Check action parameters for Unicode
        for i, action in enumerate(data.get("actions", [])):
            if isinstance(action.get("parameters"), dict):
                unicode_in_params = self.check_dict_for_unicode(action["parameters"])
                if unicode_in_params:
                    errors.append(f"Action {i} parameters contain Unicode: {unicode_in_params}")
        
        return errors
    
    def find_unicode_characters(self, text: str) -> List[str]:
        """Find any non-ASCII Unicode characters"""
        unicode_chars = []
        for char in text:
            if ord(char) > 127:
                unicode_chars.append(f"{char} (U+{ord(char):04X})")
        return unicode_chars
    
    def check_dict_for_unicode(self, d: Dict, path: str = "") -> List[str]:
        """Recursively check dictionary for Unicode characters"""
        unicode_found = []
        
        for key, value in d.items():
            current_path = f"{path}.{key}" if path else key
            
            if isinstance(value, str):
                chars = self.find_unicode_characters(value)
                if chars:
                    unicode_found.append(f"{current_path}: {chars}")
            elif isinstance(value, dict):
                unicode_found.extend(self.check_dict_for_unicode(value, current_path))
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, str):
                        chars = self.find_unicode_characters(item)
                        if chars:
                            unicode_found.append(f"{current_path}[{i}]: {chars}")
        
        return unicode_found
    
    def validate_against_scenario(self, data: Dict, scenario: Dict) -> List[str]:
        """Validate response against expected scenario outcomes"""
        errors = []
        expected = scenario.get("expected_response", {})
        
        # Check narration presence
        if expected.get("has_narration") and not data.get("narration"):
            errors.append("Expected narration but none provided")
        
        # Check action count
        if "actions_count" in expected:
            actual_count = len(data.get("actions", []))
            expected_count = expected["actions_count"]
            if actual_count != expected_count:
                self.log_validation("Action count", False, f"Expected {expected_count}, got {actual_count}")
                errors.append(f"Expected {expected_count} actions, got {actual_count}")
            else:
                self.log_validation("Action count", True)
        
        # Check minimum actions
        if "minimum_actions" in expected:
            actual_count = len(data.get("actions", []))
            min_count = expected["minimum_actions"]
            if actual_count < min_count:
                errors.append(f"Expected at least {min_count} actions, got {actual_count}")
        
        # Check required actions
        if "required_actions" in expected:
            actual_actions = [a["action"] for a in data.get("actions", [])]
            for required in expected["required_actions"]:
                if required not in actual_actions:
                    self.log_validation(f"Required action '{required}'", False, "Not found")
                    errors.append(f"Missing required action: {required}")
                else:
                    self.log_validation(f"Required action '{required}'", True)
        
        # Check expected parameters
        if "expected_parameters" in expected:
            # This is a simplified check - could be made more sophisticated
            for action in data.get("actions", []):
                if action["action"] in expected.get("required_actions", []):
                    # Found the action, check its parameters
                    for param, value in expected["expected_parameters"].items():
                        if param not in action["parameters"]:
                            errors.append(f"Action {action['action']} missing expected parameter: {param}")
        
        return errors
    
    def validate_game_rules(self, data: Dict) -> List[str]:
        """Validate against 5th edition game rules"""
        errors = []
        
        for i, action in enumerate(data.get("actions", [])):
            if action["action"] == "updateCharacterInfo" and "changes" in action["parameters"]:
                # Parse changes and validate game rules
                changes_str = action["parameters"]["changes"]
                if isinstance(changes_str, str):
                    try:
                        changes = json.loads(changes_str)
                        
                        # Check HP updates
                        if "hitPoints" in changes:
                            hp = changes["hitPoints"]
                            if not isinstance(hp, (int, float)) or hp < 0:
                                errors.append(f"Action {i}: Hit points must be non-negative number")
                        
                        # Check level updates
                        if "level" in changes:
                            level = changes["level"]
                            if not isinstance(level, int) or level < 1 or level > 20:
                                errors.append(f"Action {i}: Level must be between 1 and 20")
                        
                        # Check ability scores
                        for ability in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
                            if ability in changes:
                                score = changes[ability]
                                if not isinstance(score, int) or score < 1 or score > 30:
                                    errors.append(f"Action {i}: {ability} must be between 1 and 30")
                    
                    except json.JSONDecodeError:
                        pass  # Already handled in parameter validation
            
            elif action["action"] == "updateTime" and "timeEstimate" in action["parameters"]:
                try:
                    time_val = int(str(action["parameters"]["timeEstimate"]))
                    # Check reasonable time limits
                    if time_val > 1440:  # More than 24 hours
                        self.log_validation(f"Action {i} time reasonable", False, f"{time_val} minutes")
                        errors.append(f"Action {i}: Time update of {time_val} minutes seems excessive")
                except ValueError:
                    pass  # Already handled
        
        return errors
    
    def get_validation_summary(self) -> Dict:
        """Get summary of validation results"""
        total_checks = len(self.validation_log)
        passed_checks = sum(1 for log in self.validation_log if log["passed"])
        
        return {
            "total_checks": total_checks,
            "passed": passed_checks,
            "failed": total_checks - passed_checks,
            "success_rate": passed_checks / total_checks if total_checks > 0 else 0,
            "log": self.validation_log
        }


def validate_response_file(filename: str, scenario_file: str = None) -> None:
    """Validate responses from a file"""
    validator = DMResponseValidator()
    
    # Load response
    try:
        with open(filename, 'r') as f:
            response = f.read()
    except Exception as e:
        print(f"Error reading file: {e}")
        return
    
    # Load scenario if provided
    scenario = None
    if scenario_file:
        try:
            with open(scenario_file, 'r') as f:
                scenarios = json.load(f)
                # Assume first scenario for now
                scenario = scenarios.get("test_scenarios", [{}])[0]
        except Exception as e:
            print(f"Error loading scenario: {e}")
    
    # Validate
    is_valid, errors, data = validator.validate_response(response, scenario)
    
    # Print results
    print("=" * 80)
    print(f"VALIDATION REPORT: {filename}")
    print("=" * 80)
    
    if is_valid:
        print("[PASS] Response is valid!")
        print(f"\nNarration: {data['narration'][:100]}...")
        print(f"Actions: {len(data['actions'])}")
        for action in data['actions']:
            print(f"  - {action['action']}")
    else:
        print("[FAIL] Response validation failed!")
        print(f"\nErrors found: {len(errors)}")
        for error in errors:
            print(f"  - {error}")
    
    # Print validation summary
    summary = validator.get_validation_summary()
    print(f"\nValidation Summary:")
    print(f"  Total checks: {summary['total_checks']}")
    print(f"  Passed: {summary['passed']}")
    print(f"  Failed: {summary['failed']}")
    print(f"  Success rate: {summary['success_rate']:.1%}")


def main():
    """Command-line validation tool"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python dm_response_validator.py <response_file> [scenario_file]")
        sys.exit(1)
    
    response_file = sys.argv[1]
    scenario_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    validate_response_file(response_file, scenario_file)


if __name__ == "__main__":
    main()
