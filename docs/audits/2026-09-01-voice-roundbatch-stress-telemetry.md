Provenance: Verbatim copy of `/mnt/c/vra-evidence/voice_repair_c76e29a4/stress/CONSOLIDATED_STRESS_TELEMETRY_REPORT.md` with this three-line header added.
Source revision: `a9924876d51d23d4d042de4459c3001fcb31ad29`.
Source SHA-256: `dcecf722a1f96410a9f8ab074c8dfddfe9770418669818d735b553b62a0a7215`.

# NPC Voice Round-Batch Stress and Telemetry Report

Date: 2026-09-01
Revision: `a9924876d51d23d4d042de4459c3001fcb31ad29`
Provider: real OpenAI (`gpt-5.6-luna`, reasoning `none` for T105)
Runtime: native Windows headless product path

## Overall disposition

The typed round-batch voice path passed every product-legal combat tier available in the
preserved campaign inventory: five measured player rounds across three scenario campaigns,
plus one resumed roll-continuation completion. One- and two-companion T105 batches completed
in parallel, reached the single T096 adjudication, and were truthfully incorporated by T097.

The required 6-party/9-enemy ceiling was **BLOCKED: no legal fixture available**. The
inventory contained no product-created playable state with that roster. The largest
preserved encounter was a 4-party/3-enemy legacy T045 fixture, which stopped on #267 before
a live voice result could be injected. A 5-party/2-enemy Pumpkin King snapshot had the human
PC unconscious and was not a legal player-round fixture. No party, encounter, HP, initiative,
or state was fabricated or edited.

## Scenario inventory and verdicts

| Scenario | Product-legal provenance | Actors | Measured player rounds | Verdict |
|---|---|---:|---:|---|
| Keep of Doom C02-E2 | authentic active campaign copy | 3 party / 1 enemy | 1 | PASS: two voices collected together; stale attacks adjusted to defend; completion/XP/archive/handoff exact once |
| Thornwood RO06-E1 | authentic product-created active campaign | 2 party / 2 enemies | 2 | PASS: one voice each round; combat completed |
| Pumpkin King D15-E1 | official save at D14, legal travel and authored encounter | 3 party / 3 enemies | 2 | PASS: two voices each round; Sacred Flame and Cure Wounds continuations completed |
| Thornwood TW04-E1 | authentic active campaign copy | 3 party / 1 enemy | resumed roll continuation | PASS: damage continuation, companion action, completion/XP/handoff; opening voice dispatch had already occurred before the copied boundary, so no new T105 batch |
| Kharos V07-E3 | authentic restored unversioned encounter | 4 party / 3 enemies | first resumed action | A4 live injection NOT-REACHED; resumed omission polarity PASS; player continuation FAILED on #267 legacy T045 runtime |
| Pumpkin King 5-party snapshot | authentic preserved snapshot | 5 party / 2 enemies | 0 | BLOCKED: human PC already unconscious; not a legal player turn |
| Requested ceiling | no product-created fixture found | 6 party / 9 enemies | 0 | BLOCKED: no legal assembly available; no state editing permitted |

## Combat round timing dataset

Times below exclude human think time between roll prompts. `Round processing` is the sum of
the engine-processing intervals for the submitted action and its required roll continuations.
`Deterministic/other` is the residual after subtracting captured T105, T096, and T097 model
durations; it includes reconciliation, commits, delivery, enemy-window processing, and, on
completion rounds, final outcome/handoff work. Input-to-first-status acknowledgement was
visibly immediate in every live run, but the original driver did not timestamp the send edge;
that segment is therefore reported as `UNKNOWN (< one observed event cycle)` rather than
inventing precision.

| Scenario / round | Party | Voice batch | T096 total | Deterministic/other | T097 | Round processing | Input->ack |
|---|---:|---:|---:|---:|---:|---:|---|
| Keep of Doom accepted round | 3 | 4.049 s | 9.716 s (includes one typed correction) | 16.576 s | 2.813 s | 33.154 s | UNKNOWN; immediate visually |
| Thornwood RO06-E1 round 1 | 2 | 3.774 s | 9.998 s across attack/damage continuations | 4.492 s | 2.233 s | 20.497 s | UNKNOWN; immediate visually |
| Thornwood RO06-E1 round 2 | 2 | 3.835 s | 9.265 s across attack/damage continuations | 23.080 s including completion/handoff | 2.421 s | 38.601 s | UNKNOWN; immediate visually |
| Pumpkin King D15-E1 round 1 | 3 | 4.401 s | 11.155 s across spell/damage continuations | 4.352 s | 3.187 s | 23.095 s | UNKNOWN; immediate visually |
| Pumpkin King D15-E1 round 2 | 3 | 4.367 s | 7.826 s across spell/healing continuations | 7.122 s | 3.406 s | 22.721 s | UNKNOWN; immediate visually |

The separate TW04-E1 copied continuation took 2.331 s to request damage and 26.625 s from
damage submit through combat completion and main handoff. It is excluded from full-round
aggregates because the accepted-action and voice-dispatch boundary predates the copy.

### Aggregates by party size

Small samples use ordinary median and nearest-observed p95/max; no statistical generality is
claimed.

| Party size | Rounds | p50 | p95 | max |
|---:|---:|---:|---:|---:|
| 2 | 2 | 29.549 s | 38.601 s | 38.601 s |
| 3 | 3 | 23.095 s | 33.154 s | 33.154 s |
| All typed measured rounds | 5 | 23.095 s | 38.601 s | 38.601 s |

