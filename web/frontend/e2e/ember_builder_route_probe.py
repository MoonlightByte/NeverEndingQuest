"""Read-only standalone Flask route probe in an existing disposable export.

Use the source directory created by ember_runtime_server.py, never a game
checkout. No builder job is started and all outbound networking is prohibited.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import runpy
import sys
import types


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-root", required=True, type=Path)
    args = parser.parse_args()
    export = args.export_root.resolve()
    if export.name != "source" or not export.parent.name.startswith("neq-ember-runtime-") or (export / ".git").exists():
        parser.error("Use a disposable ember_runtime_server.py source export")
    for name in tuple(os.environ):
        if any(part in name.upper() for part in ("API_KEY", "TOKEN", "SECRET", "CREDENTIAL", "PROXY")):
            os.environ.pop(name, None)
    secrets = types.ModuleType("utils.secret_store")
    secrets.get_secret = lambda name: None
    secrets.set_secret = lambda name, value: False
    secrets.delete_secret = lambda name: False
    sys.modules["utils.secret_store"] = secrets

    def deny_network(event: str, _args: tuple) -> None:
        if event in {"socket.connect", "socket.getaddrinfo"}:
            raise PermissionError("Outbound networking disabled in standalone route probe")

    sys.addaudithook(deny_network)
    os.chdir(export)
    sys.path.insert(0, str(export))
    namespace = runpy.run_path(str(export / "module_builder_web.py"), run_name="ember_route_probe")
    client = namespace["app"].test_client()
    html = client.get("/")
    assert html.status_code == 200
    assert b"ember-builder" in html.data and b"/static/css/ember-toolkit.css" in html.data
    paths = ["/static/css/ember-toolkit.css", "/static/css/ember-tokens.css", "/static/css/ember-fonts.css"]
    paths += [f"/static/fonts/ember/{font.name}" for font in (export / "web/static/fonts/ember").glob("*.woff2")]
    for route in paths:
        response = client.get(route)
        assert response.status_code == 200 and response.data, route
    print(json.dumps({"standalone_route": "/", "status": html.status_code, "assets_verified": len(paths), "jobs_started": 0}))


if __name__ == "__main__":
    main()
