## Context

The new readiness audit surfaces missing narrative fields in character sheets and PDF exports, but remediation is manual. For tabletop facilitation, recovery must be fast, safe, and in the GUI. The requested behavior is a `Repair` button that runs in the background (no chat output), proposes fixes, and applies only after explicit confirmation.

Constraints:
- Preserve mechanical truth: repair must never alter mechanics.
- Keep merge-safe boundaries and minimal host-file edits.
- Reuse shared audit contract from `utils/character_creation_audit.py`.
- Keep operation non-destructive unless DM confirms apply.

## Goals / Non-Goals

**Goals:**
- Add a `Repair` UI action in readiness warning area.
- Implement preview -> confirm workflow.
- Generate candidate narrative content from character context and bounded history.
- Enforce strict narrative-only field whitelist.
- Re-audit after apply and persist only on success.
- Add cooldown and logs to avoid abuse/spam.

**Non-Goals:**
- No automatic silent writes without DM confirmation.
- No repair of mechanical or schema-critical combat fields.
- No dependency on chat message injection for repair flow.

## Decisions

### 1) Two-step endpoint design (preview and apply)
Decision: Expose separate endpoints:
- `POST /api/character_sheet/readiness_repair/preview`
- `POST /api/character_sheet/readiness_repair/apply`

Rationale:
- Keeps write path explicit and auditable.
- Enables trust-preserving preview UI.

Alternatives considered:
- Single auto-apply endpoint: rejected (low transparency, higher risk).

### 2) Strict field whitelist for repair
Decision: Only these fields are writable by repair:
- `personality_traits`, `ideals`, `bonds`, `flaws`, `backgroundFeature.description`

Rationale:
- Prevents accidental mechanical drift.

Alternatives considered:
- Open-ended patch object from LLM: rejected (unsafe).

### 3) Bounded generation with deterministic fallback
Decision: Preview generation uses LLM when available, else deterministic templated content per missing field.

Rationale:
- Keeps feature reliable when provider is down or quota-limited.

Alternatives considered:
- LLM-only path: rejected (availability/cost risk).

### 4) Audit gates before and after apply
Decision:
- Preview uses readiness audit to identify missing fields.
- Apply revalidates patched payload with `audit_character_creation(..., enable_enrichment=False)` and blocks save on failure.

Rationale:
- Guarantees consistent contract with current creation/readiness rules.

### 5) Lightweight cooldown + logging
Decision: Add per-character cooldown (for example 15s) for preview/apply attempts and structured logs with actor/session metadata when available.

Rationale:
- Protects backend from repeated clicks and supports debugging.

## Risks / Trade-offs

- [LLM output low quality or generic] -> Mitigation: preview lets DM accept/reject; deterministic fallback still unblocks readiness.
- [Whitelist bypass attempts] -> Mitigation: server reconstructs patch from whitelist only, ignores extra keys.
- [Concurrent edits to same character] -> Mitigation: re-read latest file at apply time and re-audit before write.
- [UI complexity creep] -> Mitigation: keep modal minimal (field-by-field before/after + confirm/cancel).

## Migration Plan

1. Add backend preview/apply handlers with whitelist and audit gates.
2. Add generator helper (LLM + deterministic fallback) with strict JSON extraction.
3. Add `Repair` button and preview modal in sheet warning UI.
4. Add cooldown/logging and error messaging.
5. Verify with readiness-negative and readiness-positive characters.

Rollback strategy:
- Hide/disable Repair UI button.
- Keep readiness warnings unchanged.
- Retain backend code disabled by route flag if needed.

## Open Questions

- Should preview allow inline DM edits before confirm, or only accept/cancel in phase 1?
- Should cooldown be global per character or per browser session + character?
