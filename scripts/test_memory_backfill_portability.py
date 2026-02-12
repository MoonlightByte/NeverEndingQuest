# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Memory backfill source selection and portability tests.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
import importlib.util

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory.memory_ingest import backfill_memory_db_from_histories
from core.memory.memory_portability import (
    export_memory_db_package,
    import_memory_db_package,
    validate_memory_package,
)

BACKFILL_SCRIPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backfill_memory_db.py")
_spec = importlib.util.spec_from_file_location("backfill_memory_db", BACKFILL_SCRIPT_PATH)
_module = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_module)
parse_sources_arg = _module.parse_sources_arg


class TestMemoryBackfillPortability(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="neq_memory_portability_test_")
        self.db_path = os.path.join(self.temp_dir, "memory.db")
        self.journal_path = os.path.join(self.temp_dir, "journal.json")
        self.conversation_path = os.path.join(self.temp_dir, "conversation_history.json")
        self.combat_path = os.path.join(self.temp_dir, "combat_history.json")

        with open(self.journal_path, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "journal_entries": [
                        {
                            "timestamp": "2026-02-13T10:00:00Z",
                            "title": "Watch Log",
                            "content": "Acheron reviewed watch rotations.",
                        }
                    ]
                },
                handle,
            )

        with open(self.conversation_path, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "conversation_history": [
                        {"role": "user", "content": "Acheron asks about the north road."},
                        {"role": "assistant", "content": "The road is blocked by fallen pines."},
                    ]
                },
                handle,
            )

        with open(self.combat_path, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "conversation_history": [
                        {"role": "user", "content": "Acheron attacks the shadow."},
                        {"role": "assistant", "content": "The shadow reels and retreats."},
                    ]
                },
                handle,
            )

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_parse_sources_valid_and_invalid(self) -> None:
        self.assertEqual(parse_sources_arg("journal"), ["journal"])
        self.assertEqual(parse_sources_arg("journal,combat"), ["journal", "combat"])

        with self.assertRaises(ValueError):
            parse_sources_arg("journal,foo")

    def test_selective_backfill_journal_only(self) -> None:
        result = backfill_memory_db_from_histories(
            db_path=self.db_path,
            journal_path=self.journal_path,
            conversation_path=self.conversation_path,
            combat_history_path=self.combat_path,
            sources=["journal"],
        )
        self.assertEqual(result.get("status"), "success")
        self.assertEqual(result.get("sources_ingested", {}).get("journal"), 1)
        self.assertEqual(result.get("sources_ingested", {}).get("conversation_history"), 0)
        self.assertEqual(result.get("sources_ingested", {}).get("combat_history"), 0)

        # Idempotency: second run does not duplicate journal entry rows.
        second = backfill_memory_db_from_histories(
            db_path=self.db_path,
            journal_path=self.journal_path,
            conversation_path=self.conversation_path,
            combat_history_path=self.combat_path,
            sources=["journal"],
        )
        self.assertEqual(second.get("status"), "success")

        import sqlite3

        conn = sqlite3.connect(self.db_path)
        count = conn.execute("SELECT COUNT(*) FROM journal_entries").fetchone()[0]
        conn.close()
        self.assertEqual(count, 1)

    def test_export_import_portability_safety(self) -> None:
        # Seed DB first.
        seed_result = backfill_memory_db_from_histories(
            db_path=self.db_path,
            journal_path=self.journal_path,
            conversation_path=self.conversation_path,
            combat_history_path=self.combat_path,
            sources=["journal", "conversation", "combat"],
        )
        self.assertEqual(seed_result.get("status"), "success")

        package_dir = os.path.join(self.temp_dir, "package")
        export_result = export_memory_db_package(self.db_path, package_dir, overwrite=False)
        self.assertEqual(export_result.get("status"), "success")
        self.assertTrue(os.path.exists(os.path.join(package_dir, "manifest.json")))
        self.assertTrue(os.path.exists(os.path.join(package_dir, "memory.db")))

        # Non-destructive default: existing target blocks import.
        target_db_path = os.path.join(self.temp_dir, "target_existing.db")
        shutil.copy2(self.db_path, target_db_path)
        blocked = import_memory_db_package(package_dir, target_db_path, overwrite=False, dry_run=False)
        self.assertEqual(blocked.get("status"), "error")

        # Dry-run import validates but does not write.
        target_new = os.path.join(self.temp_dir, "target_new.db")
        dry_run = import_memory_db_package(package_dir, target_new, overwrite=False, dry_run=True)
        self.assertEqual(dry_run.get("status"), "success")
        self.assertTrue(dry_run.get("dry_run"))
        self.assertFalse(os.path.exists(target_new))

        # Incompatible schema version is rejected.
        manifest_path = os.path.join(package_dir, "manifest.json")
        with open(manifest_path, "r", encoding="utf-8") as handle:
            manifest = json.load(handle)
        manifest["schema_version"] = "memory-db-package/v999"
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2)

        validation = validate_memory_package(package_dir)
        self.assertEqual(validation.get("status"), "error")


if __name__ == "__main__":
    unittest.main()
