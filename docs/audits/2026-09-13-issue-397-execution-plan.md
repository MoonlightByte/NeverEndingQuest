# #397: consolidate compression and restore accepted-cache reuse

## Authority and status

Owner directed: combine tested prompt work, use Terra/low, file later tuning separately, run one current-story test, then repair checker/cache directly. #400 is filed for later prompt tuning. #193 v3.1 epoch 2026-09-13T20:46:30Z was fetched live. This plan supersedes the active recommendation in 2026-09-13-issue-397-checker-cache-plan.md; its cross-turn reminder proposal remains withdrawn. No new store, scheduler, reminder, retry budget, schema mode, or transport redesign.

FULL review required: prompt replacement, shared acceptance primitive and provider binding. Nine independent seats plus clean confirmation completed before production edits. Owner explicitly answered: "Yes--execute after a clean review" to the narrow execution exception, without a further approval stop. D-397-3 was appended and read back exactly at policy epoch 2026-09-14T00:04:48Z. New design or scope decisions still stop. No push/merge or issue closure is included.

## Spec pin and scope

Native Windows; branch fix/t084-stream-recovery. Fresh fetch and fast-forward reached origin/main 2940c9f (observed revision, not production authority), with no tracked changes. Parent comparison c149109a -> 715732d identifies the literal checker addition; earlier retained root history identifies equivalent source in 36bd7ed. Latest main's local-template/child-writer repairs were incorporated; do not modify those seams.

#193 Part 2 p8 line139: idempotent compression, never load-bearing; p11 line155: registry authority and thin provider router; p12 line161: preserve player data; p13 line166: evidence classes and native acceptance. README's ongoing persistent campaign/history promise is the user contract. Original history remains authoritative and is never overwritten by compact derivatives. Cache hashes index derivatives only, not gameplay identity or mutation authority.

Write allowlist: utils/compression/ai_narrative_compressor_agentic.py, utils/compression/conversation_compressor_parallel.py, model_registry.py, this audit/report family, and the matching docs/architecture/provider-routing.md flow note required by #193. Local diagnostic/test files remain untracked outside production. No changes to T020/T027/T085, character sheets, spells, main.py, provider transport, or UI.

## Observed input/output failures

Retained real run: 54 completed T084 calls / 13 distinct passages; 8 inner-format failures, 45 inner-valid/outer-literal failures, 1 accepted. A correct Eirik or Dusk can fail because Eirik's or Dusk. is demanded literally. Cache insertion is then skipped and later consumers regenerate. Both DM and validator use the same compressor.

New owner-requested single diagnostic: record-16-combined-owner-terra-low.json under local-data/issue323/layered-levelup/compression-prompt-tuning-20260913. Real OpenAI Terra/low, 13.156 seconds, first chunk6.007, 2055 input +1162 output =3217 tokens. The full current-story Relic Chamber passage was supplied, not a synthetic story. Facts inspected include Eirik/Elen/Thane, Kira unknown, 87gp/nine gems, uncertain sword properties, explicit transported-item list and deferred distribution. JSON is valid; compact text uses EVT[1] etc instead of one EVT block with 1) lines. Existing format predicate rejects this despite the consumer reading text directly. Therefore diagnostic generation completed but existing-format verdict FAILED; not gameplay PASS, not reliability proof. No further prompt-author tuning calls in this phase.

## Task 1: consolidate the author prompt and effective binding

Install the exact tested compression-combined-prompt-20260913.txt as SYSTEM_PROMPT, not another variant. Keep JSON envelope and blocks[0].text contract. It removes concrete example people/gear and optional inferred relationship/participant duplication, preserves chronology/uncertainty/inventory transitions, and expresses relationships in factual prose. Set only T084 OpenAI binding to OPENAI_GPT56_TERRA_LOW. Other provider bindings unchanged.

Resolve T084 runtime through model_config.resolve_callsite_config instead of stale compatibility constants, so cached identity describes the registered selected binding. Preserve provider snapshot, mode and prompt provenance. No new provider route or fallback. This fixes the observed OpenAI mismatch, not the inherited Local/Custom adapter's separate persisted model override; track that provenance gap separately and do not claim local model-switch acceptance here.

