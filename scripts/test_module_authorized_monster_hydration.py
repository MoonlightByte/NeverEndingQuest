#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Regression tests for module-authorized monster hydration."""

import json
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.module_monster_authority import (
    authorize_module_monster,
    build_module_monster_authority,
    materialize_authorized_monster_file,
    resolve_authorized_monster_reference,
)


class TestModuleMonsterAuthority(unittest.TestCase):
    def test_night_cultist_is_authorized_from_authored_module_content(self):
        result = authorize_module_monster("Night_of_the_Restless_Dead", "Cultist")
        self.assertTrue(result["authorized"])
        self.assertEqual(result["slug"], "cultist")
        self.assertTrue(result["sources"])

    def test_night_cult_fanatic_is_not_authorized(self):
        result = authorize_module_monster("Night_of_the_Restless_Dead", "Cult Fanatic")
        self.assertFalse(result["authorized"])
        self.assertEqual(result["slug"], "cult_fanatic")

    def test_unauthorized_monster_fails_closed_without_hydration(self):
        with (
            patch(
                "utils.module_monster_authority.find_reusable_monster_path"
            ) as mock_reuse,
            patch("utils.module_monster_authority.subprocess.run") as mock_run,
        ):
            result = materialize_authorized_monster_file(
                "Night_of_the_Restless_Dead",
                "Cult Fanatic",
                "core/generators/monster_builder.py",
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_class"], "unauthorized_monster_reference")
        mock_reuse.assert_not_called()
        mock_run.assert_not_called()

    def test_authorized_missing_monster_attempts_builder_hydration(self):
        builder_calls = []

        def _record_builder(args, capture_output, text):
            builder_calls.append(args)
            return SimpleNamespace(returncode=1, stdout="", stderr="builder failed")

        def _exists_side_effect(path):
            path_str = str(path)
            if path_str.endswith("monsters/cultist.json"):
                return False
            return True

        with (
            patch(
                "utils.module_monster_authority.find_reusable_monster_path",
                return_value=None,
            ),
            patch(
                "utils.module_monster_authority.os.path.exists",
                side_effect=_exists_side_effect,
            ),
            patch(
                "utils.module_monster_authority.subprocess.run",
                side_effect=_record_builder,
            ),
        ):
            result = materialize_authorized_monster_file(
                "Night_of_the_Restless_Dead",
                "Cultist",
                "core/generators/monster_builder.py",
                compendium_lookup={},
                allow_generation=True,
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_class"], "authorized_monster_hydration_failed")
        self.assertEqual(builder_calls[0][0], sys.executable)
        self.assertIn("--module", builder_calls[0])
        self.assertIn("Night_of_the_Restless_Dead", builder_calls[0])

    def test_flavored_cultist_leader_resolves_to_cultist_for_hydration(self):
        builder_calls = []
        authority = {
            "cultist": {
                "sources": [{"type": "authored_area_content", "name": "Cultist"}]
            },
        }

        def _record_builder(args, capture_output, text):
            builder_calls.append(args)
            return SimpleNamespace(returncode=1, stdout="", stderr="builder failed")

        def _exists_side_effect(path):
            path_str = str(path)
            if path_str.endswith("monsters/cultist.json"):
                return False
            return True

        with (
            patch(
                "utils.module_monster_authority.build_module_monster_authority",
                return_value=authority,
            ),
            patch(
                "utils.module_monster_authority.find_reusable_monster_path",
                return_value=None,
            ),
            patch(
                "utils.module_monster_authority.os.path.exists",
                side_effect=_exists_side_effect,
            ),
            patch(
                "utils.module_monster_authority.subprocess.run",
                side_effect=_record_builder,
            ),
        ):
            result = materialize_authorized_monster_file(
                "Night_of_the_Restless_Dead",
                "Cultist Leader",
                "core/generators/monster_builder.py",
                compendium_lookup={},
                allow_generation=True,
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_class"], "authorized_monster_hydration_failed")
        self.assertEqual(result.get("canonical_slug"), "cultist")
        self.assertEqual(builder_calls[0][2], "Cultist")

    def test_authorized_hydration_passes_authored_context_file(self):
        captured_context = {}

        def _exists_side_effect(path):
            path_str = str(path)
            if path_str.endswith("monsters/cultist.json"):
                return False
            return True

        def _record_builder(args, capture_output, text):
            self.assertIn("--context-file", args)
            context_index = args.index("--context-file") + 1
            context_path = args[context_index]
            self.assertTrue(os.path.exists(context_path))
            with open(context_path, "r", encoding="utf-8") as handle:
                captured_context.update(json.load(handle))
            return SimpleNamespace(returncode=1, stdout="", stderr="builder failed")

        with (
            patch(
                "utils.module_monster_authority.find_reusable_monster_path",
                return_value=None,
            ),
            patch(
                "utils.module_monster_authority.os.path.exists",
                side_effect=_exists_side_effect,
            ),
            patch(
                "utils.module_monster_authority.subprocess.run",
                side_effect=_record_builder,
            ),
        ):
            result = materialize_authorized_monster_file(
                "Night_of_the_Restless_Dead",
                "Cultist",
                "core/generators/monster_builder.py",
                compendium_lookup={},
                allow_generation=True,
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_class"], "authorized_monster_hydration_failed")
        self.assertEqual(captured_context.get("module"), "Night_of_the_Restless_Dead")
        self.assertIn("requested_name", captured_context)
        self.assertIn("monster_name", captured_context)
        self.assertIn("monster_slug", captured_context)

    def test_structured_monster_not_filtered_by_npc_overlap(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as temp_dir:
            module_dir = Path(temp_dir) / "Overlap_Module"
            areas_dir = module_dir / "areas"
            areas_dir.mkdir(parents=True, exist_ok=True)

            (module_dir / "module_context.json").write_text(
                json.dumps(
                    {
                        "npcs": {
                            "echoes_of_the_party": {
                                "name": "Echoes of the Party"
                            }
                        }
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            (areas_dir / "TMS001.json").write_text(
                json.dumps(
                    {
                        "areaId": "TMS001",
                        "locations": [
                            {
                                "locationId": "G04",
                                "monsters": [
                                    {
                                        "name": "Echoes of the Party",
                                        "type": "Aberration",
                                    }
                                ],
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            with patch(
                "utils.module_monster_authority.ModulePathManager"
            ) as mock_manager:
                manager_instance = mock_manager.return_value
                manager_instance.module_dir = str(module_dir)
                manager_instance.get_area_ids.return_value = ["TMS001"]
                manager_instance.get_area_path.side_effect = lambda area_id: str(
                    areas_dir / f"{area_id}.json"
                )

                authority = build_module_monster_authority("Overlap_Module")

            self.assertIn("echoes_of_the_party", authority)
            sources = authority["echoes_of_the_party"].get("sources") or []
            self.assertTrue(
                any(source.get("type") == "authored_structured_monster" for source in sources)
            )


class TestCanonicalMonsterReferenceResolution(unittest.TestCase):
    def test_exact_match_stays_exact(self):
        authority = {
            "cultist": {
                "sources": [{"type": "authored_area_content", "name": "Cultist"}]
            },
        }
        with patch(
            "utils.module_monster_authority.build_module_monster_authority",
            return_value=authority,
        ):
            result = resolve_authorized_monster_reference(
                "Night_of_the_Restless_Dead", "Cultist"
            )

        self.assertTrue(result["authorized"])
        self.assertEqual(result["resolution_mode"], "exact")
        self.assertEqual(result["canonical_slug"], "cultist")

    def test_canonicalizable_flavor_resolves_unique_base(self):
        authority = {
            "cultist": {
                "sources": [{"type": "authored_area_content", "name": "Cultist"}]
            },
            "skeleton": {
                "sources": [{"type": "authored_area_content", "name": "Skeleton"}]
            },
        }
        with patch(
            "utils.module_monster_authority.build_module_monster_authority",
            return_value=authority,
        ):
            result = resolve_authorized_monster_reference(
                "Night_of_the_Restless_Dead", "Cultist Leader"
            )

        self.assertTrue(result["authorized"])
        self.assertEqual(result["resolution_mode"], "subset_unique")
        self.assertEqual(result["canonical_slug"], "cultist")

    def test_adjective_flavor_resolves_without_modifier_collision(self):
        authority = {
            "cultist": {
                "sources": [{"type": "authored_area_content", "name": "Cultist"}]
            },
            "red": {"sources": [{"type": "authored_area_content", "name": "Red"}]},
        }
        with patch(
            "utils.module_monster_authority.build_module_monster_authority",
            return_value=authority,
        ):
            result = resolve_authorized_monster_reference(
                "Night_of_the_Restless_Dead", "Red-Cloaked Cultist"
            )

        self.assertTrue(result["authorized"])
        self.assertEqual(result["resolution_mode"], "subset_unique")
        self.assertEqual(result["canonical_slug"], "cultist")

    def test_exact_stronger_variant_remains_exact(self):
        authority = {
            "bandit": {
                "sources": [{"type": "authored_area_content", "name": "Bandit"}]
            },
            "bandit_captain": {
                "sources": [{"type": "authored_area_content", "name": "Bandit Captain"}]
            },
        }
        with patch(
            "utils.module_monster_authority.build_module_monster_authority",
            return_value=authority,
        ):
            result = resolve_authorized_monster_reference(
                "Night_of_the_Restless_Dead", "Bandit Captain"
            )

        self.assertTrue(result["authorized"])
        self.assertEqual(result["resolution_mode"], "exact")
        self.assertEqual(result["canonical_slug"], "bandit_captain")

    def test_ambiguous_label_fails_closed(self):
        authority = {
            "skeleton": {
                "sources": [{"type": "authored_area_content", "name": "Skeleton"}]
            },
            "guard": {"sources": [{"type": "authored_area_content", "name": "Guard"}]},
        }
        with patch(
            "utils.module_monster_authority.build_module_monster_authority",
            return_value=authority,
        ):
            result = resolve_authorized_monster_reference(
                "Night_of_the_Restless_Dead", "Skeleton Guard"
            )

        self.assertFalse(result["authorized"])
        self.assertEqual(result["resolution_mode"], "ambiguous")
        self.assertEqual(result["reason"], "ambiguous_candidates")
        self.assertEqual(sorted(result["candidates"]), ["guard", "skeleton"])

    def test_nonsense_label_fails_closed(self):
        authority = {
            "cultist": {
                "sources": [{"type": "authored_area_content", "name": "Cultist"}]
            },
        }
        with patch(
            "utils.module_monster_authority.build_module_monster_authority",
            return_value=authority,
        ):
            result = resolve_authorized_monster_reference(
                "Night_of_the_Restless_Dead",
                "Abyssal Grave-Priest of the Hollow Sun",
            )

        self.assertFalse(result["authorized"])
        self.assertEqual(result["resolution_mode"], "unauthorized")
        self.assertEqual(result["reason"], "no_canonical_match")


class TestCombatBuilderSourceContracts(unittest.TestCase):
    def test_combat_builder_uses_authorized_materialization_helper(self):
        file_path = os.path.join(
            PROJECT_ROOT, "core", "generators", "combat_builder.py"
        )
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        self.assertIn(
            "from utils.module_monster_authority import materialize_authorized_monster_file",
            source,
        )
        self.assertIn(
            "resolution_result = materialize_authorized_monster_file(", source
        )
        self.assertIn('error_class = resolution_result.get("error_class"', source)
        self.assertIn('error_message = resolution_result.get("error_message"', source)
        self.assertIn(
            'display_name = str(monster_resolution.get("display_name")', source
        )
        self.assertIn('"monsterType": canonical_monster_type', source)

    def test_action_handler_surfaces_new_monster_failure_classes(self):
        file_path = os.path.join(PROJECT_ROOT, "core", "ai", "action_handler.py")
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        self.assertIn("unauthorized_monster_reference", source)
        self.assertIn("authorized_monster_hydration_failed", source)
        self.assertIn("authored module content", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
