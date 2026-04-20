# Implementation Notes: GUI Builder Semantic Remediation Sequencing

## Overview

This is a planning-only builder artifact pass. No runtime code changes are produced.
The deliverable is an explicit contract for the next bounded semantic remediation slice,
grounded in the completed deterministic GUI-builder chain.

---

## 1. Sequence Contract

### 1.1 Deterministic Preconditions for Semantic Remediation

Semantic remediation SHALL NOT begin until the following deterministic fixes are landed and verified:

| # | Change | Status | Gate Condition |
|---|--------|--------|----------------|
| 1 | `gui-builder-media-handoff-semantics` | DONE | Finisher correctly hands off pure media-only debt without masking semantic blockers |
| 2 | `gui-builder-module-workflow-ui-ordering` | DONE | Module Builder tab is visually first; builder workflow is default active |
| 3 | `gui-builder-gameplay-readiness-payload-normalization` | DONE | Readiness/publishability consume normalized `target` payloads from gameplay audit |
| 4 | `gui-builder-mixed-failure-classification` | DONE | Mixed media + semantic blockers are classified distinctly; media-only handoff is never applied to modules with semantic publishability blockers |

**Verification**: All 4 changes have passing test suites and are reflected in the roadmap at `plans/module-uploader-2.md` lines 946-952 (implementation order items 14-17).

**Rationale**: If any of these preconditions are missing, semantic blocker surfacing could be confounded with payload-shape bugs, media-debt misclassification, or UI workflow confusion. The deterministic chain isolates each failure class before semantic authoring defects are handled separately.

### 1.2 First Semantic Blocker Classes

The first semantic remediation slice SHALL cover these two blocker classes:

1. **`unresolved_destination_phrase`** - A destination phrase extracted from module area data that does not resolve to any known canonical location ID. These surface when freeform descriptive text contains a travel-pattern phrase ending in a destination terminal (place, sanctuary, inn, hall, chamber, etc.) but the phrase does not match any entry in the module's location catalog.

2. **`ambiguous_destination_alias`** - A destination phrase that matches multiple candidate canonical locations, making resolution non-deterministic without human disambiguation.

**Out of scope for this slice**:
- `missing_npc_authority` (requires deeper NPC scene-authority analysis)
- `phrase_collision_drift_risk` (advisory, not blocking)
- Illusion vs combatant classification (Phase 2)
- Travel alias vs evocative prose disambiguation (Phase 2)

**Detection source**: These blocker classes are already detected by `scripts/module_semantic_authority_audit.py` via `_add_blocking_finding()` with `blocker_classes` including `unresolved_destination_phrase` and `ambiguous_destination_alias`.

---

## 2. Builder-Facing Planning

### 2.1 Post-Report Operator/Remediation Sequence for Semantic Blockers

After a module build or audit surfaces semantic blockers, the operator remediation sequence SHALL be:

```
1. AUDIT REPORT surfaces semantic blockers in a distinct section
   - Blocker class: unresolved_destination_phrase / ambiguous_destination_alias
   - Unresolved phrase: "crucible hall"
   - Source field: areas/G001_BU.json -> transitions -> description
   - Candidate canonical locations (if any): []

2. OPERATOR REVIEWS the blocker finding
   - Is the phrase genuine authoring intent? (travel destination)
   - Is it evocative prose that should not be a travel alias? (atmospheric)
   - Is it a typo or partial name that should match an existing location?

3. OPERATOR RESOLVES the blocker by editing module data
   - Add destination alias to module_context.json or area connectivity
   - OR edit the source field to remove the ambiguous phrase
   - OR add explicit location entry if a genuine new destination

4. RE-AUDIT confirms resolution
   - Re-run module_semantic_authority_audit.py
   - Confirm blocker class no longer appears
   - Confirm publishability status updates accordingly
```

**Key constraint**: Steps 2-3 are human-only. No automated resolution is permitted in this slice. Future builder assistance MAY propose resolutions (see 2.3), but those proposals MUST be reviewed before apply.

### 2.2 How Unresolved Destination-Alias Blockers Feed the First Remediation Slice

The `unresolved_destination_phrase` blocker class is the strongest candidate for the first semantic remediation lane because:

1. **Clear detection**: The semantic authority audit already extracts destination phrases from canonical fields and flags unresolved ones. The extraction pipeline in `utils/module_semantic_authority.py` uses `_DESTINATION_TERMINALS` and `_LEADING_PHRASE_STOPWORDS` to identify candidate phrases, then resolves against the module location catalog.

2. **Concrete remediation path**: Each unresolved phrase has a clear resolution workflow:
   - If the phrase IS a genuine destination → add alias mapping to canonical location
   - If the phrase IS NOT a destination → edit source field to remove travel-pattern language
   - If the phrase is ambiguous → add explicit disambiguation metadata

3. **Example flow (The_Hidden_City_of_Numillian)**:
   - Audit reports: `unresolved_destination_phrase` for phrase `"paradox sanctuary"` in source field
   - Canonical location exists: `Veiled Paradox Sanctuary` → location ID `H01`
   - Operator resolution: Add `"paradox sanctuary"` as alias for `H01` in module semantic authority data
   - Re-audit confirms: phrase now resolves, blocker cleared

