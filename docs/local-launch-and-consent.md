# Online choice and experimental local models

`launch_game.bat` ships with the repository. With no arguments it offers online
play, local play, or exit. The online choice opens the public product page and
does not check Python/Git/Node, install dependencies, or create settings. The
standalone Windows installer presents the same choice before installation.
Hosted alpha access is limited; this release does not advertise open BYOK access.

Selecting local play uses the installation's `venv\Scripts\python.exe`. If that
environment is absent, the launcher directs the user to the installer/manual
setup. An installer inside a checkout uses that checkout rather than nesting
another clone, and keeps the tracked launcher instead of generating an older one.
React remains the local default; explicit arguments, including `--ui legacy`,
are forwarded. Any arguments or `NEQ_LOCAL_ONLY=1` skip the online/local menu.
`python run_web.py` and headless commands retain their noninteractive behavior.

## Acknowledgment

React and legacy settings show the experimental warning and request explicit
confirmation before selecting a local provider or first saving/testing its
endpoint. The backend checks the current disclaimer version before persistence
or probes. The local client factory also checks it before constructing a client,
so a saved pre-upgrade local configuration cannot bypass acknowledgment.

Existing local selection stays visible and does not fall back to paid OpenAI.
An unacknowledged local call fails with instructions to use Settings or
`python acknowledge_local_model.py`. This CLI displays the full warning and
requires `ACCEPT` interactively. It never reads consent from redirected input.
For deliberate automation, after reviewing the warning use:

```
python acknowledge_local_model.py --accept local-model-alpha-1
```

This records only `local_model_consent.version` and an integer UTC acceptance
timestamp in the installation's ignored `user_settings.json`. It does not change
the selected provider, collect prompts, or make an AI call. An older version does
not count after a disclaimer update. Consent is installation-wide, like the
existing local provider configuration, not a separate per-player account system.
Someone who owns and edits this open-source installation can alter its local
settings; this is an acknowledgment mechanism, not tamper-proof attestation.

The hosted edition still excludes local/custom endpoints. Consent never grants
permission to use an arbitrary URL from a hosted world.

## Checks

Python contract tests exercise actual handler bodies, Socket.IO event decorators,
temporary settings and synthetic/local provider stubs. Windows tests execute
online/exit branches without a browser/install and verify argument forwarding
and exit codes through a temporary venv. Frontend tests exercise decline/accept,
save/probe gating and prior settings behavior; browser checks verify selection
and reload behavior. No paid provider requests are used in this validation.
