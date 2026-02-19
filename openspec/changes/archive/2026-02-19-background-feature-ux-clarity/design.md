## Context

Character narrative quality currently degrades when `backgroundFeature.name` and `backgroundFeature.description` are left as generic placeholders (for example `Feature` and `Standard background feature`). Those values propagate into Character Sheet UX, portrait creation context, and PDF backstory output, which creates player confusion and weakens narrative fidelity.

Current state:
- Portrait profile modal requires both background fields but provides limited guidance.
- Legacy character files contain generic placeholder values.
- Readiness checks mostly treat blank values as incomplete; generic placeholder strings are inconsistently handled across flows.

Constraints and stakeholders:
- Core stakeholder is the facilitator/player authoring character identity fields in the GUI.
- Changes MUST remain merge-safe with upstream host files.
- Changes MUST preserve SP and TABLETOP MODE compatibility.
- Mechanical truth fields MUST remain untouched.

## Goals / Non-Goals

**Goals:**
- Provide clear, contextual UX guidance so users can confidently fill background feature fields.
- Normalize legacy generic placeholder values using deterministic, safe remediation.
- Align creation/readiness/repair checks so generic placeholders are treated as incomplete narrative quality.
- Improve downstream consumers (portrait prompts and PDF backstory text) without changing mechanics.

**Non-Goals:**
- Redesigning overall character sheet layout or broader narrative-field workflows.
- Enforcing a single canonical prose style for all campaigns.
- Introducing strict runtime blocking that prevents gameplay for legacy records.

## Decisions

### Decision 1: Guided UX copy with examples in-field
- **MUST:** Add explicit helper guidance for `Background Feature Name` and `Background Feature Description` where users enter these values (portrait modal and relevant character create/edit forms).
- **MUST:** Include concrete, system-relevant examples (for example `Criminal Contact`, `Researcher`) and short composition guidance (`1-3 sentences` explaining practical in-world access/benefit).
- **SHOULD:** Keep guidance concise and editable, so players can still author custom setting-specific text.

Alternatives considered:
- Placeholder-only generic copy (`Feature name`) was rejected due to repeated user confusion.
- Tooltip-only guidance was rejected as less discoverable than inline hints.

### Decision 2: Deterministic suggestion path for known backgrounds
- **MUST:** When background feature values are blank or match known generic placeholders, provide deterministic suggestion defaults based on known background mappings where available.
- **MUST:** Preserve user-authored non-generic values.
- **SHOULD:** Reuse existing startup wizard mapping patterns for consistency.

Alternatives considered:
- LLM-only generation was rejected for this layer due to determinism and latency concerns.
- Hard-locking to SRD strings was rejected because custom campaigns need editable text.

### Decision 3: Placeholder remediation for legacy characters
- **MUST:** Add a non-destructive remediation path that identifies and updates only clearly generic placeholder variants.
- **MUST:** Support dry-run reporting before write operations and fail-open behavior on errors.
- **SHOULD:** Provide a one-time migration helper for existing campaigns so users do not have to manually fix each sheet.

Alternatives considered:
- No migration was rejected because existing placeholders would continue polluting PDF/portrait output.
- Silent auto-mutation of all records at load time was rejected due to observability and rollback risk.

### Decision 4: Readiness and repair alignment
- **MUST:** Treat generic placeholder values as narrative-incomplete in readiness/completeness checks.
- **MUST:** Keep repair mechanics isolated to narrative fields and preserve existing mechanical immutability guarantees.
- **SHOULD:** Expand repair support to include `backgroundFeature.name` where currently only description repair is available.

Alternatives considered:
- Keeping readiness as blank-only detection was rejected because placeholders are semantically empty for UX.

### Decision 5: Merge-safe host edit boundaries
- **MUST:** Keep host-file edits minimal and mark required host hooks with `# TABLETOP MODE:` comments.
- **SHOULD:** Prefer utility/helper functions over repeated inline string checks.

## Risks / Trade-offs

- [Risk] Overwriting intentional short custom text during remediation
  -> Mitigation: only mutate values that match explicit placeholder allowlist; preserve all other values.

- [Risk] Increased form complexity from additional helper text
  -> Mitigation: concise copy, examples only, no extra mandatory fields.

- [Risk] Behavioral divergence between creation, repair, and profile readiness paths
  -> Mitigation: centralize placeholder pattern list in shared audit utility.

- [Risk] Merge conflicts in large host templates (`game_interface.html`)
  -> Mitigation: isolate changes to targeted UI labels/help text and preserve surrounding upstream structure.

## Migration Plan

1. Implement shared placeholder detection constants and deterministic replacement helpers in audit utility layer.
2. Update UX copy and examples in profile/create forms.
3. Update readiness/completeness/repair behavior to classify generic placeholders as narrative-incomplete.
4. Add migration script/helper with dry-run and apply modes for existing character files.
5. Validate with targeted tests and sample legacy character fixtures.

Rollback strategy:
- Revert helper and UI changes; remediation script is opt-in so no automatic irreversible migration is introduced.
- If remediation apply causes undesired output, restore from existing character backup files or git-tracked snapshots.

## Open Questions

- Should the migration helper run automatically at startup in advisory mode, or remain manual-only for MVP?
- Should placeholder detection include localized/non-English variants, or stay strict to current English placeholders for deterministic scope?
- Should profile modal enforce strict minimum description length, or remain semantic guidance-only with generic-placeholder blocking?
