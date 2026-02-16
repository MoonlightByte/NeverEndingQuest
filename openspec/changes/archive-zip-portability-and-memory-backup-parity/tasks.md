## 1. Archive Auto-Zip Backend

- [ ] 1.1 Add archive zip generation helper in `updates/save_game_manager.py` for `save_mode=full`.
- [ ] 1.2 Implement campaign-wide inclusion rules so archive zip covers all played modules and required recovery artifacts.
- [ ] 1.3 Include `memory_db_package/` in archive zip when present and enforce fail-closed behavior if archive zip generation fails.

## 2. Existing Save Flow Integration (No New Buttons)

- [ ] 2.1 Integrate auto-zip trigger into existing `saveGame` action path in `web/web_interface.py` response handling.
- [ ] 2.2 Return/save zip artifact status and path in success payload so current Save dialog can display operator guidance.
- [ ] 2.3 Preserve existing `essential` save behavior unchanged.

## 3. Reset Backup Memory Parity

- [ ] 3.1 Update `utils/reset_campaign.py` backup phase to capture memory state artifact when available.
- [ ] 3.2 Add clear non-fatal handling/reporting when memory artifact is absent.
- [ ] 3.3 Verify backup directory layout remains compatible with existing reset and restore expectations.

## 4. Validation and Security Checks

- [ ] 4.1 Run `python3 -m py_compile updates/save_game_manager.py web/web_interface.py utils/reset_campaign.py` and resolve issues.
- [ ] 4.2 Run smoke test: `Archive Edition` save produces zip artifact and result message includes path.
- [ ] 4.3 Run negative tests: force zip write failure and verify archive save fails explicitly; verify `essential` saves still succeed.
