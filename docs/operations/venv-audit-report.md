# Venv Audit Report

Date: 2026-04-10
Source plan: `plans/venv-audit.md`
Scope: docs, active plans, scripts, and maintenance/runtime entrypoints

## Summary

The audit found a real interpreter-guidance mismatch across the repo:

- top-level docs still use `python` or `python3` for dependency-sensitive runtime commands
- several maintenance paths can silently degrade when run under the wrong interpreter
- diary/story workflows are the highest-risk category because they can mutate runtime data while hiding dependency loss behind deterministic fallback output

Biggest mismatch:
- docs still advertise `python/python3` for Flask/OpenAI/jsonschema-sensitive commands while codepaths clearly depend on the project venv or silently degrade without it

## Deliverable 1: Command Matrix

| Source path(s) | Current command/example | Classification | Recommended replacement |
|---|---|---|---|
| `AGENTS.md:40`, `README.md:166,339,991` | `python run_web.py` | venv-required | `.venv/bin/python run_web.py` |
| `AGENTS.md:43`, `README.md:171,343` | `python launch_toolkit.py` | venv-required | `.venv/bin/python launch_toolkit.py` |
| `AGENTS.md:46`, `README.md:172,347` | `python main.py` | venv-required | `.venv/bin/python main.py` |
| `AGENTS.md:52`, `plans/version-2/module-import.md:183`, `plans/version-2/mapping/world-mapping.md:458` | `python core/validation/validate_module_files.py` | venv-required | `.venv/bin/python core/validation/validate_module_files.py --module <ModuleSlug>` |
| `scripts/validate_modules_bulk.py:12-16` | `python validate_modules_bulk.py --all` | venv-preferred | `.venv/bin/python scripts/validate_modules_bulk.py --all --json` |
| `plans/version-2/memory.md:1195-1233`, `scripts/backfill_memory_db.py:10-20` | `python3 scripts/backfill_memory_db.py --sources journal` | venv-preferred | `.venv/bin/python scripts/backfill_memory_db.py --sources journal` |
| `scripts/rebuild_players_diary.py` | no active doc example found | venv-required | `.venv/bin/python scripts/rebuild_players_diary.py --rebuild --apply` |
| `scripts/rebuild_session_diary_from_journal.py` | no active doc example found | venv-required | `.venv/bin/python scripts/rebuild_session_diary_from_journal.py --db data/memory.db --apply` |
| `scripts/remediate_session_diary_entries.py` | no active doc example found | venv-required | `.venv/bin/python scripts/remediate_session_diary_entries.py --db data/memory.db --apply` |
| `AGENTS.md:1523-1526` | `.venv/bin/python scripts/test_session_diary_mvp.py` etc. | venv-required | no change |
| `plans/version-2/journal.md:378` | `python3 -m py_compile ...` | interpreter-agnostic | no change |
| `plans/version-2/combat-manager-refactor.md:145-158` | `python3 -m py_compile ...` | interpreter-agnostic | no change |

### Highest-risk documented mismatches

1. `AGENTS.md` is internally contradictory:
   - early runtime examples still use `python`
   - later interpreter rules correctly require `.venv/bin/python`

2. `README.md` still instructs users to launch Flask/OpenAI runtime with system `python`

3. Active plans still show system `python/python3` for:
   - schema validation
   - memory DB mutation

## Deliverable 2: Silent Fallback Register

### High Risk

1. `core/memory/session_diary.py:860-952,1479-1573`
- Fallback behavior: LLM/dependency failure returns deterministic `generation_mode="fallback"` and continues
- Operational risk: wrong interpreter can silently rewrite/create diary content in `data/memory.db` with degraded output
- Recommended fix type: warn loudly in all cases; fail-closed by default for rebuild/remediation CLIs unless an explicit fallback flag is passed

2. `core/memory/story_so_far_compiler.py:211-303,438-484`
- Fallback behavior: LLM failure downgrades to deterministic story text while PDF/export still completes
- Operational risk: operator may think Story So Far used the real runtime LLM path when it did not
- Recommended fix type: warn loudly; surface `generation_mode`; add strict/fail-closed mode for maintenance/export

3. `updates/save_game_manager.py:79-93,539-546,565-595`
- Fallback behavior: `ImportError` disables memory parity/session diary and save/restore continues with disabled or legacy paths
- Operational risk: save/archive workflows can omit diary checkpoint or memory package without strong visibility
- Recommended fix type: keep fail-open for live gameplay save, but warn loudly and fail-closed for explicit archive verification workflows

### Medium Risk

