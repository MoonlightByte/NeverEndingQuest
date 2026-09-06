"""Real public action handlers + save/restore/delete/reset in a disposable campaign.

No engine is started. Process exit and the one-second restart delay are the only
lifecycle-operation intercepts; the actual Flask-SocketIO handlers, save manager, reset logic, JSON
files and backups run. Network and writes outside the fresh export are blocked.
Credential-store access is stubbed so no developer credentials are available.
All deleted files are synthetic test data; reset/restore backups are retained.
"""
from __future__ import annotations

import argparse
from collections import deque
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import types
from unittest.mock import patch


def worker(export: Path) -> None:
    export = export.resolve()
    root = export.parent
    assert export.name == "source" and root.name.startswith("neq-ember-lifecycle-")
    assert not (export / ".git").exists()
    assert (root / "lifecycle-probe.json").is_file()
    manifest = json.loads((root / "lifecycle-probe.json").read_text())
    assert manifest["export"] == str(export)
    save_mode = manifest["save_mode"]
    assert save_mode in {"essential", "full"}
    sys.dont_write_bytecode = True
    for name in tuple(os.environ):
        if any(part in name.upper() for part in ("API_KEY", "TOKEN", "SECRET", "CREDENTIAL", "PROXY")):
            os.environ.pop(name, None)
    secrets = types.ModuleType("utils.secret_store")
    secrets.get_secret = lambda name: None
    secrets.set_secret = lambda name, value: False
    secrets.delete_secret = lambda name: False
    sys.modules["utils.secret_store"] = secrets

    def check_write(target) -> None:
        if isinstance(target, int):
            return
        path = Path(os.fsdecode(target)).resolve()
        if path == Path(os.devnull):
            return
        if not path.is_relative_to(root) or path == root:
            raise PermissionError(f"Lifecycle probe write outside disposable child: {path}")

    def guard(event, args):
        if event in {"socket.connect", "socket.getaddrinfo"}:
            raise PermissionError("No outbound networking in lifecycle probe")
        if event == "open":
            mode = args[1] or ""
            flags = args[2] or 0
            if any(char in mode for char in "wa+") or flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
                check_write(args[0])
        elif event in {"os.remove", "os.rmdir", "os.mkdir", "shutil.rmtree"}:
            check_write(args[0])
        elif event == "os.rename":
            check_write(args[0])
            check_write(args[1])

    sys.addaudithook(guard)
    os.chdir(export)
    sys.path.insert(0, str(export))
    shutil.copy2(export / "config_template.py", export / "config.py")
    fixture = runpy.run_path(str(export / "tests/react_parity_server.py"), run_name="ember_lifecycle_data")
    campaign = root / "campaign"
    campaign.mkdir()
    fixture["make_fixture"](campaign)
    os.chdir(campaign)
    from web import web_interface as web
    from core.managers.status_manager import status_manager
    from updates.save_game_manager import SaveGameManager

    assert web.game_thread is None
    status_manager.set_ready()
    web.message_cache = deque(fixture["baseline_messages"](), maxlen=web.MESSAGE_CACHE_SIZE)
    client = web.socketio.test_client(web.app)
    exits = []

    def action(name, **parameters):
        client.get_received()
        client.emit("action", {"action": name, "parameters": parameters})
        return client.get_received()

    def payload(packets, event):
        matches = [packet["args"][0] for packet in packets if packet["name"] == event]
        assert matches, (event, packets)
        return matches[-1]

    def snapshot(path):
        return json.loads(path.read_text(encoding="utf-8"))

    manager = SaveGameManager()
    save_dir = campaign / manager.get_save_directory()
    player = campaign / "characters/arden_vale.json"
    original_player = snapshot(player)
    original_tracker = snapshot(campaign / "party_tracker.json")
    results = {}
    try:
        # A busy non-player operation must not create a save or destroy state.
        status_manager.update_status("Synthetic non-turn work", True)
        before_saves = sorted(path.name for path in save_dir.iterdir())
        packets = action("saveGame", description="Must not save", saveMode="essential")
        assert "Please retry" in payload(packets, "error")["message"]
        assert sorted(path.name for path in save_dir.iterdir()) == before_saves
        status_manager.set_ready()
        results["busy_save_rejected_without_new_save_entry"] = True

        packets = action("saveGame", description="Ember real persistence probe", saveMode=save_mode)
        assert payload(packets, "system_message")["content"].startswith("Game saved:")
        saves = payload(action("listSaves"), "save_list_response")
        selected = next(save for save in saves if save["description"] == "Ember real persistence probe")
        folder = selected["save_folder"]
        assert folder.startswith("save_") and Path(folder).name == folder
        saved = save_dir / folder
        assert saved.is_relative_to(campaign) and saved.is_dir()
        assert snapshot(saved / "characters/arden_vale.json") == original_player
        assert snapshot(saved / "party_tracker.json") == original_tracker
        assert snapshot(saved / "save_metadata.json")["save_mode"] == save_mode
        results["save_list_and_actual_files"] = True

        changed = {**original_player, "hitPoints": 7}
        player.write_text(json.dumps(changed), encoding="utf-8")
        # Invalid/missing metadata is rejected without touching current data.
        corrupt = save_dir / "save_ember_corrupt_fixture"
        corrupt.mkdir()
        (corrupt / "save_metadata.json").write_text("not JSON", encoding="utf-8")
        with patch.object(web.os, "_exit", side_effect=lambda code: exits.append(code)), patch.object(web.socketio, "sleep", return_value=None):
            packets = action("restoreGame", saveFolder=corrupt.name)
            assert payload(packets, "error")["message"].startswith("Restore failed:")
            assert snapshot(player) == changed and exits == []
            packets = action("restoreGame", saveFolder=folder)
            assert "Game restored successfully" in payload(packets, "restore_complete")["message"]
            assert snapshot(player) == original_player
            assert snapshot(campaign / "party_tracker.json") == original_tracker
            assert exits == [0]
        assert list((campaign / "modules/backups").glob("restore_backup_*"))
        results["corrupt_restore_rejected_and_real_restore_backed_up"] = True

        # Reconnect and list through actual Socket.IO, not fixture canned lists.
        client.disconnect()
        client.connect()
        listed = payload(action("listSaves"), "save_list_response")
        assert any(save["save_folder"] == folder for save in listed)
        packets = action("deleteSave", saveFolder=folder)
        assert payload(packets, "system_message")["content"].startswith("Save deleted:")
        assert not saved.exists()
        packets = action("deleteSave", saveFolder=folder)
        assert payload(packets, "error")["message"].startswith("Delete failed:")
        results["reconnect_list_delete_and_missing_delete_error"] = True

        # Nuclear reset is confined to this synthetic campaign by the audit
        # guard. Production reset creates its own recoverable backup first.
        with patch.object(web.os, "_exit", side_effect=lambda code: exits.append(code)), patch.object(web.socketio, "sleep", return_value=None):
            packets = action("nuclearReset")
        assert "Campaign has been reset" in payload(packets, "reset_complete")["message"]
        assert snapshot(campaign / "party_tracker.json") == {}
        assert not player.exists()
        assert not (campaign / "player_storage.json").exists()
        backups = list((campaign / "modules/backups").glob("campaign_backup_*"))
        assert backups and any((backup / "characters/arden_vale.json").is_file() for backup in backups)
        assert len(web.message_cache) == 0 and exits == [0, 0]
        assert web.game_thread is None
        results["actual_reset_and_retained_backup"] = True
    finally:
        if client.is_connected():
            client.disconnect()
    report = {"source_head": manifest["head"], "export": str(export), "campaign": str(campaign), "save_mode": save_mode,
              "checks": results, "network": "blocked", "engine_jobs": 0,
              "lifecycle_intercepts": ["process exit", "restart sleep"],
              "credential_store": "stubbed",
              "limits": ["No browser clicks", "No live engine/provider/interview", "No active-turn save queue", "No recovery from reset backup"],
              "retained_backups": True}
    (root / "lifecycle-result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("LIFECYCLE_PROBE_RESULT " + json.dumps(report), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--temp-parent", type=Path, required=False)
    parser.add_argument("--save-mode", choices=["essential", "full"], default="essential")
    args = parser.parse_args()
    if args.worker:
        worker(args.worker)
        return
    repo = Path(__file__).resolve().parents[3]
    root = Path(tempfile.mkdtemp(prefix="neq-ember-lifecycle-", dir=args.temp_parent))
    export = root / "source"
    export.mkdir()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    print(f"Disposable lifecycle export: {export} (HEAD {head})", flush=True)
    archive = subprocess.Popen(["git", "archive", head], cwd=repo, stdout=subprocess.PIPE)
    try:
        subprocess.run(["tar", "-x", "-C", str(export)], stdin=archive.stdout, check=True)
    finally:
        archive.stdout.close()
    if archive.wait() != 0:
        raise RuntimeError("Tracked public export failed")
    (root / "lifecycle-probe.json").write_text(json.dumps({"head": head, "export": str(export), "save_mode": args.save_mode}), encoding="utf-8")
    subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", str(export)], cwd=export, check=True)


if __name__ == "__main__":
    main()
