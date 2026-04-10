# Developer Diary - ONCNotes (OpenCode Notes)

**Purpose:** Ongoing conversational analysis of combat chat logs, OCNote patterns, and system insights discovered through gameplay testing.

**Format:** Chronological entries with timestamps, summarizing narrative flow, combat mechanics, OCNote analysis, and architectural insights.

**Relationship to Other Docs:**
- Complements `activeContext.md` (current work focus)
- Complements `progress.md` (achievements and todo lists)
- More informal/conversational than formal documentation
- Captures "in-the-moment" developer observations

---

## Entry 001 - 2026-02-03T22:10:00 - Split-Party Combat Testing

**Context:** Initial full analysis of combat chat log showing split-party narrative freeze and recovery.

### Narrative Summary
The split-party scenario reached its climax and resolution. acheron and Tester remained in the crypt while the main party fought upstairs. The LLM gradually lost crypt context over 8-10 turns, repeatedly asking about Claris (upstairs) instead of acknowledging crypt activity. acheron attempted to engage Tester and search for secrets but encountered the "freeze" - the LLM defaulted to "What does Claris do?" despite crypt activity. The decision to rejoin was made via narrative bridge ("walk up the stairs"), successfully transitioning back. Combat intensified with Xerxes falling (death saves), but Cyrius landed the killing blow. Combat concluded with transition to narrative mode.

### Combat Interactions
- **Round 4:** Rejoining phase - Party reunited
- **Xerxes:** `/att servant 11` → Miss → Falls unconscious → Death save: 14 → One success
- **Cyrius:** Mace attack (20, 4 dmg) → Defeats final phantom → Combat ends
- **Result:** Victory, transition to narrative

### OCNote Analysis

**OCNote 1 [acheron]:** "LLM forgot NPCs Kira and Henry in crypt"
- **Insight:** Freeze point at ~8-10 turns exceeds @SPLIT_PARTY_GUIDANCE's 3-5 turn promise
- **Action:** Guidance needs tuning to 5-8 or 8-10 turns

**OCNote 2 [Tester]:** "Sub-party frozen out... contextual memory compressed"
- **Insight:** Correct diagnosis - Head-Body-Tail compression pushes secondary track first
- **Implication:** Validates combat save/freeze proposal for longer splits

**OCNote 3 [acheron]:** "Confirmed hard freeze. Will rejoin."
- **Insight:** Recovery via narrative bridge works ("walk up stairs")
- **Success:** @SPLIT_PARTY_GUIDANCE recovery clause functions correctly

**OCNote 4 [Cyrius]:** "'What does Henry do?' remains stubbornly"
- **Critical Bug:** Post-rejoin, LLM asks about Henry (never active PC in queue)
- **Hypothesis:** Turn queue cleanup issue OR context hallucination
- **Next Step:** Investigate if Henry was ever in queue

### Architectural Insights

**The Four-Layer Ecosystem:**
1. **Web GUI /commands** - Human override (trust but verify)
2. **OCNotes** - Real-time pair-programming through gameplay
3. **LLM reactions** - Organic works until it doesn't (8-10 turn limit discovered)
4. **Python state** - Must remain source of truth

**Dialogue-Driven Development Pattern:**
```
Play → Observe → OCNote → Analyze → Design Fix → Retest → Document
```

**Boundary Rules Discovered:**
- Narrative/Atmosphere: Let LLM handle (weaves beautifully)
- Mechanics/Queue: Hard-code in Python (will hallucinate)
- Recovery: Hybrid (human bridge + LLM acceptance)

### Next Steps
- [ ] Test adjusted persistence (5-8 vs 3-5 turns)
- [ ] Investigate Henry turn queue bug
- [ ] Consider `/save combat` command implementation
- [ ] Build OCNote aggregation system

---

*This diary is updated incrementally as new chat logs are analyzed.*

---

## Entry 002 - 2026-02-05T12:45:00 - The Mechanics vs. Narrative Philosophy: State Hallucination Bug

**Context:** Analysis of Feb 5 session revealed a critical architectural question: how do we balance hard-coded Python mechanics with LLM narrative freedom? The exhaustion bug became a case study.

### Narrative Summary

The party completed a major combat in the Great Hall (Feb 3), rested overnight with active watches, and by dawn most PCs had recovered through healing and rest. However, upon resuming the session (Feb 5), the LLM repeatedly narrated PCs as "unconscious," "paralyzed," and "unable to move" despite full HP restoration. Acheron (21/21 HP) was described as "limb and drifting on the edge of unconsciousness." Tester, upon arriving in the crypt, was told "his body refuses to move." The LLM was hallucinating exhaustion state from the end of the Feb 3 session, completely overriding the actual character JSON state.

