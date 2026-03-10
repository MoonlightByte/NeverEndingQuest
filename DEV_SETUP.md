# NeverEndingQuest-TTRPG Developer Setup

This guide is for contributors working on the tabletop fork.

## 1. Prerequisites

- Python 3.9+
- Git
- Virtual environment support (`venv`)
- OpenAI API key (or configured provider path used by your branch)

## 2. Clone and install

```bash
git clone https://github.com/zeug-zz/NeverEndingQuest-TTRPG.git
cd NeverEndingQuest-TTRPG
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config_template.py config.py
```

Then edit `config.py` and set required keys.

## 3. Run modes

```bash
# Main web interface
python run_web.py
# default: http://localhost:8357

# Module toolkit entry
python launch_toolkit.py

# Terminal mode (limited)
python main.py
```

## 4. Core validation and tests

Run what matches your change scope.

```bash
# Module schema integrity
python core/validation/validate_module_files.py

# Multi-PC combat regression suite
python scripts/test_multi_pc_combat.py

# NPC arrival narration-state sync
python scripts/test_npc_arrival_state_sync.py

# Usage/cost debug tab regressions
python scripts/test_usage_rollups_debug_tab.py
```

## 5. Collaboration structure

Keep these folders available in PRs and branch history:

- `AGENTS.md`
- `scripts/`
- `openspec/`
- `plans/`
- `memory-bank/`
- `adrs/`
- `.opencode/skills/`

## 6. OpenSpec workflow

- Active changes: `openspec/changes/`
- Archived changes: `openspec/changes/archive/`
- Stable specs: `openspec/specs/`

When a change is stale but worth preserving for collaborators, archive it instead of deleting it.

## 7. Playwright policy

Use Playwright CLI workflows only for browser smoke and automation.

- Skill reference: `.opencode/skills/neq-playwright-smoke/SKILL.md`
- MCP Playwright test server is intentionally disabled in `opencode.json`.

## 8. Fork architecture quick map

- Canonical engineering contract: `AGENTS.md`
- Tabletop runtime core: `main.py`, `core/managers/combat_manager.py`, `core/managers/multi_pc_combat.py`
- Web runtime: `web/web_interface.py`, `web/templates/game_interface.html`, `web/static/js/tabletop_mode.js`
- Party state source: `party_tracker.json`

## 9. Common gotchas

- Windows console compatibility: avoid Unicode in Python log/user text.
- Preserve upstream behavior whenever possible; extend with minimal hooks.
- Mark host-file integration edits with `# TABLETOP MODE:` comments.
