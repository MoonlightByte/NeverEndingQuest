## Why

Git-first installs are now the default distribution path for this fork, but several gameplay-mutated JSON families still live inside shipped module content. Normal play can therefore dirty a tester's repo, block fast-forward updates, and blur the boundary between canonical authored data and local runtime state. A recent fresh-install startup failure on Windows also proved that some startup/preflight paths still assume gitignored runtime state already exists, when first-run bootstrap is supposed to create it on demand.

## What Changes

- MUST classify mutable gameplay files into canonical shipped content vs runtime local state, with an explicit contract for each file family.
- MUST complete canonical backup coverage before any live module files are untracked from Git.
- MUST harden startup/reset hydration so missing live area and plot files are recreated from tracked `_BU` sources.
- MUST treat `player_quests_<module>.json` as derived runtime output and regenerate it when absent instead of treating it as canonical content.
- MUST validate that ordinary gameplay mutations no longer dirty tracked repo content in Git installs.
- SHOULD keep runtime filenames unchanged where possible so existing readers/writers continue to work through hydration rather than path rewrites.
- SHOULD keep host-file changes additive and merge-safe, with minimal hooks and `# TABLETOP MODE:` markers where host edits are required.

## Non-Goals

- This change does NOT introduce a new database or alternate persistence backend.
- This change does NOT redesign gameplay state schemas beyond what is required to separate canonical and runtime data.
- This change does NOT relocate every runtime file into a brand-new directory layout if the current filenames can remain stable.
- This change does NOT alter gameplay rules, prompt contracts, or LLM behavior except where startup/bootstrap ordering must respect missing runtime state.

## Capabilities

### New Capabilities
- `git-install-runtime-state-separation`: Git installs SHALL separate canonical shipped module content from mutable local runtime state, including root bootstrap state that is intentionally untracked.
- `module-runtime-state-hydration`: Startup and reset flows SHALL hydrate missing live module state from canonical backups and regenerate derived runtime projections when absent.
- `git-install-update-safe-gameplay`: Ordinary gameplay in a Git install SHALL preserve update readiness by avoiding tracked-file dirtiness from runtime mutations.

### Modified Capabilities
None.

## Impact

- Affected code:
  - `utils/startup_wizard.py`
  - `utils/reset_campaign.py`
  - `utils/reconcile_location_state.py`
  - `updates/plot_update.py`
  - `utils/quest_player_formatter.py`
  - `web/extensions/start_game_preflight.py`
  - `.gitignore`
  - shipped module data under `modules/*`
- Runtime behavior:
  - Fresh clones SHALL remain bootstrappable even when gitignored runtime files are absent.
  - Live gameplay state SHALL continue using current runtime filenames, but those files SHALL no longer be treated as canonical shipped content.
  - Git installs SHALL remain update-safe after normal play when no code edits exist.
- Risks:
  - Missing `_BU` coverage can strand a module without a canonical hydration source.
  - Utilities may still assume live files are shipped rather than hydrated.
  - Verification must distinguish gameplay-generated dirtiness from intentional developer edits.
- Fallback strategy (MUST):
  - If canonical backup coverage or hydration guarantees are incomplete, the rollout SHALL stop before untracking live files.
  - If verification finds tracked gameplay dirtiness after cleanup, the change SHALL remain in scaffold/planning state until the remaining write paths are hardened.
- Merge safety / compatibility:
  - MUST preserve single-player and TABLETOP MODE compatibility.
  - MUST prefer additive hydration and tracking-boundary changes over broad path rewrites.
  - SHOULD reuse existing startup/reset/bootstrap mechanisms instead of inventing parallel flows.
