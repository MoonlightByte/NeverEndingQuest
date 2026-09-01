Provenance: Verbatim copy of `/mnt/c/vra-evidence/voice_repair_c76e29a4/a3_c7/A3_C7_VERDICT.md` with this three-line header added.
Source revision: `a9924876d51d23d4d042de4459c3001fcb31ad29`.
Source SHA-256: `13dae28b689faf05ac39f53f9ebc618189d08bd8bab96320c8d764408252f87e`.

# A3-C7 Native Windows Typed-Combat Verdict

Date: 2026-09-01
Branch: `integration/npc-voice-episodic`
Commit: `a9924876d51d23d4d042de4459c3001fcb31ad29`
Provider: OpenAI
Voice model: `gpt-5.6-luna`, reasoning `none`
Game: copied real Keep of Doom encounter `C02-E2`

## Verdict

Core A3 typed-combat round-batch: **PASS**.

One accepted non-empty player action opened a combat-owned round scope, dispatched both
companion T105 calls in parallel after the fresh player sentence, collected both results,
fed one actor-keyed `npcVoiceIntents` map to T096, preserved that map across the player's
attack and damage continuations, committed mechanics once, produced one T097 narration,
closed the encounter, awarded XP once, and returned an actionable main-DM prompt.

The main owner metric passed: the player-facing combat narration reflected the supplied
companion characterization. Elen's advisory said to keep pressure on the armor while
watching the others; the committed scene made her attack stale after the player's killing
blow, and T096 legally adjusted her to defend. T097 rendered her lowering her bow but
remaining guarded and watchful. Thane's advisory emphasized holding the guardian away from
the group; after the kill, T096 adjusted him to defend and T097 rendered him holding ground,
bow poised, scanning the aftermath. No private `thought` text was quoted.

## Real inputs and visible outputs

1. `I strike the Animated Armor with my mace.`
   - Visible changing voice status: 0/2 at 0, 1, 2, and 3 seconds, then ready.
   - T096 requested: `Roll Eirik's mace attack against the Animated Armor.`
2. `I rolled 15 on the d20 for my mace attack.`
   - T096 requested: `Roll damage for Eirik's mace.`
   - No second T105 batch was dispatched for this continuation.
3. `I rolled 8 bludgeoning damage with my mace.`
   - T097 narrated the committed kill and both companions' adjusted guarded behavior.
   - Completion and main-DM handoff followed, then a fresh prompt.

## Round-batch evidence

| Measure | Result |
|---|---:|
| Selected actors | 2 |
| Physical T105 calls | 2 |
| Valid results | 2 |
| Per-call latency | 3.947 s, 4.031 s |
| Sum of per-call latency | 7.978 s |
| Batch wall | 4.049 s |
| Parallel overlap saved | 3.929 s (49.2% of serial sum) |
| T105 tokens | 1,526 + 1,545 = 3,071 |
| Reissues/reaps/completed-invalid/stale rejects | 0 |

The T096 request at protocol sequence 205 contains the full immutable actor-keyed map:

- Scout Elen: say/do/want/thought present; `do` requests a longbow attack on the armor.
- Ranger Thane: say/do/want/thought present; `do` requests a longbow attack while keeping
  the armor focused away from the others.

## Segmented timing

Unix timestamps come from the native headless protocol stream.

| Segment | Start -> end | Wall |
|---|---|---:|
| First action input accepted -> first visible status | seq 173 -> 194 | 0.323 s |
| Parallel T105 batch | telemetry batch | 4.049 s |
| Batch-ready -> T096 request issued | seq 198 -> 205 | 0.909 s |
| First T096 call -> roll-request narration | seq 205 -> 235 | 3.441 s |
| Attack-roll continuation T096 -> damage prompt | seq 288 -> 346 | 3.250 s |
| Damage input accepted -> first status | seq 348 -> 367 | 0.070 s |
| Final T096 attempt 1 (completed invalid) | seq 373 -> 390 | 2.474 s |
| Final T096 attempt 2 (accepted) | seq 394 -> 413 | 2.699 s |
| Accepted T096 -> mechanics persisted | seq 413 -> 438 | 0.098 s |
| T097 request -> committed narration | seq 439 -> 525 | 12.542 s |
| T097 narration -> main-DM next prompt | seq 525 -> 1130 | 38.948 s |
| Final damage input -> next main-DM prompt | seq 348 -> 1130 | 59.397 s |

The completed-invalid row above is a T096 correction attempt, not a T105 completed-invalid
voice result. It therefore does not exercise the Fork-3 T105 failure branch.

## Durable state

- Encounter `C02-E2` is `completion.status = closed`.
- `pendingTurn` and `pendingDelivery` are null after successful delivery.
- Four stable delivery IDs are recorded, including the final turn.
- Fifteen mechanical event IDs are recorded; the last committed slice includes the player
  and both companions.
- Rewards, summary publication, and transcript archive receipts are true.
- XP was awarded once: 200 total / 66 per participant.
- The combat archive and full combat conversation contain the final T097 narration.

## Honest reachability dispositions

| Subcase | Disposition |
|---|---|
| Full typed combat, real parallel T105, T096, mechanics, T097, completion | PASS |
| Fresh player sentence visible to both T105 packets | PASS (T096 map and protocol request) |
| Same map retained across roll/damage continuations without redispatch | PASS |
| Adjust-if-stale behavior after player's killing blow | PASS |
| Two successive newly opened resumed rounds in this fixture | NOT-REACHED (enemy died in the first voiced round) |
| M30 / more than four advised actors | NOT-REACHED |
| Structural 600-second provider reissue | NOT-REACHED |
| T105 completed-invalid one-beat degradation | NOT-REACHED |
| Missing-authority one-beat degradation | CODE-PROVEN by focused C7 matrix; not naturally reached here |
| Load/Reset/quit whole-batch fencing | NOT-RUN in this leg; held for A5 |

## Evidence

- `protocol_live.ndjson` - complete player-visible/debug protocol stream
- `voice_telemetry_live.jsonl` - candidate, physical-call, merge, and batch telemetry
- `runtime_live/debug/combat/agentic_attempts.jsonl` - T096/T097 attempt ledger
- `runtime_live/debug/api_captures/api_calls_master.jsonl` - provider capture ledger
- `runtime_live/modules/conversation_history/combat_conversation_history.json` - durable combat transcript
- `runtime_live/modules/encounters/encounter_C02-E2.json` - final authoritative encounter
- `runtime_live/combat_logs/C02-E2/combat_chat_C02-E2_5c921fb6a86a41eca4a25b74adcbcc66.json` - archived combat transcript
- `c7/dev/C7_AUTHORITY_CHECKS_FINAL.out` - focused scope/missing-authority/supersession matrix

