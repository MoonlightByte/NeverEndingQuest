#!/usr/bin/env python3
"""
Test for Task 1.3: Transition pre-validation receives raw player utterance.

Verifies that:
1. pre_validate_transition accepts raw_player_input parameter
2. When raw_player_input is provided, it's used instead of DM-note-augmented text
3. Single-player path remains unchanged (backward compatible)
"""

import unittest
import sys
import os
import ast

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestFunctionSignatures(unittest.TestCase):
    """Test that function signatures are correct."""

    def _get_function_def(self, relative_path, function_name):
        file_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            *relative_path,
        )
        with open(file_path, "r", encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename=file_path)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == function_name:
                return node
        self.fail(f"Function {function_name} not found in {'/'.join(relative_path)}")

    def test_pre_validate_transition_accepts_raw_player_input(self):
        """
        Test 1: pre_validate_transition function signature includes raw_player_input parameter.
        """
        function_def = self._get_function_def(("core", "ai", "action_handler.py"), "pre_validate_transition")
        params = [arg.arg for arg in function_def.args.args]
        
        self.assertIn('raw_player_input', params,
            "pre_validate_transition must accept raw_player_input parameter")
        
        # Check it's optional (has default value)
        default_arg_names = params[-len(function_def.args.defaults):] if function_def.args.defaults else []
        self.assertIn('raw_player_input', default_arg_names,
            "raw_player_input should default to None for backward compatibility")
        raw_input_default = function_def.args.defaults[default_arg_names.index('raw_player_input')]
        self.assertIsInstance(raw_input_default, ast.Constant)
        self.assertIsNone(raw_input_default.value)

    def test_validate_transition_request_receives_player_request(self):
        """
        Test 2: validate_transition_request accepts player_request parameter.
        """
        function_def = self._get_function_def(("core", "ai", "transition_validator.py"), "validate_transition_request")
        params = [arg.arg for arg in function_def.args.args]
        
        self.assertIn('player_request', params,
            "validate_transition_request must accept player_request parameter")


class TestCodeContracts(unittest.TestCase):
    """Test that code changes are present in source files."""

    def test_action_handler_uses_raw_player_input(self):
        """
        Test 3: action_handler.py uses raw_player_input when provided.
        """
        action_handler_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'core', 'ai', 'action_handler.py'
        )
        
        with open(action_handler_path, 'r') as f:
            content = f.read()
        
        # Check for the raw_player_input logic
        self.assertIn(
            "player_request = raw_player_input if raw_player_input else \"\"",
            content,
            "action_handler.py should prefer raw_player_input when provided"
        )
        
        self.assertIn(
            "TABLETOP MODE: Prefer raw_player_input for clearer intent detection",
            content,
            "action_handler.py should have TABLETOP MODE comment"
        )

    def test_main_py_passes_raw_input(self):
        """
        Test 4: main.py passes raw player input to pre_validate_transition.
        """
        main_py_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'main.py'
        )
        
        with open(main_py_path, 'r') as f:
            content = f.read()
        
        # Check that main.py passes raw_player_input
        self.assertIn(
            "raw_player_input=raw_player_input_for_transition",
            content,
            "main.py should pass raw_player_input to pre_validate_transition"
        )
        
        self.assertIn(
            "TABLETOP MODE: Pass raw player input for pre-validation",
            content,
            "main.py should have TABLETOP MODE comment for raw input"
        )


class TestPreValidateTransitionBehavior(unittest.TestCase):
    """Source checks for fail-closed transition pre-validation."""

    def test_pre_validate_transition_rejects_unknown_destination(self):
        action_handler_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'core', 'ai', 'action_handler.py'
        )

        with open(action_handler_path, 'r', encoding='utf-8') as f:
            content = f.read()

        self.assertIn(
            "if not location_graph.validate_location_id_format(new_location_id):",
            content,
        )
        self.assertIn(
            "Travel Blocked: Destination location '",
            content,
        )
        self.assertIn(
            "No valid path exists between",
            content,
        )


class TestCommonInstructionTailRemoval(unittest.TestCase):
    """Test that common instruction tail is not appended in multi-PC mode."""

    def test_dm_note_skips_common_instructions_in_multi_pc(self):
        """
        Test 5: main.py conditionally skips common instructions in multi-PC mode.
        """
        main_py_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'main.py'
        )
        
        with open(main_py_path, 'r') as f:
            content = f.read()
        
        # Check for the multi-PC mode detection we added
        self.assertIn(
            "TABLETOP MODE: Multi-PC path uses leaner prompt",
            content,
            "main.py should contain multi-PC mode detection for prompt simplification"
        )
        
        self.assertIn(
            "is_multi_pc_mode = MULTIPLAYER_MODE and len(party_members) > 1",
            content,
            "main.py should detect multi-PC mode correctly"
        )
        
        self.assertIn(
            "if not is_multi_pc_mode:",
            content,
            "main.py should conditionally skip common instructions in multi-PC mode"
        )


if __name__ == '__main__':
    unittest.main()
