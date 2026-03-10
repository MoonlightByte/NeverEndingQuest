# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

# OpenSpec Tasks: fork-origin-update-channel

## Step 1.1 - Add fork origin resolver in version checker [DONE]

- [x] Add helper(s) in `utils/version_checker.py` to resolve update repo from `origin` remote URL.
- [x] Return deterministic `owner/repo` or safe `None` on parse failure.
- [x] Keep existing public `check_for_updates()` signature compatible.

**Verification:**
```bash
python3 -m py_compile utils/version_checker.py
```

## Step 1.2 - Make version check fork-aware with safe fallback [DONE]

- [x] Replace hardcoded MoonlightByte GitHub URLs with resolver-derived URLs.
- [x] Preserve status contract (`update_available`, `up_to_date`, `unknown`).
- [x] Ensure unresolved target returns `unknown` without raising.

**Verification:**
```bash
python3 -m py_compile utils/version_checker.py
python3 -c "from utils.version_checker import check_for_updates; print(check_for_updates(silent=True))"
```

## Step 2.1 - Harden GUI update command to explicit fork pull [DONE]

- [x] Update `web/web_interface.py` `trigger_update` handler to use explicit fork remote/branch.
- [x] Add dirty worktree preflight gate before git mutation.
- [x] Use `--ff-only` pull semantics and fail closed on non-fast-forward outcomes.

**Verification:**
```bash
python3 -m py_compile web/web_interface.py
```

## Step 2.2 - Align startup version notice path [DONE]

- [x] Ensure `run_web.py` startup notice uses fork-aware checker output unchanged contract-wise.
- [x] Keep startup behavior non-blocking if checker fails.

**Verification:**
```bash
python3 -m py_compile run_web.py
```

## Step 3.1 - Update UI copy to fork-channel messaging [DONE]

- [x] Update update-button/dialog/status strings in `web/templates/game_interface.html` to indicate fork-source updates.
- [x] Preserve event flow and modal behavior.

**Verification:**
```bash
rg -n "Update Available|fork|origin" web/templates/game_interface.html
```

## Step 4.1 - Add focused regression coverage [DONE]

- [x] Add `scripts/test_version_checker_fork_update.py` with resolver and URL contract tests.
- [x] Add updater preflight behavior test(s) for dirty tree and ff-only failure handling (source-level or unit-level).

**Verification:**
```bash
python3 scripts/test_version_checker_fork_update.py
```

## Step 4.2 - Final validation gate [DONE]

- [x] Run compile and targeted tests for touched files.
- [x] Validate OpenSpec change.

**Verification:**
```bash
python3 -m py_compile utils/version_checker.py web/web_interface.py run_web.py
python3 scripts/test_version_checker_fork_update.py
openspec validate fork-origin-update-channel
```
