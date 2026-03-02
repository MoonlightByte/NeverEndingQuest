#!/usr/bin/env python3
"""
Unit tests for homebrew_preflight.py
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import TestCase

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from homebrew_preflight import assess_source_readiness


class TestTitleHygieneDetection(TestCase):
    """Test clone prefix detection and recommendations."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_detects_clone_adventure_prefix(self):
        """Should detect and recommend removing CLONE - ADVENTURE: prefix."""
        source = self.temp_dir / "test.md"
        source.write_text('```metadata\ntitle: CLONE - ADVENTURE: The Secret Keep\n```\n\n## Room 1: Start\nStart room.')
        
        result = assess_source_readiness(str(source))
        
        title_issues = [i for i in result["issues"] if i["type"] == "title_hygiene"]
        self.assertEqual(len(title_issues), 1)
        self.assertEqual(title_issues[0]["current"], "CLONE - ADVENTURE: The Secret Keep")
        self.assertEqual(title_issues[0]["recommended"], "The Secret Keep")

    def test_detects_clone_dash_prefix(self):
        """Should detect CLONE - prefix variant."""
        source = self.temp_dir / "test.md"
        source.write_text('```metadata\ntitle: CLONE - The Secret Keep\n```\n\n## Room 1: Start\nStart room.')
        
        result = assess_source_readiness(str(source))
        
        title_issues = [i for i in result["issues"] if i["type"] == "title_hygiene"]
        self.assertTrue(len(title_issues) > 0)
        self.assertIn("The Secret Keep", title_issues[0]["recommended"])

    def test_detects_clone_colon_prefix(self):
        """Should detect CLONE: prefix variant."""
        source = self.temp_dir / "test.md"
        source.write_text('```metadata\ntitle: CLONE: The Secret Keep\n```\n\n## Room 1: Start\nStart room.')
        
        result = assess_source_readiness(str(source))
        
        title_issues = [i for i in result["issues"] if i["type"] == "title_hygiene"]
        self.assertTrue(len(title_issues) > 0)

    def test_no_issue_for_clean_title(self):
        """Should not flag clean titles."""
        source = self.temp_dir / "test.md"
        source.write_text('```metadata\ntitle: The Secret Keep\n```\n\n## Room 1: Start\nStart room.')
        
        result = assess_source_readiness(str(source))
        
        title_issues = [i for i in result["issues"] if i["type"] == "title_hygiene"]
        self.assertEqual(len(title_issues), 0)


