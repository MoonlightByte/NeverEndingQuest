#!/usr/bin/env python3
"""Regression tests for static-media strict-cache rebuild behavior."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.toolkit.pack_manager import PackManager


class TestStaticMediaStrictCache(unittest.TestCase):
    def setUp(self):
        self.temp_root = Path(tempfile.mkdtemp(prefix="neq_strict_cache_"))
        self._orig_packs_dir = PackManager.PACKS_DIRECTORY
        self._orig_active_file = PackManager.ACTIVE_PACK_FILE
        self._orig_static_root = PackManager.STATIC_MEDIA_ROOT

        PackManager.PACKS_DIRECTORY = str(self.temp_root / "graphic_packs")
        PackManager.ACTIVE_PACK_FILE = str(self.temp_root / "data" / "active_pack.json")
        PackManager.STATIC_MEDIA_ROOT = self.temp_root / "web" / "static" / "media"

        (self.temp_root / "data").mkdir(parents=True, exist_ok=True)
        PackManager.STATIC_MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
        (PackManager.STATIC_MEDIA_ROOT / "npcs").mkdir(parents=True, exist_ok=True)
        (PackManager.STATIC_MEDIA_ROOT / "monsters").mkdir(parents=True, exist_ok=True)
        (PackManager.STATIC_MEDIA_ROOT / "videos").mkdir(parents=True, exist_ok=True)
        (PackManager.STATIC_MEDIA_ROOT / "videos" / "keep.txt").write_text("keep", encoding="utf-8")

        self._create_pack("pack_a", npc_files=["guard.jpg", "guard_thumb.jpg"], monster_files=["ogre.jpg"])
        self._create_pack("pack_b", npc_files=["guard.jpg", "mage.jpg"], monster_files=["ogre.jpg", "troll.jpg"])

        active_payload = {
            "active_pack": "pack_b",
            "active_packs": ["pack_a", "pack_b"],
        }
        with open(PackManager.ACTIVE_PACK_FILE, "w", encoding="utf-8") as handle:
            json.dump(active_payload, handle, indent=2)

    def tearDown(self):
        PackManager.PACKS_DIRECTORY = self._orig_packs_dir
        PackManager.ACTIVE_PACK_FILE = self._orig_active_file
        PackManager.STATIC_MEDIA_ROOT = self._orig_static_root
        shutil.rmtree(self.temp_root, ignore_errors=True)

    def _create_pack(self, name: str, npc_files, monster_files):
        base = Path(PackManager.PACKS_DIRECTORY) / name
        (base / "npcs").mkdir(parents=True, exist_ok=True)
        (base / "monsters").mkdir(parents=True, exist_ok=True)
        manifest = {"name": name, "safe_name": name}
        with open(base / "manifest.json", "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2)

        for filename in npc_files:
            (base / "npcs" / filename).write_text(name, encoding="utf-8")
        for filename in monster_files:
            (base / "monsters" / filename).write_text(name, encoding="utf-8")

    def _write_live_file(self, media_type: str, filename: str):
        target = PackManager.STATIC_MEDIA_ROOT / media_type / filename
        target.write_text("live", encoding="utf-8")

    def test_audit_reports_orphans_and_collisions(self):
        self._write_live_file("npcs", "guard.jpg")
        self._write_live_file("npcs", "orphan.jpg")
        self._write_live_file("monsters", "ogre.jpg")

        manager = PackManager()
        report = manager.audit_static_runtime_cache()

        self.assertTrue(report["success"])
        self.assertEqual(report["active_packs"], ["pack_a", "pack_b"])

        npc_target = report["targets"]["npcs"]
        self.assertIn("orphan.jpg", npc_target["orphaned_files"])
        self.assertIn("guard.jpg", npc_target["collisions"])

        monster_target = report["targets"]["monsters"]
        self.assertIn("ogre.jpg", monster_target["collisions"])

    def test_rebuild_dry_run_does_not_modify_live_files(self):
        self._write_live_file("npcs", "legacy.jpg")
        manager = PackManager()

        result = manager.rebuild_static_runtime_cache(dry_run=True, create_backup=False)
        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "dry_run")
        self.assertTrue((PackManager.STATIC_MEDIA_ROOT / "npcs" / "legacy.jpg").exists())

    def test_rebuild_clears_targets_and_preserves_sibling_dirs(self):
        self._write_live_file("npcs", "legacy.jpg")
        self._write_live_file("monsters", "legacy.jpg")

        manager = PackManager()
        result = manager.rebuild_static_runtime_cache(
            active_packs=["pack_a"],
            create_backup=True,
            dry_run=False,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "rebuild")
        self.assertTrue(result.get("backup", {}).get("success"))

        npcs_live = sorted([f.name for f in (PackManager.STATIC_MEDIA_ROOT / "npcs").iterdir() if f.is_file()])
        monsters_live = sorted([f.name for f in (PackManager.STATIC_MEDIA_ROOT / "monsters").iterdir() if f.is_file()])

        self.assertEqual(npcs_live, ["guard.jpg", "guard_thumb.jpg"])
        self.assertEqual(monsters_live, ["ogre.jpg"])
        self.assertFalse((PackManager.STATIC_MEDIA_ROOT / "npcs" / "legacy.jpg").exists())
        self.assertFalse((PackManager.STATIC_MEDIA_ROOT / "monsters" / "legacy.jpg").exists())
        self.assertTrue((PackManager.STATIC_MEDIA_ROOT / "videos" / "keep.txt").exists())


if __name__ == "__main__":
    unittest.main()