**The Root Cause:**
- Rest automation worked perfectly: `_process_character_rest()` correctly cleared exhaustion from `condition_affected` arrays
- **But** the DM Note formatting (`format_pc_full_stats`, `format_pc_condensed`) never displayed `condition_affected` to the LLM
- Without seeing "Conditions: None," the LLM relied on conversation history memory ("party was exhausted") and continued that narrative thread into Feb 5

### Combat Interactions

- **Feb 3 Night:** Long rest completed, watches assigned (Tester → Cyrius → Kira → Henry → Acheron)
- **Dawn Recovery:** Claris healed Xerxes, Liri healed Festivus
- **Feb 5 Session Start:** All PCs at full HP but LLM narrates unconsciousness/paralysis
- **Resolution:** Player had to explicitly state "I'm at full HP" multiple times to override hallucination

### OCNote Analysis

**OCNote 1 [Line 570 - acheron]:** "Narration looks good... I wonder if the Narrator LLM is tracking food portions?"
- **Insight:** LLM tracks inventory when explicitly prompted through proactive DM narration
- **Pattern:** Human DM narration → LLM synchronization works for inventory
- **Implication:** This pattern should extend to ALL state updates

**OCNote 2 [Line 624 - Cyrius]:** "LLM updated rations for each active_pc... proactive DM just has to narrate"
- **Insight:** Confirms narration-driven synchronization works
- **Key Finding:** LLM ignores [OCNote: ...] format - functions as meta-commentary without breaking immersion
- **Success:** OCNote threading works as intended

**OCNote 3 [Line 678 - acheron]:** "Healing had to be via spell, there doesn't seem to be a rest dividend? Spell slots haven't updated"
- **Critical Gap Identified:** Rest automation updates JSON files, but LLM doesn't see these updates without explicit narration
- **The Bug:** Python state ≠ LLM perception of state

**OCNote 4 [Line 885 - Tester]:** "Latest 'rest' prompting resulted in persistent 'exhaustion' tag... system isn't responding with full character reset!"
- **The Smoking Gun:** LLM hallucinated "paralysis" and "unconsciousness" for all PCs at session start
- **Mechanical Truth:** All PCs had full HP, no exhaustion in JSON
- **LLM Perception:** "His body refuses to move" (Tester), "limp and drifting" (Acheron)
- **Analysis:** Conversation history from Feb 3 ending (exhausted party) overrode Feb 5 mechanical reality

### Architectural Insight: The Hierarchy of Truth

**The Core Philosophical Question:**
How do we balance Python's mechanical accuracy with LLM narrative freedom without constraining the "DM magic"?

**Our Resolution (Plan C Implementation):**

```
┌─────────────────────────────────────────┐
│  TIER 1: PYTHON (Objective Reality)    │
│  • HP, max HP, death status            │
│  • Spell slots (current/max)           │
│  • Exhaustion levels (1-6)             │
│  • Death save successes/failures       │
│  [NON-NEGOTIABLE - Source of Truth]    │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│  TIER 2: LLM (Subjective Interpretation)│
│  • "Despite full HP, your old wound    │
│     aches from the battle"             │
│  • "You feel weary even after rest"    │
│    (atmospheric, not mechanical)       │
│  • Emotional states, tension, mood     │
│  [FREEDOM WITHIN CONSTRAINTS]          │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│  TIER 3: PLAYER (The Bridge)           │
│  • Sees Python reality (character sheet)│
│  • Experiences LLM narrative            │
│  • Can challenge: "But my HP is full!" │
│  [TRUST BUT VERIFY]                    │
└─────────────────────────────────────────┘
```

**Why This Preserves LLM Freedom:**

The LLM isn't constrained—it gains **clarity**. It knows the mechanical truth (HP 21/21, Conditions: None) and narrates *from* that foundation. The story is richer because:
- The axe can actually kill you (Python enforces this)
- Characters can be "tired warriors" without being mechanically exhausted
- The tension comes from knowing the *actual* stakes (real HP numbers)

**The Golden Rule:**
> "Python enforces reality; you interpret it."

**Implementation (2026-02-05):**

1. **DM Note Enhancement:** Added `condition_affected` display
   - Full stats: `Conditions: None` or `Conditions: Exhaustion L1, Prone`
   - Condensed stats: `Cond: Exhaustion L1` (concise for non-Active PCs)

2. **@STATE_SYNC Directive (system_prompt_compressed.txt):**
```javascript
@STATE_SYNC={
  bookmark: "SESSION BOUNDARY - State below is current mechanical truth",
  truth_source: "DM Note character stats are GROUND TRUTH for HP, conditions, slots",
  override: "If narrative memory contradicts DM Note, DM Note WINS",
  narrative_freedom: "You may narrate SUBJECTIVE experience, BUT mechanical state MUST match DM Note",
  principle: "Python enforces reality; you interpret it"
}
```

