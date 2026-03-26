#!/usr/bin/env python3
"""Regression tests for startup area hydration contracts (Step 3.1)."""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from utils.runtime_hydration import (
    hydrate_missing_live_area_files_from_bu,
    hydrate_missing_module_plot_files_from_bu,
)


class TestRuntimeAreaHydration(unittest.TestCase):
    """Behavioral tests for deterministic missing-area hydration."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="area_hydration_")
        self.modules_root = Path(self.temp_dir) / "modules"
        self.modules_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_json(self, path: Path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)

    def test_missing_live_area_is_restored_from_bu(self):
        """Missing live area file should be recreated from matching BU file."""
        bu_file = self.modules_root / "ModuleOne" / "areas" / "A001_BU.json"
        self._write_json(bu_file, {"locationId": "A001", "name": "Area One"})

        live_file = self.modules_root / "ModuleOne" / "areas" / "A001.json"
        self.assertFalse(live_file.exists())

        result = hydrate_missing_live_area_files_from_bu(str(self.modules_root))

        self.assertEqual(result["restored"], 1)
        self.assertEqual(result["failed"], 0)
        self.assertTrue(live_file.exists())
        self.assertEqual(live_file.read_text(encoding="utf-8"), bu_file.read_text(encoding="utf-8"))

    def test_existing_live_area_is_not_overwritten(self):
        """Hydration must not overwrite an existing live area file."""
        bu_file = self.modules_root / "ModuleOne" / "areas" / "A001_BU.json"
        live_file = self.modules_root / "ModuleOne" / "areas" / "A001.json"

        self._write_json(bu_file, {"locationId": "A001", "name": "BU Version"})
        self._write_json(live_file, {"locationId": "A001", "name": "Live Version"})

        before_text = live_file.read_text(encoding="utf-8")
        result = hydrate_missing_live_area_files_from_bu(str(self.modules_root))
        after_text = live_file.read_text(encoding="utf-8")

        self.assertEqual(result["restored"], 0)
        self.assertEqual(result["skipped_existing"], 1)
        self.assertEqual(before_text, after_text)
        self.assertNotEqual(after_text, bu_file.read_text(encoding="utf-8"))

    def test_stale_live_area_with_missing_location_ids_is_repaired(self):
        """Existing live area should be repaired when canonical location IDs diverge."""
        bu_file = self.modules_root / "ModuleOne" / "areas" / "A001_BU.json"
        live_file = self.modules_root / "ModuleOne" / "areas" / "A001.json"

        self._write_json(
            bu_file,
            {
                "areaId": "A001",
                "locations": [
                    {"locationId": "L1", "name": "Old Hall", "npcs": []},
                    {"locationId": "L2", "name": "New Refuge", "npcs": [{"name": "Keeper"}]},
                ],
            },
        )
        self._write_json(
            live_file,
            {
                "areaId": "A001",
                "locations": [
                    {"locationId": "L1", "name": "Old Hall", "encounters": [{"id": "E1"}]},
                ],
            },
        )

        result = hydrate_missing_live_area_files_from_bu(str(self.modules_root))
        repaired_payload = json.loads(live_file.read_text(encoding="utf-8"))

        self.assertEqual(result["repaired_existing"], 1)
        self.assertEqual(len(repaired_payload["locations"]), 2)
        first_location = repaired_payload["locations"][0]
        self.assertEqual(first_location["locationId"], "L1")
        self.assertEqual(first_location["encounters"], [{"id": "E1"}])

    def test_restored_files_are_reported_in_deterministic_order(self):
        """Restored file list should be deterministic regardless of filesystem order."""
        self._write_json(
            self.modules_root / "Zeta" / "areas" / "Z001_BU.json",
            {"locationId": "Z001"},
        )
        self._write_json(
            self.modules_root / "Alpha" / "areas" / "A001_BU.json",
            {"locationId": "A001"},
        )

        result = hydrate_missing_live_area_files_from_bu(str(self.modules_root))
        restored = result["restored_files"]

        expected = [
            str(self.modules_root / "Alpha" / "areas" / "A001.json"),
            str(self.modules_root / "Zeta" / "areas" / "Z001.json"),
        ]
        self.assertEqual(restored, expected)


class TestRuntimePlotHydration(unittest.TestCase):
    """Behavioral tests for deterministic missing module_plot hydration."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="plot_hydration_")
        self.modules_root = Path(self.temp_dir) / "modules"
        self.modules_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_json(self, path: Path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)

    def test_missing_module_plot_is_restored_from_bu(self):
        """Missing live module_plot should be recreated from module_plot_BU."""
        bu_file = self.modules_root / "ModuleOne" / "module_plot_BU.json"
        self._write_json(bu_file, {"plotTitle": "Module One"})

        live_file = self.modules_root / "ModuleOne" / "module_plot.json"
        self.assertFalse(live_file.exists())

        result = hydrate_missing_module_plot_files_from_bu(str(self.modules_root))

        self.assertEqual(result["restored"], 1)
        self.assertEqual(result["failed"], 0)
        self.assertTrue(live_file.exists())
        self.assertEqual(live_file.read_text(encoding="utf-8"), bu_file.read_text(encoding="utf-8"))

    def test_existing_module_plot_is_not_overwritten(self):
        """Hydration must not overwrite existing live module_plot content."""
        bu_file = self.modules_root / "ModuleOne" / "module_plot_BU.json"
        live_file = self.modules_root / "ModuleOne" / "module_plot.json"

        self._write_json(bu_file, {"plotTitle": "Backup Plot"})
        self._write_json(live_file, {"plotTitle": "Live Plot"})

        before_text = live_file.read_text(encoding="utf-8")
        result = hydrate_missing_module_plot_files_from_bu(str(self.modules_root))
        after_text = live_file.read_text(encoding="utf-8")

        self.assertEqual(result["restored"], 0)
        self.assertEqual(result["skipped_existing"], 1)
        self.assertEqual(before_text, after_text)
        self.assertNotEqual(after_text, bu_file.read_text(encoding="utf-8"))

    def test_stale_live_plot_with_missing_plot_points_is_repaired(self):
        """Existing live plot should be repaired when canonical plot points diverge."""
        bu_file = self.modules_root / "ModuleOne" / "module_plot_BU.json"
        live_file = self.modules_root / "ModuleOne" / "module_plot.json"

        self._write_json(
            bu_file,
            {
                "plotTitle": "Canonical Plot",
                "plotPoints": [
                    {"id": "PP001", "title": "Start", "status": "not started"},
                    {"id": "PP002", "title": "Refuge", "status": "not started"},
                ],
            },
        )
        self._write_json(
            live_file,
            {
                "plotTitle": "Live Plot",
                "plotPoints": [
                    {"id": "PP001", "title": "Start", "status": "completed", "plotImpact": "done"},
                ],
            },
        )

        result = hydrate_missing_module_plot_files_from_bu(str(self.modules_root))
        repaired_payload = json.loads(live_file.read_text(encoding="utf-8"))

        self.assertEqual(result["repaired_existing"], 1)
        self.assertEqual(len(repaired_payload["plotPoints"]), 2)
        self.assertEqual(repaired_payload["plotPoints"][0]["status"], "completed")
        self.assertEqual(repaired_payload["plotPoints"][0]["plotImpact"], "done")

    def test_restored_module_plot_files_are_deterministic(self):
        """Restored module_plot list should be deterministic by module path."""
        self._write_json(self.modules_root / "Zeta" / "module_plot_BU.json", {"plotTitle": "Zeta"})
        self._write_json(self.modules_root / "Alpha" / "module_plot_BU.json", {"plotTitle": "Alpha"})

        result = hydrate_missing_module_plot_files_from_bu(str(self.modules_root))
        restored = result["restored_files"]

        expected = [
            str(self.modules_root / "Alpha" / "module_plot.json"),
            str(self.modules_root / "Zeta" / "module_plot.json"),
        ]
        self.assertEqual(restored, expected)