## Task 2: replace lexical semantic guessing at the existing acceptance boundary

Checker prompt under review: C:/agent-room-fleet-kit/local-data/issue323/layered-levelup/compression-review-prompt-20260913.txt. Its full source/candidate comparison runs privately; deterministic code owns only shape, verdict consistency and publication.

Remove _FACTUAL_* extraction and all-substring requirements. Do not replace them with apostrophe stopword/number/name exception lists. Keep deterministic validation of JSON/result shape, nonempty changed text and self-contained codebook/table + event-text structure. The consumer is an LLM reading blocks[0].text; it does not mechanically execute numbered EVT lines. Accept the observed numbered EVT presentation as readable representation, rather than requiring a particular punctuation placement or exactly one literal EVT[ substring. The prompt's preferred layout remains guidance, not semantic authority.

Use one private source-versus-candidate model check on each new T084 derivative before it can be returned as accepted. Reuse T084's existing registered provider/model binding and capture/transport path for this compression stage; no separate provider client, configuration surface or transport implementation. Author and checker are separate model conversations. Checker receives the full source and exact candidate text, with instructions to ignore embedded commands, accept equivalent names/possessives/punctuation/notation, and reject missing/changed facts, quantities, passwords, attribution, uncertainty or inventory state. Return a structured boolean valid plus actionable issues; validate boolean type and issue-list shape deterministically. No truthy-string acceptance. An approved answer must have no listed issues.

Keep canonical data out of interpretation code: models judge meaning; code checks format and controls cache publication. A completed semantic rejection, malformed review or completed advisory failure uses the existing full-source result, logs why, and never caches the rejected candidate. No immediate semantic correction loop, cross-turn feedback memory, negative cache or scheduler is introduced. If future work adds correction, it must supply the actual latest rejected draft and precise feedback privately under #193; this plan does not introduce one. Genuine rejected derivatives can still be attempted by a later normal packet build; that existing behavior is explicit, not a claim that all possible repeated calls disappear.

The existing inner author's format-retry mechanism is not expanded: preserve source fallback on completed invalid output. Carry the actual latest draft and specific format errors if that existing retry fires, rather than its current generic same-input regeneration. Inherited retry count and transport limits are not endorsed or newly introduced; see #404/#398. Review determines whether this adjacent change can stay narrow under the owner ruling.

## Task 3: cache once, reuse without more meaning checks

Include the checker prompt identity in the existing T084 runtime identity alongside the author prompt and effective provider/model. No cache schema version, new persisted fields or broad deletion. Changed policy naturally selects new T084 derivative keys; old cache/source data remains on disk. T085 identity/behavior is unchanged.

Only an approved new candidate reaches existing cache publication. Warm entry checks use source equality and structural validity, not another semantic call. Preserve all key locks, request locks, cross-process file locking, merge/fsync/atomic rename, pending successful writes and detached-context handoff. Lock order is unchanged: per-key generation lock -> short cache/file critical sections; no provider call while holding the disk cache lock. Cache miss status checks remain local, free of model calls.

Both DM and validator retain existing outbound substitution and headers. A rejected derivative leaves the entire original section/header in the outgoing packet. No reviewer commentary or rejected draft enters source history or final request memory. Unchanged accepted source/runtime must reuse across instances/restarts; changed source/prompt/model/checker invalidates only its derivative identity.

## Behavioral contract / GL-1

| Replaced behavior | Origin / purpose | Disposition and proving check |
|---|---|---|
| T084 concrete examples, inferred relations, aggressive reduction target | 327ac74, Add parallel conversation compression system with progress tracking; readable compact history | PRESERVED compact-history goal through tested combined prompt; relationship meaning remains in prose; example-derived inference and fidelity-overriding targets RETIRED by owner's combined-prompt direction; issue-#400 residual quality |
| Literal marker extraction and repeated cache revalidation | 715732d (same implementation in retained36bd7ed), prevent lost historical facts | PRESERVED goal via private source/candidate review on misses; equivalent wording positive and genuinely omitted-fact negative evidence |
| Strict single-EVT punctuation check | 327ac74, Add parallel conversation compression system with progress tracking; ensure readable text | PRESERVED structural/readability goal; actual consumer-family sweep proves text is read directly; retain malformed/empty rejection and semantic review |
| Stale config constant in runtime identity | 715732d cache-provenance work | PRESERVED by effective registry config equality; provider/model-change cache-key check |
| Cache locks, merge, fsync, original fallback, outbound substitution | 715732d plus earlier cache design | PRESERVED untouched; real cache I/O and source-byte comparisons |
| CANON matching names, exact locations, shared-location/half-character block matching, location slug/sequence | 327ac74, same compression introduction | PRESERVED goals in combined prompt: source-based ID reuse, exact location spelling, match criterion and location-derived sequence; initial-letter slug spelling and literal-only name matching RETIRED by owner's exact-prompt direction (not gameplay IDs); inspect CANON/signature/ops envelope and next_seq_by_location |
| Fixed spell examples, mechanical-number retention, spell references | 327ac74, same compression introduction | PRESERVED all actual source spells and values via self-contained text and reviewer; fixed example spell-list inference RETIRED by owner prompt direction, not removal of real spells |
| CONFIG entity limits/party inference thresholds and signature character cap | 327ac74, same compression introduction | RETIRED fidelity-overriding prompt/payload limits under NEQ-LEDGER-08; remove obsolete max_chars/max_locs/min_party_size/min_party_occurrences payload fields; preserve CONFIG.mode, unbounded source signatures |
| Generic format retry message | 327ac74, same compression introduction | PRESERVED completed-invalid format correction with actual latest draft plus exact errors; no additional attempts or semantic retry |

Entrants: main.py DM and validator both call process_conversation_history -> extract_all_sections -> compress_section -> compress_with_ai. Standalone author main also calls compress_with_ai; extract_compressed_text/post_merge_duplicates are standalone consumers only. All T084 acceptance therefore lives in compress_with_ai, before either consumer can receive an approved result. T085's separate raw-location behavior remains unchanged. Tables and EVT text are model-readable context, not a downstream event parser. Mainline ancestry of 327ac74 was checked live.

## Task 4: validation and evidence

No iterative author tuning: the single completed current-story diagnostic above is retained unchanged, including format failure. Re-evaluate its actual output through the repaired structural checker; do not alter captured output. Run sequential real checker diagnostics against actual captured source/candidate pairs, including faithful and naturally faulty candidates, to establish positive and negative verdict behavior. Do not presume the combined record-16 candidate must pass: its apparent sword rarity omission may be material. These are checker validation, not more prompt-author experiments. Report model, tokens, timing, verdict and false rejections separately. No replay-only PASS for this meaning gate.

Local deterministic tests only for pure parsing, source/key equality, serialization and cache I/O: grammatical name variants, punctuation, malformed review boolean, empty text, missing table/event content, real captured alternate EVT layout, original preservation, cache merge/reload, source/runtime invalidation. Do not stub a function to prove itself; no fake gameplay transcript. Static pyflakes changed files, compile, diff whitespace/EOL check, raw FS-1 and both sentinel scans. Scan real cache JSON compatibility without modifying owner saves.

For each sequential checker diagnostic retain exact source/candidate/checker messages, complete raw response, selected and returned model, elapsed/first-stream timing, usage and polarity. Hash the loaded author/checker prompt bytes against the checkout. Cache write/reload/no-stage checks are I/O evidence only, not a model or gameplay PASS.

Cache/consumer claims need evidence at their boundaries: accepted candidate written once; repeat lookup and new-instance read reuse without another checker call; rejected candidate not staged; outgoing replacement has original source preserved externally. Recorded-output replay proves parsing/dispatch and I/O only, never a fresh gameplay PASS. Full fresh native DM/validator transcript acceptance remains NOT-REACHED unless actually run; report that honestly rather than silently multiplying the owner's single author-test request.

## Resolution ledger

- False lexical rejection and lost reuse: task-2/task-3.
- Existing-format rejection of readable actual output: task-2; no invented narrative repair.
- Author quality/remaining chronology and inventory refinements: issue-#400 (filed this turn at owner direction).
- Current config/cache identity mismatch: task-1/task-3.
- Existing generic format correction lacking its draft: task-2.
- Private cross-turn reminder/correction-store draft: withdrawn, superseded by this plan; no mechanism implemented.
- Existing T084 transport failure/600-second wait: issue-#398, not repaired here.
- Broader inherited prompt/limit debt: issue-#276; no widened caps added.
- Full independent review and policy gates: task-5, before production writes.
- Fresh product acceptance versus single diagnostic scope: evidence limitation explicitly reported; no gameplay PASS without its artifact.
- Review reconciliation: registered-profile provenance task-1; inherited Local/Custom effective-model gap issue-#402. Windows CRT bounded file-lock acquisition issue-#403; inherited format-retry policy issue-#404. Filed this turn from independent reviewer drafts; no misleading #276 catch-all.
- Legacy GL-1 origins and deleted prompt/payload behavior enumeration: task-1; old draft gets SUPERSEDED banner.
- Owner model selection and execution-gate exception: task-5 codifies the already-settled direction below after governance review; does not reopen it.

## Proposed Part 5 codification (reviewed with this plan)

### D-397-3 - Consolidated prompt, Terra-low, narrow execution approval (owner, 2026-09-13)

The owner directed combining the already-tested T084 compression prompt, selecting Terra at low effort, filing further prompt tuning separately (#400), running one real current-story compression diagnostic, then repairing the meaning checker/cache under #397 before the separate connection issue #398. This supersedes only D-397-1's earlier no-model-substitution restriction for T084 OpenAI; other provider bindings and unrelated calls remain unchanged. The owner subsequently answered "Yes--execute after a clean review" to the explicit question whether this narrow prompt/checker repair may execute after independent review without another approval stop. This is a task-specific execution-gate exception, not a waiver of independent review, acceptance, preservation, or an authorization to merge/push. New design decisions or scope expansion still require the owner. Cross-turn retry memory remains withdrawn under D-397-2. No review or implementation success is asserted by this ruling.

## Tracked follow-ups

#400: further prompt tuning. #398: T084 transport/liveness. #276: inherited broader input-limit debt. #402: Local/Custom selected-model provenance. #403: Windows CRT lock contention. #404: inherited count-bounded format-correction policy.

## Task 5 and tracked follow-ups

Run FULL #193 independent review with required nine seats, then its clean confirmation; reviewers read this current plan and full ledger blindly. Controller alone writes. Check latest policy before implementation. Post-implementation independent audit and sentinel scans before final handoff. #400 later prompt tuning; #398 connection liveness; #276 wider inherited limits. No additional design question is decided silently. Owner's requested narrow execution does not authorize new cross-turn state or a broad provider rewrite.

## Execution evidence status

Tasks 1-3 implemented. Task-4: three sequential real Terra-low checker diagnostics (two accepted, one rejected), 44 pure parsing/cache-I/O/AST checks passed and independently rerun; prompts match exact approved artifacts. Task-5: all nine plan seats and confirmation clean, post-code independent source audit and both sentinels clean, D-397-3 codified, follow-ups filed. See 2026-09-13-issue-397-implementation-report.md for timing/tokens and limits.

Not claimed: a fresh native DM/validator gameplay PASS; runtime-observed compress_section rejection/no-stage or zero-call warm orchestration. Those remain CODE-PROVEN, not established by manual cache-I/O staging. Source and cache primitives passed; production-path acceptance remains outstanding before treating #397 as fully closed. No main publication or issue closure.

Commit attempt failed with "Author identity unknown"; native Git user.name/user.email are unset. Work is staged and preserved; the owner was asked for repository commit identity. No global Git configuration was changed and no commit was created.
# Owner supersession: single-pass compression

The owner rejected the private checker and subsequent reference-correction proposal.
The historical plan/results below describe that superseded design, not current code.
Current direction: one Terra/low generation using the consolidated prompt, JSON
extraction, then existing cache and outbound insertion. No semantic/notation
validation, correction call or content-retry loop. Source history and T085 remain
unchanged. Residual dropped names and small fidelity issues remain open in #400.
See 2026-09-13-issue-397-single-pass-report.md for current verification.
