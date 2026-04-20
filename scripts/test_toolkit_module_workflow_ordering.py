#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Toolkit Module Workflow Ordering Source Contracts
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

import unittest
from pathlib import Path


class TestToolkitModuleWorkflowOrdering(unittest.TestCase):
    """Source-level contracts for toolkit workflow tab ordering."""

    def setUp(self) -> None:
        self.template_source = Path("web/templates/module_toolkit.html").read_text(
            encoding="utf-8"
        )

    def test_module_builder_tabs_are_first(self) -> None:
        builder_index = self.template_source.index(
            "onclick=\"switchTab('builder')\">Module Builder"
        )
        media_gen_index = self.template_source.index(
            "onclick=\"switchTab('media-gen')\">Module Media Generator"
        )
        packs_index = self.template_source.index(
            "onclick=\"switchTab('packs')\">Graphic Pack Management"
        )

        self.assertLess(builder_index, media_gen_index)
        self.assertLess(media_gen_index, packs_index)

    def test_builder_is_default_active_tab(self) -> None:
        self.assertIn(
            '<button class="tab active" onclick="switchTab(\'builder\')">Module Builder</button>',
            self.template_source,
        )
        self.assertIn('<div id="builder-tab" class="tab-content active">', self.template_source)
        self.assertIn('<div id="packs-tab" class="tab-content">', self.template_source)

    def test_graphic_pack_manager_tools_still_present(self) -> None:
        self.assertIn("onclick=\"switchTab('generator')\"", self.template_source)
        self.assertIn("onclick=\"switchTab('npcs')\"", self.template_source)
        self.assertIn('<div id="generator-tab" class="tab-content">', self.template_source)
        self.assertIn('<div id="npcs-tab" class="tab-content">', self.template_source)


if __name__ == "__main__":
    unittest.main()
