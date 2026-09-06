"""Exercise actual public entry points only inside a fresh disposable export.

Run after ``npm run build`` with the game's Python environment. This exports
tracked HEAD (never ignored config/settings), copies compiled public assets,
overlays the current public launcher with a recorded SHA-256, and runs actual
Flask test clients without a server or engine. Missing-build
checks occur before installing the copied build in the export: no live dist is
renamed or deleted. The retained export and exact HEAD are printed as evidence.
This is route/launcher/static-asset coverage, not inference or browser rendering.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from html.parser import HTMLParser
import hashlib
import io
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import sys
import tempfile
import types
from unittest.mock import patch


class AssetLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.urls: list[str] = []

    def handle_starttag(self, tag, attrs) -> None:
        values = dict(attrs)
        if tag == "script" and values.get("src"):
            self.urls.append(values["src"])
        if tag == "link" and values.get("href"):
            self.urls.append(values["href"])


def check_build_freshness(export: Path, launcher) -> dict:
    """Change only disposable export mtimes; restore every one in finally."""
    frontend = export / "web/frontend"
    index = frontend / "dist/index.html"
    tokens = export / "web/static/css/ember-tokens.css"
    react_font = frontend / "src/theme/fonts/cinzel-latin.woff2"
    standalone_font = export / "web/static/fonts/ember/cinzel-latin.woff2"
    unrelated_image = export / "web/static/media/npcs/scout_elen.jpg"
    touched = [index, tokens, react_font, standalone_font, unrelated_image]
    original = {path: (path.stat().st_atime_ns, path.stat().st_mtime_ns) for path in touched}
    newest_input = max(path.stat().st_mtime_ns for path in frontend.rglob("*") if path.is_file())
    built_at = max(newest_input, *(stamp[1] for stamp in original.values())) + 60_000_000_000
    try:
        os.utime(index, ns=(built_at, built_at))
        assert launcher._react_build_is_current(frontend)
        for path, expected_current in ((tokens, False), (react_font, False), (standalone_font, True), (unrelated_image, True)):
            os.utime(path, ns=(built_at + 10_000_000_000, built_at + 10_000_000_000))
            assert launcher._react_build_is_current(frontend) is expected_current, f"Incorrect build freshness after changing {path.relative_to(export)}"
            os.utime(path, ns=original[path])
        return {"shared_tokens_mark_stale": True, "bundled_font_marks_stale": True,
                "standalone_font_ignored": True, "unrelated_static_image_ignored": True}
    finally:
        for path, timestamps in original.items():
            os.utime(path, ns=timestamps)


def worker(export: Path) -> None:
    export = export.resolve()
    marker = export.parent / "entrypoint-probe.json"
    if (export.name != "source" or not export.parent.name.startswith("neq-ember-entrypoints-")
            or not marker.is_file() or (export / ".git").exists()):
        raise RuntimeError("Worker requires this probe's disposable export")
    manifest = json.loads(marker.read_text())
    assert manifest["export"] == str(export)
    assert not (export / "web/frontend/dist").exists()
    sys.dont_write_bytecode = True
    for name in tuple(os.environ):
        if any(part in name.upper() for part in ("API_KEY", "TOKEN", "SECRET", "CREDENTIAL", "PROXY")):
            os.environ.pop(name, None)
    os.environ["NEQ_WEB_HOST"] = "127.0.0.1"
    secrets = types.ModuleType("utils.secret_store")
    secrets.get_secret = lambda name: None
    secrets.set_secret = lambda name, value: False
    secrets.delete_secret = lambda name: False
    sys.modules["utils.secret_store"] = secrets

    def deny_network(event: str, _args: tuple) -> None:
        if event in {"socket.connect", "socket.getaddrinfo"}:
            raise PermissionError("Outbound networking disabled in entry-point probe")

    sys.addaudithook(deny_network)
    os.chdir(export)
    sys.path.insert(0, str(export))
    shutil.copy2(export / "config_template.py", export / "config.py")
    import run_web

    assert run_web.parse_args([]).ui == "legacy"
    for option in ("legacy", "react", "choose"):
        assert run_web.parse_args(["--ui", option]).ui == option
    with redirect_stdout(io.StringIO()):
        assert not run_web.ensure_react_frontend(export, npm_command=None)
        failed_commands = []

        def failed_build(command, **kwargs):
            failed_commands.append(command)
            assert Path(kwargs["cwd"]).resolve() == export / "web/frontend"
            return types.SimpleNamespace(returncode=1)

        assert not run_web.ensure_react_frontend(export, npm_command="fixture-npm", runner=failed_build)
        assert failed_commands == [["fixture-npm", "ci"]]
        for option in ("legacy", "react", "choose"):
            assert run_web.select_ui(option, False) == "legacy"
        assert run_web.select_ui("react", True) == "react"
        assert run_web.select_ui("choose", True, input_fn=lambda _: "1") == "react"
        assert run_web.select_ui("choose", True, input_fn=lambda _: "2") == "legacy"

    # Exercise the actual main's NEQ_START_PATH selection without spawning its
    # web process. Return nonzero from the fake child to stop its restart loop.
    launches = []
    for requested, available, expected in (("legacy", False, "/"), ("react", False, "/"), ("react", True, "/play/")):
        calls = []

        def child(command, **kwargs):
            calls.append((command, kwargs["env"]["NEQ_START_PATH"]))
            return types.SimpleNamespace(returncode=1)

        with patch.object(run_web, "ensure_react_frontend", return_value=available) as ensure, patch.object(run_web.subprocess, "run", side_effect=child), redirect_stdout(io.StringIO()):
            run_web.main(requested)
        assert calls == [([sys.executable, "web/web_interface.py"], expected)]
        assert ensure.call_count == (0 if requested == "legacy" else 1)
        launches.append({"requested": requested, "build_available": available, "start_path": expected})

    # These are production imports/routes, not extracted or copied handlers.
    from web import web_interface
    client = web_interface.app.test_client()
    assert web_interface.game_thread is None
    legacy = client.get("/")
    assert legacy.status_code == 200 and b"NeverEndingQuest" in legacy.data
    missing = {}
    for route in ("/play", "/play/", "/play/assets/missing.js"):
        response = client.get(route)
        assert response.status_code == 503 and b"React frontend not built" in response.data
        missing[route] = response.status_code
    toolkit = client.get("/toolkit")
    assert toolkit.status_code == 200 and b"ember-toolkit" in toolkit.data

    static_paths = [f"/static/css/{name}" for name in ("ember-tokens.css", "ember-fonts.css", "ember-toolkit.css")]
    static_paths += [f"/static/js/{path.name}" for path in (export / "web/static/js").glob("ember-*.js")]
    static_paths += [f"/static/fonts/ember/{path.name}" for path in (export / "web/static/fonts/ember").glob("*.woff2")]
    assert len([path for path in static_paths if path.endswith(".woff2")]) == 11
    for route in static_paths:
        response = client.get(route)
        assert response.status_code == 200 and response.data, route
        assert response.data == (export / "web" / route.lstrip("/")).read_bytes(), route

    # Only this fresh export's copied build moves; no user/worktree path is a
    # mutation target. The missing-build assertions above needed no deletion.
    copied_build = export.parent / "prebuilt-public-dist"
    copied_build.rename(export / "web/frontend/dist")
    freshness = check_build_freshness(export, run_web)
    built = client.get("/play/")
    assert built.status_code == 200 and b'id="root"' in built.data
    assert b"__NEQ_VERSION__" not in built.data
    assert client.get("/play").data == built.data
    assert client.get("/play/unknown-client-route").data == built.data
    assert client.get("/").data == legacy.data
    assert client.get("/toolkit").status_code == 200
    links = AssetLinks()
    links.feed(built.get_data(as_text=True))
    assets = [url for url in links.urls if url.startswith("/play/")]
    assert any(url.endswith(".js") for url in assets)
    assert any(url.endswith(".css") for url in assets)
    bundled_fonts = set()
    for route in assets:
        response = client.get(route)
        assert response.status_code == 200 and response.data, route
        assert response.data == (export / "web/frontend/dist" / route.removeprefix("/play/")).read_bytes(), route
        if route.endswith(".css"):
            css = response.get_data(as_text=True)
            assert "fonts.googleapis.com" not in css and "fonts.gstatic.com" not in css
            bundled_fonts.update(re.findall(r"url\([\"']?(/play/[^)\"']+\.woff2)[\"']?\)", css))
    assert bundled_fonts, "Built player must contain resolvable self-hosted font URLs"
    for route in bundled_fonts:
        response = client.get(route)
        assert response.status_code == 200 and response.data.startswith(b"wOF2"), route

    standalone = runpy.run_path(str(export / "module_builder_web.py"), run_name="ember_entrypoint_builder")
    builder_client = standalone["app"].test_client()
    builder = builder_client.get("/")
    assert builder.status_code == 200 and b"ember-builder" in builder.data
    for route in static_paths:
        response = builder_client.get(route)
        assert response.status_code == 200 and response.data, route
        assert response.data == (export / "web" / route.lstrip("/")).read_bytes(), route
    assert standalone["current_build"]["active"] is False
    assert standalone["current_build"]["thread"] is None
    assert web_interface.game_thread is None
    print("ENTRYPOINT_PROBE_RESULT " + json.dumps({
        "source_head": manifest["head"], "export": str(export),
        "working_launcher_sha256": manifest["launcher_sha256"], "build_freshness": freshness,
        "launcher_default": "legacy", "launcher_options": ["legacy", "react", "choose"],
        "launch_selection": launches, "missing_build": missing,
        "legacy_with_and_without_build": 200, "react_with_build": 200,
        "toolkit_with_and_without_build": 200, "standalone_builder": 200,
        "shared_assets_per_flask_app": len(static_paths), "built_entry_assets": len(assets),
        "built_fonts": len(bundled_fonts), "engine_and_builder_jobs_started": 0,
        "outbound_network": "disabled", "retained_export": True,
        "limitations": ["No browser rendering or model inference", "Legacy/toolkit Socket.IO CDN behavior is not an offline guarantee"],
    }), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--temp-parent", type=Path, help="Existing directory on a volume with room for a tracked export")
    args = parser.parse_args()
    if args.worker:
        worker(args.worker)
        return
    repo = Path(__file__).resolve().parents[3]
    dist = repo / "web/frontend/dist"
    if not (dist / "index.html").is_file():
        parser.error("Build the public frontend before running this probe")
    root = Path(tempfile.mkdtemp(prefix="neq-ember-entrypoints-", dir=args.temp_parent))
    export = root / "source"
    export.mkdir()
    print(f"Preparing disposable entry-point export: {export}", flush=True)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    archive = subprocess.Popen(["git", "archive", head], cwd=repo, stdout=subprocess.PIPE)
    try:
        subprocess.run(["tar", "-x", "-C", str(export)], stdin=archive.stdout, check=True)
    finally:
        archive.stdout.close()
    if archive.wait() != 0:
        raise RuntimeError("Tracked public export failed")
    shutil.copytree(dist, root / "prebuilt-public-dist")
    # Exactly one explicit tracked source overlay lets an uncommitted launcher
    # fix be tested without pulling ignored config/runtime files into fixtures.
    shutil.copy2(repo / "run_web.py", export / "run_web.py")
    launcher_sha256 = hashlib.sha256((export / "run_web.py").read_bytes()).hexdigest()
    (root / "entrypoint-probe.json").write_text(json.dumps({"export": str(export), "head": head, "launcher_sha256": launcher_sha256}), encoding="utf-8")
    print(f"Disposable entry-point export: {export} (HEAD {head})", flush=True)
    subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", str(export)], cwd=export, check=True)


if __name__ == "__main__":
    main()
