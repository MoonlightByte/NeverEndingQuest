## 1. Scene Authority Metadata Contract
- [x] 1.1 Add additive schema support for location-level `sceneAuthority.presentSceneAnchors` metadata.
- [x] 1.2 Keep the metadata contract minimal: require only `anchorId` and `aliases` for the initial rollout.
- [x] 1.3 Preserve full backward compatibility for legacy location files with no `sceneAuthority` metadata.

## 2. Metadata-First Runtime Evaluation
- [x] 2.1 Refactor `utils/narrator_location_exclusivity_guard.py` to build a module-local present-scene anchor index from authored metadata.
- [x] 2.2 Prefer metadata-driven exclusivity checks when anchors are authored.
- [x] 2.3 Keep the existing Thornwood-specific guard as fallback when metadata is absent.

## 3. Low-Risk Migration Slice
- [x] 3.1 Backfill Thornwood NC05-exclusive anchors using the new `sceneAuthority.presentSceneAnchors` contract.
- [x] 3.2 Verify Thornwood behavior remains identical after metadata adoption.
- [x] 3.3 Do not broaden module backfill beyond Thornwood in this change.

## 4. Route-Block Grounding Stability
- [x] 4.1 Preserve existing authored-exit grounding behavior using current low-risk metadata surfaces (`connectivity`, `transition_hints`, existing blocker-like keys).
- [x] 4.2 Avoid introducing a broad new blocker ontology unless current surfaces prove insufficient.
- [x] 4.3 Add regression coverage showing metadata-first scene authority does not regress authored-exit grounding.

## 5. Prompt, Tests, and Verification
- [x] 5.1 Update prompt/validator contract text to describe authored scene authority metadata in generic terms rather than Thornwood-only language.
- [x] 5.2 Add tests for metadata-present generic exclusivity, legacy fallback exclusivity, and foreshadow-vs-present distinction.
- [x] 5.3 Run focused compile/tests and module validation, then validate the OpenSpec change.

SHOULD: Keep this slice infrastructure-first and migration-safe.
SHOULD: Treat broad multi-module backfill as a follow-up once the metadata contract is proven stable.
