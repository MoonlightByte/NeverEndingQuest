# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""World narrative toolkit route tests."""

import io
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

from flask import Flask

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory.memory_db import init_memory_db
from web.routes.world_narrative_routes import (
    register_world_narrative_routes,
    reset_world_jobs_for_tests,
)


class TestWorldNarrativeRoutes(unittest.TestCase):
    def setUp(self) -> None:
        self.original_cwd = os.getcwd()
        self.temp_dir = tempfile.mkdtemp(prefix="neq_world_routes_test_")
        os.chdir(self.temp_dir)
        os.makedirs("user_uploads/text", exist_ok=True)
        os.makedirs("user_uploads", exist_ok=True)

        self.app = Flask(__name__)
        register_world_narrative_routes(self.app)
        self.client = self.app.test_client()

        reset_world_jobs_for_tests()

        self.db_path = os.path.join(self.temp_dir, "memory.db")
        init_memory_db(self.db_path)

    def tearDown(self) -> None:
        reset_world_jobs_for_tests()
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_upload_requires_attestation(self) -> None:
        response = self.client.post(
            "/api/toolkit/world/sources/upload",
            data={"file": (io.BytesIO(b"demo"), "novel.pdf")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload.get("status"), "error")

    def test_upload_accepts_pdf_with_attestation(self) -> None:
        response = self.client.post(
            "/api/toolkit/world/sources/upload",
            data={
                "attest_copyright": "true",
                "file": (io.BytesIO(b"%PDF-1.4\n"), "story.pdf"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload.get("status"), "success")
        self.assertTrue(os.path.exists(payload.get("path")))
        self.assertIn(os.path.join("user_uploads", "text"), payload.get("path"))

    def test_upload_rejects_non_pdf_with_attestation(self) -> None:
        response = self.client.post(
            "/api/toolkit/world/sources/upload",
            data={
                "attest_copyright": "true",
                "file": (io.BytesIO(b"not-pdf"), "story.txt"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload.get("status"), "error")

    def test_extract_rejects_non_pdf_path(self) -> None:
        txt_path = os.path.join(self.temp_dir, "user_uploads", "text", "notes.txt")
        with open(txt_path, "w", encoding="utf-8") as handle:
            handle.write("notes")

        response = self.client.post(
            "/api/toolkit/world/sources/extract",
            json={"path": txt_path},
        )
        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload.get("status"), "error")

    def test_extract_rejects_legacy_user_uploads_root(self) -> None:
        legacy_pdf_path = os.path.join(self.temp_dir, "user_uploads", "legacy.pdf")
        with open(legacy_pdf_path, "wb") as handle:
            handle.write(b"%PDF-1.4\n")

        response = self.client.post(
            "/api/toolkit/world/sources/extract",
            json={"path": legacy_pdf_path},
        )
        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload.get("status"), "error")

    def test_ingest_rejects_payload_with_banned_key(self) -> None:
        atoms_path = os.path.join(self.temp_dir, "user_uploads", "text", "bad_atoms.json")
        with open(atoms_path, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "schema_version": "inspiration-anonymous/v1",
                    "profile": {"profile_id": "profile.test", "profile_kind": "test"},
                    "source": "forbidden",
                    "atoms": [
                        {
                            "atom_id": "atom.test",
                            "atom_type": "motif",
                            "label": "Test",
                            "description": "Valid abstract motif",
                            "weight": 0.6,
                            "srd_compatibility": "compatible",
                        }
                    ],
                },
                handle,
            )

        response = self.client.post(
            "/api/toolkit/world/sources/ingest",
            json={"atoms_path": atoms_path, "db_path": self.db_path},
        )
        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload.get("status"), "error")
        self.assertTrue(payload.get("key_hits"))

    def test_ingest_writes_anonymous_atoms(self) -> None:
        atoms_path = os.path.join(self.temp_dir, "user_uploads", "text", "good_atoms.json")
        with open(atoms_path, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "schema_version": "inspiration-anonymous/v1",
                    "generated_at": "2026-02-22T10:00:00Z",
                    "profile": {"profile_id": "profile.dark", "profile_kind": "dark_fantasy"},
                    "atoms": [
                        {
                            "atom_id": "atom.hidden_refuge",
                            "atom_type": "motif",
                            "label": "Hidden refuge",
                            "description": "A sanctuary exists beneath ordinary society.",
                            "weight": 0.73,
                            "srd_compatibility": "compatible",
                        }
                    ],
                },
                handle,
            )

        response = self.client.post(
            "/api/toolkit/world/sources/ingest",
            json={"atoms_path": atoms_path, "db_path": self.db_path},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload.get("status"), "success")

        conn = sqlite3.connect(self.db_path)
        try:
            profile_count = conn.execute("SELECT COUNT(*) FROM inspiration_profiles").fetchone()[0]
            atom_count = conn.execute("SELECT COUNT(*) FROM inspiration_atoms").fetchone()[0]
            stats_count = conn.execute("SELECT COUNT(*) FROM atom_statistics").fetchone()[0]
        finally:
            conn.close()

        self.assertEqual(profile_count, 1)
        self.assertEqual(atom_count, 1)
        self.assertEqual(stats_count, 1)

    def test_ingest_rejects_legacy_user_uploads_root(self) -> None:
        legacy_atoms_path = os.path.join(self.temp_dir, "user_uploads", "legacy_atoms.json")
        with open(legacy_atoms_path, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "schema_version": "inspiration-anonymous/v1",
                    "generated_at": "2026-02-22T10:00:00Z",
                    "profile": {"profile_id": "profile.dark", "profile_kind": "dark_fantasy"},
                    "atoms": [
                        {
                            "atom_id": "atom.hidden_refuge",
                            "atom_type": "motif",
                            "label": "Hidden refuge",
                            "description": "A sanctuary exists beneath ordinary society.",
                            "weight": 0.73,
                            "srd_compatibility": "compatible",
                        }
                    ],
                },
                handle,
            )

        response = self.client.post(
            "/api/toolkit/world/sources/ingest",
            json={"atoms_path": legacy_atoms_path, "db_path": self.db_path},
        )
        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload.get("status"), "error")


if __name__ == "__main__":
    unittest.main()
