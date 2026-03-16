## Why

`Manage Party -> Create with DM` currently uses a separate mid-campaign character-creation stack from the startup wizard path. The startup wizard DM creation in `utils/startup_wizard.py` is the stable upstream-aligned behavior, but the mid-campaign GUI flow has drifted into a second prompt builder, a second finalization path, and partially duplicated persistence logic. That drift already produced a real regression: the GUI path accepted malformed prompt state, emitted broken finalization retries, and could stall in creation mode while startup creation continued to work.

Without a refactor, the two creation paths will continue to diverge. Fixes made to startup will not naturally reach the GUI path, and future UI/prompt changes can widen the gap further.

## What Changes

- Extract a shared character-creation core for prompt/context assembly and final JSON finalization so startup and mid-campaign DM creation reuse the same contract.
- Preserve startup wizard interview behavior as the canonical baseline while keeping its terminal-owned loop and startup bootstrap semantics intact.
- Rework `Manage Party -> Create with DM` so it becomes a web adapter around the shared creation core instead of a parallel implementation.
- Collapse duplicate finalization logic so startup and GUI creation use one audit/correction/persistence contract.
- Add focused regression coverage for startup parity, mid-campaign creation-mode recovery, and duplicate-finalizer prevention.

### MUST Contract

- The startup wizard DM creation behavior SHALL remain the canonical baseline for character-creation prompt rules and finalization expectations.
- The mid-campaign `Create with DM` flow SHALL reuse the shared character-creation core instead of maintaining a separate prompt/finalization implementation.
- The refactor SHALL preserve startup-specific behavior, including iterative onboarding and `startup_incomplete` lifecycle handling.
- The refactor SHALL preserve mid-campaign-specific behavior, including target level, party/location context, conversation backup/restore, creation-mode pause/resume, and web queue integration.
- Final character JSON handling SHALL use one shared audit/correction contract across startup and GUI DM creation.
- The refactor SHALL remain backward-compatible with Roll Your Own and Add Existing flows.

### SHOULD Guidance

- The shared core SHOULD live in a neutral utility module rather than inside `startup_wizard.py` or a web route.
- The startup and GUI entry points SHOULD become thin adapters over shared services.
- The refactor SHOULD reduce direct writes to `characters/` from scattered call sites by routing persistence through one helper.
- Host-file edits SHOULD stay minimal and use `# TABLETOP MODE:` markers where required.

### Non-goals

- No redesign of the startup wizard interview UX or pacing.
- No redesign of Roll Your Own, Add Existing, or unrelated character-sheet editing flows.
- No conversion of the web GUI to use terminal `input()`/`print()` directly.
- No change to character schema requirements beyond what the shared audit already enforces.

## Capabilities

### Modified Capabilities

- `tt-pc-creation-workflows`: extend the capability so startup and mid-campaign DM creation share one prompt/finalization core while preserving adapter-specific runtime behavior.

## Impact

- Affected code (planned):
  - `utils/startup_wizard.py`
  - `utils/pc_manager.py`
  - `utils/character_creator.py`
  - `main.py`
  - `web/routes/tabletop_party_routes.py`
  - `prompts/character_creation/dm_interview_prompt.txt` or replacement shared prompt assets
  - focused regression tests under `scripts/`
- Merge-safety impact: medium; this is a structural refactor, but it remains inside existing character-creation boundaries and should reduce future drift.
- SP/MP compatibility impact:
  - Startup single-player creation MUST remain unchanged in behavior.
  - Mid-campaign tabletop creation MUST retain current web pause/resume semantics.
- Rollout risk: medium; finalization and persistence paths are sensitive and can strand facilitators in creation mode if the shared contract is incomplete.
- Fallback strategy:
  - If the shared core cannot safely finalize, keep creation mode active and emit deterministic corrective guidance.
  - If adapter wiring proves unsafe, preserve startup behavior first and temporarily keep GUI on the existing path behind isolated guards until parity is proven.
