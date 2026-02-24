## Builder Prompt Sequence

### Step 2.1 Prompt
Implement OpenSpec `pc-creation-startup-fixes` Step 2.1 only.
- Goal: Make add-more prompt line-visible in web startup flow before input capture.
- Allowed files: `utils/startup_wizard.py`
- Forbidden: gameplay narration logic, combat logic, schema changes.
- Verify: `python3 -m py_compile utils/startup_wizard.py`
- Expected output: PASS - prompt now emitted via print() before input()

### Step 2.2 Prompt
Implement OpenSpec `pc-creation-startup-fixes` Step 2.2 only.
- Goal: Strict yes/no parser + reprompt-only behavior for blank/invalid input.
- Allowed files: `utils/startup_wizard.py`
- Forbidden: defaulting blank input to no.
- Verify: 
  - `python3 -m py_compile utils/startup_wizard.py`
  - `.venv/bin/python3 scripts/test_startup_multipc_reprompt.py` (or verify logic manually)
- Expected output: PASS - blank/invalid reprompts; y/yes continues; n/no exits

### Step 2.3 Prompt
Implement OpenSpec `pc-creation-startup-fixes` Step 2.3 only.
- Goal: Apply strict yes/no parsing to secondary retry decision after failed creation.
- Allowed files: `utils/startup_wizard.py`
- Forbidden: changes to primary add-more prompt (already done in 2.2).
- Verify: `python3 -m py_compile utils/startup_wizard.py`
- Expected output: PASS - both decision points have reprompt-safe behavior

### Step 2.4 Prompt
Implement OpenSpec `pc-creation-startup-fixes` Step 2.4 only.
- Goal: Document explicit-exit contract and ensure no implicit termination paths.
- Allowed files: `utils/startup_wizard.py` (comments/documentation only)
- Forbidden: logic changes (should be no-op if 2.1-2.3 done correctly).
- Verify: Code audit confirms all break paths are explicit `n/no` branches.
- Expected output: PASS - labeled EXPLICIT EXIT 1 and 2, else branches use continue

### Step 2.5 Prompt
Implement OpenSpec `pc-creation-startup-fixes` Step 2.5 only.
- Goal: Preserve existing per-character creation retry and failure/success messaging.
- Allowed files: `utils/startup_wizard.py` (only if fix needed)
- Forbidden: message text changes, flow changes.
- Verify: Non-regression check - messages unchanged:
  - "Dungeon Master: Additional player creation failed."
  - "Dungeon Master: Added player {name} to startup party."
- Expected output: PASS (or zero-diff if already compliant)

### Step 3.1 Prompt
Implement OpenSpec `pc-creation-startup-fixes` Step 3.1 only.
- Goal: Fix null-guard order in `displayCharacterStats` - check `!data` before `data.name`.
- Allowed files: `web/templates/game_interface.html`
- Forbidden: broad UI redesign.
- Verify: 
  - Source check: null guard appears before first `data.*` access
  - `python3 scripts/test_character_sheet_stats_resilience.py`
- Expected output: PASS - data.name access occurs after null guard return

### Step 3.2 Prompt
Implement OpenSpec `pc-creation-startup-fixes` Step 3.2 only.
- Goal: Add deterministic waiting/error render states for null stats payload.
- Allowed files: `web/templates/game_interface.html`
- Forbidden: backend/socket changes.
- Verify:
  - Source check: `if (error)` branch with amber error text
  - Source check: waiting state "Loading character stats... (waiting for data)"
  - `python3 scripts/test_character_sheet_stats_resilience.py`
- Expected output: PASS - null path distinguishes backend error vs waiting

### Step 3.3 Prompt
Implement OpenSpec `pc-creation-startup-fixes` Step 3.3 only.
- Goal: Add defensive try/catch to ensure transient exceptions don't block later renders.
- Allowed files: `web/templates/game_interface.html`
- Forbidden: changes to polling/signature contract.
- Verify:
  - Source check: try block wraps main render body
  - Source check: catch (renderError) with console.error + container fallback
  - `python3 scripts/test_character_sheet_stats_resilience.py`
