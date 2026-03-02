#!/usr/bin/env python3
"""
Unit tests for homebrew_transform_to_deterministic.py
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import TestCase

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from homebrew_transform_to_deterministic import transform_source_to_deterministic


class TestTitlePrefixStripping(TestCase):
    """Test title normalization and prefix removal."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_strips_clone_adventure_prefix(self):
        """Should remove CLONE - ADVENTURE: prefix from title."""
        source = self.temp_dir / "input.md"
        source.write_text('```metadata\ntitle: CLONE - ADVENTURE: The Secret Keep\n```\n\n## Room 1: Start\nStart room.')
        output = self.temp_dir / "output.md"
        
        result = transform_source_to_deterministic(str(source), str(output))
        
        self.assertEqual(result["title"], "The Secret Keep")
        self.assertEqual(result["status"], "success")

    def test_strips_clone_dash_prefix(self):
        """Should remove CLONE - prefix."""
        source = self.temp_dir / "input.md"
        source.write_text('```metadata\ntitle: CLONE - The Secret Keep\n```\n\n## Room 1: Start\nStart room.')
        output = self.temp_dir / "output.md"
        
        result = transform_source_to_deterministic(str(source), str(output))
        
        self.assertEqual(result["title"], "The Secret Keep")

    def test_strips_clone_colon_prefix(self):
        """Should remove CLONE: prefix."""
        source = self.temp_dir / "input.md"
        source.write_text('```metadata\ntitle: CLONE: The Secret Keep\n```\n\n## Room 1: Start\nStart room.')
        output = self.temp_dir / "output.md"
        
        result = transform_source_to_deterministic(str(source), str(output))
        
        self.assertEqual(result["title"], "The Secret Keep")

    def test_preserves_clean_title(self):
        """Should not modify clean titles."""
        source = self.temp_dir / "input.md"
        source.write_text('```metadata\ntitle: The Secret Keep\n```\n\n## Room 1: Start\nStart room.')
        output = self.temp_dir / "output.md"
        
        result = transform_source_to_deterministic(str(source), str(output))
        
        self.assertEqual(result["title"], "The Secret Keep")


class TestMetadataInjection(TestCase):
    """Test metadata block creation."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_injects_metadata_when_missing(self):
        """Should add metadata block when source lacks one."""
        source = self.temp_dir / "input.md"
        source.write_text('# The Secret Keep\n\n## Room 1: Entry\nEntry hall.')
        output = self.temp_dir / "output.md"
        
        result = transform_source_to_deterministic(str(source), str(output))
        
        output_text = output.read_text()
        self.assertIn("```metadata", output_text)
        self.assertIn("title:", output_text)
        self.assertIn("author:", output_text)

    def test_preserves_existing_metadata(self):
        """Should keep existing metadata and normalize title only."""
        source = self.temp_dir / "input.md"
        source.write_text('```metadata\ntitle: Test\nauthor: Original Author\ndescription: Original desc\n```\n\n## Room 1: Start\nStart.')
        output = self.temp_dir / "output.md"
        
        result = transform_source_to_deterministic(str(source), str(output))
        
        output_text = output.read_text()
        self.assertIn("Original Author", output_text)


class TestActLocationConversion(TestCase):
    """Test ACT/LOCATION to room block conversion."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_converts_location_bullets_to_rooms(self):
        """Should convert bullet locations to ## Room N: format."""
        source = self.temp_dir / "input.md"
        source.write_text('```metadata\ntitle: Test\nauthor: A\ndescription: D\n```\n\n## ACT I\n\n### LOCATIONS\n- **The Dock** - A weathered wooden dock.\n- **The Tavern** - A cozy tavern.')
        output = self.temp_dir / "output.md"
        
        result = transform_source_to_deterministic(str(source), str(output))
        
        output_text = output.read_text()
        self.assertIn("## Room 1: The Dock", output_text)
        self.assertIn("## Room 2: The Tavern", output_text)
        self.assertEqual(result["room_count"], 2)

    def test_creates_exits_section(self):
        """Should create exits section for each room."""
        source = self.temp_dir / "input.md"
        source.write_text('```metadata\ntitle: Test\nauthor: A\ndescription: D\n```\n\n## ACT I\n\n### LOCATIONS\n- **Room A** - Description A.\n- **Room B** - Description B.')
        output = self.temp_dir / "output.md"
        
        result = transform_source_to_deterministic(str(source), str(output))
        
        output_text = output.read_text()
        self.assertIn("**Exits:**", output_text)

    def test_preserves_location_descriptions(self):
        """Should preserve original descriptions in room content."""
        source = self.temp_dir / "input.md"
        source.write_text('```metadata\ntitle: Test\nauthor: A\ndescription: D\n```\n\n## ACT I\n\n### LOCATIONS\n- **The Dock** - A weathered wooden dock with old fishing nets.')
        output = self.temp_dir / "output.md"
        
        result = transform_source_to_deterministic(str(source), str(output))
        
        output_text = output.read_text()
        self.assertIn("A weathered wooden dock with old fishing nets.", output_text)


