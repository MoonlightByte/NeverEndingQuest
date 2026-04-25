# Tasks: toolkit-semantic-shortform-destination-normalization

## 1. Semantic Short-Form Contract
- [x] 1.1 Define the deterministic boundary for collapsing unresolved short-form destination phrases against already-resolved authored aliases.
- [x] 1.2 Define the ambiguity boundary so competing short-form matches remain blocking.
- [x] 1.3 Define the provenance fields or equivalent reporting detail needed for reviewable normalization.

## 2. Deterministic Normalization Implementation
- [x] 2.1 Implement short-form destination normalization in the semantic-authority path using already-resolved authored aliases from the same module.
- [x] 2.2 Preserve unresolved state for phrases that do not have exactly one deterministic anchor.
- [x] 2.3 Ensure normalized short-form phrases no longer surface as semantic publishability blockers.

## 3. Reporting And Finisher Alignment
- [x] 3.1 Preserve structured reporting detail so normalized short forms remain inspectable in publishability output.
- [x] 3.2 Preserve the existing mixed-failure contract for true semantic blockers.
- [x] 3.3 Verify modules with only media debt plus normalized short-form phrases become eligible for explicit media handoff semantics.

## 4. Regression Coverage
- [x] 4.1 Add a regression covering `Murder_at_the_Drowning_Lass` short-form collapse for `oath chamber` and `remnant sanctuary`.
- [x] 4.2 Add an ambiguous counterexample regression where the phrase remains unresolved and blocking.
- [x] 4.3 Add or update finisher/reporting regression coverage to prove media-only vs mixed-failure behavior remains unchanged.

## 5. Verification
- [x] 5.1 Run targeted semantic-authority regression tests.
- [x] 5.2 Run targeted publishability/finisher regression tests.
- [x] 5.3 Capture a canary result showing semantic blockers cleared for `Murder_at_the_Drowning_Lass` while media handoff remains explicit.
