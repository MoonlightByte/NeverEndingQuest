# Issue #262 no-limits implementation and acceptance

Date: 2026-09-02

Branch: `integration/npc-voice-episodic`

Approved plan SHA-256:
`9d99e24ce012a7ecd8d337735a3c2d51cf390a0446c6e15b81a512656cb6d435`

This record covers slices C0-C5 and the native-Windows, real-OpenAI acceptance
that was reachable without manufacturing campaign state. It makes no TTS,
legacy-retirement, or overall ship claim.

## Implementation ledger

| Slice | Commit | Disposition |
|---|---|---|
| C0 source hygiene | `bbc532c2` | Removed tracked runtime residue and obsolete seed-file repair |
| C0 privacy correction | `4958d92c` | Restored the legitimate `0993430e` fresh-game private-sidecar exclusion after A/B testing caught its accidental removal |
| C1 NPC persistence/context | `93a17bad` | Retired destructive episode, profile, relationship, and voice-contract limits; added T107 fallback provenance and fresh-next-beat retry |
| C2 combat context | `51277bd5` | Retired semantic capability, SRD, exchange, narration-code, T041, and T042 limits |
| C3 world/validation context | `be4df1cb` | Retired hub/module/alignment/history/T014 limits and the lexical T112 pre-screen; deleted zero-reader recall helpers |
| C4 simplifier | `1ba542e1` | Removed stale bounded/truncation claims without adding a path or mechanism |
| C5 docs/evidence | this record | Current flow documentation, sentinel dispositions, development gates, and native verdicts |

The C0 A/B gate found that restoring all of `core/headless/bootstrap.py` to
`origin/main` also removed the independent private-memory copy filter introduced
by `0993430e`. The focused test proved that a fresh game then copied
`npc_agent_state.json` and `legacy_memories.json` from the source tree. Commit
`4958d92c` restores only that privacy boundary. The obsolete seed-file workaround
remains deleted.

## Development gates

- All 19 changed Python files compile with native Windows
  `C:\Python312\python.exe`.
- The full `0214cbdf..HEAD` diff passes `git diff --check`.
- The unchanged React/TTS source is outside this tranche. As an additional
  non-gating check, the frontend source completed `tsc -b && vite build` using
  the repository's already-installed dependency tree; no package was installed.
- Focused D1-D22 and S1 replacement-contract checks passed, including complete
  episode/profile values, T107 fallback promotion, lexical-screen retirement,
  full capability/reference/exchange/code/history values, optional T014 typing,
  and 19/19 baseline-valid sidecars remaining candidate-valid.
- The current ignored NPC test corpus records 125 passed / 29 failures after
  excluding the test module that imports the owner-approved deleted zero-reader
  `recall_episodes` helper. The plan's numerical target of 27-or-fewer failures
  is therefore **NOT MET**. Classification against the prior 137/27 record found
  24 inherited failures, five newly stale assertions that encode the deliberately
  retired retention/fallback behavior, and three former stale assertions that now
  pass. No new product-behavior failure was identified, but that classification
  does not relabel the numerical gate as passed.
- `test_fresh_headless_copy_excludes_private_runtime_but_reopen_preserves_it`
  passes after `4958d92c`. No tracked test was edited and no deleted helper was
  resurrected.

## Sentinel disposition

The raw remaining-hit scan is stored at
`C:\vra-evidence\issue262_native_4958d92c\dev\sentinel_remaining.txt`.
The remaining semantic selections are only the owner-ratified strict top-two
episode recall and one arc-seed pick. The identity alias maximum is an
identity/deduplication guard, not model-context truncation. Episode schema
lengths cover provenance/coordinate identifiers. Other hits are diagnostics,
hash prefixes, time formatting, applied/delivered receipt retention, mechanical
IDs, or retired legacy/compression paths. TTS remains unchanged and assigned
whole to #276.

`relationship_store.py:477` keeps `aliases[-32:]` as identity-integrity history consumed in full by `_identity_names` at line 215; it is preserved, not a model-context cap.
Surviving non-legacy conversation-compression recency windows are assigned to the #276 follow-on; legacy-runtime compression remains owned by #191 retirement.

## Native fixture and provider

Runtime source: this branch after `4958d92c`.

Game fixture: a fresh copy of the authentic Keep_of_Doom acceptance lineage at
`C:\vra-evidence\issue262_native_4958d92c\game_a3`.

Interpreter/provider: native Windows `C:\Python312\python.exe`, OpenAI only.
Every captured call in this run reports `gpt-5.6-luna`, except already-existing
historical fixture records. Commands were submitted one at a time after reading
each response.

## Live verdicts

### A1 - long location and early recall: PASSED with a capture-observability caveat

The party remained in Fallen Barracks (C04) for genuine exploration and
companion conversation. Immediately before departure, the durable segment was
16,177 characters across 17 messages, SHA-256
`9642a03cdbec89c700d385562d0b5ee9f0c3ad2e6969b45bdc0b82bdf259271f`.
The first event identified settled dust, buckled flagstones, split roots, and a
safe path around the weakened floor. Later events covered letters, the burned
trail, shadow residue, and route choice.

Normal C04 -> C06 travel created exactly one new T108 episode (ordinal 139).
It retained the early weakened-floor event and late shadow-residue events in one
grounded record. Its 639-character summary crossed the former 600-character
boundary, and its full fact lines included 115-, 128-, and 151-character values,
crossing the former 120-character boundary. After departure, the player asked
Thane about the first event. Thane accurately recalled the settled dust,
buckled stones, split roots, and safe route; the DM exposed no private thought
and chose no player action.