class TestMetadataDetection(TestCase):
    """Test metadata completeness checks."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_detects_missing_author(self):
        """Should flag missing author field."""
        source = self.temp_dir / "test.md"
        source.write_text('```metadata\ntitle: Test\ndescription: A test\n```\n\n## Room 1: Start\nStart.')
        
        result = assess_source_readiness(str(source))
        
        author_issues = [i for i in result["issues"] if i["type"] == "metadata_missing" and i.get("field") == "author"]
        self.assertEqual(len(author_issues), 1)
        self.assertEqual(author_issues[0]["severity"], "fixable")

    def test_detects_missing_description(self):
        """Should flag missing description field."""
        source = self.temp_dir / "test.md"
        source.write_text('```metadata\ntitle: Test\nauthor: Test Author\n```\n\n## Room 1: Start\nStart.')
        
        result = assess_source_readiness(str(source))
        
        desc_issues = [i for i in result["issues"] if i["type"] == "metadata_missing" and i.get("field") == "description"]
        self.assertEqual(len(desc_issues), 1)

    def test_complete_metadata_no_issues(self):
        """Should not flag issues when all required metadata present."""
        source = self.temp_dir / "test.md"
        source.write_text('```metadata\ntitle: Test\nauthor: Test Author\ndescription: A test module\n```\n\n## Room 1: Start\nStart.')
        
        result = assess_source_readiness(str(source))
        
        meta_issues = [i for i in result["issues"] if i["type"] == "metadata_missing"]
        self.assertEqual(len(meta_issues), 0)


class TestStructureClassification(TestCase):
    """Test structure type classification."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_classifies_room_based_structure(self):
        """Should classify ## Room N: format as room_based."""
        source = self.temp_dir / "test.md"
        source.write_text('```metadata\ntitle: Test\nauthor: A\ndescription: D\n```\n\n## Room 1: Entry\nEntry hall.\n\n## Room 2: Chamber\nMain chamber.')
        
        result = assess_source_readiness(str(source))
        
        self.assertEqual(result["structure_class"], "room_based")
        self.assertTrue(result["can_auto_transform"])

    def test_classifies_act_location_structure(self):
        """Should classify ACT/LOCATIONS format as act_location."""
        source = self.temp_dir / "test.md"
        source.write_text('```metadata\ntitle: Test\nauthor: A\ndescription: D\n```\n\n## ACT I\n\n### LOCATIONS\n- **Dock** - A wooden dock.\n- **Tavern** - A cozy tavern.')
        
        result = assess_source_readiness(str(source))
        
        self.assertEqual(result["structure_class"], "act_location")

    def test_auto_transform_true_for_parseable_act_location(self):
        """Should set can_auto_transform=true for parseable ACT/LOCATION."""
        source = self.temp_dir / "test.md"
        source.write_text('```metadata\ntitle: Test\nauthor: A\ndescription: D\n```\n\n## ACT I\n\n### LOCATIONS\n- **Dock** - A wooden dock north of town.\n- **Tavern** - A cozy tavern.')
        
        result = assess_source_readiness(str(source))
        
        self.assertEqual(result["structure_class"], "act_location")
        self.assertTrue(result["can_auto_transform"])

    def test_classifies_unknown_structure(self):
        """Should classify non-matching structures as unknown."""
        source = self.temp_dir / "test.md"
        source.write_text('```metadata\ntitle: Test\nauthor: A\ndescription: D\n```\n\n# Chapter 1\n\nSome narrative text without room headers.')
        
        result = assess_source_readiness(str(source))
        
        self.assertEqual(result["structure_class"], "unknown")
        self.assertFalse(result["can_auto_transform"])

    def test_unknown_structure_returns_manual_required(self):
        """Should signal manual_required for unknown structures."""
        source = self.temp_dir / "test.md"
        source.write_text('```metadata\ntitle: Test\nauthor: A\ndescription: D\n```\n\nJust some text.')
        
        result = assess_source_readiness(str(source))
        
        struct_issues = [i for i in result["issues"] if i["type"] == "structure_unknown"]
        self.assertEqual(len(struct_issues), 1)
        self.assertEqual(struct_issues[0]["severity"], "manual_required")


class TestEdgeCases(TestCase):
    """Test edge cases and error handling."""

    def test_missing_file_returns_blocked(self):
        """Should return blocked for missing source file."""
        result = assess_source_readiness("/nonexistent/path/file.md")
        
        self.assertFalse(result["ready"])
        self.assertEqual(result["structure_class"], "unknown")
        source_issues = [i for i in result["issues"] if i["type"] == "source_missing"]
        self.assertEqual(len(source_issues), 1)

    def test_extracts_title_from_metadata(self):
        """Should prefer metadata title over H1 or filename."""
        source = Path(tempfile.mkdtemp()) / "test.md"
        source.write_text('```metadata\ntitle: Metadata Title\nauthor: A\ndescription: D\n```\n\n# H1 Title\n\n## Room 1: Start\nStart.')
        
        result = assess_source_readiness(str(source))
        
        self.assertEqual(result["title"], "Metadata Title")
        import shutil
        shutil.rmtree(source.parent, ignore_errors=True)


class TestReadyCalculation(TestCase):
    """Test ready=true/false calculation logic."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_ready_true_for_complete_room_based(self):
        """Should be ready when room-based, clean title, complete metadata."""
        source = self.temp_dir / "test.md"
        source.write_text('```metadata\ntitle: The Keep\nauthor: Author Name\ndescription: A keep module\n```\n\n## Room 1: Entry\nEntry hall.\n\n## Room 2: Hall\nMain hall.')
        
        result = assess_source_readiness(str(source))
        
        self.assertTrue(result["ready"])
        self.assertTrue(result["can_auto_transform"])

    def test_ready_false_for_missing_metadata(self):
        """Should not be ready when metadata incomplete."""
        source = self.temp_dir / "test.md"
        source.write_text('```metadata\ntitle: The Keep\nauthor: Author Name\n```\n\n## Room 1: Entry\nEntry hall.')
        
        result = assess_source_readiness(str(source))
        
        self.assertFalse(result["ready"])

    def test_ready_false_for_unclean_title(self):
        """Should not be ready when title has hygiene issues."""
        source = self.temp_dir / "test.md"
        source.write_text('```metadata\ntitle: CLONE - The Keep\nauthor: Author Name\ndescription: A keep\n```\n\n## Room 1: Entry\nEntry hall.')
        
        result = assess_source_readiness(str(source))
        
        self.assertFalse(result["ready"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
