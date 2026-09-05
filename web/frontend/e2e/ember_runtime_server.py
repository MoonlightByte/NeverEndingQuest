"""Run the existing real-Flask parity harness in a disposable tracked export.

No private configuration, user settings, saves or OS credentials are copied.
This verifies real routes/hydration, not model inference: the underlying harness
replaces paid/destructive actions and provider persistence with test responses.
The export is retained for inspection; its path is printed at startup.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import types


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=4205)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[3]
    dist = repo / "web/frontend/dist"
    if not (dist / "index.html").is_file():
        parser.error("Build the public frontend first with npm run build")
    root = Path(tempfile.mkdtemp(prefix="neq-ember-runtime-"))
    export = root / "source"
    export.mkdir()
    # Only committed public files, never ignored settings/configuration. Archive
    # extraction has an explicit fresh destination, not a user-supplied target.
    archive = subprocess.Popen(["git", "archive", "HEAD"], cwd=repo, stdout=subprocess.PIPE)
    try:
        subprocess.run(["tar", "-x", "-C", str(export)], stdin=archive.stdout, check=True)
    finally:
        archive.stdout.close()
    if archive.wait() != 0:
        raise RuntimeError("Public tracked export failed")
    shutil.copytree(dist, export / "web/frontend/dist")
    shutil.copy2(export / "config_template.py", export / "config.py")

    # Disable inherited credentials and credential-store access BEFORE any game
    # module import. No secret values are inspected or printed.
    for name in tuple(os.environ):
        if any(part in name.upper() for part in ("API_KEY", "TOKEN", "SECRET", "CREDENTIAL", "PROXY")):
            os.environ.pop(name, None)
    secrets = types.ModuleType("utils.secret_store")
    secrets.get_secret = lambda name: None
    secrets.set_secret = lambda name, value: False
    secrets.delete_secret = lambda name: False
    sys.modules["utils.secret_store"] = secrets

    # Prevent model, telemetry and endpoint requests, including requests to a
    # developer's other localhost services. Inbound browser traffic is allowed.
    def network_guard(event: str, event_args: tuple) -> None:
        if event == "socket.connect":
            address = event_args[1]
            if not (isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"} and address[1] == args.port):
                raise PermissionError("Outbound networking disabled in Ember runtime fixture")
        elif event == "socket.getaddrinfo":
            if event_args[0] not in {"127.0.0.1", "::1", "localhost", None}:
                raise PermissionError("External DNS disabled in Ember runtime fixture")

    sys.addaudithook(network_guard)
    print(f"Isolated public runtime export: {root}", flush=True)
    print("Provider inference/persistence and destructive actions are fixture doubles.", flush=True)
    os.chdir(export)
    sys.path.insert(0, str(export))
    # Nonexistent child: the original harness's reset cannot target a checkout.
    sys.argv = ["react_parity_server.py", "--port", str(args.port), "--fixture-dir", str(root / "campaign")]
    runpy.run_path(str(export / "tests/react_parity_server.py"), run_name="__main__")


if __name__ == "__main__":
    main()
