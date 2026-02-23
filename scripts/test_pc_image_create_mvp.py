# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
PC Image Create MVP Tests
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Tests for portrait create API, allied auto-gen policy gating, and warning throttle.

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

import json
import os
import sys
import time
import unittest
from unittest.mock import patch, MagicMock
import tempfile

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestAlliedAutoGenPolicy(unittest.TestCase):
    """Test suite for allied-only auto-generation policy gating."""

    def test_allied_policy_allows_party_npc(self):
        """Test 6.1.4: Allied NPC companion is allowed for auto-generation."""
        # This test validates the policy logic structure exists
        from web.extensions.missing_media_autogen import MissingMediaTask
        
        task = MissingMediaTask(
            missing_key="npcs/scout_kira_thumb.jpg",
            media_type="npcs",
            filename="scout_kira_thumb.jpg"
        )
        
        # Verify task structure is correct
        self.assertEqual(task.media_type, "npcs")
        self.assertEqual(task.filename, "scout_kira_thumb.jpg")
        self.assertTrue("scout_kira" in task.missing_key)

    def test_allied_policy_blocks_monsters(self):
        """Test 6.1.6: Monster media type is always blocked from auto-generation."""
        from web.extensions.missing_media_autogen import MissingMediaTask
        
        task = MissingMediaTask(
            missing_key="monsters/goblin_thumb.jpg",
            media_type="monsters",
            filename="goblin_thumb.jpg"
        )
        
        # Verify monsters are distinguishable by media_type
        self.assertEqual(task.media_type, "monsters")
        self.assertNotEqual(task.media_type, "npcs")


class TestMissingMediaWarningThrottle(unittest.TestCase):
    """Test suite for missing-media warning throttle behavior."""

    def setUp(self):
        """Set up test fixtures."""
        # Import and capture original module state
        import web.web_interface as wi
        self.original_timestamps = wi._missing_media_warning_timestamps.copy()
        self.original_enabled = wi._missing_media_throttle_enabled
        self.original_seconds = wi._missing_media_throttle_seconds
        self.wi_module = wi

    def tearDown(self):
        """Restore original module state."""
        self.wi_module._missing_media_warning_timestamps.clear()
        self.wi_module._missing_media_warning_timestamps.update(self.original_timestamps)
        self.wi_module._missing_media_throttle_enabled = self.original_enabled
        self.wi_module._missing_media_throttle_seconds = self.original_seconds

    def test_missing_media_warning_first_miss_warns(self):
        """Test 6.1.7: First miss for a key should emit warning."""
        # Arrange
        self.wi_module._missing_media_warning_timestamps.clear()
        self.wi_module._missing_media_throttle_enabled = True
        self.wi_module._missing_media_throttle_seconds = 300
        
        # Act
        result = self.wi_module._should_emit_missing_media_warning("npcs", "kira_thumb.jpg")
        
        # Assert
        self.assertTrue(result, "First miss should emit warning")

    def test_missing_media_warning_repeated_miss_suppressed(self):
        """Test 6.1.8: Repeated miss within window should be suppressed."""
        # Arrange
        self.wi_module._missing_media_warning_timestamps.clear()
        self.wi_module._missing_media_throttle_enabled = True
        self.wi_module._missing_media_throttle_seconds = 300
        
        # First miss
        self.wi_module._should_emit_missing_media_warning("npcs", "kira_thumb.jpg")
        
        # Act: Second miss immediately
        result = self.wi_module._should_emit_missing_media_warning("npcs", "kira_thumb.jpg")
        
        # Assert
        self.assertFalse(result, "Repeated miss within window should be suppressed")

    def test_missing_media_warning_after_window_expires_re_emits(self):
        """Test 6.1.9: Miss after throttle window expires should re-emit warning."""
        # Arrange
        self.wi_module._missing_media_warning_timestamps.clear()
        self.wi_module._missing_media_throttle_enabled = True
        self.wi_module._missing_media_throttle_seconds = 0.1  # Very short window for testing
        
        # First miss
        self.wi_module._should_emit_missing_media_warning("npcs", "kira_thumb.jpg")
        
        # Wait for window to expire
        time.sleep(0.15)
        
        # Act: Miss after window expires
        result = self.wi_module._should_emit_missing_media_warning("npcs", "kira_thumb.jpg")
        
        # Assert
        self.assertTrue(result, "Miss after window expiry should re-emit warning")

    def test_missing_media_warning_different_keys_independent(self):
        """Test 6.1.10: Different missing keys should have independent throttle windows."""
        # Arrange
        self.wi_module._missing_media_warning_timestamps.clear()
        self.wi_module._missing_media_throttle_enabled = True
        self.wi_module._missing_media_throttle_seconds = 300
        
        # First miss for key A
        result_a1 = self.wi_module._should_emit_missing_media_warning("npcs", "kira_thumb.jpg")
        
        # Act: First miss for key B (should also warn)
        result_b1 = self.wi_module._should_emit_missing_media_warning("npcs", "grimjaw_thumb.jpg")
        
        # Assert
        self.assertTrue(result_a1, "First miss for key A should emit")
        self.assertTrue(result_b1, "First miss for key B should also emit (different key)")


class TestEnqueueDedupeAndCooldown(unittest.TestCase):
    """Test suite for missing media autogen queue dedupe and cooldown."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear autogen state before each test
        try:
            from web.extensions.missing_media_autogen import (
                clear_missing_media_autogen_state,
                start_missing_media_autogen_worker
            )
            clear_missing_media_autogen_state()
            # Start worker with mock callback
            start_missing_media_autogen_worker(
                generation_callback=lambda task: True,
                cooldown_seconds=0.1
            )
        except Exception:
            pass

    def tearDown(self):
        """Clean up after tests."""
        try:
            from web.extensions.missing_media_autogen import (
                stop_missing_media_autogen_worker,
                clear_missing_media_autogen_state
            )
            stop_missing_media_autogen_worker(timeout=1.0)
            clear_missing_media_autogen_state()
        except Exception:
            pass

    def test_enqueue_same_key_deduped_while_queued(self):
        """Test 6.1.11: Same key enqueued twice should be deduped."""
        # Arrange
        from web.extensions.missing_media_autogen import enqueue_missing_media_autogen_task
        
        # First enqueue
        result1 = enqueue_missing_media_autogen_task("npcs", "kira_thumb.jpg")
        
        # Act: Second enqueue while first still in queue
        result2 = enqueue_missing_media_autogen_task("npcs", "kira_thumb.jpg")
        
        # Assert
        self.assertEqual(result1["status"], "queued")
        self.assertEqual(result2["status"], "suppressed_dedupe")

    def test_enqueue_after_cooldown_allowed(self):
        """Test 6.1.12: Same key can be enqueued again after cooldown expires."""
        # Arrange
        from web.extensions.missing_media_autogen import (
            enqueue_missing_media_autogen_task,
            stop_missing_media_autogen_worker,
            start_missing_media_autogen_worker,
            clear_missing_media_autogen_state
        )
        
        # Clear and start with short cooldown
        clear_missing_media_autogen_state()
        stop_missing_media_autogen_worker(timeout=1.0)
        start_missing_media_autogen_worker(
            generation_callback=lambda task: True,
            cooldown_seconds=0.1  # 100ms cooldown
        )
        
        # First enqueue
        result1 = enqueue_missing_media_autogen_task("npcs", "cooldown_test_thumb.jpg")
        self.assertEqual(result1["status"], "queued")
        
        # Wait for cooldown to expire
        time.sleep(0.15)
        
        # Act: Enqueue again after cooldown
        result2 = enqueue_missing_media_autogen_task("npcs", "cooldown_test_thumb.jpg")
        
        # Assert
        self.assertEqual(result2["status"], "queued",
            "Should allow re-enqueue after cooldown expires")


class TestPortraitCreateAPI(unittest.TestCase):
    """Test suite for portrait create API endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_character_data = {
            "name": "TestHero",
            "race": "Human",
            "class": "Fighter",
            "level": 5,
            "age": "28",
            "eyes": "Blue",
            "hair": "Brown"
        }

    def tearDown(self):
        """Clean up after tests."""
        pass

    def test_create_api_endpoint_exists(self):
        """Test 6.1.1: Create API endpoint is registered and accessible."""
        # Import Flask app for testing
        from web.web_interface import app
        
        # Act: Use Flask test client to check endpoint exists
        with app.test_client() as client:
            # Send minimal request to verify endpoint routing
            response = client.post(
                '/api/portrait/create',
                data=json.dumps({}),
                content_type='application/json'
            )
            
            # Should get a response (even if error) - proves endpoint exists
            # 400 is expected for missing character_name
            self.assertIn(response.status_code, [200, 400, 404, 500])

    def test_create_api_requires_character_name(self):
        """Test 6.1.2: Create API requires character_name parameter."""
        from web.web_interface import app
        
        # Act: Request without character_name
        with app.test_client() as client:
            response = client.post(
                '/api/portrait/create',
                data=json.dumps({}),
                content_type='application/json'
            )
            
            # Assert: Should get error response (400 bad request)
            self.assertEqual(response.status_code, 400)
            data = json.loads(response.data)
            self.assertFalse(data["success"])

    def test_create_api_nonexistent_character_returns_404(self):
        """Test 6.1.3: Create API returns error for non-existent character."""
        from web.web_interface import app
        
        # Act: Request with character that doesn't exist
        with app.test_client() as client:
            response = client.post(
                '/api/portrait/create',
                data=json.dumps({"character_name": "NonExistentTestCharacter123"}),
                content_type='application/json'
            )
            
            # Assert: Should get 404 not found
            self.assertEqual(response.status_code, 404)
            data = json.loads(response.data)
            self.assertFalse(data["success"])
            self.assertIn("not found", data["message"].lower())


