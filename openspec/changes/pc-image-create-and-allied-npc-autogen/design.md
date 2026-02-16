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

## Risks / Trade-offs

- [Risk] API cost spikes from repeated misses -> Mitigation: dedupe, cooldown, allied-only policy.
- [Risk] Worker failure leaves assets missing -> Mitigation: fail-open fallback chain, no hard user-path failure.
- [Risk] Filename normalization mismatches -> Mitigation: centralize normalization in portrait service.
- [Risk] Corrupt character JSON affects sheet stats path -> Mitigation: keep image fallback independent from stats payload where possible.
- [Trade-off] Additional worker state in web process -> Accepted for non-blocking behavior and low implementation complexity.

## Migration Plan

1. Add optional appearance fields in schema/default/manual-create/UI.
2. Add portrait service and create endpoint.
3. Add Character Sheet `Upload / Create` UI behavior.
4. Add missing-media warning throttle.
5. Add allied-only auto-heal worker and enqueue hook.
6. Add regression tests and smoke validations.

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
