## Context

Current media behavior already favors module assets and falls back to static media, but portrait generation is not integrated into sheet UX and missing media warnings can flood logs.

Hard constraints:

- Upload portrait path MUST remain unchanged and functional.
- Auto-generation on miss MUST apply only to allied NPC companions in MVP.
- Non-allied NPC and monster misses MUST default to fallback rendering only in MVP.
- Missing-media generation MUST be asynchronous and non-blocking.
- Any new Python-visible logs/messages MUST be ASCII only.
- Host-file edits MUST remain minimal and marked with `# TABLETOP MODE:`.
- Schema updates MUST be backward compatible (optional fields only).

Implementation preferences:

- Reuse existing toolkit generation logic rather than creating parallel provider plumbing.
- Centralize prompt composition in one portrait service.
- Keep auto-generation policy behind config flags.

## Goals / Non-Goals

Goals:

- Provide `Upload / Create` portrait UX in Character Sheet.
- Generate portraits from character state plus appearance metadata.
- Auto-heal missing portraits for allied companions only.
- Reduce warning spam via key-based throttle.
- Preserve promotion continuity (NPC -> PC image linkage by name).

Non-goals:

- Full auto-gen for all NPCs/monsters.
- Any combat mechanics change.
- Any save/restore pipeline change.

## Decisions

1. **Create a dedicated portrait service**

   Decision:
   - Add `core/toolkit/portrait_service.py` to own prompt building, generation calls, and file output.

   Rationale:
   - Avoids duplicating ad-hoc image prompt logic across web handlers.
   - Enables reuse from both Character Sheet create and allied auto-heal worker.

   Alternative considered:
   - Inline logic in `web/web_interface.py`. Rejected due to coupling and weaker testability.

2. **Add allied-only missing-media auto-heal worker**

   Decision:
   - Add `web/extensions/missing_media_autogen.py` with queue + dedupe + cooldown.
   - Enqueue only for allied NPC companion misses when enabled.

   Rationale:
   - Keeps media request path fast and non-blocking.
   - Prevents repeated API calls on the same missing key.

   Alternative considered:
   - Generate directly during `/media/...` miss. Rejected due to latency and reliability risk.

3. **Throttle missing-media warning logs**

   Decision:
   - Add key-based warning throttle in `/media/...` serving path.

   Rationale:
   - Removes repeated warning floods while preserving first-signal diagnostics.

   Alternative considered:
   - Demote all misses to debug. Rejected because first miss warning is still useful.

4. **Add optional appearance fields**

   Decision:
   - Add `age`, `height`, `weight`, `eyes`, `skin`, `hair` as optional schema fields and include in prompt context when available.

   Rationale:
   - Better image prompts with zero breakage for existing character files.

   Alternative considered:
   - Keep prompt-only extraction from narrative text. Rejected due to inconsistency and lower control.

5. **Preserve fallback continuity and promotion invariants**

   Decision:
   - Keep existing name-based fallback chain and ensure NPC -> PC promotion continues to resolve by same identity.

   Rationale:
   - Existing behavior already aligns with user expectation and requires no data migration.

6. **Reuse-first recovery for allied NPC missing media**

   Decision:
   - On allied NPC image miss, attempt to materialize `/media/npcs` variants from existing portrait stores before any provider call.

   Rationale:
   - Eliminates unnecessary image-generation spend.
   - Resolves current path contract mismatch between portrait outputs and media-serving inputs.

7. **Canonical identity dedupe**

   Decision:
   - Dedupe by normalized NPC identity key, not by requested filename variant.

   Rationale:
   - Prevents duplicate generation caused by `_thumb` vs full-image misses for same NPC.

8. **Frontend stale-miss cache expiry**

   Decision:
   - Make missing-image cache TTL-based instead of permanent negative cache.

   Rationale:
   - Allows UI to discover assets that appear shortly after async worker completion without requiring full reload.

9. **Always-open full-profile modal for Character Sheet Create**

   Decision:
   - Character Sheet portrait `Create` SHALL always open a profile modal before submitting generation.
   - Modal SHALL prefill current character values and allow player edits each time.

   Rationale:
   - Gives player direct agency to tune appearance and narrative profile at create time.
   - Removes conditional client branching tied to missing-field checks.

10. **Fail-closed required profile completeness for create**

   Decision:
   - Portrait create submissions SHALL require all of the following to be non-empty (trimmed):
     - Appearance: `age`, `height`, `weight`, `eyes`, `skin`, `hair`
     - Personality/Background: `personality_traits`, `ideals`, `bonds`, `flaws`, `backgroundFeature.name`, `backgroundFeature.description`
   - Backend SHALL reject incomplete payloads with a safe structured validation response.

   Rationale:
   - Guarantees complete portrait-driving context for consistent image quality.
   - Keeps API safe for non-UI callers and stale clients.

11. **Persist-before-generate profile update contract**

   Decision:
   - `POST /api/portrait/create` SHALL persist modal profile edits to character JSON before image generation.
   - Portrait generation SHALL consume updated persisted character state.

    Rationale:
    - Keeps Character Sheet and prompt source aligned.
    - Ensures edits made in modal are not transient.