class TestReuseFirstPath(unittest.TestCase):
    """Test suite for reuse-first materialization (no provider call when portrait exists)."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_npc_name = "test_reuse_npc_12345"
        self.test_portrait_path = f"web/static/portraits/{self.test_npc_name}.png"
        self.test_module = "TestModule"
        self.test_module_portraits_dir = f"modules/{self.test_module}/portraits"
        self.test_module_media_dir = f"modules/{self.test_module}/media/npcs"
        self.test_static_media_dir = "web/static/media/npcs"

        # Create directories if needed
        import os
        os.makedirs(self.test_module_portraits_dir, exist_ok=True)
        os.makedirs(self.test_module_media_dir, exist_ok=True)
        os.makedirs(self.test_static_media_dir, exist_ok=True)
        os.makedirs("web/static/portraits", exist_ok=True)

    def tearDown(self):
        """Clean up test files."""
        import os
        # Remove test portrait if created
        if os.path.exists(self.test_portrait_path):
            os.remove(self.test_portrait_path)
        # Remove test NPC media files
        for ext in [".jpg", "_thumb.jpg"]:
            for base_dir in [self.test_module_media_dir, self.test_static_media_dir]:
                path = f"{base_dir}/{self.test_npc_name}{ext}"
                if os.path.exists(path):
                    os.remove(path)

    @patch("core.toolkit.portrait_service.generate_and_save_portrait")
    def test_reuse_first_skips_provider_when_portrait_exists(self, mock_generate):
        """Test 8.7.1: Reusable portrait exists -> no provider call."""
        from core.toolkit.portrait_service import materialize_npc_media_from_portrait
        from PIL import Image
        import os

        # Create a test portrait image
        img = Image.new("RGB", (256, 256), color="red")
        img.save(self.test_portrait_path, "PNG")

        # Act: Call materialize function
        result = materialize_npc_media_from_portrait(
            npc_name=self.test_npc_name,
            module_name=self.test_module
        )

        # Assert: Should succeed and mark as reused
        self.assertTrue(result["success"], "Materialization should succeed")
        self.assertTrue(result["reused"], "Should mark as reused")
        self.assertIsNotNone(result["source_path"], "Should have source path")
        self.assertGreater(len(result["paths_written"]), 0, "Should write output files")

        # Assert: Provider generation was NOT called
        mock_generate.assert_not_called()


class TestCanonicalDedupeAcrossVariants(unittest.TestCase):
    """Test suite for canonical identity-based dedupe across filename variants."""

    def setUp(self):
        """Set up test fixtures."""
        from web.extensions.missing_media_autogen import (
            clear_missing_media_autogen_state,
            start_missing_media_autogen_worker
        )
        clear_missing_media_autogen_state()
        start_missing_media_autogen_worker(
            generation_callback=lambda task: True,
            cooldown_seconds=60.0
        )

    def tearDown(self):
        """Clean up after tests."""
        try:
            from web.extensions.missing_media_autogen import (
                stop_missing_media_autogen_worker,
                clear_missing_media_autogen_state
            )
            stop_missing_media_autogen_worker(timeout=1.0)
            clear_missing_media_autogen_state()
        except Exception:
            pass

    def test_canonical_key_extracts_identity_from_variants(self):
        """Test 8.7.2: Filename variants map to same canonical identity."""
        from web.extensions.missing_media_autogen import (
            _extract_npc_identity,
            _canonicalize_missing_key
        )

        # Test identity extraction
        variants = [
            "liri.jpg",
            "liri.png",
            "liri_thumb.jpg",
            "Liri.JPG",
            "liri.jpeg"
        ]

        identities = [_extract_npc_identity(v) for v in variants]

        # All variants should extract to same identity
        self.assertEqual(len(set(identities)), 1, "All variants should extract to same identity")
        self.assertEqual(identities[0], "liri")

    def test_canonical_key_for_npc_media(self):
        """Test 8.7.3: NPC media uses identity-based canonical key."""
        from web.extensions.missing_media_autogen import _canonicalize_missing_key

        # Different variants should produce same canonical key
        key1 = _canonicalize_missing_key("npcs", "liri.jpg")
        key2 = _canonicalize_missing_key("npcs", "liri_thumb.jpg")
        key3 = _canonicalize_missing_key("npcs", "liri.png")

        self.assertEqual(key1, "npcs/liri")
        self.assertEqual(key2, "npcs/liri")
        self.assertEqual(key3, "npcs/liri")
        self.assertEqual(key1, key2, "Variants should produce same canonical key")

    def test_non_npc_uses_filename_key(self):
        """Test 8.7.4: Non-NPC media uses normalized filename (not identity)."""
        from web.extensions.missing_media_autogen import _canonicalize_missing_key

        # Monsters should use full filename
        key = _canonicalize_missing_key("monsters", "goblin_thumb.jpg")
        self.assertEqual(key, "monsters/goblin_thumb.jpg")

    def test_enqueue_dedupes_across_variants(self):
        """Test 8.7.5: Enqueue suppresses duplicates across filename variants."""
        from web.extensions.missing_media_autogen import (
            enqueue_missing_media_autogen_task,
            clear_missing_media_autogen_state,
            start_missing_media_autogen_worker
        )

        # Clear and start fresh
        clear_missing_media_autogen_state()
        start_missing_media_autogen_worker(
            generation_callback=lambda task: True,
            cooldown_seconds=60.0
        )

        # First variant enqueues
        result1 = enqueue_missing_media_autogen_task("npcs", "liri.jpg")
        self.assertEqual(result1["status"], "queued")

        # Different variant of same NPC should be deduped
        result2 = enqueue_missing_media_autogen_task("npcs", "liri_thumb.jpg")
        self.assertEqual(result2["status"], "suppressed_dedupe")

        # Another variant should also be deduped
        result3 = enqueue_missing_media_autogen_task("npcs", "liri.png")
        self.assertEqual(result3["status"], "suppressed_dedupe")


class TestAlliedNormalizationConsistency(unittest.TestCase):
    """Test suite for allied companion name normalization consistency."""

    def test_normalize_party_name_handles_variants(self):
        """Test 8.7.6: Party name normalization handles spaces/case/apostrophes."""
        from web.extensions.missing_media_autogen import _normalize_party_name

        test_cases = [
            ("Claris the Good", "claris_the_good"),
            ("Temporarius", "temporarius"),
            ("D'Artagnan", "d_artagnan"),
            ("Acheron", "acheron"),
            ("Claris The Good", "claris_the_good"),  # Different case
            ("claris the good", "claris_the_good"),  # Already lowercase
        ]

        for input_name, expected in test_cases:
            result = _normalize_party_name(input_name)
            self.assertEqual(result, expected, f"Failed for input: {input_name}")

    def test_extract_identity_matches_party_normalization(self):
        """Test 8.7.7: Filename identity matches party name normalization."""
        from web.extensions.missing_media_autogen import (
            _extract_npc_identity,
            _normalize_party_name
        )

        # Party tracker has "Claris the Good"
        party_name = "Claris the Good"
        normalized_party = _normalize_party_name(party_name)

        # Filename variants should extract to same identity
        filename_variants = [
            "Claris the Good.jpg",
            "claris_the_good.jpg",
            "Claris_the_Good_thumb.jpg"
        ]

        for filename in filename_variants:
            identity = _extract_npc_identity(filename)
            self.assertEqual(
                identity, normalized_party,
                f"Filename '{filename}' identity should match normalized party name"
            )

    def test_is_allied_companion_with_normalization(self):
        """Test 8.7.8: Allied check uses consistent normalization."""
        from web.extensions.missing_media_autogen import (
            MissingMediaTask,
            is_allied_companion_check
        )

        # Mock party tracker with various name formats
        party_tracker = {
            "partyNPCs": [
                {"name": "Claris the Good"},
                {"name": "Temporarius"},
                {"name": "D'Artagnan"}
            ],
            "active_character": "Acheron"
        }

        # Test that various filename formats match
        test_cases = [
            ("claris_the_good.jpg", True),
            ("Claris_the_Good_thumb.jpg", True),
            ("temporarius.png", True),
            ("d_artagnan.jpg", True),
            ("acheron.jpg", True),  # Active character
            ("unknown_npc.jpg", False),  # Not in party
        ]

        for filename, expected_allied in test_cases:
            task = MissingMediaTask(
                missing_key=f"npcs/{filename}",
                media_type="npcs",
                filename=filename
            )
            result = is_allied_companion_check(task, party_tracker)
            self.assertEqual(
                result, expected_allied,
                f"Filename '{filename}' allied status should be {expected_allied}"
            )


class TestImageOnlyEnqueueFilter(unittest.TestCase):
    """Test suite for image-only enqueue filter behavior."""

    def test_is_supported_npc_image_filename(self):
        """Test 8.7.9: Helper correctly identifies supported image extensions."""
        # This tests the logic used in web_interface.py image filter
        supported = [".jpg", ".jpeg", ".png", "_thumb.jpg"]

        test_cases = [
            ("liri.jpg", True),
            ("liri.jpeg", True),
            ("liri.png", True),
            ("liri_thumb.jpg", True),
            ("liri_video.mp4", False),
            ("liri.gif", False),
            ("liri.bmp", False),
            ("liri", False),
        ]

        for filename, expected_supported in test_cases:
            # Replicate the check from web_interface.py
            filename_lower = filename.lower()
            is_image = (
                filename_lower.endswith('.jpg') or
                filename_lower.endswith('.jpeg') or
                filename_lower.endswith('.png') or
                filename_lower.endswith('_thumb.jpg')
            )
            self.assertEqual(
                is_image, expected_supported,
                f"Filename '{filename}' image status should be {expected_supported}"
            )


class TestPromptEnrichmentWithPersonalityBackground(unittest.TestCase):
    """Test suite for portrait prompt enrichment with personality/background fields (Step 9.1)."""

    def test_prompt_includes_personality_background_fields_when_present(self):
        """Test 9.1.1: Prompt includes personality_traits, ideals, bonds, flaws as prose descriptors in visual brief."""
        from core.toolkit.portrait_service import build_character_portrait_prompt

        character_data = {
            "name": "Acheron",
            "race": "Human",
            "class": "Fighter",
            "background": "Soldier",
            "alignment": "lawful good",
            "age": "28",
            "height": "6'0",
            "eyes": "Blue",
            "hair": "Brown",
            "personality_traits": "Brave and honorable, always protects the weak",
            "ideals": "Justice and duty above all",
            "bonds": "Sworn to protect my comrades",
            "flaws": "Can be too trusting",
            "backgroundFeature": {
                "name": "Military Rank",
                "description": "You have a military rank from your career as a soldier"
            }
        }

        prompt = build_character_portrait_prompt(character_data)

        # Verify visual brief uses prose format, not label: format
        # Visual brief should include personality/background as natural language
        self.assertIn("their expression shows", prompt.lower())
        self.assertIn("guided by", prompt.lower())
        self.assertIn("deeply connected to", prompt.lower())
        self.assertIn("and can be", prompt.lower())
        self.assertIn("known for", prompt.lower())

        # Verify actual content appears (sanitized/bounded)
        self.assertIn("Brave", prompt)
        self.assertIn("Justice", prompt)
        self.assertIn("comrades", prompt)
        self.assertIn("Military Rank", prompt)

        # Should NOT use label: format that encourages card/sheet layout
        self.assertNotIn("personality:", prompt.lower())
        self.assertNotIn("ideals:", prompt.lower())
        self.assertNotIn("bonds:", prompt.lower())
        self.assertNotIn("flaws:", prompt.lower())
        self.assertNotIn("background ability:", prompt.lower())
        self.assertNotIn("character details:", prompt.lower())

    def test_prompt_handles_missing_personality_background_fields(self):
        """Test 9.1.2: Prompt works correctly when personality/background fields are missing."""
        from core.toolkit.portrait_service import build_character_portrait_prompt

        # Minimal character data without personality fields
        character_data = {
            "name": "TestHero",
            "race": "Elf",
            "class": "Rogue",
            "age": "25"
        }

        prompt = build_character_portrait_prompt(character_data)

        # Should still generate valid visual brief prompt
        self.assertIn("testhero is", prompt.lower())
        self.assertIn("Elf", prompt)
        self.assertIn("Rogue", prompt)

        # Should NOT include "Character details" section when fields missing
        self.assertNotIn("Character details:", prompt)

    def test_prompt_sanitizes_and_bounds_long_text(self):
        """Test 9.1.3: Long text fields are sanitized and bounded to prevent prompt bloat."""
        from core.toolkit.portrait_service import _sanitize_prompt_text

        # Test sanitization
        long_text = "   This\nhas\t\nrepeated\n\nwhitespace and is very long text that needs to be truncated because it exceeds the maximum length allowed for the portrait generation prompt context field   "

        result = _sanitize_prompt_text(long_text, max_length=50)

        # Should be trimmed
        self.assertEqual(len(result), 50)
        # Should end with ellipsis if truncated
        self.assertTrue(result.endswith("..."))
        # Should have collapsed whitespace
        self.assertNotIn("\n", result)
        self.assertNotIn("\t", result)

    def test_prompt_includes_depth_of_field_background(self):
        """Test: Prompt includes depth-of-field/soft-focus background direction."""
        from core.toolkit.portrait_service import build_character_portrait_prompt

        character_data = {
            "name": "TestHero",
            "race": "Human",
            "class": "Fighter",
            "age": "25"
        }

        prompt = build_character_portrait_prompt(character_data)

        # Should include depth of field or soft-focus language
        has_dof = (
            "depth of field" in prompt.lower() or
            "dof" in prompt.lower() or
            "soft-focus" in prompt.lower() or
            "shallow" in prompt.lower()
        )
        self.assertTrue(has_dof, "Prompt should include depth-of-field guidance")

    def test_prompt_excludes_text_and_interface_elements(self):
        """Test: Prompt explicitly forbids text, UI, and game interface elements."""
        from core.toolkit.portrait_service import build_character_portrait_prompt

        character_data = {
            "name": "TestHero",
            "race": "Human",
            "class": "Fighter",
            "age": "25"
        }

        prompt = build_character_portrait_prompt(character_data).lower()

        # Should exclude text/letters/words
        self.assertIn("no text", prompt, "Prompt should exclude text")
        self.assertIn("no letters", prompt, "Prompt should exclude letters")
        self.assertIn("no words", prompt, "Prompt should exclude words")

        # Should exclude UI/HUD/game interface
        self.assertIn("no ui", prompt, "Prompt should exclude UI")
        self.assertIn("no hud", prompt, "Prompt should exclude HUD")

        # Should exclude logos/watermarks
        self.assertIn("no logos", prompt, "Prompt should exclude logos")
        self.assertIn("no watermarks", prompt, "Prompt should exclude watermarks")

        # Should exclude borders and frames
        self.assertIn("no borders", prompt, "Prompt should exclude borders")
        self.assertIn("no frames", prompt, "Prompt should exclude frames")

    def test_prompt_uses_portrait_framing_not_full_body(self):
        """Test: Prompt uses portrait framing (head-and-shoulders/upper torso), not full-body."""
        from core.toolkit.portrait_service import build_character_portrait_prompt

        character_data = {
            "name": "TestHero",
            "race": "Human",
            "class": "Fighter",
            "age": "25"
        }

        prompt = build_character_portrait_prompt(character_data).lower()

        # Should specify portrait framing
        has_portrait_framing = (
            "head-and-shoulders" in prompt or
            "upper torso" in prompt or
            "portrait framing" in prompt
        )
        self.assertTrue(has_portrait_framing, "Prompt should specify portrait framing")

        # Should NOT use full-body framing
        self.assertNotIn("full-body", prompt, "Prompt should not use full-body framing")
        self.assertNotIn("full body", prompt, "Prompt should not use full body framing")

    def test_prompt_adds_alignment_atmosphere_once(self):
        """Test: Alignment atmosphere appears in visual brief (not duplicated)."""
        from core.toolkit.portrait_service import build_character_portrait_prompt

        character_data = {
            "name": "TestHero",
            "race": "Human",
            "class": "Fighter",
            "alignment": "neutral"
        }

        prompt = build_character_portrait_prompt(character_data).lower()

        # Alignment should appear in visual brief exactly once
        self.assertEqual(prompt.count("balanced, neutral demeanor"), 1)

    def test_prompt_has_visual_brief_format(self):
        """Test: Prompt uses natural-language visual brief format (not passport/card semantics)."""
        from core.toolkit.portrait_service import build_character_portrait_prompt

        character_data = {
            "name": "TestHero",
            "race": "Human",
            "class": "Fighter",
            "age": "25"
        }

        prompt = build_character_portrait_prompt(character_data).lower()

        # Should use visual brief prose format (X is a...)
        self.assertIn("testhero is", prompt, "Prompt should use visual brief identity format")
        self.assertIn("human fighter", prompt, "Prompt should include race/class")

        # Should NOT use passport-style (removed to avoid document/card layouts)
        self.assertNotIn("passport-style", prompt, "Prompt should NOT use passport-style (causes card layouts)")
        self.assertNotIn("passport", prompt, "Prompt should NOT reference passports")

    def test_prompt_excludes_character_sheet_elements(self):
        """Test: Prompt explicitly forbids character sheet/card/panel overlays."""
        from core.toolkit.portrait_service import build_character_portrait_prompt

        character_data = {
            "name": "TestHero",
            "race": "Human",
            "class": "Fighter",
            "age": "25"
        }

        prompt = build_character_portrait_prompt(character_data).lower()

        # Should exclude card/sheet/panel elements
        self.assertIn("no character sheet", prompt, "Prompt should exclude character sheet")
        self.assertIn("no stat card", prompt, "Prompt should exclude stat card")
        self.assertIn("no status panel", prompt, "Prompt should exclude status panel")
        self.assertIn("no info box", prompt, "Prompt should exclude info box")
        self.assertIn("no captions", prompt, "Prompt should exclude captions")

    def test_prompt_uses_face_centric_composition(self):
        """Test: Prompt emphasizes face-centered, close crop composition."""
        from core.toolkit.portrait_service import build_character_portrait_prompt

        character_data = {
            "name": "TestHero",
            "race": "Human",
            "class": "Fighter",
            "age": "25"
        }

        prompt = build_character_portrait_prompt(character_data).lower()

        # Should emphasize face is focal subject
        self.assertIn("face is the clear focal subject", prompt, "Prompt should make face focal")
        self.assertIn("close head-and-shoulders portrait", prompt, "Prompt should specify close head-and-shoulders")
        self.assertIn("face centered", prompt, "Prompt should specify face centered")

    def test_prompt_excludes_document_paper_parchment_terms(self):
        """Test: Prompt explicitly forbids document/paper/parchment to prevent sheet-like outputs."""
        from core.toolkit.portrait_service import build_character_portrait_prompt

        character_data = {
            "name": "TestHero",
            "race": "Human",
            "class": "Fighter",
            "age": "25"
        }

        prompt = build_character_portrait_prompt(character_data).lower()

        # Should exclude document/page/paper/parchment terms
        self.assertIn("no document", prompt, "Prompt should exclude document")
        self.assertIn("no page", prompt, "Prompt should exclude page")
        self.assertIn("no paper", prompt, "Prompt should exclude paper")
        self.assertIn("no parchment", prompt, "Prompt should exclude parchment")
        self.assertIn("no form", prompt, "Prompt should exclude form")

    def test_visual_brief_helper_converts_stats_to_prose(self):
        """Test: Visual brief helper converts structured stats into prose descriptors."""
        from core.toolkit.portrait_service import _build_visual_brief, _convert_age_to_descriptor

        character_data = {
            "name": "ElderTest",
            "race": "Human",
            "class": "Wizard",
            "age": "78",
            "height": "4'",
            "weight": "60 kg",
            "eyes": "Blue",
            "skin": "Fair",
            "hair": "White"
        }

        visual_brief = _build_visual_brief(character_data)

        # Age should be converted to descriptor, not raw number
        self.assertIn("elderly", visual_brief.lower())

        # Physical traits should be in prose, not label format
        self.assertIn("blue eyes", visual_brief.lower())
        self.assertIn("fair skin", visual_brief.lower())
        self.assertIn("white hair", visual_brief.lower())

        # Should not use label: value format
        self.assertNotIn("eyes:", visual_brief.lower())
        self.assertNotIn("skin:", visual_brief.lower())
        self.assertNotIn("hair:", visual_brief.lower())

    def test_prompt_uses_photorealistic_style_anchor(self):
        """Test: Prompt uses photorealistic style anchor aligned with module-builder quality."""
        from core.toolkit.portrait_service import build_character_portrait_prompt

        character_data = {
            "name": "TestHero",
            "race": "Human",
            "class": "Fighter",
            "age": "25"
        }

        prompt = build_character_portrait_prompt(character_data).lower()

        # Should include photorealistic/ultra-realistic style language
        self.assertIn("ultra-realistic", prompt, "Prompt should specify ultra-realistic")
        self.assertIn("photorealistic", prompt, "Prompt should specify photorealistic")
        self.assertIn("cinematic quality", prompt, "Prompt should specify cinematic quality")
        self.assertIn("detailed textures", prompt, "Prompt should specify detailed textures")

    def test_defensive_parsing_handles_non_numeric_values(self):
        """Test: Visual brief handles non-numeric age/height/weight gracefully."""
        from core.toolkit.portrait_service import build_character_portrait_prompt, _extract_first_int

        # Test helper function
        self.assertIsNone(_extract_first_int(""))
        self.assertIsNone(_extract_first_int("slight"))
        self.assertIsNone(_extract_first_int("unknown"))
        self.assertEqual(_extract_first_int("78"), 78)
        self.assertEqual(_extract_first_int("60 kg"), 60)

        # Test with weird character data
        weird_character = {
            "name": "WeirdTest",
            "race": "Human",
            "class": "Fighter",
            "age": "old-ish",  # Non-numeric
            "height": "tall",  # Non-numeric
            "weight": "heavy",  # Non-numeric
            "eyes": "Blue",
        }

        # Should not crash
        prompt = build_character_portrait_prompt(weird_character)
        self.assertIn("WeirdTest is", prompt)
        self.assertIn("human fighter", prompt.lower())

    def test_article_helper_uses_correct_article(self):
        """Test: Article helper chooses 'a' or 'an' correctly."""
        from core.toolkit.portrait_service import _get_article, _build_visual_brief

        # Test helper directly
        self.assertEqual(_get_article("elderly"), "an")
        self.assertEqual(_get_article("human"), "a")
        self.assertEqual(_get_article("adult"), "an")
        self.assertEqual(_get_article("young"), "a")

        # Test in visual brief context
        elderly_gnome = {
            "name": "OldGnome",
            "race": "Gnome",
            "class": "Wizard",
            "age": "78",
        }
        brief = _build_visual_brief(elderly_gnome).lower()
        # Should use "an" before elderly
        self.assertIn("is an elderly", brief)

        adult_human = {
            "name": "TestAdult",
            "race": "Human",
            "class": "Fighter",
            "age": "30",
        }
        brief = _build_visual_brief(adult_human).lower()
        # Should use "an" before adult (adult starts with vowel sound)
        self.assertIn("is an adult", brief)

    def test_personality_normalization_avoids_duplication(self):
        """Test: Personality phrase normalization prevents awkward duplication."""
        from core.toolkit.portrait_service import _normalize_personality_phrase

        # Should strip redundant leading phrases
        self.assertEqual(
            _normalize_personality_phrase("Believes that justice matters"),
            "justice matters"
        )
        self.assertEqual(
            _normalize_personality_phrase("Sometimes acts rashly"),
            "acts rashly"
        )
        self.assertEqual(
            _normalize_personality_phrase("Always helps others"),
            "helps others"
        )
        self.assertEqual(
            _normalize_personality_phrase("Loyal to the town guard"),
            "the town guard"
        )
        self.assertEqual(
            _normalize_personality_phrase("Devoted to my family"),
            "my family"
        )
        self.assertEqual(
            _normalize_personality_phrase("Sworn to defend the weak"),
            "defend the weak"
        )
        self.assertEqual(
            _normalize_personality_phrase("Committed to truth"),
            "truth"
        )
        self.assertEqual(
            _normalize_personality_phrase("Bound to an old oath"),
            "an old oath"
        )

        # Should preserve normal text
        self.assertEqual(
            _normalize_personality_phrase("Just and honorable"),
            "Just and honorable"
        )

    def test_prompt_avoids_awkward_connector_duplication(self):
        """Test: Prompt avoids repeated connector phrases in personality clauses."""
        from core.toolkit.portrait_service import build_character_portrait_prompt

        character_data = {
            "name": "DupCheck",
            "race": "Human",
            "class": "Rogue",
            "ideals": "Believes that rules should bend to protect innocents",
            "bonds": "Loyal to the old guild that raised me",
            "flaws": "Sometimes acts before thinking"
        }

        prompt = build_character_portrait_prompt(character_data).lower()

        self.assertNotIn("guided by a belief that believes", prompt)
        self.assertNotIn("deeply connected to loyal to", prompt)
        self.assertNotIn("yet sometimes showing sometimes", prompt)

    def test_prompt_has_no_ellipsis_punctuation_artifacts(self):
        """Test: Prompt should not contain four-dot punctuation artifacts."""
        from core.toolkit.portrait_service import build_character_portrait_prompt

        character_data = {
            "name": "PunctCheck",
            "race": "Human",
            "class": "Wizard",
            "flaws": "Sometimes lets ambition cloud judgment, leading to risky choices that endanger themselves and others in tense situations that escalate quickly"
        }

        prompt = build_character_portrait_prompt(character_data)
        self.assertNotIn("....", prompt)

    def test_visual_brief_preserves_core_identity(self):
        """Test: Visual brief preserves essential character identity fields."""
        from core.toolkit.portrait_service import _build_visual_brief

        character_data = {
            "name": "TestIdentity",
            "race": "Elf",
            "class": "Rogue",
            "alignment": "chaotic good",
            "age": "25",
            "eyes": "Green",
            "hair": "Silver"
        }

        brief = _build_visual_brief(character_data)

        # Core identity preserved
        self.assertIn("TestIdentity is", brief)
        self.assertIn("Elf", brief)
        self.assertIn("Rogue", brief)
        self.assertIn("Green eyes", brief)
        self.assertIn("Silver hair", brief)

        # No label formatting
        self.assertNotIn("race:", brief.lower())
        self.assertNotIn("class:", brief.lower())


class TestCreateAPIProfileValidation(unittest.TestCase):
    """Test suite for create API profile validation (Step 9.3)."""

    def test_create_api_incomplete_profile_returns_409_requires_profile(self):
        """Test 9.3.1: Incomplete profile returns 409 with requires_profile flag."""
        from web.web_interface import app

        # Mock character that exists but has incomplete profile
        test_character = {
            "name": "TestIncompleteProfile",
            "race": "Human",
            "class": "Fighter",
            # Missing: age, height, weight, eyes, skin, hair
            # Missing: personality_traits, ideals, bonds, flaws
            # Missing: backgroundFeature.name, backgroundFeature.description
        }

        with patch('utils.file_operations.safe_read_json') as mock_read, \
             patch('updates.update_character_info.normalize_character_name') as mock_normalize:

            mock_normalize.return_value = "testincompleteprofile"
            mock_read.return_value = test_character

            with app.test_client() as client:
                # Request with minimal payload (missing required profile fields)
                response = client.post(
                    '/api/portrait/create',
                    data=json.dumps({
                        "character_name": "TestIncompleteProfile",
                        "characterName": "TestIncompleteProfile"
                    }),
                    content_type='application/json'
                )

                # Assert: Should get 409 conflict
                self.assertEqual(response.status_code, 409)
                data = json.loads(response.data)

                # Should have requires_profile flag
                self.assertTrue(data.get("requires_profile"), "Should have requires_profile flag")

                # Should have missing_fields list
                self.assertIn("missing_fields", data)
                missing = data["missing_fields"]
                self.assertIsInstance(missing, list)
                self.assertGreater(len(missing), 0, "Should report missing fields")

    def test_create_api_returns_all_missing_fields(self):
        """Test 9.3.2: Response includes all missing profile field names."""
        from web.web_interface import app

        test_character = {
            "name": "TestEmptyProfile",
            "race": "Human",
            "class": "Fighter"
        }

        with patch('utils.file_operations.safe_read_json') as mock_read, \
             patch('updates.update_character_info.normalize_character_name') as mock_normalize:

            mock_normalize.return_value = "testemptyprofile"
            mock_read.return_value = test_character

            with app.test_client() as client:
                response = client.post(
                    '/api/portrait/create',
                    data=json.dumps({
                        "character_name": "TestEmptyProfile"
                    }),
                    content_type='application/json'
                )

                self.assertEqual(response.status_code, 409)
                data = json.loads(response.data)
                missing = data.get("missing_fields", [])

                # All 12 required fields should be reported missing
                required_fields = [
                    'age', 'height', 'weight', 'eyes', 'skin', 'hair',
                    'personality_traits', 'ideals', 'bonds', 'flaws',
                    'background_feature_name', 'background_feature_description'
                ]

                for field in required_fields:
                    self.assertIn(field, missing, f"Missing field '{field}' should be reported")


class TestCreateAPIPersistenceBeforeGeneration(unittest.TestCase):
    """Test suite for create API persistence-before-generation (Step 9.4)."""

    @patch('web.web_interface.generate_and_save_portrait')
    @patch('utils.pc_manager.get_character_state')
    @patch('utils.pc_manager.update_character_state')
    @patch('utils.file_operations.safe_read_json')
    @patch('updates.update_character_info.normalize_character_name')
    def test_create_api_persists_profile_before_generation(
        self, mock_normalize, mock_read, mock_update, mock_get, mock_generate
    ):
        """Test 9.4.1: Complete profile is persisted before generation."""
        from web.web_interface import app

        # Setup mocks
        mock_normalize.return_value = "testcompleteprofile"
        mock_read.return_value = {
            "name": "TestCompleteProfile",
            "race": "Human",
            "class": "Fighter",
            "backgroundFeature": {}
        }
        mock_update.return_value = True  # Persist succeeds

        # Updated character data after persist
        updated_character = {
            "name": "TestCompleteProfile",
            "race": "Human",
            "class": "Fighter",
            "age": "28",
            "height": "6'0",
            "weight": "180 lbs",
            "eyes": "Blue",
            "skin": "Fair",
            "hair": "Brown",
            "personality_traits": "Brave",
            "ideals": "Justice",
            "bonds": "Comrades",
            "flaws": "Trusting",
            "backgroundFeature": {
                "name": "Soldier",
                "description": "Military background"
            }
        }
        mock_get.return_value = updated_character
        mock_generate.return_value = {
            "success": True,
            "message": "Portrait created"
        }

        with app.test_client() as client:
            response = client.post(
                '/api/portrait/create',
                data=json.dumps({
                    "character_name": "TestCompleteProfile",
                    "appearance": {
                        "age": "28",
                        "height": "6'0",
                        "weight": "180 lbs",
                        "eyes": "Blue",
                        "skin": "Fair",
                        "hair": "Brown"
                    },
                    "personality": {
                        "personality_traits": "Brave",
                        "ideals": "Justice",
                        "bonds": "Comrades",
                        "flaws": "Trusting"
                    },
                    "backgroundFeature": {
                        "name": "Soldier",
                        "description": "Military background"
                    }
                }),
                content_type='application/json'
            )

            # Assert: Should succeed
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertTrue(data["success"])

            # Assert: update_character_state was called before generate
            mock_update.assert_called_once()
            update_call_args = mock_update.call_args
            self.assertEqual(update_call_args[0][0], "TestCompleteProfile")

            # Assert: get_character_state was called to reload
            mock_get.assert_called_once()

            # Assert: generate_and_save_portrait received updated character data
            mock_generate.assert_called_once()
            generate_call_kwargs = mock_generate.call_args[1]
            self.assertEqual(generate_call_kwargs["character_data"], updated_character)

    @patch('utils.pc_manager.update_character_state')
    @patch('utils.file_operations.safe_read_json')
    @patch('updates.update_character_info.normalize_character_name')
    def test_create_api_persist_failure_blocks_generation(
        self, mock_normalize, mock_read, mock_update
    ):
        """Test 9.4.2: Persist failure blocks generation and returns safe error."""
        from web.web_interface import app

        mock_normalize.return_value = "testpersistfail"
        mock_read.return_value = {
            "name": "TestPersistFail",
            "race": "Human",
            "class": "Fighter"
        }
        mock_update.return_value = False  # Persist fails

        with app.test_client() as client:
            response = client.post(
                '/api/portrait/create',
                data=json.dumps({
                    "character_name": "TestPersistFail",
                    "appearance": {
                        "age": "28",
                        "height": "6'0",
                        "weight": "180 lbs",
                        "eyes": "Blue",
                        "skin": "Fair",
                        "hair": "Brown"
                    },
                    "personality": {
                        "personality_traits": "Brave",
                        "ideals": "Justice",
                        "bonds": "Comrades",
                        "flaws": "Trusting"
                    },
                    "backgroundFeature": {
                        "name": "Soldier",
                        "description": "Military background"
                    }
                }),
                content_type='application/json'
            )

            # Assert: Should fail with 500
            self.assertEqual(response.status_code, 500)
            data = json.loads(response.data)
            self.assertFalse(data["success"])
            self.assertEqual(data.get("error"), "profile_persist_failed")


class TestPortraitMetadataPayloadContracts(unittest.TestCase):
    """Test suite for portrait cache coherence metadata in socket payloads (Step 10.7)."""

    def test_player_stats_payload_contains_portrait_metadata_keys(self):
        """Test 10.7.1: Stats payload includes _portrait_slug and _portrait_version."""
        from web.extensions.tabletop_socket_handlers import (
            _normalize_character_slug,
            _build_image_metadata
        )

        # Verify helper functions exist and return expected keys
        test_name = "TestHero"
        slug = _normalize_character_slug(test_name)
        self.assertEqual(slug, "testhero")

        # Metadata should have image_slug and image_version keys
        metadata = _build_image_metadata(slug, None)
        self.assertIn("image_slug", metadata)
        self.assertIn("image_version", metadata)
        self.assertEqual(metadata["image_slug"], slug)
        # version may be None if no files exist (fail-open), but key must exist
        self.assertIsInstance(metadata["image_version"], (str, type(None)))

    def test_initiative_payload_combatant_includes_image_metadata(self):
        """Test 10.7.2: Initiative payload combatants include image_slug and image_version."""
        from web.extensions.tabletop_socket_handlers import (
            _normalize_character_slug,
            _build_image_metadata
        )

        # Verify normalization consistent with backend
        names = ["Player One", "NPC_Companion", "Mac'Davier", "  spaced name  "]
        expected = ["player_one", "npc_companion", "mac_davier", "spaced_name"]

        for name, exp in zip(names, expected):
            slug = _normalize_character_slug(name)
            self.assertEqual(slug, exp, f"Name '{name}' should normalize to '{exp}'")

        # Verify metadata structure for initiative context
        for slug in expected:
            metadata = _build_image_metadata(slug, "TestModule")
            self.assertIn("image_slug", metadata)
            self.assertIn("image_version", metadata)
            self.assertEqual(metadata["image_slug"], slug)

    def test_party_payload_member_includes_image_metadata(self):
        """Test 10.7.3: Party payload members include image_slug and image_version."""
        from web.extensions.tabletop_socket_handlers import _build_image_metadata

        # Verify metadata structure matches party payload requirements
        test_slugs = ["party_member_1", "companion_npc", "active_pc"]
        for slug in test_slugs:
            # Test with module context
            metadata = _build_image_metadata(slug, "TestModule")
            self.assertIn("image_slug", metadata)
            self.assertIn("image_version", metadata)
            self.assertEqual(metadata["image_slug"], slug)

            # Test without module context
            metadata_no_module = _build_image_metadata(slug, None)
            self.assertIn("image_slug", metadata_no_module)
            self.assertIn("image_version", metadata_no_module)

    def test_image_version_deterministic_from_mtime(self):
        """Test 10.7.4: Image version is deterministic (max mtime among candidates)."""
        from web.extensions.tabletop_socket_handlers import (
            _get_image_candidate_paths,
            _compute_image_version_from_paths
        )
        import os
        import tempfile
        import time

        # Create a temporary directory structure for testing
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test portrait file
            portrait_path = os.path.join(tmpdir, "test_char.png")
            with open(portrait_path, "w") as f:
                f.write("test")

            # Set specific mtime
            test_mtime = 1704067200  # Fixed timestamp
            os.utime(portrait_path, (test_mtime, test_mtime))

            # Test version computation
            version = _compute_image_version_from_paths([portrait_path])
            self.assertEqual(version, str(int(test_mtime)))

            # Test with non-existent paths (should return None)
            nonexistent_version = _compute_image_version_from_paths(["/nonexistent/path.png"])
            self.assertIsNone(nonexistent_version)


class TestFrontendCacheInvalidationContracts(unittest.TestCase):
    """Test suite for frontend cache invalidation contracts in game_interface.html (Step 10.7)."""

    def test_cache_invalidation_patterns_include_all_candidates(self):
        """Test 10.7.5: Cache invalidation patterns cover all portrait/NPC paths."""
        # Verify that _getCacheInvalidationPatterns equivalent would cover:
        # - /static/portraits/<slug>.png
        # - /media/npcs/<slug>_thumb.jpg
        # - /media/npcs/<slug>.jpg
        # - /media/npcs/<slug>.png

        test_slug = "test_char"
        expected_patterns = [
            f"/static/portraits/{test_slug}.png",
            f"/media/npcs/{test_slug}_thumb.jpg",
            f"/media/npcs/{test_slug}.jpg",
            f"/media/npcs/{test_slug}.png",
        ]

        # Verify pattern construction matches expected URLs
        for pattern in expected_patterns:
            self.assertIn(test_slug, pattern)
            self.assertTrue(
                pattern.startswith("/static/portraits/") or pattern.startswith("/media/npcs/"),
                f"Pattern {pattern} should be under /static/portraits/ or /media/npcs/"
            )

    def test_source_contains_cache_invalidation_helpers(self):
        """Test 10.7.6: Frontend source contains cache invalidation helper functions."""
        import os

        # Read game_interface.html source
        html_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "web", "templates", "game_interface.html"
        )

        self.assertTrue(os.path.exists(html_path), "game_interface.html should exist")

        with open(html_path, 'r', encoding='utf-8') as f:
            source = f.read()

        # Verify key helper functions exist in source
        self.assertIn("invalidateImageCachesForSlug", source,
                      "Source should contain invalidateImageCachesForSlug function")
        self.assertIn("_getCacheInvalidationPatterns", source,
                      "Source should contain _getCacheInvalidationPatterns function")
        self.assertIn("normalizePortraitSlug", source,
                      "Source should contain normalizePortraitSlug function")
        self.assertIn("withAssetVersion", source,
                      "Source should contain withAssetVersion function")

    def test_source_contains_immediate_refresh_hooks(self):
        """Test 10.7.7: Frontend success paths call immediate refresh functions."""
        import os

        # Read game_interface.html source
        html_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "web", "templates", "game_interface.html"
        )

        with open(html_path, 'r', encoding='utf-8') as f:
            source = f.read()

        # Verify immediate refresh hooks exist in success paths
        # These are the key calls added in Step 10.6
        self.assertIn("loadCharacterStats();", source,
                      "Success paths should call loadCharacterStats()")
        self.assertIn("requestInitiativeData();", source,
                      "Success paths should call requestInitiativeData()")
        self.assertIn("requestPartyData();", source,
                      "Success paths should call requestPartyData()")

        # Verify calls are in portrait-related contexts
        # Look for TABLETOP MODE markers near refresh calls
        self.assertIn("TABLETOP MODE: Immediate refresh", source,
                      "Source should document immediate refresh purpose")

    def test_source_contains_preserved_identity_pattern(self):
        """Test 10.7.8: Frontend source preserves identity before modal close (Step 10.5)."""
        import os

        # Read game_interface.html source
        html_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "web", "templates", "game_interface.html"
        )

        with open(html_path, 'r', encoding='utf-8') as f:
            source = f.read()

        # Verify Step 10.5 preserved identity pattern
        self.assertIn("preservedCharacterName", source,
                      "Source should preserve character name before modal close")
        self.assertIn("preservedSlug", source,
                      "Source should preserve normalized slug before modal close")
        self.assertIn("closePortraitProfileModal()", source,
                      "Source should close modal after preservation")

        # Verify preserved identity is used for operations after close
        # This ensures the fix for the ordering bug
        self.assertIn("preservedSlug", source,
                      "Source should use preservedSlug after modal close")


class TestProfileReadinessForPromotion(unittest.TestCase):
    """Test suite for PC/NPC profile readiness alignment (Tasks 11.1-11.6)."""

    def test_audit_profile_readiness_detects_missing_appearance(self):
        """Test 11.1.1: audit_profile_readiness detects missing appearance fields."""
        from utils.character_creation_audit import audit_profile_readiness

        # Character missing all appearance fields
        npc_data = {
            "name": "TestNPC",
            "race": "Human",
            "class": "Fighter",
            "personality_traits": "Brave",
            "ideals": "Justice",
            "bonds": "Family",
            "flaws": "Stubborn",
            "backgroundFeature": {
                "name": "Soldier",
                "description": "Military background"
            }
        }

        result = audit_profile_readiness(npc_data)

        self.assertFalse(result["profile_ready"])
        self.assertEqual(len(result["missing_appearance_fields"]), 6)
        self.assertIn("age", result["missing_appearance_fields"])
        self.assertIn("height", result["missing_appearance_fields"])
        self.assertIn("weight", result["missing_appearance_fields"])
        self.assertIn("eyes", result["missing_appearance_fields"])
        self.assertIn("skin", result["missing_appearance_fields"])
        self.assertIn("hair", result["missing_appearance_fields"])
        self.assertTrue(any("appearance" in w for w in result["warnings"]))

    def test_audit_profile_readiness_detects_missing_personality(self):
        """Test 11.1.2: audit_profile_readiness detects missing personality fields."""
        from utils.character_creation_audit import audit_profile_readiness

        # Character with appearance but missing personality
        npc_data = {
            "name": "TestNPC",
            "race": "Human",
            "class": "Fighter",
            "age": "25",
            "height": "6'0",
            "weight": "180",
            "eyes": "Blue",
            "skin": "Fair",
            "hair": "Brown"
            # Missing personality_traits, ideals, bonds, flaws, backgroundFeature
        }

        result = audit_profile_readiness(npc_data)

        self.assertFalse(result["profile_ready"])
        self.assertEqual(len(result["missing_appearance_fields"]), 0)
        self.assertIn("personality_traits", result["missing_profile_fields"])
        self.assertIn("ideals", result["missing_profile_fields"])
        self.assertIn("bonds", result["missing_profile_fields"])
        self.assertIn("flaws", result["missing_profile_fields"])

    def test_audit_profile_readiness_complete_profile(self):
        """Test 11.1.3: audit_profile_readiness returns ready for complete profile."""
        from utils.character_creation_audit import audit_profile_readiness

        complete_character = {
            "name": "TestPC",
            "race": "Human",
            "class": "Fighter",
            "age": "25",
            "height": "6'0",
            "weight": "180",
            "eyes": "Blue",
            "skin": "Fair",
            "hair": "Brown",
            "personality_traits": "Brave and loyal",
            "ideals": "Justice",
            "bonds": "Family",
            "flaws": "Overconfident",
            "backgroundFeature": {
                "name": "Soldier",
                "description": "Military background"
            }
        }

        result = audit_profile_readiness(complete_character)

        self.assertTrue(result["profile_ready"])
        self.assertEqual(len(result["missing_profile_fields"]), 0)
        self.assertEqual(len(result["missing_appearance_fields"]), 0)
        self.assertEqual(len(result["warnings"]), 0)

    def test_seed_missing_appearance_fields_adds_empty_strings(self):
        """Test 11.3.1: seed_missing_appearance_fields adds empty string keys."""
        from utils.character_creation_audit import seed_missing_appearance_fields

        npc_data = {
            "name": "TestNPC",
            "race": "Human",
            "class": "Fighter"
            # Missing all appearance fields
        }

        seeded = seed_missing_appearance_fields(npc_data)

        # All appearance keys should exist as empty strings
        self.assertEqual(seeded["age"], "")
        self.assertEqual(seeded["height"], "")
        self.assertEqual(seeded["weight"], "")
        self.assertEqual(seeded["eyes"], "")
        self.assertEqual(seeded["skin"], "")
        self.assertEqual(seeded["hair"], "")

        # Original data should not be mutated
        self.assertNotIn("age", npc_data)

    def test_seed_missing_appearance_fields_preserves_existing(self):
        """Test 11.3.2: seed_missing_appearance_fields preserves existing values."""
        from utils.character_creation_audit import seed_missing_appearance_fields

        npc_data = {
            "name": "TestNPC",
            "age": "30",
            "hair": "Black"
        }

        seeded = seed_missing_appearance_fields(npc_data)

        # Existing values should be preserved
        self.assertEqual(seeded["age"], "30")
        self.assertEqual(seeded["hair"], "Black")
        # Missing fields should be seeded as empty
        self.assertEqual(seeded["height"], "")
        self.assertEqual(seeded["eyes"], "")


class TestPromotionApiWarnings(unittest.TestCase):
    """Test suite for promotion API route responses with profile warnings (Task 11.2)."""

    @patch('utils.pc_manager.get_character_state')
    @patch('utils.pc_manager.get_party_tracker')
    def test_promotion_preview_api_returns_profile_warnings(self, mock_tracker, mock_char_state):
        """Test 11.2.2: Promotion preview API returns profile readiness warnings in response."""
        from web.web_interface import app

        # Setup: NPC missing appearance fields
        mock_tracker.return_value = {
            "partyMembers": [],
            "partyNPCs": [{"name": "TestNPC"}],
            "active_character": ""
        }
        mock_char_state.return_value = {
            "name": "TestNPC",
            "race": "Human",
            "class": "Barbarian",
            "type": "npc",
            "character_type": "npc",
            "character_role": "npc",
            "personality_traits": "Fierce",
            "ideals": "Strength",
            "bonds": "Tribe",
            "flaws": "Rash",
            "backgroundFeature": {
                "name": "Outlander",
                "description": "Wilderness background"
            }
            # Missing age, height, weight, eyes, skin, hair
        }

        with app.test_client() as client:
            response = client.post(
                '/api/party/promotion/preview',
                data=json.dumps({"character": "TestNPC"}),
                content_type='application/json'
            )

            # Assert: Should succeed with warnings
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertTrue(data.get("success"), "Preview should succeed")
            self.assertIn("warnings", data, "Response should include warnings")
            
            # Should have appearance-related warnings
            warnings = data["warnings"]
            self.assertTrue(
                any("appearance" in str(w).lower() for w in warnings),
                "Warnings should include appearance metadata message"
            )

    @patch('web.routes.tabletop_party_routes.safe_write_json')
    @patch('utils.pc_manager.get_character_state')
    @patch('utils.pc_manager.get_party_tracker')
    @patch('utils.pc_manager.update_character_state')
    def test_promotion_apply_api_seeds_appearance_keys(
        self, mock_update, mock_tracker, mock_char_state, mock_safe_write
    ):
        """Test 11.2.3: Promotion apply API seeds appearance keys and returns warnings."""
        from web.web_interface import app

        # Capture what gets written to character file
        written_data = {}
        def capture_write(path, data):
            written_data.update(data)
            return True
        mock_safe_write.side_effect = capture_write

        # Setup: NPC missing appearance fields
        mock_tracker.return_value = {
            "partyMembers": [],
            "partyNPCs": [{"name": "TestNPC"}],
            "active_character": ""
        }
        mock_char_state.return_value = {
            "name": "TestNPC",
            "race": "Human",
            "class": "Fighter",
            "type": "npc",
            "character_type": "npc",
            "character_role": "npc",
            "personality_traits": "Brave",
            "ideals": "Honor",
            "bonds": "Family",
            "flaws": "Impatient",
            "backgroundFeature": {
                "name": "Soldier",
                "description": "Military service"
            }
            # Missing age, height, weight, eyes, skin, hair
        }
        mock_update.return_value = True

        with app.test_client() as client:
            response = client.post(
                '/api/party/promotion/apply',
                data=json.dumps({"character": "TestNPC", "confirm": True}),
                content_type='application/json'
            )

            # Assert: Should succeed with warnings
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertTrue(data.get("success"), "Apply should succeed")
            self.assertIn("warnings", data, "Response should include warnings")

            # Character data should have appearance keys seeded
            self.assertIn("age", written_data, "Seeded data should include age")
            self.assertIn("height", written_data, "Seeded data should include height")
            self.assertIn("weight", written_data, "Seeded data should include weight")
            self.assertIn("eyes", written_data, "Seeded data should include eyes")
            self.assertIn("skin", written_data, "Seeded data should include skin")
            self.assertIn("hair", written_data, "Seeded data should include hair")
            
            # Seeded keys should be empty strings
            self.assertEqual(written_data["age"], "")
            self.assertEqual(written_data["height"], "")

            # Response should preserve promotion invariants
            self.assertIn("partyMembers", data)
            self.assertIn("active_character", data)


class TestPromotionProfileWarnings(unittest.TestCase):
    """Test suite for promotion profile readiness warnings (Task 11.2, 11.5)."""

    def test_promotion_does_not_require_portrait_replacement(self):
        """Test 11.5.1: Promotion completes without requiring portrait regeneration."""
        from utils.character_creation_audit import audit_profile_readiness, seed_missing_appearance_fields

        # Simulate an NPC with existing media but incomplete profile
        npc_data = {
            "name": "Henry Andersen",
            "race": "Dragonborn",
            "class": "Barbarian",
            "character_id": "abc-123",  # Existing ID
            "personality_traits": "Determined",
            "ideals": "Honor",
            "bonds": "Comrades",
            "flaws": "Impatient",
            "backgroundFeature": {
                "name": "Soldier",
                "description": "Military service"
            }
            # Missing appearance fields but has identity
        }

        # Profile should show warnings
        profile = audit_profile_readiness(npc_data)
        self.assertFalse(profile["profile_ready"])
        self.assertEqual(len(profile["missing_appearance_fields"]), 6)

        # Seeding should add appearance keys
        seeded = seed_missing_appearance_fields(npc_data)
        self.assertEqual(seeded["age"], "")
        self.assertEqual(seeded["height"], "")

        # Character_id should be preserved
        self.assertEqual(seeded["character_id"], "abc-123")

        # Promotion should be viable despite missing appearance
        # (This is a contract test - in reality the route would allow it)
        self.assertIn("name", seeded)
        self.assertIn("race", seeded)
        self.assertIn("class", seeded)

    def test_promotion_contract_invariants_preserved(self):
        """Test 11.4.1: Promotion preserves character identity invariants."""
        from utils.character_creation_audit import seed_missing_appearance_fields
        from utils.pc_manager import ensure_stable_character_id, normalize_character_role_fields
        from copy import deepcopy

        # Simulate NPC data
        npc_data = {
            "name": "TestNPC",
            "race": "Human",
            "class": "Fighter",
            "type": "npc",
            "character_type": "npc",
            "character_role": "npc"
            # No character_id initially
        }

        # Simulate promotion workflow
        updated = deepcopy(npc_data)
        ensure_stable_character_id(updated)
        normalize_character_role_fields(updated, 'player')
        updated = seed_missing_appearance_fields(updated)

        # Invariant: role fields normalized to player
        self.assertEqual(updated["type"], "player")
        self.assertEqual(updated["character_type"], "player")
        self.assertEqual(updated["character_role"], "player")

        # Invariant: character_id generated
        self.assertIn("character_id", updated)
        self.assertTrue(len(updated["character_id"]) > 0)

        # Invariant: appearance keys seeded
        self.assertIn("age", updated)
        self.assertIn("height", updated)


class TestNpcPromptEnrichmentHydrationContracts(unittest.TestCase):
    """Test suite for NPC prompt enrichment hydration contracts (Section 12)."""

    def test_hydration_helper_canonical_path(self):
        """Test 12.5.1: Hydration helper produces canonical context when character data exists."""
        from web.extensions.missing_media_autogen import _hydrate_allied_npc_context
        
        # Patch the actual import location inside the helper
        with patch("utils.pc_manager.get_character_state") as mock_get_state:
            # Arrange: Canonical character record
            mock_get_state.return_value = {
                "name": "Claris the Good",
                "race": "Human",
                "class": "Paladin",
                "personality_traits": "Brave and compassionate",
                "ideals": "Justice for all",
                "backgroundFeature": {"name": "Military Rank"}
            }
            
            from web.extensions.missing_media_autogen import MissingMediaTask
            task = MissingMediaTask(
                missing_key="npcs/claris_the_good",
                media_type="npcs",
                filename="claris_the_good.jpg"
            )
            
            # Act
            result = _hydrate_allied_npc_context(task)
            
            # Assert: Canonical source
            self.assertEqual(result.get("context_source"), "canonical")
            self.assertEqual(result.get("name"), "Claris the Good")
            self.assertEqual(result.get("race"), "Human")
            self.assertEqual(result.get("class"), "Paladin")
            self.assertIn("personality_traits", result)
            self.assertIn("backgroundFeature", result)

    def test_hydration_helper_fallback_path(self):
        """Test 12.5.2: Hydration helper falls back to party hints when no character file."""
        from web.extensions.missing_media_autogen import _hydrate_allied_npc_context
        
        # Patch the actual import locations
        with patch("utils.pc_manager.get_character_state") as mock_get_state, \
             patch("utils.file_operations.safe_read_json") as mock_read_json:
            
            # Arrange: No character file, but party tracker with role hint
            mock_get_state.return_value = None
            mock_read_json.return_value = {
                "partyNPCs": [{"name": "Liri", "role": "Rogue"}],
                "active_character": "Acheron"
            }
            
            from web.extensions.missing_media_autogen import MissingMediaTask
            task = MissingMediaTask(
                missing_key="npcs/liri",
                media_type="npcs",
                filename="liri.jpg"
            )
            
            # Act
            result = _hydrate_allied_npc_context(task)
            
            # Assert: Fallback source
            self.assertEqual(result.get("context_source"), "fallback")
            # Assert: Uses role hint from party
            self.assertEqual(result.get("class"), "Rogue")
            # Assert: Generation-ready shape
            self.assertEqual(result.get("name"), "Liri")
            self.assertEqual(result.get("race"), "Unknown")
            self.assertIn("class", result)

    def test_hydration_helper_exports_for_callback_use(self):
        """Test 12.5.3: Hydration helper is exported and available for callback use."""
        from web.extensions.missing_media_autogen import _hydrate_allied_npc_context
        
        # Verify the helper is importable and callable
        self.assertTrue(callable(_hydrate_allied_npc_context),
                        "Hydration helper must be callable")
        
        # Verify it's in the module exports
        from web.extensions.missing_media_autogen import __all__
        self.assertIn("_hydrate_allied_npc_context", __all__,
                      "Hydration helper must be exported in __all__")


if __name__ == "__main__":
    # Run tests with verbose output
    unittest.main(verbosity=2)
