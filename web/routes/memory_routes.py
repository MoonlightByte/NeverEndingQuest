# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Web Routes - Memory retrieval endpoints.
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0
"""

import os
from typing import Any

from flask import Flask, jsonify, request, send_file

from core.memory.memory_db import DEFAULT_MEMORY_DB_PATH
from core.memory.memory_retrieval import get_entity_timeline
from core.memory.session_diary import list_diary_entries
from core.memory.story_so_far_compiler import get_or_build_story_pdf
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

    @app.route('/api/journal/diary', methods=['GET'])
    def get_journal_diary() -> Any:
        """Return draft and confirmed diary entries."""
        try:
            include_draft_raw = str(request.args.get('include_draft', 'true')).strip().lower()
            include_draft = include_draft_raw not in ('false', '0', 'no')

            limit_raw = request.args.get('limit', '20')
            try:
                limit = int(limit_raw)
            except (TypeError, ValueError):
                limit = 20

            before_sort_key_raw = request.args.get('before_sort_key')
            before_sort_key = None
            if before_sort_key_raw not in (None, ''):
                try:
                    before_sort_key = int(before_sort_key_raw)
                except (TypeError, ValueError):
                    before_sort_key = None

            result = list_diary_entries(
                db_path=DEFAULT_MEMORY_DB_PATH,
                include_draft=include_draft,
                limit=limit,
                before_sort_key=before_sort_key,
            )
            status_code = 200 if result.get('status') == 'success' else 200
            return jsonify(result), status_code
        except Exception as route_error:
            error(
                f"MEMORY_ROUTE: Failed to fetch journal diary: {route_error}",
                exception=route_error,
                category="web_interface",
            )
            return jsonify({
                'status': 'error',
                'draft': None,
                'entries': [],
                'next_before_sort_key': None,
                'message': 'Journal diary unavailable',
            }), 200

    @app.route('/api/journal/story-so-far/pdf', methods=['GET'])
    def download_story_so_far_pdf() -> Any:
        """Build or reuse confirmed-only story PDF and return it as an attachment."""
        try:
            result = get_or_build_story_pdf(DEFAULT_MEMORY_DB_PATH)
            if result.get('status') != 'success':
                return jsonify({
                    'status': 'error',
                    'message': result.get('message', 'Story PDF unavailable'),
                }), 500

            pdf_path = result.get('pdf_path')
            if not pdf_path:
                return jsonify({
                    'status': 'error',
                    'message': 'Story PDF path missing',
                }), 500

            pdf_path = os.path.abspath(str(pdf_path))
            if not os.path.exists(pdf_path):
                return jsonify({
                    'status': 'error',
                    'message': 'Story PDF unavailable',
                }), 500

            return send_file(
                pdf_path,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=result.get('download_name', 'Story_So_Far.pdf'),
            )
        except Exception as route_error:
            error(
                f"MEMORY_ROUTE: Failed to build story PDF: {route_error}",
                exception=route_error,
                category="web_interface",
            )
            return jsonify({
                'status': 'error',
                'message': 'Story PDF unavailable',
            }), 500
