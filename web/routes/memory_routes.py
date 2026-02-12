# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Web Routes - Memory retrieval endpoints.
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0
"""

from typing import Any

from flask import Flask, jsonify, request

from core.memory.memory_db import DEFAULT_MEMORY_DB_PATH
from core.memory.memory_retrieval import get_entity_timeline
from utils.enhanced_logger import error


def register_memory_routes(app: Flask) -> None:
    """Register read-only memory inspection routes."""

    @app.route('/api/memory/entity/<entity_id>', methods=['GET'])
    def get_memory_entity_timeline(entity_id: str) -> Any:
        """Return ranked memory timeline for one entity."""
        try:
            limit_raw = request.args.get('limit', '25')
            try:
                limit = int(limit_raw)
            except (TypeError, ValueError):
                limit = 25

            timeline = get_entity_timeline(entity_id=entity_id, limit=limit, db_path=DEFAULT_MEMORY_DB_PATH)
            return jsonify({
                "status": "success",
                "entity_id": entity_id,
                "timeline": timeline,
                "count": len(timeline),
            })
        except Exception as route_error:
            error(
                f"MEMORY_ROUTE: Failed to fetch timeline for {entity_id}: {route_error}",
                exception=route_error,
                category="web_interface",
            )
            # Graceful fallback: non-blocking failure for existing gameplay paths.
            return jsonify({
                "status": "error",
                "entity_id": entity_id,
                "timeline": [],
                "count": 0,
                "message": "Memory DB unavailable",
            }), 200