- Expected output: PASS - try/catch present with fallback UI message

### Step 3.4 Prompt
Implement OpenSpec `pc-creation-startup-fixes` Step 3.4 only.
- Goal: Verify polling refresh behavior is preserved as recovery path.
- Allowed files: `web/templates/game_interface.html` (only if fix needed)
- Forbidden: interval/timer changes.
- Verify:
  - Source check: `setInterval(..., 5000)` present
  - Source check: Character tab branch calls `loadCharacterStats()`
  - Source check: Stats socket handler passes `response.error`
- Expected output: PASS (zero-diff if already compliant)

### Step 4.1 Prompt
Implement OpenSpec `pc-creation-startup-fixes` Step 4.1 only.
- Goal: Add focused startup tests for explicit yes/no + blank/invalid reprompt behavior.
- Allowed files: `scripts/test_startup_multipc_reprompt.py` (new)
- Forbidden: edits to other test files.
- Verify:
  - Compile: `.venv/bin/python3 -m py_compile scripts/test_startup_multipc_reprompt.py`
  - Run: `.venv/bin/python3 scripts/test_startup_multipc_reprompt.py`
- Expected output: 3 tests PASS (or SKIP with graceful fallback if deps missing)

### Step 4.2 Prompt
Implement OpenSpec `pc-creation-startup-fixes` Step 4.2 only.
- Goal: Add focused UI source-contract tests for null-safe `displayCharacterStats`.
- Allowed files: `scripts/test_character_sheet_stats_resilience.py` (new)
- Forbidden: edits to other test files.
- Verify:
  - Compile: `python3 -m py_compile scripts/test_character_sheet_stats_resilience.py`
  - Run: `python3 scripts/test_character_sheet_stats_resilience.py`
- Expected output: 5 tests PASS

### Step 4.3 Prompt
Implement OpenSpec `pc-creation-startup-fixes` Step 4.3 only.
- Goal: Run compile/syntax checks and capture pass/fail summary.
- Allowed files: None (verification only)
- Forbidden: code changes.
- Verify:
  ```bash
  # Compile checks
  .venv/bin/python3 -m py_compile utils/startup_wizard.py
  .venv/bin/python3 -m py_compile scripts/test_startup_multipc_reprompt.py
  .venv/bin/python3 -m py_compile scripts/test_character_sheet_stats_resilience.py
  
  # Targeted tests
  .venv/bin/python3 scripts/test_startup_multipc_reprompt.py
  .venv/bin/python3 scripts/test_character_sheet_stats_resilience.py
  
  # OpenSpec validation
  openspec validate pc-creation-startup-fixes
  ```
- Expected output: All PASS, change valid

---

## Final Verification Bundle

Execute this exact command set to validate the entire change:

```bash
cd /Users/zeug/Projects/NeverEndingQuest

# Compile validation
.venv/bin/python3 -m py_compile utils/startup_wizard.py
.venv/bin/python3 -m py_compile scripts/test_startup_multipc_reprompt.py
.venv/bin/python3 -m py_compile scripts/test_character_sheet_stats_resilience.py

# Targeted regression tests
.venv/bin/python3 scripts/test_startup_multipc_reprompt.py
.venv/bin/python3 scripts/test_character_sheet_stats_resilience.py

# OpenSpec validation
openspec validate pc-creation-startup-fixes
```

**Expected Results:**
- Compile: All PASS (no syntax errors)
- Startup tests: 3 PASS (or SKIP gracefully if jsonschema missing in non-venv)
- Stats resilience tests: 5 PASS
- OpenSpec: `Change 'pc-creation-startup-fixes' is valid`

**Acceptance Criteria:**
- [ ] All compile checks PASS
- [ ] All targeted tests PASS
- [ ] OpenSpec validation reports "valid"
- [ ] No breaking changes to existing flows