The live T108 subprocess still does not write its private request to
`api_calls_master.jsonl`. Therefore the complete-source request-capture row is
`BLOCKED (observability)` even though the >16,000 source, exact disk commit, and
early-event recall all fired and passed. Headline/tag/fact/witness maxima not
crossed by the authentic response are `NOT-REACHED`.

### A1b - authentic T113 upgrade: NOT-REACHED

No legally available fresh copied pre-episode save with a bounded one-time
upgrade was present in this acceptance fixture. The known authentic historical
fixture entails a large serial backlog. It was not edited or replaced, and old
evidence was not relabeled as current acceptance.

### A2 - recall/profile/relationship context: PARTIAL PASS

- A concrete post-departure recall reached T112/T105 and was grounded in the
  newly committed early episode: `PASSED`.
- An ordinary present-tense action sharing stored location terms proceeded
  normally and did not narrate a fabricated retrospective memory. The private
  T112 request was not captured, so its exact empty-anchor row is
  `BLOCKED (observability)`.
- Authentic T107 output above the old profile cardinalities, T107
  completed-invalid recovery, 3+ arc seeds, and 4+ relationship events in each
  T105 lens were `NOT-REACHED`.

### A3 - typed combat: PASSED for reached behavior

The copied fixture opened at C02-E2 round 4 with Ranger Thane and Scout Elen.
One immediate Mace action produced the full typed lifecycle:

1. a parallel two-actor T105 batch with changing 0/2 and 1/2 progress;
2. a T096 player-owned attack request;
3. accepted attack roll 17;
4. a T096 player-owned damage request;
5. accepted damage 6;
6. exact committed defeat of the Animated Armor;
7. one stable T097 narration grounded in committed mechanics and companion
   voice;
8. exact-once XP 6825 -> 6891, combat closure, and an actionable main prompt.

`debug/combat/agentic_attempts.jsonl` records the live T096/T097 calls and
OpenAI model. The real sheet had four capability candidates and no SRD reference
match in this particular turn. Consequently the 25+/13+/9+ capability rows,
9+ exchanges, 25+ correction codes, and T041/T042 extrema are `NOT-REACHED`.

### A4 - world context: PARTIAL PASS

Real C02 -> C04 and C04 -> C06 transitions completed with the three-agent
departure/arrival/stitch chain and exact five-minute clock advances. The C04 ->
C06 validation request contained the complete chronological C04 exchange set
(well above five prior messages), the current travel turn once, and no future
message: the reached history row passed. Authentic >3 hub/service/alignment and
long T014 update boundaries were `NOT-REACHED`.

### A5 - TTS: OUT-OF-SCOPE

No TTS verdict is claimed. #276 owns the complete producer/four-consumer change.

### A6 - integrated regression: PASSED

The typed combat, grounded companion recall, ordinary inspection, and two
transitions all returned control to the player. Narration used second person,
did not expose private thoughts, did not invent a player roll or action, and
kept HP/XP/location/time aligned with authoritative files. No technical cap text
reached the player.

### A7 - boundary matrix

| Family | Live disposition |
|---|---|
| T108 source above 16,000 + early recall | PASSED behavior; request capture BLOCKED on observability |
| T108 summary above 600 | PASSED (ordinal 139 = 639 chars; prior ordinal 138 = 721 chars) |
| T108 fact line above 120 | PASSED (ordinal 139 includes 128/151; prior ordinal 138 includes 122/141) |
| T065 five-plus history messages | PASSED |
| typed clarification and immutable voice map | PASSED for attack+damage chain |
| T112 concrete early recall | PASSED |
| T112 exact empty-anchor ordinary-action capture | BLOCKED on private request observability |
| all other A7 old-boundary maxima | NOT-REACHED through authentic traffic |

Development checks prove preservation at the other boundaries but are not
relabeled as live acceptance.

## Observed independent liveness event

During the C04 Arcana-result beat, three parallel conversation-compression
provider children received no response headers. Native `py-spy` showed each in
`ssl.read -> httpcore._receive_response_headers -> OpenAI create`, while the
engine waited in `conversation_compressor_parallel._process_conversation_history`
and worker threads waited in `call_live_provider.communicate`. There was no Git
child, file lock, stdin wait, or T105 involvement. At the configured 600-second
transport boundary the original children were reaped and the same player beat
continued coherently without restart or duplicate input. This proves structural
recovery but also records a roughly ten-minute player-silent compression wait;
it is not repaired or attributed to #262 here.

## Evidence

Durable local root:
`C:\vra-evidence\issue262_native_4958d92c`

Key files:

- `game_a3/modules/conversation_history/chat_history.json`
- `game_a3/data/companion_memories/episode_ledger.json`
- `game_a3/data/companion_memories/npc_agent_state.json`
- `game_a3/debug/api_captures/api_calls_master.jsonl`
- `game_a3/debug/combat/agentic_attempts.jsonl`
- `game_a3/modules/logs/headless_raw.log`
- `forensics/pyspy_57108.txt`
- `forensics/pyspy_43272.txt`
- `forensics/pyspy_804.txt`
- `dev/sentinel_remaining.txt`
- `SHA256SUMS.txt`

The runtime exited cleanly through the supported out-of-band quit command. No
acceptance repair, state edit, synthetic provider result, or model substitution
was used.
