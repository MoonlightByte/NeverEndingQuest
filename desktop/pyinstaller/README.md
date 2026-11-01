# Desktop server build (PyInstaller)

Builds the game server the desktop app ships, as one folder: `dist-server/neq-server/run_web.exe`
with its files in `dist-server/neq-server/_internal/` (#1681).

On Windows, from a clean checkout, with 64-bit Python 3.12 and Node.js (only needed when the
React player is not built yet):

    powershell -ExecutionPolicy Bypass -File desktop\pyinstaller\build.ps1 -Python C:\Path\To\Python312\python.exe

The script checks the rules-engine pair in `bin/`, installs `requirements-build.txt` with
`pip --require-hashes` into a fresh venv, builds the React player if it is stale, fetches and
hash-checks tiktoken's `cl100k_base` file, runs PyInstaller with `neq-server.spec`, checks the
packaged engine copies against `bin/`, and smoke-tests the result (pass `-SkipSmoke` to skip):
the provider child and combat_builder run as bundled modules, the server answers `/health` with
a launch token, and `/shutdown` stops it with exit 0. No model request is sent.

- `neq-server.spec` ships only git-tracked files from the data folders, so local saves never
  enter a build.
- `rthook_neq.py` points tiktoken at the bundled encoding file.
- `requirements-build.txt` is generated with uv; the command is in its header.
