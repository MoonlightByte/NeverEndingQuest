## Builder Execution Prompts - fork-origin-update-channel

Use this guide with `tasks.md`. Execute in order and stop after each prompt for verification.

---

## Execution Contract

MUST:
- MUST implement only this change scope.
- MUST keep edits limited to:
  - `utils/version_checker.py`
  - `web/web_interface.py`
  - `run_web.py`
  - `web/templates/game_interface.html`
  - `scripts/test_version_checker_fork_update.py` (new)
- MUST preserve existing SocketIO event names and payload shape.
- MUST use explicit fork-target update commands and fast-forward-only semantics.
- MUST fail closed on dirty worktree and git preflight failure.
- MUST keep Python log/output text ASCII-only.

SHOULD:
- SHOULD add concise `# TABLETOP MODE:` markers where host hooks are modified.
- SHOULD keep helper logic in `utils/version_checker.py` centralized and reusable.
- SHOULD avoid broad refactors unrelated to update flow.

Edit Strategy:
- Apply one anchored patch at a time, then run `python3 -m py_compile` on touched Python files.

---

## Prompt 1 - Fork Target Resolver + Version Checker

Implement tasks 1.1 and 1.2 from `tasks.md`.

Goal:
- Replace hardcoded upstream URLs with resolver-derived fork URLs.

Scope:
- `utils/version_checker.py`

Required:
- Add helper to resolve `origin` remote URL into GitHub `owner/repo`.
- Build release and raw VERSION URLs from resolved fork coordinates.
- Preserve `check_for_updates()` return contract.
- Return `unknown` status when target cannot be resolved.

Verify:
```bash
python3 -m py_compile utils/version_checker.py
python3 -c "from utils.version_checker import check_for_updates; print(check_for_updates(silent=True))"
```

Report:
- List helper function names and exact fallback behavior.

---

## Prompt 2 - GUI Updater Preflight and Explicit Fork Pull

Implement task 2.1.

Goal:
- Make updater deterministic and fork-only.

Scope:
- `web/web_interface.py`

Required:
- Add clean-worktree preflight.
- Resolve/update against explicit fork remote/branch.
- Replace implicit pull behavior with explicit fast-forward-only pull path.
- Emit `update_error` on any preflight/git failure, without process exit.

Verify:
```bash
python3 -m py_compile web/web_interface.py
```

Report:
- Include command sequence and failure cases handled.

---

## Prompt 3 - Startup Notice and UI Messaging

Implement tasks 2.2 and 3.1.

Scope:
- `run_web.py`
- `web/templates/game_interface.html`

Required:
- Keep startup check non-blocking but fork-aware via shared checker output.
- Update update-button/dialog copy to indicate fork-source channel.
- Preserve modal/event behavior and update trigger flow.

Verify:
```bash
python3 -m py_compile run_web.py
```

Report:
- Provide before/after message text summary.

---

## Prompt 4 - Regression Tests + Final Gate

Implement tasks 4.1 and 4.2.

Scope:
- `scripts/test_version_checker_fork_update.py`

Required:
- Add tests for origin resolver parsing and fallback.
- Add tests for URL generation against fork owner/repo.
- Add source/behavior checks for updater preflight contract (dirty tree and ff-only failure path).

Verify:
```bash
python3 -m py_compile utils/version_checker.py web/web_interface.py run_web.py
python3 scripts/test_version_checker_fork_update.py
openspec validate fork-origin-update-channel
```

Report:
- PASS/FAIL with key evidence lines for each command.

---

## Prompt 5 - Final Handoff

Required:
- Confirm `tasks.md` checklist alignment with implementation.
- Provide changed file list and short risk notes.

Ready signal:
- "fork-origin-update-channel is apply-ready."
