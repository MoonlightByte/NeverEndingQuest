#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Runtime regression tests for web Create-with-DM route fail-closed recovery."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from flask import Flask
    from web.routes.tabletop_party_routes import register_tabletop_party_routes
    ROUTE_IMPORT_ERROR = None
except Exception as import_error:  # pragma: no cover - guarded runtime dependency
    Flask = None
    register_tabletop_party_routes = None
    ROUTE_IMPORT_ERROR = import_error


class _RecordingQueue:
    def __init__(self, fail_on_put: bool = False):
        self.fail_on_put = fail_on_put
        self.items = []

    def put(self, item):
        if self.fail_on_put:
            raise RuntimeError("queue_put_failed")
        self.items.append(item)


class TestWebCreationRouteRecovery(unittest.TestCase):
    def setUp(self) -> None:
        if ROUTE_IMPORT_ERROR is not None:
            raise unittest.SkipTest(f"Route runtime dependencies unavailable: {ROUTE_IMPORT_ERROR}")

    def _build_client(self, queue):
        app = Flask(__name__)
        register_tabletop_party_routes(app, queue)
        return app.test_client()

    def _party_tracker(self):
        return {
            "partyMembers": ["alpha"],
            "active_character": "alpha",
            "worldConditions": {"currentLocation": "Test Location"},
            "module": "Test_Module",
        }

    def test_create_player_marker_write_failure_fails_closed_without_abort(self) -> None:
        queue = _RecordingQueue()
        client = self._build_client(queue)

        with patch("web.routes.tabletop_party_routes.backup_conversation_history", return_value=True), patch(
            "web.routes.tabletop_party_routes.safe_write_json", return_value=False
        ), patch(
            "web.routes.tabletop_party_routes.pc_manager.get_party_tracker", return_value=self._party_tracker()
        ), patch(
            "web.routes.tabletop_party_routes.pc_manager.get_character_creation_prompt", return_value="prompt"
        ), patch(
            "web.routes.tabletop_party_routes.abort_character_creation_session"
        ) as abort_mock:
            response = client.post("/api/party/create_player", json={"name": "UnitTestMarkerWriteFailure"})

        self.assertEqual(response.status_code, 500)
        self.assertIn("Failed to activate character creation mode", response.get_json().get("error", ""))
        self.assertEqual(queue.items, [])
        abort_mock.assert_not_called()

    def test_create_player_post_marker_failure_aborts_stale_session(self) -> None:
        queue = _RecordingQueue(fail_on_put=True)
        client = self._build_client(queue)

        with patch("web.routes.tabletop_party_routes.backup_conversation_history", return_value=True), patch(
            "web.routes.tabletop_party_routes.safe_write_json", return_value=True
        ), patch(
            "web.routes.tabletop_party_routes.pc_manager.get_party_tracker", return_value=self._party_tracker()
        ), patch(
            "web.routes.tabletop_party_routes.pc_manager.get_character_creation_prompt", return_value="prompt"
        ), patch(
            "web.routes.tabletop_party_routes.abort_character_creation_session", return_value={"marker_removed": True}
        ) as abort_mock:
            response = client.post("/api/party/create_player", json={"name": "UnitTestQueueFailure"})

        self.assertEqual(response.status_code, 500)
        abort_mock.assert_called_once_with(reason="web_create_player_route_error")

    def test_finalize_creation_needs_retry_keeps_session_active(self) -> None:
        queue = _RecordingQueue()
        client = self._build_client(queue)

        with patch(
            "web.routes.tabletop_party_routes.finalize_character_creation_candidate",
            return_value={
                "status": "needs_retry",
                "audit_result_type": "schema_error",
                "missing_paths": ["$.backstory"],
                "corrective_guidance": "Provide missing backstory.",
            },
        ), patch("web.routes.tabletop_party_routes.abort_character_creation_session") as abort_mock:
            response = client.post("/api/party/finalize_creation", json={"character_data": {"name": "Retry Hero"}})

        self.assertEqual(response.status_code, 400)
        abort_mock.assert_not_called()

    def test_finalize_creation_terminal_error_aborts_session(self) -> None:
        queue = _RecordingQueue()
        client = self._build_client(queue)

        with patch(
            "web.routes.tabletop_party_routes.finalize_character_creation_candidate",
            return_value={"status": "error", "error_message": "finalizer_failure"},
        ), patch(
            "web.routes.tabletop_party_routes.is_creation_mode_active", return_value=True
        ), patch(
            "web.routes.tabletop_party_routes.abort_character_creation_session", return_value={"marker_removed": True}
        ) as abort_mock:
            response = client.post("/api/party/finalize_creation", json={"character_data": {"name": "Fail Hero"}})

        self.assertEqual(response.status_code, 500)
        abort_mock.assert_called_once_with(reason="web_finalize_creation_terminal_error")

    def test_finalize_creation_persist_failure_aborts_session(self) -> None:
        queue = _RecordingQueue()
        client = self._build_client(queue)

        with patch(
            "web.routes.tabletop_party_routes.finalize_character_creation_candidate",
            return_value={"status": "success", "character_data": {"name": "Persist Hero"}},
        ), patch(
            "web.routes.tabletop_party_routes.persist_dm_created_character",
            return_value={"success": False, "error": "disk_write_failed"},
        ), patch(
            "web.routes.tabletop_party_routes.is_creation_mode_active", return_value=True
        ), patch(
            "web.routes.tabletop_party_routes.abort_character_creation_session", return_value={"marker_removed": True}
        ) as abort_mock:
            response = client.post("/api/party/finalize_creation", json={"character_data": {"name": "Persist Hero"}})

        self.assertEqual(response.status_code, 500)
        abort_mock.assert_called_once_with(reason="web_finalize_creation_persist_failure")

    def test_finalize_terminal_error_without_active_creation_skips_abort(self) -> None:
        queue = _RecordingQueue()
        client = self._build_client(queue)

        with patch(
            "web.routes.tabletop_party_routes.finalize_character_creation_candidate",
            return_value={"status": "error", "error_message": "finalizer_failure"},
        ), patch(
            "web.routes.tabletop_party_routes.is_creation_mode_active", return_value=False
        ), patch("web.routes.tabletop_party_routes.abort_character_creation_session") as abort_mock:
            response = client.post("/api/party/finalize_creation", json={"character_data": {"name": "Fail Hero"}})

        self.assertEqual(response.status_code, 500)
        abort_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
