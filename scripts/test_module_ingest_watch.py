# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Tests - Module Ingest Watch Worker
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Tests for watch worker lifecycle: archive move, sidecar writing, collision-safe naming.

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import tempfile
import shutil
import time
from pathlib import Path

from web.extensions import module_ingest_watch as watch


class TestArchiveMoveBehavior(unittest.TestCase):
    """Test file archival with status-bearing filenames."""

    def setUp(self):
        """Create temp directories."""
        self.temp_dir = tempfile.mkdtemp()
        self.watch_dir = Path(self.temp_dir) / "watch"
        self.archive_dir = Path(self.temp_dir) / "archive"
        self.watch_dir.mkdir()
        self.archive_dir.mkdir()

    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.temp_dir)

    def test_archive_moves_file_with_status(self):
        """File moved to archive with status in filename."""
        source_file = self.watch_dir / "test_adventure.txt"
        source_file.write_text("Test content")

        # Manually trigger archive via internal function
        archived = watch._archive_processed_file(source_file, self.archive_dir, "success")

        # Verify source no longer exists
        self.assertFalse(source_file.exists())

        # Verify archived file exists with status prefix
        self.assertTrue(archived.exists())
        self.assertIn("_success_", archived.name)
        self.assertIn("test_adventure.txt", archived.name)

    def test_archive_quarantined_status(self):
        """Quarantined files get quarantine status in filename."""
        source_file = self.watch_dir / "bad_source.txt"
        source_file.write_text("Bad content")

        archived = watch._archive_processed_file(source_file, self.archive_dir, "quarantined")

        self.assertIn("_quarantined_", archived.name)

    def test_archive_error_status(self):
        """Error files get error status in filename."""
        source_file = self.watch_dir / "error_source.txt"
        source_file.write_text("Error content")

        archived = watch._archive_processed_file(source_file, self.archive_dir, "error")

        self.assertIn("_error_", archived.name)


class TestCollisionSafeNaming(unittest.TestCase):
    """Test collision-safe archive naming."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.archive_dir = Path(self.temp_dir) / "archive"
        self.archive_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_collision_handling(self):
        """Multiple files with same name get indexed suffixes."""
        # Create first file and archive it
        source1 = Path(self.temp_dir) / "test.txt"
        source1.write_text("content1")
        archived1 = watch._archive_processed_file(source1, self.archive_dir, "success")

        # Create second file with same name and archive it
        source2 = Path(self.temp_dir) / "test.txt"
        source2.write_text("content2")
        archived2 = watch._archive_processed_file(source2, self.archive_dir, "success")

        # Both should exist with different names
        self.assertTrue(archived1.exists())
        self.assertTrue(archived2.exists())
        self.assertNotEqual(archived1.name, archived2.name)

        # Second should have index suffix
        self.assertIn("_1_", archived2.name)


class TestSidecarResultWriting(unittest.TestCase):
    """Test sidecar JSON result file creation."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.archive_dir = Path(self.temp_dir) / "archive"
        self.archive_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_sidecar_created_with_result(self):
        """Sidecar JSON created with status and metadata."""
        source_file = Path(self.temp_dir) / "source.txt"
        source_file.write_text("content")

        # Archive first
        archived = watch._archive_processed_file(source_file, self.archive_dir, "success")

        # Write sidecar
        result = {
            "status": "success",
            "module_slug": "Test_Module",
            "artifacts": ["test.json"],
            "validation": {"passed": True},
        }
        watch._write_result_sidecar(archived, result)

        # Verify sidecar exists
        sidecar = archived.with_suffix(f"{archived.suffix}.result.json")
        self.assertTrue(sidecar.exists())

        # Verify content
        import json
        with open(sidecar) as f:
            data = json.load(f)
        self.assertEqual(data["result"]["status"], "success")
        self.assertEqual(data["result"]["module_slug"], "Test_Module")

    def test_quarantine_sidecar_contains_errors(self):
        """Quarantine sidecar includes error details."""
        source_file = Path(self.temp_dir) / "bad.txt"
        source_file.write_text("bad")

        archived = watch._archive_processed_file(source_file, self.archive_dir, "quarantined")

        result = {
            "status": "quarantined",
            "module_slug": "Bad_Module",
            "validation": {"passed": False, "errors": ["Schema error"]},
            "quarantine_reason": "validation_failed",
        }
        watch._write_result_sidecar(archived, result)

        sidecar = archived.with_suffix(f"{archived.suffix}.result.json")
        import json
        with open(sidecar) as f:
            data = json.load(f)
        self.assertEqual(data["result"]["quarantine_reason"], "validation_failed")
        self.assertIn("Schema error", data["result"]["validation"]["errors"])