class TestStartupWizardHydrationContracts(unittest.TestCase):
    """Source-contract checks for startup wizard hydration orchestration."""

    @classmethod
    def setUpClass(cls):
        repo_root = Path(__file__).resolve().parents[1]
        cls.startup_wizard_source = (repo_root / "utils" / "startup_wizard.py").read_text(
            encoding="utf-8"
        )

    def test_startup_wizard_uses_area_and_plot_hydration_helpers(self):
        self.assertIn("hydrate_missing_live_area_files_from_bu", self.startup_wizard_source)
        self.assertIn("hydrate_missing_module_plot_files_from_bu", self.startup_wizard_source)
        self.assertIn(
            'area_result = hydrate_missing_live_area_files_from_bu("modules")',
            self.startup_wizard_source,
        )
        self.assertIn(
            'plot_result = hydrate_missing_module_plot_files_from_bu("modules")',
            self.startup_wizard_source,
        )

    def test_startup_wizard_preserves_non_area_bu_hydration(self):
        self.assertIn('if "areas" in bu_file.parts:', self.startup_wizard_source)
        self.assertIn('live_file = str(bu_file).replace("_BU.json", ".json")', self.startup_wizard_source)


class TestWebRuntimeHydrationContracts(unittest.TestCase):
    """Source-contract checks for web launch hydration parity."""

    @classmethod
    def setUpClass(cls):
        repo_root = Path(__file__).resolve().parents[1]
        cls.web_interface_source = (repo_root / "web" / "web_interface.py").read_text(
            encoding="utf-8"
        )

    def test_web_run_game_loop_hydrates_runtime_files_before_main_loop(self):
        self.assertIn("from utils.startup_wizard import initialize_game_files_from_bu", self.web_interface_source)
        self.assertIn("initialize_game_files_from_bu()", self.web_interface_source)
        run_loop_start = self.web_interface_source.index("def run_game_loop():")
        run_loop_source = self.web_interface_source[run_loop_start:]
        hydrate_index = run_loop_source.index("initialize_game_files_from_bu()")
        main_loop_index = run_loop_source.rindex("dm_main.main_game_loop()")
        self.assertLess(hydrate_index, main_loop_index)


