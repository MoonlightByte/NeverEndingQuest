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

## Owner-authorized constructed-scale addendum

Date: 2026-09-01
Revision exercised: `dcc172f034b52c43b2a019fc551f4cca3c489192`

The owner subsequently authorized schema-valid fixture construction through
`party_tracker.json` plus one validated character file per member. No encounter,
initiative ledger, combat HP, roll, or event was edited. The official Thornwood module was
entered through ordinary play, and `createEncounter` naturally produced TW05-E1 with six
living companions and the authored full garrison: four sentries, four warriors, and Captain
Gorvek. The resulting encounter contained one human PC plus 15 automatic actors.

Every constructed character file validated against `schemas/char_schema.json`, and the party
tracker validated against `schemas/party_schema.json` before launch. A first low-HP fixture was rejected as
inadequate after the opening initiative window reduced the number of living companions. The
final fixture used six independently identified, schema-valid 50-HP companion sheets and a
schema-valid 41/47-HP player sheet; all were alive when the encounter opened.

The post-run integrity scan found that the product writer had removed the required
`worldConditions.weatherConditions` field from `party_tracker.json`. Character validation,
the six-member roster, the 16 encounter rows, and the nine authored hostiles remained intact.
This runtime/schema mismatch is recorded separately; it does not retroactively invalidate the
pre-launch constructed-fixture validation, but the post-run party-schema verdict is **FAILED**.
Issue: https://github.com/MoonlightByte/NeverEndingQuest/issues/271

### Large-tier verdict

The 15-automatic-actor round completed through the real native-Windows headless path and real
OpenAI. The player's declaration, attack roll, damage roll, the remaining automatic actor
window, T096 adjudication, T097 narration, commit, and return to round 2 all completed.

The exact initiative order placed Scout Kira before the player and four living companions
after the player in the measured window. Consequently the immutable T105 map contained four
actors (Ranger Derek, Ranger Thane, Scout Elen, and Spirit-Touched Hermit Maelo), not all six
living companions. This proves the four-voice dispatch and the 6-companion/9-enemy mechanical
ceiling, but a single greater-than-four T105 dispatch remains honestly **NOT-REACHED**. The
test does not relabel that M30 boundary as passing merely because six companions were present.

### Four-voice batch telemetry

| Metric | Result |
|---|---:|
| Selected / merged | 4 / 4 |
| Batch wall | 17.889 s |
| Thought calls | 4.290 / 4.449 / 4.528 / 4.752 s |
| Classification calls | 3.425 / 3.502 / 3.540 / 4.021 s |
| Physical calls | 8, all valid on attempt 1 |
| Total tokens | 11,301 |
| Lifecycle faults | none: zero reap, reissue, stale rejection, or completed-invalid |

The four thought calls overlapped: their slowest call was 4.752 s while their serial sum was
18.019 s. The batch then performed four relationship-classification calls, also overlapped.
This fixture therefore cannot be compared as a pure one-stage line extension of the earlier
3.8/4.4-second curve; its 17.889-second wall includes both stages plus collection overhead.
No dollar cost was exposed, so tokens remain the cost proxy.

The measured player turn used three accepted-input continuations. T096 durations were
4.516 s (declaration), 5.625 s (attack-roll continuation), and 4.219 s (damage continuation).
The committed round T097 narration took 4.000 s. The remaining five-actor automatic window
then required one T096 correction (4.250 + 3.234 s) and a 2.938-second T097 narration before
returning to the next prompt. Input acknowledgement remained within one observed event cycle.

### Addendum evidence