class TestFileStabilityGuard(unittest.TestCase):
    """Test file stability detection."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.watch_dir = Path(self.temp_dir) / "watch"
        self.archive_dir = Path(self.temp_dir) / "archive"
        self.watch_dir.mkdir()
        self.archive_dir.mkdir()
        # Reset stability cache
        watch._file_stability_cache.clear()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)
        watch._file_stability_cache.clear()

    def test_unstable_file_not_processed(self):
        """New file is considered unstable on first check."""
        source_file = self.watch_dir / "new.txt"
        source_file.write_text("content")

        # First check - should be unstable
        is_stable = watch._is_file_stable(source_file)
        self.assertFalse(is_stable)

        # Wait a tiny bit and check again
        time.sleep(0.1)

        # Second check - now stable (signature unchanged)
        is_stable = watch._is_file_stable(source_file)
        self.assertTrue(is_stable)


class TestCandidateFileListing(unittest.TestCase):
    """Test watch folder candidate enumeration."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.watch_dir = Path(self.temp_dir) / "watch"
        self.archive_dir = Path(self.temp_dir) / "archive"
        self.watch_dir.mkdir()
        self.archive_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_supported_extensions_only(self):
        """Only supported extensions returned as candidates."""
        # Create various files
        (self.watch_dir / "good.md").write_text("markdown")
        (self.watch_dir / "good.txt").write_text("text")
        (self.watch_dir / "bad.pdf").write_text("pdf")
        (self.watch_dir / ".hidden").write_text("hidden")

        candidates = watch._list_candidate_files(
            self.watch_dir, self.archive_dir, [".md", ".txt"]
        )

        names = [c.name for c in candidates]
        self.assertIn("good.md", names)
        self.assertIn("good.txt", names)
        self.assertNotIn("bad.pdf", names)
        self.assertNotIn(".hidden", names)

    def test_archive_subdirectory_excluded(self):
        """Files in archive subdirectory excluded."""
        # Create file in watch root
        (self.watch_dir / "root.txt").write_text("root")

        # Create file in archive (simulating previous ingest)
        (self.archive_dir / "archived.txt").write_text("archived")

        candidates = watch._list_candidate_files(
            self.watch_dir, self.archive_dir, [".txt"]
        )

        names = [c.name for c in candidates]
        self.assertIn("root.txt", names)
        self.assertNotIn("archived.txt", names)


class TestWorkerStats(unittest.TestCase):
    """Test worker statistics tracking."""

    def setUp(self):
        # Reset stats before each test
        watch._worker_stats = {
            "start_time": None,
            "last_scan_time": None,
            "files_seen": 0,
            "files_ingested": 0,
            "files_quarantined": 0,
            "files_failed": 0,
            "last_file": None,
        }

    def test_stats_initial_state(self):
        """Stats start at zero/null."""
        stats = watch.get_module_ingest_watch_stats()
        self.assertEqual(stats["files_seen"], 0)
        self.assertEqual(stats["files_ingested"], 0)
        self.assertEqual(stats["files_quarantined"], 0)


class TestWatcherDeterministicDefault(unittest.TestCase):
    """Test that watcher always forces deterministic ingest for markdown/text files."""

    def setUp(self):
        """Create temp directories."""
        self.temp_dir = tempfile.mkdtemp()
        self.watch_dir = Path(self.temp_dir) / "watch"
        self.archive_dir = Path(self.temp_dir) / "archive"
        self.watch_dir.mkdir()
        self.archive_dir.mkdir()

    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.temp_dir)

    def test_watcher_calls_importer_with_use_deterministic_true(self):
        """Watcher must force deterministic ingest for watched markdown files."""
        # Create a markdown source file
        source_file = self.watch_dir / "test_adventure.md"
        source_file.write_text("""```metadata
title: Test Adventure
```

## Room 1: Start
Start description.

## Room 2: End
End description.
""")

        # Track importer call arguments via mock
        import core.importers.homebrewery_importer as importer
        orig_importer = importer.import_homebrewery_adventure_to_module
        
        call_args = {}
        def mock_importer(**kwargs):
            call_args.update(kwargs)
            return {
                "status": "dry_run",
                "module_slug": "Test_Adventure",
                "artifacts": [],
                "validation": {"passed": True, "errors": [], "failed_count": 0, "success_rate": "100%"},
                "quarantine_reason": None,
                "registration": {
                    "registration_attempted": False,
                    "registration_success": False,
                    "registry_module_present": False,
                    "registration_errors": ["Registration skipped in non-strict mode"],
                },
            }
        
        importer.import_homebrewery_adventure_to_module = mock_importer
        
        try:
            # Call the watcher function
            result = watch._process_source_file(source_file, strict_validation=False)
            
            # Verify deterministic flag was forced
            self.assertIn("use_deterministic", call_args)
            self.assertTrue(call_args["use_deterministic"])
            
            # Verify source_path and strict were passed correctly
            self.assertIn("source_path", call_args)
            self.assertEqual(call_args["source_path"], str(source_file))
            self.assertIn("strict", call_args)
            self.assertFalse(call_args["strict"])
        finally:
            importer.import_homebrewery_adventure_to_module = orig_importer

    def test_watcher_calls_importer_with_use_deterministic_true_txt_files(self):
        """Watcher must force deterministic ingest for watched text files."""
        # Create a text source file
        source_file = self.watch_dir / "test_adventure.txt"
        source_file.write_text("""```metadata
title: Text Adventure
```

## Room 1: Text Room
Text description.
""")

        import core.importers.homebrewery_importer as importer
        orig_importer = importer.import_homebrewery_adventure_to_module
        
        call_args = {}
        def mock_importer(**kwargs):
            call_args.update(kwargs)
            return {
                "status": "dry_run",
                "module_slug": "Text_Adventure",
                "artifacts": [],
                "validation": {"passed": True, "errors": [], "failed_count": 0, "success_rate": "100%"},
                "quarantine_reason": None,
                "registration": {
                    "registration_attempted": False,
                    "registration_success": False,
                    "registry_module_present": False,
                    "registration_errors": ["Registration skipped in non-strict mode"],
                },
            }
        
        importer.import_homebrewery_adventure_to_module = mock_importer
        
        try:
            result = watch._process_source_file(source_file, strict_validation=True)
            
            # Verify deterministic flag was forced even for .txt
            self.assertIn("use_deterministic", call_args)
            self.assertTrue(call_args["use_deterministic"])
            
            # Verify strict mode was passed correctly
            self.assertTrue(call_args["strict"])
        finally:
            importer.import_homebrewery_adventure_to_module = orig_importer


if __name__ == "__main__":
    unittest.main(verbosity=2)
