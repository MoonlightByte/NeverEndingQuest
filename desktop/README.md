# NeverEndingQuest desktop shell (Windows)

The Electron app that starts the game server and opens the game in its own window. Windows only.
The installer (A3) and updates (A4) build on this folder.

## What it does

- Starts the server with `--no-browser --port-or-free <port> --data-dir %APPDATA%\NeverEndingQuest` and `NEQ_DESKTOP=1`.
  The port is the last run's (`run\last-port`, 8357 on the first launch), so the game keeps the same address and
  its settings stored in the page carry over between launches. The server takes a free port only if that one is busy;
  if `run\last-port` exists but cannot be read, the shell asks for any free port (`--port 0`).
  Packaged: `resources\server\run_web.exe` (the PyInstaller folder). From a checkout: `run_web.py --serve`.
- Reads the port from `%APPDATA%\NeverEndingQuest\run\port` (deleted before every start; accepted only when its
  pid is the server the app started), with the `NEQ_PORT=<n>` stdout line as a fallback.
- Opens `http://127.0.0.1:<port>/play/` once `/health` reports ready. Every request carries a per-launch token
  in the `X-NEQ-Local-Token` header; the token is never put in a URL, cookie or log.
- Your saves, settings and logs stay in `%APPDATA%\NeverEndingQuest`. Logs: `logs\desktop.log` and `logs\server.log`
  (Game > Open logs).

## Load and Reset

Loading a save or resetting ends the server with exit code 0, and it expects to be started again. The app
restarts it with the same token and the last port, then reloads the game window (at a new address if that port
was taken). Only a non-zero exit, or a restarted server that stops before it is ready, shows the
"game server stopped" dialog.

## Closing

Quit asks the server to save and stop, then waits for it, with no time limit. During a turn the window says
"Finishing your turn..." and closes when the turn is saved. Game > Force quit stops the server at once and is the
only way the app ever kills it. Quitting while the game is still starting closes it as soon as it is ready.

On Windows logoff or shutdown the app asks the server to save, but Windows decides how long it waits.

## Building the installer

Windows, from a checkout, with Node.js 20.19 or newer, after building the server folder
(`desktop/pyinstaller/build.ps1`, which writes `dist-server/neq-server`):

    python -m pip install --require-hashes --no-deps -r desktop/build-tools/requirements-icon.txt
    python desktop/build-tools/make_icon.py
    cd desktop
    npm ci
    npm run dist:installer

The result is `desktop/release/NeverEndingQuest-Setup-<version>.exe` (per user, no admin prompt) with
`latest.yml` and the `.blockmap` beside it. The installer refuses an install folder that is, contains or sits
inside `%APPDATA%\NeverEndingQuest`, and uninstalling keeps that folder. Running the uninstaller by hand with
`--delete-app-data` would remove it, saves included; the Apps settings page never passes that flag.

Releases come from the desktop-windows workflow on a v* tag. They are unsigned for now (owner decision D-A0-8):
`electron-builder.release.yml` is used, and `electron-builder.signed.yml` takes over only when the `release`
environment has the Azure Trusted Signing variables (AZURE_SIGNING_ENDPOINT, AZURE_SIGNING_ACCOUNT,
AZURE_CERT_PROFILE) and the OIDC ids (AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_SUBSCRIPTION_ID).

## Updates

The installed app from a tag release checks this repository's published GitHub releases once per launch and
downloads a newer installer in the background (prereleases only when the running version is one). Dev runs and
manual workflow builds never check. A downloaded update is offered only on the start screen or after a save has
finished, never during a turn or while a save is still being written:

- **Update and restart** quits the normal way (the server saves and stops), then installs and starts the new
  version.
- **Later** installs it the next time you quit, again only after the server has stopped. Force quit never
  installs.

Before installing, the app checks that nothing from the install folder is still running. If something is, it
shows Keep waiting / Force quit. Releases are not code-signed yet (D-A0-8), so the downloaded installer is
checked against the sha512 in the release's latest.yml but not for a signature.

Neither the installer nor the uninstaller ever closes a running game: if NeverEndingQuest is running, they ask
you to quit it with Game > Quit (which saves first) and press Retry. Cancel stops them. Uninstalling also removes
the update download cache (`%LOCALAPPDATA%\neverendingquest-desktop-updater`).

## Running from a checkout (developers)

From the repository root, with the game's Python environment set up:

    cd desktop
    npm ci
    set NEQ_DESKTOP_PYTHON=C:\path\to\venv\Scripts\python.exe
    npm run dev

`NEQ_DESKTOP_PYTHON` is read by the shell only and never passed to the server. Without it the shell runs `python`.

A Windows venv's `python.exe` is a launcher that starts the real interpreter as its own child, so the pid in
`run\port` never matches the process the shell started. In dev mode the port therefore always comes from the
stdout line. This is expected; do not loosen the pid check, which keeps a stale port file from a crashed run
from being read.
