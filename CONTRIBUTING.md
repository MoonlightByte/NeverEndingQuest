# Contributing to NeverEndingQuest-TTRPG

Thanks for contributing to the tabletop fork.

This repository is a merge-safe extension of upstream NeverEndingQuest focused on facilitator-led multiplayer sessions.

## Source of truth

Use these in order:

1. `AGENTS.md` (canonical repo rules and architecture guidance)
2. Active OpenSpec change artifacts in `openspec/changes/`
3. Stable capability specs in `openspec/specs/`
4. Long-term planning in `plans/`
5. ADR decisions in `adrs/`

## Before you start

- Read `AGENTS.md` first.
- Check for an active OpenSpec change you should continue instead of starting a new one.
- Prefer extension files and minimal host-file edits.
- Mark required host-file edits with `# TABLETOP MODE:` comments.

## Development setup

See `DEV_SETUP.md` for install, run, test, and troubleshooting.

## Pull request workflow

1. Create a feature branch from your fork default branch.
2. Keep scope tight and additive.
3. Update or add tests for behavior changes.
4. Run targeted verification commands.
5. Update docs when behavior or workflow changes.
6. Open PR with clear summary, verification, and risk notes.

## Required checks for code changes

Run the most relevant checks for your scope:

- `python run_web.py` (startup sanity)
- `python core/validation/validate_module_files.py`
- `python scripts/test_multi_pc_combat.py` (if combat touched)
- `python scripts/test_npc_arrival_state_sync.py` (if narration-state sync touched)
- `python scripts/test_usage_rollups_debug_tab.py` (if usage/cost UI touched)

If you add new tests, include exact run commands in the PR description.

## Coding guardrails

- Use ASCII in Python user-facing output and logs.
- Use atomic JSON operations (`safe_read_json`, `safe_write_json`) for state files.
- Do not break single-player compatibility while extending multiplayer flows.
- Avoid destructive git operations in PR branches.

## Playwright policy

This fork uses Playwright CLI workflows only.

- Use local CLI flows documented in `.opencode/skills/neq-playwright-smoke/SKILL.md`.
- Do not rely on Playwright test MCP server workflows.

## Documentation expectations

When behavior changes, update at least one of:

- `README.md` (user-facing behavior)
- `AGENTS.md` (repo-wide engineering contract)
- OpenSpec artifacts (`openspec/changes/*` and `openspec/specs/*`)
- ADRs in `adrs/` for durable architecture decisions
