# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Memory Portability - Export/import helpers.
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0
"""

import hashlib
import json
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from utils.enhanced_logger import error, info
from utils.file_operations import safe_read_json


PACKAGE_SCHEMA_VERSION = "memory-db-package/v1"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_file(file_path: str) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _count_rows(conn: sqlite3.Connection, table_name: str) -> int:
    try:
        row = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
        return int(row[0]) if row else 0
    except Exception:
        return 0


def _get_applied_migrations(conn: sqlite3.Connection) -> List[str]:
    try:
        rows = conn.execute("SELECT migration_id FROM schema_migrations ORDER BY migration_id").fetchall()
        return [str(row[0]) for row in rows]
    except Exception:
        return []


def _build_campaign_metadata() -> Dict[str, Any]:
    tracker = safe_read_json("party_tracker.json") or {}
    return {
        "active_character": tracker.get("active_character"),
        "party_members": tracker.get("partyMembers", []) or [],
        "party_npcs": [
            item.get("name", "") if isinstance(item, dict) else str(item)
            for item in (tracker.get("partyNPCs", []) or [])
        ],
    }


def export_memory_db_package(
    source_db_path: str,
    output_dir: str,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """Export memory DB into portable package directory with manifest."""
    if not os.path.exists(source_db_path):
        return {
            "status": "error",
            "message": f"Source DB not found: {source_db_path}",
        }

    if os.path.exists(output_dir):
        if not overwrite:
            return {
                "status": "error",
                "message": f"Output directory already exists: {output_dir}",
            }
        shutil.rmtree(output_dir, ignore_errors=True)

    os.makedirs(output_dir, exist_ok=True)
    db_filename = "memory.db"
    package_db_path = os.path.join(output_dir, db_filename)
    shutil.copy2(source_db_path, package_db_path)

    conn: Optional[sqlite3.Connection] = None
    try:
        conn = sqlite3.connect(package_db_path)
        row_counts = {
            "entities": _count_rows(conn, "entities"),
            "journal_entries": _count_rows(conn, "journal_entries"),
            "memory_events": _count_rows(conn, "memory_events"),
            "memory_links": _count_rows(conn, "memory_links"),
        }
        applied_migrations = _get_applied_migrations(conn)
    finally:
        if conn is not None:
            conn.close()

    db_hash = _sha256_file(package_db_path)
    manifest = {
        "schema_version": PACKAGE_SCHEMA_VERSION,
        "exported_at": _utc_now_iso(),
        "source_db_path": source_db_path,
        "db_filename": db_filename,
        "db_sha256": db_hash,
        "db_size_bytes": os.path.getsize(package_db_path),
        "row_counts": row_counts,
        "applied_migrations": applied_migrations,
        "campaign_metadata": _build_campaign_metadata(),
    }

    manifest_path = os.path.join(output_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)

    info(
        f"MEMORY_PORTABILITY: Exported package to {output_dir}",
        category="memory_db",
    )
    return {
        "status": "success",
        "output_dir": output_dir,
        "manifest_path": manifest_path,
        "db_path": package_db_path,
        "row_counts": row_counts,
        "db_sha256": db_hash,
    }


def validate_memory_package(package_dir: str) -> Dict[str, Any]:
    """Validate package manifest, hash, and schema compatibility."""
    manifest_path = os.path.join(package_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        return {"status": "error", "message": f"Manifest missing: {manifest_path}"}

    try:
        with open(manifest_path, "r", encoding="utf-8") as handle:
            manifest = json.load(handle)
    except Exception as read_error:
        return {"status": "error", "message": f"Invalid manifest JSON: {read_error}"}

    if manifest.get("schema_version") != PACKAGE_SCHEMA_VERSION:
        return {
            "status": "error",
            "message": (
                f"Unsupported schema version: {manifest.get('schema_version')} "
                f"(expected {PACKAGE_SCHEMA_VERSION})"
            ),
        }

    db_filename = str(manifest.get("db_filename", "memory.db"))
    db_path = os.path.join(package_dir, db_filename)
    if not os.path.exists(db_path):
        return {"status": "error", "message": f"Package DB missing: {db_path}"}

    current_hash = _sha256_file(db_path)
    expected_hash = str(manifest.get("db_sha256", ""))
    if current_hash != expected_hash:
        return {
            "status": "error",
            "message": "Integrity hash mismatch for package DB",
            "expected_hash": expected_hash,
            "actual_hash": current_hash,
        }

    conn: Optional[sqlite3.Connection] = None
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'")
        applied_migrations = _get_applied_migrations(conn)
    except Exception as validation_error:
        return {
            "status": "error",
            "message": f"Schema validation failed: {validation_error}",
        }
    finally:
        if conn is not None:
            conn.close()

    return {
        "status": "success",
        "manifest": manifest,
        "db_path": db_path,
        "applied_migrations": applied_migrations,
    }


def import_memory_db_package(
    package_dir: str,
    target_db_path: str,
    overwrite: bool = False,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Import package DB into target path with safety checks."""
    validation = validate_memory_package(package_dir)
    if validation.get("status") != "success":
        return validation

    package_db_path = str(validation.get("db_path"))
    target_exists = os.path.exists(target_db_path)

    if target_exists and not overwrite:
        return {
            "status": "error",
            "message": f"Target DB already exists: {target_db_path}",
            "hint": "Use --overwrite to replace existing DB",
        }

    if dry_run:
        return {
            "status": "success",
            "dry_run": True,
            "target_db_path": target_db_path,
            "package_db_path": package_db_path,
            "action": "validate_only",
            "would_overwrite": bool(target_exists and overwrite),
            "manifest": validation.get("manifest"),
        }

    try:
        os.makedirs(os.path.dirname(target_db_path) or ".", exist_ok=True)
        shutil.copy2(package_db_path, target_db_path)
        info(
            f"MEMORY_PORTABILITY: Imported package DB to {target_db_path}",
            category="memory_db",
        )
        return {
            "status": "success",
            "dry_run": False,
            "target_db_path": target_db_path,
            "package_db_path": package_db_path,
        }
    except Exception as import_error:
        error(
            f"MEMORY_PORTABILITY: Import failed: {import_error}",
            exception=import_error,
            category="memory_db",
        )
        return {
            "status": "error",
            "message": str(import_error),
            "target_db_path": target_db_path,
        }