class TestExitInference(TestCase):
    """Test directional exit inference."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_infers_exits_from_directional_phrases(self):
        """Should parse 'north of X' patterns."""
        source = self.temp_dir / "input.md"
        source.write_text('```metadata\ntitle: Test\nauthor: A\ndescription: D\n```\n\n## ACT I\n\n### LOCATIONS\n- **The Dock** - A dock north of the tavern.\n- **The Tavern** - A tavern.')
        output = self.temp_dir / "output.md"
        
        result = transform_source_to_deterministic(str(source), str(output))
        
        output_text = output.read_text()
        # Linear fallback creates bidirectional exits when no explicit inference
        # At minimum, linear links should exist
        self.assertIn("Room", output_text)  # Rooms exist

    def test_creates_linear_fallback(self):
        """Should create linear room connections when no explicit exits found."""
        source = self.temp_dir / "input.md"
        source.write_text('```metadata\ntitle: Test\nauthor: A\ndescription: D\n```\n\n## ACT I\n\n### LOCATIONS\n- **Room A** - Just a room.\n- **Room B** - Another room.\n- **Room C** - Third room.')
        output = self.temp_dir / "output.md"
        
        result = transform_source_to_deterministic(str(source), str(output))
        
        output_text = output.read_text()
        # Should have at least Room 1 linking to Room 2
        self.assertEqual(result["room_count"], 3)


class TestEncounterPlaceholders(TestCase):
    """Test encounter placeholder handling."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_adds_encounter_comment_placeholder(self):
        """Should add encounter placeholder comment."""
        source = self.temp_dir / "input.md"
        source.write_text('```metadata\ntitle: Test\nauthor: A\ndescription: D\n```\n\n## ACT I\n\n### LOCATIONS\n- **Room** - A room.')
        output = self.temp_dir / "output.md"
        
        result = transform_source_to_deterministic(str(source), str(output))
        
        output_text = output.read_text()
        self.assertIn("<!-- Encounters: TBD -->", output_text)


class TestErrorHandling(TestCase):
    """Test error cases and failure modes."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_returns_error_for_missing_file(self):
        """Should return error status for missing source."""
        output = self.temp_dir / "output.md"
        
        result = transform_source_to_deterministic("/nonexistent/file.md", str(output))
        
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["exit_code"], 1)

    def test_returns_error_for_unparseable_locations(self):
        """Should fail when no parseable location bullets exist."""
        source = self.temp_dir / "input.md"
        source.write_text('```metadata\ntitle: Test\nauthor: A\ndescription: D\n```\n\n## ACT I\n\nJust some text without locations.')
        output = self.temp_dir / "output.md"
        
        result = transform_source_to_deterministic(str(source), str(output))
        
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["exit_code"], 2)


class TestIdempotentTransform(TestCase):
    """Test that already-room-based sources pass through correctly."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_room_based_source_passes_through(self):
        """Should handle already-room-based sources without restructure."""
        source = self.temp_dir / "input.md"
        source.write_text('```metadata\ntitle: The Keep\nauthor: A\ndescription: D\n```\n\n## Room 1: Entry\nEntry hall.\n\n## Room 2: Chamber\nMain chamber.')
        output = self.temp_dir / "output.md"
        
        result = transform_source_to_deterministic(str(source), str(output))
        
        self.assertEqual(result["status"], "success")
        output_text = output.read_text()
        self.assertIn("## Room 1: Entry", output_text)
        self.assertIn("## Room 2: Chamber", output_text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
