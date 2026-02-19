# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Regression test: Duplicate PC return narration fix.

Validates:
- Exactly one narration prompt queued on add_character
- Return narration only for characters with prior retirement history
- Entrance narration for first-time adds
"""

import json
import os
import sys
import tempfile
import unittest
from queue import Queue
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Check Flask availability
try:
    from flask import Flask
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False


class TestDuplicateReturnNarrationFix(unittest.TestCase):
    """Test that add_character queues exactly one narration prompt."""

    def setUp(self):
        """Set up test environment with mocked dependencies."""
        if not FLASK_AVAILABLE:
            self.skipTest("Flask not installed")

        self.temp_dir = tempfile.mkdtemp()
        self.user_input_queue = Queue()

        # Create a minimal Flask app for testing
        self.app = Flask(__name__)

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _setup_mock_party_tracker(self, party_members=None):
        """Create a mock party tracker with specified members."""
        return {
            "partyMembers": party_members or [],
            "partyNPCs": [],
            "active_character": party_members[0] if party_members else "",
            "worldConditions": {"currentLocation": "Test Location"}
        }

    def _create_character_file(self, name, with_retirement_history=False):
        """Create a character JSON file with optional retirement history."""
        char_data = {
            "name": name,
            "race": "Human",
            "class": "Fighter",
            "level": 1,
            "personality_traits": "A brave warrior",
            "character_id": f"test-{name.lower().replace(' ', '-')}-id"
        }

        if with_retirement_history:
            char_data["_tabletop_role_history"] = [
                {
                    "timestamp": "2024-01-01T10:00:00Z",
                    "action": "retired_from_party",
                    "from_role": "player",
                    "to_role": "retired_player",
                    "source": "manage_party_remove_character",
                    "actor": "dm"
                }
            ]

        char_filename = f"{name.lower().replace(' ', '_')}.json"
        char_path = os.path.join(self.temp_dir, char_filename)

        with open(char_path, 'w') as f:
            json.dump(char_data, f)

        return char_path, char_data

    def test_true_return_gets_single_return_narration(self):
        """Test that a character with retirement history gets exactly ONE return narration."""
        # Setup: Create a retired character
        retired_char_name = "Temporarius"
        char_path, _ = self._create_character_file(retired_char_name, with_retirement_history=True)

        # Queue should start empty
        self.assertEqual(self.user_input_queue.qsize(), 0)

        # Mock the route registration to use our test environment
        with patch('web.routes.tabletop_party_routes.pc_manager') as mock_pc_manager:
            # Setup party tracker mock (character NOT in party, which is correct for re-add)
            mock_tracker = self._setup_mock_party_tracker(party_members=["Acheron"])
            mock_pc_manager.get_party_tracker.return_value = mock_tracker
            mock_pc_manager.add_pc.return_value = True
            mock_pc_manager.get_entrance_prompt.return_value = f"[SYSTEM] {retired_char_name} has joined dramatically."

            # Mock _load_character_data to return our character data
            with patch('web.routes.tabletop_party_routes.safe_read_json') as mock_read:
                mock_read.return_value = json.load(open(char_path))

                with patch('web.routes.tabletop_party_routes.safe_write_json') as mock_write:
                    mock_write.return_value = True

                    # Import and register route
                    from web.routes.tabletop_party_routes import register_tabletop_party_routes
                    register_tabletop_party_routes(self.app, self.user_input_queue)

                    # Make request via test client
                    with self.app.test_client() as client:
                        response = client.post('/api/party/add_character',
                                               data=json.dumps({"character": retired_char_name}),
                                               content_type='application/json')

        # Verify response success
        self.assertEqual(response.status_code, 200)

        # CRITICAL: Queue should have EXACTLY ONE item
        self.assertEqual(self.user_input_queue.qsize(), 1,
                        "FAIL: More than one narration prompt was queued (duplicate bug)")

        # Verify the prompt is return-style (contains "returned")
        prompt = self.user_input_queue.get()
        self.assertIn("returned", prompt.lower(),
                     "FAIL: Expected return narration for retired character")

        print(f"[PASS] True return: single prompt queued with correct return style")

    def test_first_time_add_gets_single_entrance_narration(self):
        """Test that a character without retirement history gets exactly ONE entrance narration."""
        # Setup: Create a brand new character (no retirement history)
        new_char_name = "NewHero"
        char_path, _ = self._create_character_file(new_char_name, with_retirement_history=False)

        # Clear queue
        self.user_input_queue = Queue()
        self.assertEqual(self.user_input_queue.qsize(), 0)

        # Mock the route registration
        with patch('web.routes.tabletop_party_routes.pc_manager') as mock_pc_manager:
            mock_tracker = self._setup_mock_party_tracker(party_members=["Acheron"])
            mock_pc_manager.get_party_tracker.return_value = mock_tracker
            mock_pc_manager.add_pc.return_value = True
            mock_pc_manager.get_entrance_prompt.return_value = f"[SYSTEM] {new_char_name} has joined dramatically."

            with patch('web.routes.tabletop_party_routes.safe_read_json') as mock_read:
                # First call loads character data, second might load character file
                def side_effect(path):
                    if new_char_name.lower() in path.lower():
                        return json.load(open(char_path))
                    return {}
                mock_read.side_effect = side_effect

                with patch('web.routes.tabletop_party_routes.safe_write_json') as mock_write:
                    mock_write.return_value = True

                    # Re-register routes with fresh queue
                    from web.routes.tabletop_party_routes import register_tabletop_party_routes
                    register_tabletop_party_routes(self.app, self.user_input_queue)

                    with self.app.test_client() as client:
                        response = client.post('/api/party/add_character',
                                               data=json.dumps({"character": new_char_name}),
                                               content_type='application/json')

        # Verify response success
        self.assertEqual(response.status_code, 200)

        # CRITICAL: Queue should have EXACTLY ONE item
        self.assertEqual(self.user_input_queue.qsize(), 1,
                        "FAIL: More than one narration prompt was queued")

        # Verify the prompt uses entrance style (via mocked get_entrance_prompt)
        prompt = self.user_input_queue.get()
        self.assertIn("joined", prompt.lower(),
                     "FAIL: Expected entrance narration for new character")

        print(f"[PASS] First-time add: single prompt queued with correct entrance style")

    def test_idempotent_add_is_quiet(self):
        """Test that adding a character already in party queues no narration (idempotent)."""
        existing_char_name = "ExistingPC"
        char_path, _ = self._create_character_file(existing_char_name, with_retirement_history=False)

        # Clear queue
        self.user_input_queue = Queue()

        # Mock with character ALREADY in party
        with patch('web.routes.tabletop_party_routes.pc_manager') as mock_pc_manager:
            mock_tracker = self._setup_mock_party_tracker(
                party_members=["Acheron", existing_char_name]  # Already in party
            )
            mock_pc_manager.get_party_tracker.return_value = mock_tracker
            mock_pc_manager.add_pc.return_value = True  # Route still succeeds

            with patch('web.routes.tabletop_party_routes.safe_read_json') as mock_read:
                mock_read.side_effect = lambda path: json.load(open(char_path)) if existing_char_name.lower() in path.lower() else {}

                # Re-register routes
                from web.routes.tabletop_party_routes import register_tabletop_party_routes
                register_tabletop_party_routes(self.app, self.user_input_queue)

                with self.app.test_client() as client:
                    response = client.post('/api/party/add_character',
                                           data=json.dumps({"character": existing_char_name}),
                                           content_type='application/json')

        # Verify response success (still returns 200, idempotent)
        self.assertEqual(response.status_code, 200)

        # Queue should be EMPTY (was_previously_member=True, no narration queued)
        self.assertEqual(self.user_input_queue.qsize(), 0,
                        "FAIL: Idempotent add should not queue any narration")

        print(f"[PASS] Idempotent add: no narration queued (quiet)")


class TestHelperFunctionLogic(unittest.TestCase):
    """Test the _has_prior_retirement_history helper logic directly."""

    def _has_prior_retirement_history(self, character_data):
        """Copy of helper logic from route for direct testing."""
        history = character_data.get("_tabletop_role_history")
        if not isinstance(history, list):
            return False
        for event in history:
            if not isinstance(event, dict):
                continue
            # Retirement markers: action=retired_from_party OR to_role=retired_player
            if event.get("action") == "retired_from_party":
                return True
            if event.get("to_role") == "retired_player":
                return True
        return False

    def test_no_history_returns_false(self):
        """Character without history should not be classified as return."""
        char_data = {"name": "NewHero"}
        self.assertFalse(self._has_prior_retirement_history(char_data))

    def test_retired_from_party_returns_true(self):
        """Character with retired_from_party action should be return."""
        char_data = {
            "_tabletop_role_history": [
                {"action": "retired_from_party", "to_role": "retired_player"}
            ]
        }
        self.assertTrue(self._has_prior_retirement_history(char_data))

    def test_retired_to_role_returns_true(self):
        """Character with to_role=retired_player should be return (even without action)."""
        char_data = {
            "_tabletop_role_history": [
                {"to_role": "retired_player"}
            ]
        }
        self.assertTrue(self._has_prior_retirement_history(char_data))

    def test_other_role_transitions_not_return(self):
        """Character with other role transitions should not be return."""
        char_data = {
            "_tabletop_role_history": [
                {"action": "promoted_to_pc", "from_role": "npc", "to_role": "player"}
            ]
        }
        self.assertFalse(self._has_prior_retirement_history(char_data))

    def test_empty_history_not_return(self):
        """Character with empty history array should not be return."""
        char_data = {"_tabletop_role_history": []}
        self.assertFalse(self._has_prior_retirement_history(char_data))


if __name__ == "__main__":
    unittest.main(verbosity=2)