- Fixture/post-run integrity scan: `/mnt/c/vra-evidence/voice_readiness_shipclean_8f51bef3/bigstress_validation_6voice.txt`
- Final six-companion game: `/mnt/c/vra-voice-bigstress-6voice`
- T105 telemetry: `/mnt/c/vra-evidence/voice_readiness_shipclean_8f51bef3/bigstress6voice_voice_telemetry.jsonl`
- T096/T097 attempts: `/mnt/c/vra-voice-bigstress-6voice/debug/combat/agentic_attempts.jsonl`
- Full native protocol/debug transcript: `/mnt/c/vra-voice-bigstress-6voice/modules/logs/headless_raw.log`

Updated scale dispositions:

- Four-voice M30 dispatch: **SUPERSEDED as the scale ceiling** by the dedicated W4/W5
  six-voice evidence below. The original four-entry measurement remains valid telemetry.
- Six living companions plus nine enemies / 15 automatic actors: **PASS** for encounter and
  complete-round scale.
- Single greater-than-four voice-map dispatch: **SUPERSEDED; PASS** in W4/W5 with six
  selected, six physical, and six merged twice.

## 2026-09-02 W6/W7 correction and storyteller evidence

Revision exercised: `40f06ab75065e1292e0f5de3a838154e067df066`

The earlier rows stating that a four-entry map was the largest live combat dispatch and
that a greater-than-four map was NOT-REACHED are superseded. Dedicated #272 W4/W5
acceptance at `c7b30769a540b8d4043806c3907472c5e5cccbf7` ran the real 16-actor
Thornwood encounter for two player declarations. Each declaration produced one batch with
six selected, six physical calls, and six merged results; the same six-entry map reached
T096 and T097. Zero dispatch-degraded or advisory-omitted warnings occurred.

W4/W5 also superseded the broad historical row `DM use of spoon-fed voice data: PASS`:
the six-entry maps reached T097, but both narrations omitted every companion `say` line.
That downstream narration result was not a #272 cap failure; it became the W6 prompt-tuning
gate.

### W6 - storyteller prompt

W6 shipped the scene-first storyteller prompt and T105 direct-address correction in
`40f06ab7`, with `gpt-5.6-luna` at reasoning `none`.

### W7 - live narration and telemetry

W7 then completed two further native-Windows real-OpenAI combat turns. The owner accepted
the live tone: turn 1 grouped
the volley as a scene and adapted Morwenna's line to Eirik; turn 2 ended on Morwenna's
fall without a roster-style closer. The post-player slices each carried four voice entries
because Thane and Kira had already acted in separate pre-player initiative slices; W7 is
not used as the six-entry cap proof.

W7 latency telemetry:

| Round | Selected / physical / merged | Per-call latency | Batch wall | Disposition |
|---|---:|---|---:|---|
| 1 | 4 / 4 / 4 | 4.379 / 5.047 / 13.166 / 13.345 s | 13.360 s | complete; no lifecycle fault |
| 2 | 4 / 4 / 4 | 4.738 / 4.991 / 5.596 / 13.208 s | 13.252 s | complete; no lifecycle fault |

Both batches had one roughly 13-second luna tail call that determined batch wall time.
This is recorded as provider latency telemetry; it caused no reissue, reap, stale reject,
completed-invalid result, or correctness failure.

The required manual event-truth check found a separate defect. Turn 1 narrated a Kira
arrow absent from that slice's `authoritativeFacts`; turn 2 had no extra current-beat
strike but referred to Morwenna's earlier blast. Issue #275 owns the cumulative
`encounterActivity.recentFacts` payload leak. Tone acceptance does not convert that truth
failure into a pass.

Evidence:

- W4/W5 cap proof: `/mnt/c/vra-evidence/issue_272_w4_c7b30769/W4_W5_VERDICT.md`
- W7 verbatim suggestions, narration, and truth audit:
  `/mnt/c/vra-evidence/issue_272_w7_40f06ab7/W7_LIVE_VERBATIM_EVIDENCE.md`
- #272 closure: https://github.com/MoonlightByte/NeverEndingQuest/issues/272
- Separate narration-truth defect: https://github.com/MoonlightByte/NeverEndingQuest/issues/275