**Token Efficiency:**
- Condition line: ~15 tokens per character
- @STATE_SYNC: ~80 tokens total
- Bookmark concept embedded (no session start message needed)

### Why Only PCs, Not NPCs?

The exhaustion hallucination only affected PCs because:
- **PCs:** Load from persistent JSON files via `load_party_character_data()` → DM Note formatting shows conditions
- **NPCs:** Generated dynamically or from location data → No `condition_affected` tracking
- **Result:** NPCs are "fresh" each session; PCs carry (hallucinated) narrative baggage

This is actually a feature, not a bug. NPCs should feel alive in the moment. PCs need mechanical consistency for player trust.

### Next Steps

- [ ] Test updated DM Note with condition display in gameplay
- [ ] Verify @STATE_SYNC prevents session-start hallucination
- [ ] Monitor for other state synchronization gaps (spell slots, features)
- [ ] Consider if NPCs need mechanical condition tracking for consistency

### Key Takeaway

The exhaustion bug wasn't a rest automation failure—it was a **perception synchronization failure**. Python did its job perfectly. The LLM simply couldn't see the results. By adding conditions to the DM Note, we didn't constrain the LLM—we gave it eyes to see the reality Python was already maintaining.

**This is the heart of the player-LLM-Python loop:** Trust requires mechanical transparency. Freedom requires mechanical boundaries. Python provides the former; the system prompt provides the latter.

---

*The question isn't "Should the LLM follow Python?" but "How do we ensure the LLM can see what Python has done?"*

## Entry 002 - 2026-02-24 - Portrait Download and Popup Quality Fixes

**Context:** Addressing low-resolution issues in character portrait downloads and popup modals.

### Problems Identified

**1. Portrait Download Resolution**
- Sidebar "Download" button was fetching only 256x256 web portraits
- AI-generated portraits were being saved at 256x256 after resize, losing original DALL-E resolution (1024x1024)
- Upload path had ordering bug: variables referenced before definition

**2. Initiative/Party Strip Popup Quality**
- NPC popups in narration strip were opening thumbnails (128x128) instead of full images
- `imageCandidates` was thumb-first for both tile rendering AND popup fallback
- Edda Ravenscroft appeared blurry in popup despite having 1024x1024 full image available

### Fixes Implemented

**Portrait Service (`core/toolkit/portrait_service.py`)**
- Preserve full-resolution copy before resize: `full_res_image = img.convert('RGBA')...`
- Save `_full.png` sidecar to static portraits AND module portraits
- Create 256x256 compatibility image separately: `compat_image = full_res_image.resize(...)`
- Maintains backward compatibility with existing `<name>.png` paths