class TestResetPlotHydrationContracts(unittest.TestCase):
    """Source-contract checks for reset compatibility with module_plot BU restoration."""

    @classmethod
    def setUpClass(cls):
        repo_root = Path(__file__).resolve().parents[1]
        cls.reset_source = (repo_root / "utils" / "reset_campaign.py").read_text(
            encoding="utf-8"
        )

    def test_reset_module_restores_from_bu_generic_mapping(self):
        self.assertIn('if file.endswith("_BU.json"):', self.reset_source)
        self.assertIn('original_file = bu_file.replace("_BU.json", ".json")', self.reset_source)
        self.assertIn('shutil.copy2(bu_file, original_file)', self.reset_source)


class TestStartupAreaCoverageInShippedModules(unittest.TestCase):
    """Repository-level guard: shipped live area and plot files have BU backups."""

    def test_shipped_modules_have_matching_area_bu_files(self):
        repo_root = Path(__file__).resolve().parents[1]
        modules_root = repo_root / "modules"

        module_dirs = sorted(p.parent for p in modules_root.glob("*/module_context.json"))
        self.assertGreater(len(module_dirs), 0, "Expected at least one shipped module")

        missing = []
        for module_dir in module_dirs:
            areas_dir = module_dir / "areas"
            if not areas_dir.exists():
                continue

            live_area_files = sorted(
                path for path in areas_dir.glob("*.json") if not path.name.endswith("_BU.json")
            )
            for live_file in live_area_files:
                backup_file = areas_dir / f"{live_file.stem}_BU.json"
                if not backup_file.exists():
                    missing.append(str(backup_file))

        self.assertEqual(
            missing,
            [],
            f"Missing area backup files: {missing}",
        )

    def test_shipped_modules_have_matching_module_plot_bu_files(self):
        repo_root = Path(__file__).resolve().parents[1]
        modules_root = repo_root / "modules"

        module_dirs = sorted(p.parent for p in modules_root.glob("*/module_context.json"))
        self.assertGreater(len(module_dirs), 0, "Expected at least one shipped module")

        missing = []
        for module_dir in module_dirs:
            live_plot = module_dir / "module_plot.json"
            backup_plot = module_dir / "module_plot_BU.json"
            if live_plot.exists() and not backup_plot.exists():
                missing.append(str(backup_plot))

        self.assertEqual(
            missing,
            [],
            f"Missing module_plot backup files: {missing}",
        )


if __name__ == "__main__":
    unittest.main()
