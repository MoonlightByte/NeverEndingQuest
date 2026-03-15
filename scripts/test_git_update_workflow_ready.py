#!/usr/bin/env python3
"""Step 5.3 Git update-workflow readiness verification."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import List


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


class TestGitUpdateWorkflowReady(unittest.TestCase):
    """Verifies ff-only update remains available after runtime gameplay mutations."""

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
        self.temp_dir = Path(tempfile.mkdtemp(prefix="git_update_ready_"))
        self.remote_bare = self.temp_dir / "remote.git"
        self.seed_clone = self.temp_dir / "seed"
        self.gameplay_clone = self.temp_dir / "gameplay"
        self.upstream_clone = self.temp_dir / "upstream"

        self._run(["git", "init", "--bare", str(self.remote_bare)], cwd=self.temp_dir)
        self._run(["git", "clone", "--no-hardlinks", str(PROJECT_ROOT), str(self.seed_clone)], cwd=self.temp_dir)

        self._configure_git_identity(self.seed_clone)
        self._run(["git", "remote", "set-url", "origin", str(self.remote_bare)], cwd=self.seed_clone)

        self._overlay_current_change_files(self.seed_clone)
        self._align_step_4_tracking_boundary(self.seed_clone)
        self._commit_if_needed(self.seed_clone, "chore: seed runtime-state boundary")

        self._run(["git", "push", "origin", "HEAD:main"], cwd=self.seed_clone)
        self._run([
            "git",
            "--git-dir",
            str(self.remote_bare),
            "symbolic-ref",
            "HEAD",
            "refs/heads/main",
        ], cwd=self.temp_dir)

        self._run(["git", "clone", str(self.remote_bare), str(self.gameplay_clone)], cwd=self.temp_dir)
        self._run(["git", "clone", str(self.remote_bare), str(self.upstream_clone)], cwd=self.temp_dir)
        self._configure_git_identity(self.upstream_clone)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _run(self, cmd: List[str], cwd: Path) -> str:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    def _configure_git_identity(self, repo: Path):
        self._run(["git", "config", "user.name", "NEQ Smoke"], cwd=repo)
        self._run(["git", "config", "user.email", "neq-smoke@example.com"], cwd=repo)

    def _overlay_current_change_files(self, target_repo: Path):
        for rel_path in self.OVERLAY_FILES:
            src = PROJECT_ROOT / rel_path
            if not src.exists():
                continue
            dst = target_repo / rel_path
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    def _align_step_4_tracking_boundary(self, repo: Path):
        ls_out = self._run(
            [
                "git",
                "ls-files",
                "modules/*/areas/*.json",
                "modules/*/module_plot.json",
                "modules/*/player_quests_*.json",
            ],
            cwd=repo,
        )
        targets = [line for line in ls_out.splitlines() if line and not line.endswith("_BU.json")]
        if targets:
            self._run(["git", "rm", "--cached", "-f", "--", *targets], cwd=repo)

        self._run(
            [
                "git",
                "add",
                "--",
                ".gitignore",
                "utils/runtime_hydration.py",
                "utils/startup_wizard.py",
                "utils/quest_player_formatter.py",
                "web/extensions/tabletop_socket_handlers.py",
                "modules/Night_of_the_Restless_Dead/areas/NIG001_BU.json",
                "modules/Night_of_the_Restless_Dead/module_plot_BU.json",
            ],
            cwd=repo,
        )

    def _commit_if_needed(self, repo: Path, message: str):
        status = self._run(["git", "status", "--porcelain"], cwd=repo)
        if status:
            self._run(["git", "commit", "-m", message], cwd=repo)

    def _write_minimal_config(self, repo: Path):
        config_py = repo / "config.py"
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

    def _tracked_status_lines(self, repo: Path) -> List[str]:
        out = self._run(["git", "status", "--short"], cwd=repo)
        return sorted([line for line in out.splitlines() if line and not line.startswith("??")])

    def _run_runtime_operations(self, repo: Path):
        script = r'''
import json
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

for path in [
    module_dir / "areas" / "G001.json",
    module_dir / "module_plot.json",
    module_dir / f"player_quests_{module_name}.json",
]:
    if path.exists():
        path.unlink()

area_result = hydrate_missing_live_area_files_from_bu("modules")
plot_result = hydrate_missing_module_plot_files_from_bu("modules")
assert area_result["restored"] >= 1, area_result
assert plot_result["restored"] >= 1, plot_result

plot_data = json.loads((module_dir / "module_plot.json").read_text(encoding="utf-8"))
plot_point_id = next((p.get("id") for p in plot_data.get("plotPoints", []) if p.get("id")), None)
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
plot_payload = json.dumps({plot_point_id: {"status": "in progress", "plotImpact": "Update workflow smoke"}})
plot_update.client = _FakeClient(plot_payload)
updated = plot_update.update_plot(plot_point_id, "in progress", "Update workflow smoke", "module_plot.json", max_retries=1)
assert updated is not None

area_id = None
location_id = None
for area_file in sorted((module_dir / "areas").glob("*.json")):
    if area_file.name.endswith("_BU.json"):
        continue
    data = json.loads(area_file.read_text(encoding="utf-8"))
    aid = data.get("areaId", area_file.stem)
    for location in data.get("locations", []):
        lid = location.get("locationId")
        monsters = location.get("monsters", [])
        if lid and monsters:
            area_id = aid
            location_id = lid
            break
    if area_id and location_id:
        break

if not (area_id and location_id):
    area_files = [f for f in sorted((module_dir / "areas").glob("*.json")) if not f.name.endswith("_BU.json")]
    assert area_files
    first_area = area_files[0]
    data = json.loads(first_area.read_text(encoding="utf-8"))
    area_id = data.get("areaId", first_area.stem)
    locations = data.get("locations", [])
    assert locations
    location = locations[0]
    location["locationId"] = location.get("locationId", "AUTO001")
    location["monsters"] = [{"name": "Smoke Goblin", "hp": 7}]
    first_area.write_text(json.dumps(data, indent=2), encoding="utf-8")
    location_id = location["locationId"]

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
print("RUNTIME_OPS_OK")
'''
        out = self._run([sys.executable, "-c", script], cwd=repo)
        self.assertIn("RUNTIME_OPS_OK", out)

    def test_ff_only_update_available_after_runtime_operations(self):
        self._write_minimal_config(self.gameplay_clone)

        baseline_status = self._tracked_status_lines(self.gameplay_clone)
        self._run_runtime_operations(self.gameplay_clone)
        after_runtime_status = self._tracked_status_lines(self.gameplay_clone)

        self.assertEqual(
            baseline_status,
            after_runtime_status,
            "Runtime operations introduced tracked-state drift before update",
        )

        marker = self.upstream_clone / "SMOKE_UPSTREAM_MARKER.txt"
        marker.write_text("upstream fast-forward marker\n", encoding="utf-8")
        self._run(["git", "add", "SMOKE_UPSTREAM_MARKER.txt"], cwd=self.upstream_clone)
        self._run(["git", "commit", "-m", "chore: smoke upstream marker"], cwd=self.upstream_clone)
        self._run(["git", "push", "origin", "main"], cwd=self.upstream_clone)

        before_head = self._run(["git", "rev-parse", "HEAD"], cwd=self.gameplay_clone)
        self._run(["git", "pull", "--ff-only", "origin", "main"], cwd=self.gameplay_clone)
        after_head = self._run(["git", "rev-parse", "HEAD"], cwd=self.gameplay_clone)

        self.assertNotEqual(before_head, after_head, "Fast-forward update did not advance HEAD")


if __name__ == "__main__":
    unittest.main()
