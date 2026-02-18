projectbrief

# NeverEndingQuest - Tabletop Multiplayer

Implementation of local tabletop multiplayer functionality for NeverEndingQuest, allowing a facilitator/staff member to manage multiple player characters (PCs) on a single laptop.

## Core Goals
- Implement a merge-safe tabletop multiplayer "plugin".
- Transition from LLM-prompted PC management to hard-wired Python functions.
- Provide a tabbed UI for managing multiple character sheets.
- Maintain full compatibility with single-player mode.

## Key Stakeholders
- Public Library Staff (Facilitators)
- D&D Players (Local participants)

## Recent Work Log

### 2026-02-19: Section 9 Portrait Profile Modal + NPC Initiative Popup Fix

**Section 9 Complete: Portrait Create with Full Profile Modal (Steps 9.1-9.9)**
- **9.1** Prompt enrichment: Added personality_traits, ideals, bonds, flaws, backgroundFeature to portrait prompts
- **9.2** API payload contract: Extended `/api/portrait/create` to accept full profile (appearance + personality + background)
- **9.3** Backend validation: 409 error with `requires_profile` flag for incomplete profiles
- **9.4** Persistence: Profile edits save to character JSON before generation
- **9.5** Always-open modal: Character Sheet `Create` now opens full-profile modal with 12 fields
- **9.6** Client validation: Submit blocked until all required fields filled
- **9.7** Success refresh: Portrait cache-bust + stats reload after create
- **9.8** Regression tests: 8 new tests covering prompt enrichment, validation, persistence
- **9.9** Verification: All 27 tests pass, compile checks pass

**Files modified for Section 9:**
- `core/toolkit/portrait_service.py` - Prompt enrichment with personality/background
- `web/web_interface.py` - API validation and persistence logic
- `web/templates/game_interface.html` - Full-profile modal UI + refresh logic
- `scripts/test_pc_image_create_mvp.py` - Regression tests

**Bugfix: NPC Ally Initiative Popup**
- Fixed: NPC allies in initiative tracker now show full portrait on click
- Root cause: Click handler attached inside async video callbacks (unreliable)
- Solution: Unconditional click attachment with canonical slug normalization
- Fallback chain: video → .jpg → .png → thumbnail background
- Filename normalization now handles apostrophes/hyphens correctly

**Files modified for bugfix:**
- `web/templates/game_interface.html` - NPC initiative click handler refactor

## Active Changes (Pending Commit)
- OpenSpec documentation updates for Section 9
- Generated NPC media files (should be .gitignored or committed)

## Next Steps
- Address remaining bugs in backlog
- Archive Section 9 change when ready
- Continue merge-safe implementation pattern