4. **Anti-example (The_Ancients_Lab)**:
   - Audit reports: `unresolved_destination_phrase` for phrase `"crucible hall"` + media debt
   - This module has mixed failure (media + semantic)
   - It should remain failed until BOTH classes are resolved
   - This is NOT a candidate for the first semantic-only lane because media debt is also present

### 2.3 Reviewable-Builder Guidance and Python-Authority Constraints

**Python authority is non-negotiable**:
- Python (`scripts/audit_module_publishability.py`, `scripts/module_semantic_authority_audit.py`) determines final publishability status
- No builder assistance, LLM proposal, or operator workflow may override Python's publishability verdict
- If Python says `publishable_status=fail`, the module remains unpublished regardless of builder suggestions

**Reviewable builder assistance**:
- Future builder slices MAY produce proposed resolution artifacts for semantic blockers
- Any proposal MUST include: the blocker finding, the proposed resolution, the source evidence, and the expected audit outcome
- Proposals MUST be presented for human review before any module data is modified
- The review step is mandatory, not optional

**Prohibited in this and subsequent semantic slices**:
- Autonomous semantic repair (no LLM-generated edits applied without review)
- Silently resolving destination aliases by relaxing extraction
- Suppressing blocker findings to achieve publishability
- Widening the blocker class scope beyond the two named classes without explicit OpenSpec change

---

## 3. Artifact Verification

### 3.1 Roadmap Sequencing Updated

The rollout sequence at `plans/module-uploader-2.md` lines 946-952 and 1044-1052 already places this slice (item 5) after the four deterministic GUI-builder fixes (items 1-4).

The implementation order at lines 1008-1031 confirms:
- Items 14-17 correspond to the four completed deterministic fixes
- Item 18 corresponds to this slice: "Add a builder semantic remediation sequencing slice for unresolved destination-alias and similar authoring defects"
- Items 19-21 are Phase 2 LLM work that comes AFTER this slice

No roadmap edits are required in this planning-only pass. The sequencing is already correct.

### 3.2 Builder-Facing Review/Prompt Artifacts for Next Semantic Remediation Slice

The `builder_review.md` in this change directory serves as the primary builder-facing contract. It defines:

- **MUST contract**: Planning-focused, post-deterministic stage, Python authority preserved, reviewable assistance, no autonomous repair
- **SHOULD guidance**: Small first blocker set, explicit operator workflow language, ready for later builder slice
- **Proposed step sequence**: Lock boundary → Define first lane → Produce next-step contract

**Builder prompt for next implementation slice**:

```
Implement the first bounded semantic remediation lane for unresolved destination phrases.

Scope:
- Add a builder-facing remediation section to the module audit output
  that surfaces unresolved_destination_phrase findings with:
  - the unresolved phrase
  - the source field where it was found
  - candidate canonical locations (if any partial matches exist)
- Add a reviewable-proposal workflow where builder assistance can
  suggest destination alias resolutions, but proposals MUST be human-reviewed
  before any module data is modified
- Preserve Python authority over final publishability state unchanged

Allowed:
- Extension of audit output format for semantic blocker detail
- Reviewable proposal generation (not auto-apply)
- Operator-facing workflow documentation

Forbidden:
- Autonomous semantic repair
- Relaxing destination extraction to suppress blockers
- Overriding Python publishability verdict
- Widening scope beyond unresolved_destination_phrase and
  ambiguous_destination_alias
```

### 3.3 Concrete Blocker Example

**Module**: `The_Hidden_City_of_Numillian`

**Blocker**: `unresolved_destination_phrase`

**Finding detail**:
- Unresolved phrase: `"paradox sanctuary"`
- Source: Module area data containing descriptive text with a destination terminal (`sanctuary` in `_DESTINATION_TERMINALS`)
- Canonical location: `Veiled Paradox Sanctuary` exists in the module with location ID `H01`
- Resolution: The phrase `"paradox sanctuary"` is a partial/informal reference to the canonical `"Veiled Paradox Sanctuary"`. Adding it as a destination alias for `H01` would resolve the blocker.

**How this enters the sequence**:
1. Operator runs `module_semantic_authority_audit.py --module The_Hidden_City_of_Numillian`
2. Audit reports `unresolved_destination_phrase` for `"paradox sanctuary"`
3. Operator reviews: confirms it IS genuine authoring intent (travel destination)
4. Operator resolves: adds `"paradox sanctuary"` as alias for location `H01`
5. Re-audit confirms: phrase now resolves, `unresolved_destination_phrase` blocker cleared

**Contrast with anti-example**:
- `The_Ancients_Lab` has `unresolved_destination_phrase` for `"crucible hall"` BUT ALSO has media debt
- This module has mixed failure and is NOT a candidate for the first semantic-only remediation lane
- It must remain failed until both classes are resolved

---

## Summary

| Task | Deliverable | Status |
|------|-------------|--------|
| 1.1 | Deterministic preconditions table | Defined |
| 1.2 | First semantic blocker classes (2) | Identified |
| 2.1 | Operator remediation sequence | Defined |
| 2.2 | Unresolved destination-alias flow | Documented |
| 2.3 | Reviewable-builder + Python authority | Preserved |
| 3.1 | Roadmap sequencing confirmed | Verified (no edits needed) |
| 3.2 | Builder-facing prompt for next slice | Produced |
| 3.3 | Concrete blocker example (Numillian) | Captured |

No runtime code changes were made. This slice is planning-only as specified.
