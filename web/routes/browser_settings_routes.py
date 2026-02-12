# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Web Routes - Browser settings endpoints
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

from typing import Any, Callable, Set

from flask import Flask, jsonify, request

from utils.enhanced_logger import error


def register_browser_settings_routes(
    app: Flask,
    get_preferred_browser_setting: Callable[[], str],
    set_preferred_browser_setting: Callable[[str], bool],
    allowed_browser_preferences: Set[str],
) -> None:
    """Register browser preference API routes."""

    @app.route('/api/settings/browser', methods=['GET'])
    def get_browser_settings() -> Any:
        """Return persisted browser preference for startup auto-open."""
        try:
            preferred_browser = get_preferred_browser_setting()
            return jsonify({
                'success': True,
                'preferred_browser': preferred_browser,
            })
        except Exception as route_error:
            error(f"Failed to fetch browser settings: {route_error}", exception=route_error, category="web_interface")
            return jsonify({
                'success': False,
                'error': 'Failed to fetch browser settings',
            }), 500

    @app.route('/api/settings/browser', methods=['POST'])
    def set_browser_settings() -> Any:
        """Persist browser preference for startup auto-open."""
        try:
            data = request.get_json(silent=True) or {}
            preferred_browser = str(data.get('preferred_browser', '')).lower().strip()

            if preferred_browser not in allowed_browser_preferences:
                return jsonify({
                    'success': False,
                    'error': 'Invalid preferred_browser. Expected one of: default, chrome, edge',
                }), 400

            if not set_preferred_browser_setting(preferred_browser):
                return jsonify({
                    'success': False,
                    'error': 'Failed to save browser settings',
                }), 500

            return jsonify({
                'success': True,
                'preferred_browser': preferred_browser,
            })
        except Exception as route_error:
            error(f"Failed to save browser settings: {route_error}", exception=route_error, category="web_interface")
            return jsonify({
                'success': False,
                'error': 'Failed to save browser settings',
            }), 500