## Voice-batch wall curve and overlap proof

| Batch | Actors | Per-call latency | Batch wall | Serial sum | Parallel saving | Tokens |
|---|---:|---|---:|---:|---:|---:|
| `011250c3b9b3f638` | 1 | 3.759 s | 3.774 s | 3.759 s | n/a | 1,443 |
| `382a3398b2d69461` | 1 | 3.831 s | 3.835 s | 3.831 s | n/a | 1,537 |
| `72503a2759ae05db` | 2 | 3.947 / 4.031 s | 4.049 s | 7.978 s | 49.2% | 3,071 |
| `d6eb925411267ab6` | 2 | 4.276 / 4.394 s | 4.401 s | 8.670 s | 49.2% | 3,227 |
| `69cc4e3a2cc59f85` | 2 | 3.902 / 4.361 s | 4.367 s | 8.263 s | 47.2% | 3,538 |

| Voice actors | Batches | p50 wall | p95 wall | max wall |
|---:|---:|---:|---:|---:|
| 1 | 2 | 3.805 s | 3.835 s | 3.835 s |
| 2 | 3 | 4.367 s | 4.401 s | 4.401 s |

The two-call batches finish within 7-18 ms of their slowest physical call, directly proving
parallel overlap rather than serial execution. Dollar cost is **UNKNOWN** because every
capture reports `costDisposition=unknown`; token counts above are the authoritative available
cost proxy. Combat T105 physical-call total across these five batches is 12,816 tokens.

Two earlier Pumpkin King OOC batches took 23.602 s (six physical calls) and 19.015 s (four
physical calls) because their classification calls needed completed-invalid correction
attempts. They are retained as lifecycle evidence but excluded from the combat wall curve.

## Lifecycle and authority observations

- Successful combat T105 calls: all valid on attempt 1; no transport reissue, reap, stale
  rejection, or completed-invalid actor omission occurred naturally.
- Keep of Doom T096: one completed-invalid intent was corrected while reusing the same voice
  map; no second T105 batch launched.
- Kharos legacy resume: three selected actors received typed `missing_authority`, zero provider
  children launched, and the empty batch completed in 6 ms. This is the owner-ratified resumed
  first-beat omission, not evidence of live injection.
- The 600-second structural transport-reissue branch, T105 completed-invalid one-beat degrade,
  and M30/>4-voice dispatch remained **NOT-REACHED** naturally. They are not relabeled as PASS.
- Save/Load round-trip core remained PASS from A5; no stress scenario naturally fired a pending
  batch during Load/Reset/quit.

## Owner metric: does the DM narrate the spoon-fed data?

**PASS on every typed voiced round.** The actor-keyed map arrived in the single T096 request.
T096 kept the player's action authoritative, adjusted only NPC actions made stale by ordered
resolution, and preserved the supplied motive/voice. T097 narrated committed actions first,
wove visible companion behavior/dialogue naturally, and did not expose private thought text.
Roll continuations did not redispatch or duplicate voice work.

The typed Sacred Flame control is especially relevant to the A4 stop: D15-E1 accepted the
spell declaration, requested player-owned damage, consumed the continuation, resolved the
save, narrated the committed result, and returned to the next prompt without asking the player
for the code-owned spell DC. Protocol sequences: 3214, 3275, 3302, 3406, 3574.

## Legacy A4 disposition

Issue: https://github.com/MoonlightByte/NeverEndingQuest/issues/267

The V07-E3 Sacred Flame chain is a `T045-legacy-runtime` defect and is explicitly
`resolved-by-retirement`. Fork-1a and D-VR-13b prohibit a legacy-only fix. The Phase-B
retirement skeleton now cites #267 as mandatory GL-1 evidence that forward migration must
cover canonical spell-DC and continuation behavior. A4 live voice injection remains
NOT-REACHED, while its resumed missing-authority omission polarity is PASS.

## Evidence roots

- A3 Keep of Doom: `/mnt/c/vra-evidence/voice_repair_c76e29a4/a3_c7`
- Thornwood 2-party/2-enemy: `/mnt/c/vra-evidence/voice_repair_c76e29a4/stress/s0_2party_2foes`
- Pumpkin King 3-party/3-enemy: `/mnt/c/vra-evidence/voice_repair_c76e29a4/stress/s2_3party_2foes`
- Kharos legacy: `/mnt/c/vra-evidence/voice_repair_c76e29a4/stress/s3_4party_3foes_legacy`
- Thornwood resumed continuation: `/mnt/c/vra-evidence/voice_repair_c76e29a4/stress/s4_3party_1foe`
- A4/A5 verdict: `/mnt/c/vra-evidence/voice_repair_c76e29a4/a3_c7/A4_A5_VERDICT.md`

## Final verdicts

- Typed round-batch architecture at legally available one- and two-companion sizes: **PASS**.
- Main-DM use of voice data: **PASS**.
- Parallelism: **PASS**, directly timed.
- Typed Sacred Flame shape: **PASS**.
- A4 legacy live injection: **NOT-REACHED**; legacy continuation **FAILED #267**, retirement-only.
- 4+ voice/M30 and 6-party/9-enemy live scale: **BLOCKED / NOT TESTED**, no legal fixture.
- Overall feature ship: **OWNER-OPEN (D-VR-9)**.
