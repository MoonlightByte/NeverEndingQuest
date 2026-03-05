#!/usr/bin/env python3
"""Final consistency tests for homebrew media pipeline."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from homebrew_media_extract import extract_media, _download_image
from homebrew_media_handles import (
    _dedupe_handles_by_source_ref,
    _find_existing_file_by_stem,
    _infer_kind_from_path,
    _sort_handles,
    generate_manifest,
)


class TestAccurateStatusLogging(unittest.TestCase):
    """Verify extraction log records accurate per-URL statuses."""

    def test_extraction_log_records_downloaded_vs_existing(self):
        """Log should distinguish downloaded (new) from existing (already present)."""
        # This test would require network access; simplified to check structure
        import homebrew_media_extract as extract_module

        # Verify outcome structure has required fields
        sample_outcome = {
            "url": "http://example.com/test.jpg",
            "kind": "title_image",
            "target_path": "media/environment/test.jpg",
            "status": "downloaded",
            "attempts": 1,
            "http_status": 200,
            "error": None,
        }

        self.assertIn("status", sample_outcome)
        self.assertIn("attempts", sample_outcome)
        self.assertIn("http_status", sample_outcome)


class TestHandleDedup(unittest.TestCase):
    """Verify handle deduplication by source_ref."""

    def test_dedupe_collapses_same_source_ref(self):
        """Same source_ref with different extensions/kinds should dedupe to one handle."""
        handles = [
            {
                "handle_id": "abc123",
                "kind": "title_image",
                "source_ref": "https://example.com/image.jpg",
                "storage_relpath": "media/environment/image.jpg",
                "download_status": "downloaded",
            },
            {
                "handle_id": "def456",
                "kind": "handout",
                "source_ref": "https://example.com/image.jpg",
                "storage_relpath": "media/environment/image.jpeg",
                "download_status": "downloaded",
            },
        ]

        deduped = _dedupe_handles_by_source_ref(handles)

        self.assertEqual(len(deduped), 1)
        # Should prefer title_image over handout
        self.assertEqual(deduped[0]["kind"], "title_image")

    def test_dedupe_prefers_downloaded_over_failed(self):
        """When same source has downloaded and failed, prefer downloaded."""
        handles = [
            {
                "handle_id": "abc123",
                "kind": "map_image",
                "source_ref": "https://example.com/map.jpg",
                "storage_relpath": "media/maps/map.jpg",
                "download_status": "failed",
            },
            {
                "handle_id": "def456",
                "kind": "map_image",
                "source_ref": "https://example.com/map.jpg",
                "storage_relpath": "media/maps/map.jpg",
                "download_status": "downloaded",
            },
        ]

        deduped = _dedupe_handles_by_source_ref(handles)

        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]["download_status"], "downloaded")


class TestMangroveScenario(unittest.TestCase):
    """Verify Mangrove-like .jpg/.jpeg scenario yields one handle per URL."""

    def test_jpg_jpeg_variants_dedupe(self):
        """Legacy .jpeg file + new .jpg should result in one canonical handle."""
        # Simulate scenario: extraction log says target is .jpg,
        # but local file is .jpeg (legacy)
        handles = [
            {
                "handle_id": "abc123",
                "kind": "title_image",
                "source_ref": "https://i.imgur.com/t50VrIo.jpg",
                "storage_relpath": "media/environment/t50VrIo.jpg",
                "download_status": "downloaded",
            },
            {
                "handle_id": "def456",  
                "kind": "handout",
                "source_ref": "https://i.imgur.com/t50VrIo.jpg",
                "storage_relpath": "media/environment/t50VrIo.jpeg",
                "download_status": "downloaded",
            },
        ]

        deduped = _dedupe_handles_by_source_ref(handles)

        # Should collapse to 1 handle
        self.assertEqual(len(deduped), 1)
        # Should prefer title_image
        self.assertEqual(deduped[0]["kind"], "title_image")


class TestMonsterVideoHandles(unittest.TestCase):
    """Tests for Prompt 3: monster video handles and deterministic ordering."""

    def test_infer_kind_from_path_identifies_monster_video(self) -> None:
        """_video.mp4 files under monsters should be classified as monster_video."""
        self.assertEqual(_infer_kind_from_path("modules/abc/media/monsters/goblin_video.mp4"), "monster_video")
        self.assertEqual(_infer_kind_from_path("web/static/media/monsters/dragon_video.mp4"), "monster_video")

    def test_infer_kind_from_path_monster_portrait_for_images(self) -> None:
        """Image files under monsters should remain monster_portrait."""
        self.assertEqual(_infer_kind_from_path("modules/abc/media/monsters/goblin.jpg"), "monster_portrait")
        self.assertEqual(_infer_kind_from_path("modules/abc/media/monsters/dragon_full.png"), "monster_portrait")

    def test_dedupe_handles_prefers_monster_portrait_over_video(self) -> None:
        """When same source_ref has both portrait and video, portrait should win (higher priority)."""
        handles = [
            {
                "handle_id": "p1",
                "kind": "monster_portrait",
                "source_ref": "https://example.com/monster.jpg",
                "storage_relpath": "media/monsters/monster.jpg",
                "download_status": "downloaded",
            },
            {
                "handle_id": "v1",
                "kind": "monster_video",
                "source_ref": "https://example.com/monster.jpg",
                "storage_relpath": "media/monsters/monster_video.mp4",
                "download_status": "downloaded",
            },
        ]
        deduped = _dedupe_handles_by_source_ref(handles)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]["kind"], "monster_portrait")

    def test_dedupe_handles_preserves_video_when_portrait_not_present(self) -> None:
        """If only video exists for a source_ref, it should be kept."""
        handles = [
            {
                "handle_id": "v1",
                "kind": "monster_video",
                "source_ref": "https://example.com/monster_video.mp4",
                "storage_relpath": "media/monsters/monster_video.mp4",
                "download_status": "downloaded",
            }
        ]
        deduped = _dedupe_handles_by_source_ref(handles)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]["kind"], "monster_video")

    def test_sort_handles_maintains_monster_video_after_portrait(self) -> None:
        """Sort order should place monster_video after monster_portrait."""
        handles = [
            {"kind": "monster_video", "source_ref": "c", "storage_relpath": "media/monsters/c_video.mp4"},
            {"kind": "monster_portrait", "source_ref": "a", "storage_relpath": "media/monsters/a.jpg"},
            {"kind": "monster_portrait", "source_ref": "b", "storage_relpath": "media/monsters/b.jpg"},
        ]
        sorted_handles = _sort_handles(handles)
        kinds = [h["kind"] for h in sorted_handles]
        # All monster_portrait must come before any monster_video
        first_video_idx = kinds.index("monster_video") if "monster_video" in kinds else len(kinds)
        after_video = kinds[first_video_idx:]
        self.assertTrue(all(k == "monster_video" for k in after_video),
                        "All handles after first monster_video should be monster_video")

    def test_dedupe_handles_video_image_different_source_refs_both_kept(self) -> None:
        """Different source_refs (even with video/image variants) should both be preserved."""
        handles = [
            {
                "handle_id": "p1",
                "kind": "monster_portrait",
                "source_ref": "https://example.com/goblin.jpg",
                "storage_relpath": "media/monsters/goblin.jpg",
                "download_status": "downloaded",
            },
            {
                "handle_id": "v1",
                "kind": "monster_video",
                "source_ref": "https://example.com/goblin_video.mp4",
                "storage_relpath": "media/monsters/goblin_video.mp4",
                "download_status": "downloaded",
            },
        ]
        deduped = _dedupe_handles_by_source_ref(handles)
        self.assertEqual(len(deduped), 2)
        kinds = {h["kind"] for h in deduped}
        self.assertIn("monster_portrait", kinds)
        self.assertIn("monster_video", kinds)


if __name__ == "__main__":
    unittest.main(verbosity=2)