12. **Deterministic portrait version contract across GUI surfaces**

   Decision:
   - Socket/data payload builders SHALL emit per-entity image metadata:
     - canonical image slug
     - deterministic image version (derived from latest mtime across portrait/media candidates)
   - Character Sheet stats payload SHALL emit `_portrait_slug` and `_portrait_version`.

   Rationale:
   - Removes ambiguity from browser/proxy cache behavior when files are replaced in place.
   - Gives all frontend surfaces a shared, deterministic cache-busting key.

13. **Targeted cache invalidation + immediate refresh after portrait mutation**

   Decision:
   - On successful upload/create, frontend SHALL invalidate local image caches for affected slug and refresh Character Sheet, initiative, and party data immediately.
   - Polling loop remains as fallback only.

    Rationale:
    - Prevents stale-then-revert UX caused by mixed local caches and asynchronous polling updates.
    - Preserves existing polling architecture while reducing visible inconsistency window.

14. **Profile-readiness warnings for NPC -> PC promotion (non-blocking)**

    Decision:
    - Promotion preview/apply SHALL surface portrait-profile readiness warnings for missing optional appearance/profile fields.
    - Promotion SHALL continue to hard-block only on schema-critical failures, not optional profile incompleteness.

    Rationale:
    - Keeps current NPC roster promotable without high-friction manual data cleanup.
    - Aligns player sheet quality goals with low-baggage promotion workflow.

15. **Hydrated NPC context before allied auto-generation provider calls**

    Decision:
    - Allied NPC auto-generation SHALL resolve canonical character context before provider generation when possible.
    - If canonical character state is unavailable, fallback MAY use party role/name hints.

    Rationale:
    - Prevents generic portraits caused by `Unknown`/`NPC` placeholder context.
    - Improves role/class alignment for companion portraits without changing miss-path latency contract.

## Risks / Trade-offs

- [Risk] API cost spikes from repeated misses -> Mitigation: dedupe, cooldown, allied-only policy.
- [Risk] Worker failure leaves assets missing -> Mitigation: fail-open fallback chain, no hard user-path failure.
- [Risk] Filename normalization mismatches -> Mitigation: centralize normalization in portrait service.
- [Risk] Corrupt character JSON affects sheet stats path -> Mitigation: keep image fallback independent from stats payload where possible.
- [Risk] Added required profile fields may block create if users leave fields blank -> Mitigation: always-open prefilled modal with clear required-field validation.
- [Risk] Prompt bloat from long personality/background text -> Mitigation: sanitize and length-bound free-text fields before prompt composition.
- [Risk] Inconsistent name normalization across surfaces can map to different portrait keys -> Mitigation: single shared frontend slug helper matching backend normalization semantics.
- [Risk] Version metadata drift between payload builders can cause mixed refresh behavior -> Mitigation: centralize version helper in tabletop socket extension and reuse in all payload paths.
- [Risk] Promotion warning payload changes could break older callers -> Mitigation: additive response fields only, preserve existing success/error keys.
- [Risk] Hydration lookup misses due to name normalization drift -> Mitigation: reuse canonical normalization + fuzzy fallback with fail-open generation.
- [Trade-off] Additional worker state in web process -> Accepted for non-blocking behavior and low implementation complexity.

## Migration Plan

1. Add optional appearance fields in schema/default/manual-create/UI.
2. Add portrait service and create endpoint.
3. Add Character Sheet `Upload / Create` UI behavior.
4. Add missing-media warning throttle.
5. Add allied-only auto-heal worker and enqueue hook.
6. Add regression tests and smoke validations.
7. Add always-open full-profile modal and backend completeness enforcement.
8. Add portrait cache-coherence contract (version metadata + targeted invalidation + immediate refresh hooks).
9. Add promotion-time profile-readiness warnings and appearance-key seeding.
10. Add allied NPC context hydration prior to provider generation.

Rollback strategy:

- Disable allied auto-heal via config.
- Keep warning throttle active.
- If needed, hide/disable create action while retaining upload flow.
- No destructive schema rollback required (optional fields).

## Open Questions

1. Should `age` be strictly string for display consistency, or int/string union?
2. Should create endpoint support style presets in MVP, or defer to later?
3. Should throttled misses emit periodic aggregate summaries per key?

## Verification Strategy

- Compile checks:
  - `python3 -m py_compile core/toolkit/portrait_service.py web/extensions/missing_media_autogen.py web/web_interface.py web/routes/tabletop_party_routes.py utils/character_creation_audit.py`
- Functional checks:
  - Upload flow unchanged.
  - Create flow writes portrait assets and returns success.
  - Allied NPC missing image enqueues one generation task.
  - Non-allied NPC/monster misses do not auto-generate in MVP.
  - Warning logs are throttled for repeated misses.
- Compatibility checks:
  - Existing character files validate unchanged.
  - NPC -> PC promotion preserves image resolution continuity.