4. `web/extensions/session_diary_runtime.py:17-25,43-50,84-91`
- Fallback behavior: Start Game / Exit hooks return `disabled` when imports fail
- Operational risk: diary runtime hooks silently stop running
- Recommended fix type: keep fail-open, but emit startup-visible warning

5. `core/importers/homebrewery_importer.py:42-64,964-976`
- Fallback behavior: missing validator import sets `VALIDATOR_AVAILABLE=False`; non-strict ingest can report pass-like behavior with validation skipped
- Operational risk: wrong interpreter or missing `jsonschema` can make ingest look valid
- Recommended fix type: keep only for exploratory ingest; warn loudly; fail-closed in strict/dev ingest

6. `scripts/validate_modules_bulk.py:61-91`
- Fallback behavior: auto-switches schema validation to `.venv/bin/python` if current interpreter lacks `jsonschema`
- Operational risk: split-interpreter execution hides operator mistake
- Recommended fix type: keep behavior, but print a loud warning whenever fallback interpreter is selected

7. `scripts/test_story_so_far_pdf_mvp.py:23-28,181-183`
- Fallback behavior: skips Flask route coverage if Flask is missing
- Operational risk: partial green under wrong interpreter
- Recommended fix type: fail-closed or explicit dependency-missing nonzero mode for direct invocation

8. `scripts/test_web_creation_route_recovery.py:18-25,41-42`
- Fallback behavior: skips route test class when Flask/runtime deps are missing
- Operational risk: false confidence in web-route verification
- Recommended fix type: same as above

9. `scripts/test_memory_foundation.py:21-26`
- Fallback behavior: Flask route smoke is dependency-gated
- Operational risk: reduced verification coverage
- Recommended fix type: warn/fail-closed for release verification runs

10. `scripts/test_update_encounter_ops_runtime.py:24-36` and `scripts/test_module_runtime_progression_validation.py:37-46`
- Fallback behavior: jsonschema absence skips runtime validator tests
- Operational risk: validator/runtime coverage disappears under wrong interpreter
- Recommended fix type: fail-closed for release/preflight suites; keep skip for ad hoc local dev only

### Lower Risk / Acceptable Patterns

11. `core/validation/validate_module_files.py:51-72,122-127`
- Fallback behavior: import-time `jsonschema` optional so help/bootstrapping still works; real validation fails clearly
- Operational risk: low
- Recommended fix type: keep as-is

12. `core/memory/players_diary.py:283-303,377-385`
- Fallback behavior: missing AI deps causes warning + error; rebuild/append fail closed
- Operational risk: lower because failure is explicit
- Recommended fix type: keep as-is; use as model for other maintenance paths

13. `scripts/homebrew_media_handles.py:27-32,82-91`
- Fallback behavior: no Pillow falls back to `(0,0)` dimensions
- Operational risk: metadata degradation only
- Recommended fix type: warn loudly

14. `scripts/homebrew_media_extract.py:172-175`
- Fallback behavior: no `requests` causes explicit failure
- Operational risk: low because not silent
- Recommended fix type: keep as-is

## Deliverable 3: Priority Remediation List

1. Fix top-level docs first
- `AGENTS.md`
- `README.md`
- Replace `python` runtime/schema commands with `.venv/bin/python`

2. Fix active-plan command drift
- `plans/version-2/module-import.md`
- `plans/version-2/mapping/world-mapping.md`
- `plans/version-2/memory.md`

3. Harden diary DB mutation paths
- `scripts/rebuild_session_diary_from_journal.py`
- `scripts/remediate_session_diary_entries.py`
- `core/memory/session_diary.py`
- Make fallback explicit and fail-closed by default for maintenance runs

4. Harden Story So Far export semantics
- `core/memory/story_so_far_compiler.py`
- Surface degraded mode loudly; add strict mode for maintenance/export

5. Add loud disabled-state warnings in save/runtime hook paths
- `updates/save_game_manager.py`
- `web/extensions/session_diary_runtime.py`

6. Make verification scripts less skippable in release workflows
- Flask-gated tests
- jsonschema-gated tests
- At minimum print dependency-missing summary; ideally return nonzero in maintenance/release contexts

7. Improve interpreter transparency
- `scripts/validate_modules_bulk.py`
- Print when it auto-switches validator interpreter

## Operational Conclusion

The most urgent repo-wide correction is documentation clarity.

The most dangerous code behavior is silent fallback in diary/story workflows that mutate runtime data under the wrong interpreter.

The main operational fix path should be:

1. correct command guidance to `.venv/bin/python`
2. make critical maintenance paths warn loudly or fail closed
3. keep historical/archive cleanup selective rather than exhaustive
