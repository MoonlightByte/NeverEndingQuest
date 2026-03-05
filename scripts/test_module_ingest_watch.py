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
import types
from pathlib import Path
from unittest.mock import patch

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

    def test_sidecar_preserves_canonical_media_stage_keys(self):
        """Sidecar stores canonical media stage blocks under result."""
        source_file = Path(self.temp_dir) / "media_ready.txt"
        source_file.write_text("content")

        archived = watch._archive_processed_file(source_file, self.archive_dir, "success")

        result = {
            "status": "success",
            "module_slug": "Media_Module",
            "media_extraction": {"status": "success", "duration_ms": 12},
            "media_handles": {"status": "success", "duration_ms": 8},
            "portrait_prewarm": {"status": "skipped", "duration_ms": 0},
        }
        watch._write_result_sidecar(archived, result)

        sidecar = archived.with_suffix(f"{archived.suffix}.result.json")
        import json
        with open(sidecar) as f:
            data = json.load(f)

        self.assertIn("media_extraction", data["result"])
        self.assertIn("media_handles", data["result"])
        self.assertIn("portrait_prewarm", data["result"])
        self.assertEqual(data["result"]["media_extraction"]["status"], "success")


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


class TestStrictGateAndPipelineParity(unittest.TestCase):
    """Test strict gate rejection and shared pipeline routing."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.watch_dir = Path(self.temp_dir) / "watch"
        self.archive_dir = Path(self.temp_dir) / "archive"
        self.watch_dir.mkdir()
        self.archive_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_non_ready_source_returns_quarantined_with_preflight(self):
        """Strict gate must quarantine non-ready source with explicit reason."""
        source_file = self.watch_dir / "invalid.md"
        source_file.write_text("bad source")

        fake_preflight = {
            "ready": False,
            "can_auto_transform": False,
            "issues": [
                {
                    "type": "structure_unknown",
                    "severity": "manual_required",
                    "recommended": "Convert source to deterministic format",
                }
            ],
        }

        with patch.object(watch, "assess_source_readiness", return_value=fake_preflight):
            result = watch._process_source_file(source_file, strict_validation=True)

        self.assertEqual(result.get("status"), "quarantined")
        self.assertEqual(result.get("quarantine_reason"), "preflight_not_ready")
        self.assertIn("preflight", result)
        self.assertFalse(result["validation"].get("passed", True))
        self.assertIsNone(result.get("module_slug"))

    def test_non_ready_source_does_not_attempt_pipeline_import(self):
        """Gate failures must not attempt run_ingest_pipeline import/call."""
        source_file = self.watch_dir / "invalid.txt"
        source_file.write_text("bad source")

        fake_preflight = {
            "ready": False,
            "can_auto_transform": False,
            "issues": [{"type": "metadata_missing", "severity": "fixable"}],
        }
        import_attempts = {"count": 0}
        original_import = __import__

        def tracked_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "scripts.homebrew_ingest_dev":
                import_attempts["count"] += 1
            return original_import(name, globals, locals, fromlist, level)

        with patch.object(watch, "assess_source_readiness", return_value=fake_preflight):
            with patch("builtins.__import__", side_effect=tracked_import):
                result = watch._process_source_file(source_file, strict_validation=True)

        self.assertEqual(result.get("status"), "quarantined")
        self.assertEqual(import_attempts["count"], 0)

    def test_ready_source_import_failure_returns_error(self):
        """If shared pipeline import fails, watcher returns error result."""
        source_file = self.watch_dir / "ready.md"
        source_file.write_text("ready source")

        fake_preflight = {"ready": True, "can_auto_transform": False, "issues": []}
        original_import = __import__
        saved_module = sys.modules.pop("scripts.homebrew_ingest_dev", None)

        def fail_pipeline_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "scripts.homebrew_ingest_dev":
                raise ImportError("forced import failure for test")
            return original_import(name, globals, locals, fromlist, level)

        try:
            with patch.object(watch, "assess_source_readiness", return_value=fake_preflight):
                with patch("builtins.__import__", side_effect=fail_pipeline_import):
                    result = watch._process_source_file(source_file, strict_validation=True)
        finally:
            if saved_module is not None:
                sys.modules["scripts.homebrew_ingest_dev"] = saved_module

        self.assertEqual(result.get("status"), "error")
        self.assertIn("Pipeline import failed", result.get("error", ""))
        self.assertFalse(result["validation"].get("passed", True))

    def test_ready_source_returns_pipeline_result_with_canonical_media_keys(self):
        """Gate-pass path returns shared pipeline payload including media keys."""
        source_file = self.watch_dir / "ready.md"
        source_file.write_text("ready source")

        fake_preflight = {"ready": True, "can_auto_transform": False, "issues": []}
        fake_pipeline_result = {
            "status": "success",
            "stage": "verify",
            "module_slug": "test_module",
            "media_extraction": {"status": "success", "duration_ms": 10},
            "media_handles": {"status": "success", "duration_ms": 12},
            "portrait_prewarm": {"status": "skipped", "duration_ms": 0},
            "provider_generation_allowed": False,
        }
        fake_pipeline_module = types.ModuleType("scripts.homebrew_ingest_dev")
        pipeline_calls = {"count": 0, "kwargs": None}

        def fake_run_ingest_pipeline(**kwargs):
            pipeline_calls["count"] += 1
            pipeline_calls["kwargs"] = kwargs
            return dict(fake_pipeline_result)

        setattr(fake_pipeline_module, "run_ingest_pipeline", fake_run_ingest_pipeline)

        with patch.object(watch, "assess_source_readiness", return_value=fake_preflight):
            with patch.dict(sys.modules, {"scripts.homebrew_ingest_dev": fake_pipeline_module}):
                result = watch._process_source_file(source_file, strict_validation=True)

        self.assertEqual(pipeline_calls["count"], 1)
        self.assertEqual(result.get("status"), "success")
        self.assertIn("media_extraction", result)
        self.assertIn("media_handles", result)
        self.assertIn("portrait_prewarm", result)
        self.assertIsNotNone(pipeline_calls["kwargs"])
        self.assertEqual(pipeline_calls["kwargs"].get("strict"), True)
        self.assertEqual(pipeline_calls["kwargs"].get("dry_run_only"), False)
        self.assertEqual(pipeline_calls["kwargs"].get("allow_provider"), False)

    def test_ready_source_parity_matches_shared_pipeline_result(self):
        """Watcher gate-pass result should match shared pipeline output for same fixture."""
        source_file = self.watch_dir / "parity_ready.md"
        source_file.write_text("ready source")

        fake_preflight = {"ready": True, "can_auto_transform": False, "issues": []}
        shared_result = {
            "status": "success",
            "stage": "verify",
            "module_slug": "parity_module",
            "dry_run": {"status": "dry_run", "validation": {"passed": True}},
            "guard": {"safe_to_proceed": True, "conflicts": []},
            "ingest": {"status": "success"},
            "verify": {"present": True},
            "media_extraction": {"status": "success", "duration_ms": 14},
            "media_handles": {"status": "success", "duration_ms": 9},
            "portrait_prewarm": {"status": "skipped", "duration_ms": 0},
        }
        fake_pipeline_module = types.ModuleType("scripts.homebrew_ingest_dev")

        def fake_run_ingest_pipeline(**kwargs):
            return dict(shared_result)

        setattr(fake_pipeline_module, "run_ingest_pipeline", fake_run_ingest_pipeline)

        with patch.object(watch, "assess_source_readiness", return_value=fake_preflight):
            with patch.dict(sys.modules, {"scripts.homebrew_ingest_dev": fake_pipeline_module}):
                watcher_result = watch._process_source_file(source_file, strict_validation=True)

        cli_result = fake_run_ingest_pipeline(
            source_path=str(source_file),
            strict=True,
            dry_run_only=False,
            cleanup_failed=True,
            no_media_extract=False,
            no_prewarm=False,
            media_timeout=30,
            allow_provider=False,
        )

        self.assertEqual(watcher_result, cli_result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
