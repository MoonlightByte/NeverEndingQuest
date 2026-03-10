#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

"""Regression tests for fork-origin update channel behavior."""

import os
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils import version_checker


class TestForkOriginResolver(unittest.TestCase):
    """Validate origin parsing and target resolution."""

    def test_parse_https_origin(self):
        parsed = version_checker._parse_github_owner_repo(
            "https://github.com/zeug-zz/NeverEndingQuest-TTRPG.git"
        )
        self.assertEqual(parsed, ("zeug-zz", "NeverEndingQuest-TTRPG"))

    def test_parse_ssh_origin(self):
        parsed = version_checker._parse_github_owner_repo(
            "git@github.com:zeug-zz/NeverEndingQuest-TTRPG.git"
        )
        self.assertEqual(parsed, ("zeug-zz", "NeverEndingQuest-TTRPG"))

    @patch("utils.version_checker._run_git_command")
    def test_resolve_target_prefers_origin_head(self, mock_run_git):
        mock_run_git.side_effect = [
            "https://github.com/zeug-zz/NeverEndingQuest-TTRPG.git",
            "origin/main",
        ]

        target = version_checker.resolve_update_target(repo_path=".")
        self.assertIsNotNone(target)
        self.assertEqual(target["owner_repo"], "zeug-zz/NeverEndingQuest-TTRPG")
        self.assertEqual(target["branch"], "main")
        self.assertEqual(target["remote"], "origin")

    @patch("utils.version_checker._run_git_command")
    def test_resolve_target_fallback_current_branch(self, mock_run_git):
        mock_run_git.side_effect = [
            "git@github.com:zeug-zz/NeverEndingQuest-TTRPG.git",
            None,
            "dev",
        ]

        target = version_checker.resolve_update_target(repo_path=".")
        self.assertIsNotNone(target)
        self.assertEqual(target["branch"], "dev")

    @patch("utils.version_checker._run_git_command")
    def test_resolve_target_malformed_origin_returns_none(self, mock_run_git):
        mock_run_git.side_effect = ["not-a-github-url"]

        target = version_checker.resolve_update_target(repo_path=".")
        self.assertIsNone(target)


class TestVersionCheckContract(unittest.TestCase):
    """Validate check_for_updates status contract remains stable."""

    @patch("utils.version_checker.resolve_update_target")
    @patch("utils.version_checker.get_local_version")
    def test_unresolved_target_returns_unknown(self, mock_local, mock_target):
        mock_local.return_value = "1.0.0"
        mock_target.return_value = None

        status, local_ver, remote_ver, message = version_checker.check_for_updates(silent=True)

        self.assertEqual(status, "unknown")
        self.assertEqual(local_ver, "1.0.0")
        self.assertIsNone(remote_ver)
        self.assertIn("resolve fork update source", message)

    @patch("utils.version_checker.get_latest_remote_version")
    @patch("utils.version_checker.resolve_update_target")
    @patch("utils.version_checker.get_local_version")
    def test_update_available_status_contract(self, mock_local, mock_target, mock_remote):
        mock_local.return_value = "1.0.0"
        mock_target.return_value = {
            "owner_repo": "zeug-zz/NeverEndingQuest-TTRPG",
            "branch": "main",
            "remote": "origin",
            "owner": "zeug-zz",
            "repo": "NeverEndingQuest-TTRPG",
        }
        mock_remote.return_value = "1.1.0"

        status, local_ver, remote_ver, message = version_checker.check_for_updates(silent=True)

        self.assertEqual(status, "update_available")
        self.assertEqual(local_ver, "1.0.0")
        self.assertEqual(remote_ver, "1.1.0")
        self.assertIn("zeug-zz/NeverEndingQuest-TTRPG", message)


class TestUpdaterSourceContract(unittest.TestCase):
    """Source-level checks for updater preflight and ff-only pull contract."""

    def test_trigger_update_contains_dirty_tree_gate_and_ff_only_pull(self):
        web_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "web",
            "web_interface.py",
        )
        with open(web_path, "r", encoding="utf-8") as f:
            source = f.read()

        self.assertIn("'status', '--porcelain'", source)
        self.assertIn("Update blocked: working tree has local changes.", source)
        self.assertIn("pull --ff-only", source)
        self.assertIn("Resolved fork target:", source)
        self.assertIn("resolve_update_target", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
