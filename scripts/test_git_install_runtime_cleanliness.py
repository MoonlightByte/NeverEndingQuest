#!/usr/bin/env python3
"""Step 5.2 fresh-clone runtime cleanliness smoke verification."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Dict, List, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class _FakeResponse:
    """Simple fake OpenAI chat response payload."""

    def __init__(self, content: str):
        self.choices = [type("Choice", (), {"message": type("Msg", (), {"content": content})()})()]


class _FakeClient:
    """Simple fake client with chat.completions.create API."""

    def __init__(self, content: str):
        self._content = content
        self.chat = type("Chat", (), {})()
        self.chat.completions = type("Completions", (), {})()
        self.chat.completions.create = self._create

    def _create(self, **kwargs):
        _ = kwargs
        return _FakeResponse(self._content)


class TestGitInstallRuntimeCleanliness(unittest.TestCase):
    """Deterministic smoke pass for runtime-state cleanliness contract."""

    OVERLAY_FILES = [
        ".gitignore",
        "utils/runtime_hydration.py",
        "utils/startup_wizard.py",
        "utils/quest_player_formatter.py",
        "web/extensions/tabletop_socket_handlers.py",
        "modules/Night_of_the_Restless_Dead/areas/NIG001_BU.json",
        "modules/Night_of_the_Restless_Dead/module_plot_BU.json",
    ]

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="git_clean_smoke_"))
        self.worktree_path = self.temp_dir / "worktree"

        self._run_git([
            "worktree",
            "add",
            "--detach",
            str(self.worktree_path),
            "HEAD",
        ], cwd=PROJECT_ROOT)

        self._overlay_current_change_files()
        self._write_minimal_config()
        self._align_step_4_tracking_boundary()

    def tearDown(self):
        try:
            self._run_git(["worktree", "remove", "--force", str(self.worktree_path)], cwd=PROJECT_ROOT)
        except Exception:
            pass
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _run_git(self, args: List[str], cwd: Path) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout

    def _run_python(self, script: str) -> str:
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=str(self.worktree_path),
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout

    def _overlay_current_change_files(self):
        for rel_path in self.OVERLAY_FILES:
            src = PROJECT_ROOT / rel_path
            if not src.exists():
                continue
            dst = self.worktree_path / rel_path
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    def _write_minimal_config(self):
        config_py = self.worktree_path / "config.py"
        config_py.write_text(
            "\n".join(
                [
                    "OPENAI_API_KEY = 'test-key'",
                    "PLOT_UPDATE_MODEL = 'gpt-4o-mini'",
                    "NPC_INFO_UPDATE_MODEL = 'gpt-4o-mini'",
                    "MULTIPLAYER_MODE = True",
                    "DM_MAIN_MODEL = 'gpt-4o-mini'",
                    "DM_VALIDATION_MODEL = 'gpt-4o-mini'",
                    "DM_MINI_MODEL = 'gpt-4o-mini'",
                    "DM_SUMMARIZATION_MODEL = 'gpt-4o-mini'",
                    "COMBAT_MAIN_MODEL = 'gpt-4o-mini'",
                    "ENCOUNTER_UPDATE_MODEL = 'gpt-4o-mini'",
                    "OPENROUTER_API_KEY = ''",
                    "OPENROUTER_HTTP_REFERER = ''",
                    "OPENROUTER_APP_TITLE = ''",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    def _align_step_4_tracking_boundary(self):
        ls_out = self._run_git(
            [
                "ls-files",
                "modules/*/areas/*.json",
                "modules/*/module_plot.json",
                "modules/*/player_quests_*.json",
            ],
            cwd=self.worktree_path,
        )
        targets = [line for line in ls_out.splitlines() if line and not line.endswith("_BU.json")]
        if targets:
            self._run_git(["rm", "--cached", "-f", "--", *targets], cwd=self.worktree_path)

        night_bu_area = "modules/Night_of_the_Restless_Dead/areas/NIG001_BU.json"
        night_bu_plot = "modules/Night_of_the_Restless_Dead/module_plot_BU.json"
        if (self.worktree_path / night_bu_area).exists() and (self.worktree_path / night_bu_plot).exists():
            self._run_git(["add", "--", night_bu_area, night_bu_plot, ".gitignore"], cwd=self.worktree_path)

    def _tracked_status_lines(self) -> List[str]:
        out = self._run_git(["status", "--short"], cwd=self.worktree_path)
        return sorted([line for line in out.splitlines() if line and not line.startswith("??")])

    def _find_reconcile_target(self, module_name: str) -> Tuple[str, str]:
        module_dir = self.worktree_path / "modules" / module_name / "areas"
        area_files = sorted(
            [path for path in module_dir.glob("*.json") if not path.name.endswith("_BU.json")],
            key=lambda path: path.name,
        )

        for area_file in area_files:
            data = json.loads(area_file.read_text(encoding="utf-8"))
            area_id = data.get("areaId", area_file.stem)
            for location in data.get("locations", []):
                location_id = location.get("locationId")
                monsters = location.get("monsters", [])
                if location_id and monsters:
                    return area_id, location_id

        if area_files:
            area_file = area_files[0]
            data = json.loads(area_file.read_text(encoding="utf-8"))
            area_id = data.get("areaId", area_file.stem)
            locations = data.get("locations", [])
            if locations:
                location = locations[0]
                location_id = location.get("locationId", "AUTO001")
                location["locationId"] = location_id
                location["monsters"] = [{"name": "Smoke Goblin", "hp": 7}]
                area_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
                return area_id, location_id

        raise AssertionError("Could not locate or synthesize reconciliation target")

    def test_fresh_clone_runtime_smoke_does_not_dirty_tracked_tree(self):
        baseline_tracked = self._tracked_status_lines()

        module_name = "Keep_of_Doom"
        module_dir = self.worktree_path / "modules" / module_name
        area_live = module_dir / "areas" / "G001.json"
        plot_live = module_dir / "module_plot.json"
        player_quests = module_dir / f"player_quests_{module_name}.json"

        for path in [area_live, plot_live, player_quests]:
            if path.exists():
                path.unlink()

        script = r'''
import json
import os
import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))

from utils.runtime_hydration import hydrate_missing_live_area_files_from_bu, hydrate_missing_module_plot_files_from_bu
from utils.quest_player_formatter import ensure_player_quests_file
from web.extensions.tabletop_socket_handlers import handle_plot_data_request_impl
import updates.plot_update as plot_update
import utils.reconcile_location_state as reconcile
import utils.quest_player_formatter as qpf

module_name = "Keep_of_Doom"
module_dir = ROOT / "modules" / module_name

party_tracker = {
    "module": module_name,
    "partyMembers": ["Smoke Hero"],
    "active_character": "Smoke Hero",
    "worldConditions": {},
}
(ROOT / "party_tracker.json").write_text(json.dumps(party_tracker, indent=2), encoding="utf-8")

area_result = hydrate_missing_live_area_files_from_bu("modules")
plot_result = hydrate_missing_module_plot_files_from_bu("modules")
assert area_result["restored"] >= 1, area_result
assert plot_result["restored"] >= 1, plot_result

plot_data = json.loads((module_dir / "module_plot.json").read_text(encoding="utf-8"))
plot_point_id = None
for point in plot_data.get("plotPoints", []):
    if point.get("id"):
        plot_point_id = point.get("id")
        break
assert plot_point_id is not None

class _FakeResponse:
    def __init__(self, content):
        self.choices = [type("Choice", (), {"message": type("Msg", (), {"content": content})()})()]

class _FakeClient:
    def __init__(self, content):
        self._content = content
        self.chat = type("Chat", (), {})()
        self.chat.completions = type("Completions", (), {})()
        self.chat.completions.create = self._create

    def _create(self, **kwargs):
        _ = kwargs
        return _FakeResponse(self._content)

qpf.format_quests_for_player = lambda module: True
plot_payload = json.dumps({plot_point_id: {"status": "in progress", "plotImpact": "Smoke advancement"}})
plot_update.client = _FakeClient(plot_payload)
updated = plot_update.update_plot(plot_point_id, "in progress", "Smoke advancement", "module_plot.json", max_retries=1)
assert updated is not None

# Build reconciliation target dynamically.
area_id = None
location_id = None
for area_file in sorted((module_dir / "areas").glob("*.json")):
    if area_file.name.endswith("_BU.json"):
        continue
    data = json.loads(area_file.read_text(encoding="utf-8"))
    aid = data.get("areaId", area_file.stem)
    for location in data.get("locations", []):
        monsters = location.get("monsters", [])
        lid = location.get("locationId")
        if lid and monsters:
            area_id = aid
            location_id = lid
            break
    if area_id and location_id:
        break

if not (area_id and location_id):
    # Synthesize minimal monsters on first area location.
    area_files = [f for f in sorted((module_dir / "areas").glob("*.json")) if not f.name.endswith("_BU.json")]
    assert area_files
    first_area = area_files[0]
    data = json.loads(first_area.read_text(encoding="utf-8"))
    area_id = data.get("areaId", first_area.stem)
    locations = data.get("locations", [])
    assert locations
    if not locations[0].get("locationId"):
        locations[0]["locationId"] = "AUTO001"
    locations[0]["monsters"] = [{"name": "Smoke Goblin", "hp": 7}]
    first_area.write_text(json.dumps(data, indent=2), encoding="utf-8")
    location_id = locations[0]["locationId"]

reconcile.client = _FakeClient("[]")
reconcile.run(area_id, location_id, [{"role": "assistant", "content": "The monsters are defeated."}])

regen_result = ensure_player_quests_file(module_name)
assert regen_result.get("status") in {"exists", "regenerated"}, regen_result

emits = []
def emit_fn(event, payload):
    emits.append((event, payload))
def debug_fn(message, category=None):
    _ = (message, category)

handle_plot_data_request_impl(emit_fn, debug_fn)
plot_payload_out = None
for event, payload in reversed(emits):
    if event == "plot_data_response":
        plot_payload_out = payload
        break

assert plot_payload_out is not None
assert plot_payload_out.get("error") is None
assert len(plot_payload_out.get("data", {}).get("plotPoints", [])) >= 1
print("SMOKE_OK")
'''

        out = self._run_python(script)
        self.assertIn("SMOKE_OK", out)

        after_tracked = self._tracked_status_lines()
        self.assertEqual(
            baseline_tracked,
            after_tracked,
            "Runtime smoke introduced tracked-tree drift beyond baseline",
        )


if __name__ == "__main__":
    unittest.main()
