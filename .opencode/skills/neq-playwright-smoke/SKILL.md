---
name: neq-playwright-smoke
description: Run a fast Playwright CLI smoke pass against NeverEndingQuest web UI and report deterministic pass/fail results.
license: MIT
compatibility: opencode
metadata:
  audience: developers
  workflow: testing
  project: NeverEndingQuest
---

# NeverEndingQuest Playwright Smoke Skill

## Purpose

Run a repeatable browser smoke check for the local NEQ game server at `http://localhost:8357` after UI/gameplay changes.

Use this for quick confidence, not full regression replacement.

## Trigger Phrases

- `run neq playwright smoke`
- `smoke test the game server`
- `run browser smoke checks`
- `playwright smoke for neq`

## Scope

This skill validates these contracts:

1. App loads without fatal startup errors
2. Chat input sends and DM output appears
3. Enter vs Shift+Enter behavior is correct
4. `/help` works
5. `/init 10` outside combat is blocked with guidance

Optional when available:
- Tabletop mode tab switching sanity
- TTS sanity checks

## Source of Truth

Primary checklist:
- `Docs/playwright_cli_smoke_checklist.md`

Use that file as the canonical step list. If this skill and the checklist diverge, prefer the checklist and update this skill later.

## Execution Contract

1. **Preflight + port hygiene**
    - Confirm Playwright CLI availability:
      - Prefer `playwright --version`
      - Fallback: `npx playwright --version`
    - Ensure Chromium runtime is installed for CLI runs:
      - `npx playwright install chromium`
    - Check for stale listeners on `8357`:
      - `lsof -t -nP -iTCP:8357 -sTCP:LISTEN`
      - If stale/duplicate automation servers exist, terminate listeners before starting a fresh smoke server.
    - Confirm target server reachable at `http://localhost:8357`.

2. **If server unavailable**
   - Fail fast and report blocked status.
   - Provide start commands:
     - Interactive default: `python run_web.py`
     - Automation-friendly: `NEQ_OPEN_BROWSER=0 .venv/bin/python web/web_interface.py`
   - Do not fabricate smoke results.

3. **Run smoke flow in browser**
   - Open app and wait for UI stability.
   - Send `look around the room`, verify DM response rendered.
   - Validate Enter sends and Shift+Enter inserts newline.
   - Send `/help`, verify help output appears.
   - Send `/init 10` outside combat, verify guard message behavior.

4. **Capture evidence**
   - Include any console errors observed.
   - Include screenshot paths only when a failure occurs.

5. **Report format**
   - Return compact pass/fail list with one line per check.
   - Add a final verdict: `PASS`, `PASS WITH WARNINGS`, or `FAIL`.

6. **Post-run cleanup (required)**
   - Stop automation-started server process(es) used for smoke.
   - Re-check `8357` listener state and ensure no leftover smoke server remains.
   - Recommended commands:
     - `lsof -t -nP -iTCP:8357 -sTCP:LISTEN`
     - `kill -TERM <pid>` (then `kill -KILL <pid>` only if needed)

## Guardrails

- Do not change gameplay/state files unless explicitly asked.
- Do not commit code as part of smoke execution.
- Keep output concise and actionable.
- Prefer deterministic checks over subjective UI judgments.
- Do not kill user browser processes; only terminate stale/listening NEQ server processes on `8357`.

## Notes

- This is project-specific by design (NEQ routes, commands, tabletop behavior).
- Global `playwright-cli` skill remains the generic browser automation foundation.