**Upload Portrait (`web/web_interface.py`)**
- Fixed ordering: normalize character name BEFORE using it
- Fixed ordering: resolve module directory BEFORE save attempts
- Save hi-res `_full.png` from cropped image before 256x256 resize
- Fail-open module saves (warnings only, don't block success)

**Download Logic (`web/templates/game_interface.html`)**
- New priority chain: `_full.png` → NPC `.jpg` → NPC `.png` → legacy `.png` → current `src`
- Recursive `tryDownloadCandidate()` function attempts each URL in order
- Uses `normalizePortraitSlug()` for consistent filename generation
- Preserves existing user feedback and filename sanitization

**Popup Quality (`web/templates/game_interface.html`)**
- Split `imageCandidates` into two separate arrays:
  - `tileImageCandidates`: thumb-first for fast strip rendering
  - `popupImageCandidates`: full-image-first for quality modals
- Video-first behavior preserved for characters with `_video.mp4`

### Testing

**Regression Tests Added (`scripts/test_pc_image_create_mvp.py`)**
- `TestPortraitDownloadBestResolutionContracts` (6 tests):
  - `test_download_candidates_priority`: Verifies priority chain ordering
  - `test_portrait_create_saves_hi_res_sidecar`: Confirms `_full.png` creation
  - `test_portrait_service_preserves_full_res_before_resize`: Validates copy-before-resize
  - `test_upload_portrait_normalizes_before_full_save`: Checks init ordering
  - `test_upload_portrait_saves_hi_res_sidecar`: Confirms upload path hi-res save
  - `test_legacy_256_save_paths_remain_present`: Backward compatibility check
  - `test_party_render_uses_separate_tile_and_popup_candidate_lists`: Split candidate arrays
  - `test_popup_candidates_prioritize_full_images_before_thumb`: Full > thumb ordering
  - `test_tile_candidates_use_thumb_first`: Thumb > full for tiles
  - `test_video_candidates_remain_first_in_popup_flow`: Video priority preserved

All tests pass: `Ran 6 tests in 0.002s OK`

### Files Modified

1. `web/templates/game_interface.html` - Download priority chain, split candidate arrays
2. `core/toolkit/portrait_service.py` - Full-res sidecar persistence
3. `web/web_interface.py` - Fixed upload ordering and hi-res save
4. `scripts/test_pc_image_create_mvp.py` - 10 new regression tests

### Architecture Notes

**Backward Compatibility Strategy:**
- Legacy `<name>.png` (256x256) still generated and used for UI
- New `<name>_full.png` is additive, not replacement
- Download falls through gracefully if `_full.png` missing
- NPC media fallback chain unchanged for promoted characters

**Performance Considerations:**
- Hi-res images only saved once (generation or upload time)
- Download attempts URLs sequentially (fast path: `_full.png` usually exists)
- No additional runtime overhead for display paths

**Future Work:**
- Consider progressive download for `_full.png` (lazy load in modals)
- Potential: Serve WebP variants alongside PNG for bandwidth
- Potential: Expose resolution choice in download dialog

---

## 2026-04-10 - Module Publication Semantic Phases Archived

### Summary

Completed and archived two publication-semantics OpenSpec slices:

- `openspec/changes/archive/2026-04-09-module-publication-semantic-authority-foundation/`
- `openspec/changes/archive/2026-04-09-module-publication-semantic-audit/`

### What Landed

1. **Semantic Authority Foundation**
   - Added shared helper `utils/module_semantic_authority.py`.
   - Emits deterministic location alias map, destination phrase map, and NPC scene-authority map with provenance.
   - Integrated into ingest and toolkit finisher:
     - `scripts/homebrew_ingest_dev.py`
     - `web/extensions/toolkit_module_finisher.py`

2. **Semantic Publication Audit**
   - Added standalone audit script `scripts/module_semantic_authority_audit.py`.
   - Added explicit blocker classes and structured findings for publication-unsafe semantics.
   - Keeps audit standalone from repo-wide `publishable` gate in this phase.

### Notes

- Legacy module smoke (`Night_of_the_Restless_Dead`) correctly fails with semantic payload missing blocker when semantic authority is absent.
- Next publication plan step is Phase 3 probe harness (`module-publication-live-play-probes`).

---

## 2026-04-10 - Module Publication Plan Fully Closed

### Summary

Finished the remaining publication workflow slices and archived the publication master plan.

### What Landed

1. **Live-Play Probe Harness**
   - Added `scripts/module_semantic_probe_harness.py`.
   - Deterministic publication probes now cover:
     - travel destination resolution
     - continuity handoff refs
     - hidden/revealable NPC discovery authority

2. **Publishable Gate**
   - Added `scripts/audit_module_publishability.py`.
   - Distinguishes:
     - `ready_status`
     - `publishable_status`
   - Publishability now composes readiness + semantic audit + semantic probes.

3. **Reporting Surface**
   - `web/extensions/toolkit_module_finisher.py` now reports ready vs publishable.
   - `scripts/validate_modules_bulk.py` now includes publishability reporting.

4. **Archives**
   - `openspec/changes/archive/2026-04-09-module-publication-live-play-probes/`
   - `openspec/changes/archive/2026-04-09-module-publication-publishable-gate/`
   - `plans/archive/module-publication.md`

### Notes

- Current legacy modules correctly remain not publishable under the stricter semantic gate.
- The plan is now complete: substrate -> blockers -> probes -> publishable gate.

---

## 2026-04-10 - Venv Audit Remediation Pass

### Summary

Ran the planned interpreter audit and remediated the highest-risk mismatches.

### What Landed

1. **Command Guidance Cleanup**
   - Active docs now point dependency-sensitive runtime and maintenance commands at `.venv/bin/python`.
   - Touched:
     - `AGENTS.md`
     - `README.md`
     - `plans/version-2/memory.md`
     - `plans/version-2/module-import.md`
     - `plans/version-2/mapping/world-mapping.md`

2. **Diary Maintenance Hardening**
   - `scripts/rebuild_session_diary_from_journal.py`
   - `scripts/remediate_session_diary_entries.py`
   - `--apply` now fails closed by default when AI client deps are missing while diary LLM mode is enabled, unless `--allow-fallback` is passed.

3. **Story/Validator Visibility**
   - `core/memory/story_so_far_compiler.py` now logs a loud warning when deterministic fallback story generation is used.
   - `scripts/validate_modules_bulk.py` now warns when schema validation silently falls back to a different interpreter.

4. **Audit Artifact**
   - `docs/operations/venv-audit-report.md`

### Notes

- Remaining `python` references found by the audit scanner are in archived plans only and were intentionally left untouched.
- `scripts/test_module_validation_cli.py` still has unrelated pre-existing failures; not introduced by this remediation pass.
