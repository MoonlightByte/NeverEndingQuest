# NPC Voice Final Readiness Summary

Date: 2026-09-01
Branch: `integration/npc-voice-episodic`
Reviewed product tip before this evidence-only update: `dcc172f034b52c43b2a019fc551f4cca3c489192`
Ship authority: owner-open (`D-VR-9`)

## Shipped on the branch

- One canonical T105 voice stack serves OOC and combat consumers; legacy T045 inherits only
  shared-stack improvements pending its separately governed retirement.
- Voice text and combat narration no longer use the retired character truncation caps.
- E1-E4 selective context, shared zero-new-call recall, limited-context DM authority, and the
  approved OOC/T096/T097 instruction contracts are live.
- Typed combat dispatches one parallel post-input round batch, completion-collects it, passes
  one immutable actor-keyed map to T096, persists it in the existing encounter transaction,
  and narrates committed results through T097.
- C7 owns/reuses the accepted-input live scope across the logical round and degrades a genuine
  missing-authority voice beat non-fatally.
- `4be8a67a` closes the Reset causal-identity residue from #256.
- `5e43e2fa` aligns the persisted voice envelope and runtime normalization from #265.
- `fa1b27fe` persists the immutable voice envelope at the first player-roll pause; `8da71014`
  records the architecture evidence. This closes #268.
- `dcdeea43` makes an accepted live-scope headless Load reach one truthful terminal and apply
  after quiescence. This closes #236 while leaving #201/#270 concurrency boundaries separate.

## Acceptance verdicts

| Area | Verdict | Evidence |
|---|---|---|
| Schema compatibility | PASS | 2,819 authentic encounter-shaped records scanned; zero baseline-valid records became invalid |
| OOC voice path | PASS | A1/A2 evidence under `/mnt/c/vra-evidence/voice_readiness_35320cff` |
| Typed round-batch combat | PASS | `docs/audits/2026-09-01-a3c7-combat-acceptance-verdict.md` |
| DM use of spoon-fed voice data | SUPERSEDED by W6/W7 | Six-entry W4/W5 maps exposed total `say` omission; W6/W7 tone is owner-accepted, while event truth remains FAILED #275 |
| Save/Load sidecar round trip | PASS for exercised accepted paths | A5 and ship-clean evidence roots |
| Player-roll crash replay | PASS | `/mnt/c/vra-evidence/voice_readiness_shipclean_8f51bef3/c1_268/native` |
| Accepted live-scope Load application | PASS | `/mnt/c/vra-evidence/voice_readiness_shipclean_8f51bef3/c2_236/native` |
| Small/mid combat stress | PASS | `docs/audits/2026-09-01-voice-roundbatch-stress-telemetry.md` |
| Six living companions + nine enemies | PASS for encounter and complete-round scale | constructed-scale addendum in the stress report |
| Four-voice immutable combat map | SUPERSEDED as scale ceiling | Original 4 selected/merged telemetry remains valid; W4/W5 proved six-entry maps twice |
| Single greater-than-four voice map | PASS | #272 W4/W5: 6 selected / 6 physical / 6 merged in two real rounds |
| Legacy T045 live voice injection | NOT-REACHED / continuation FAILED #267 | retirement-owned, no prohibited legacy-only repair |
| Natural transport hang/reissue | NOT-REACHED | no false pass; structural path remains code-covered |
| Post-run party schema | FAILED #271 | runtime writer removed required `weatherConditions` |

The large constructed encounter contained 16 rows: one human PC and 15 automatic actors.
It was created through ordinary official-module play. Only the party roster and validated
character files were constructed under the owner's explicit fixture authority; no encounter,
initiative, roll, HP mutation, or committed event was edited.

## Issue disposition

Closed with evidence:

- #164: retired flag/filter and packet-loss risks resolved; four-voice M30 dispatch now
  live-proven originally, now superseded by two six-of-six W4/W5 batches.
- #272: actor-count caps and whole-batch packet loss resolved; six-of-six dispatch proven
  twice on native Windows with real OpenAI.
- #236: accepted live-scope headless Load now applies after quiescence.
- #256: Reset causal identity is fenced.
- #265: persisted voice envelope and runtime normalization agree.
- #268: roll-pause restart preserves the immutable voice map.

Still open and separately owned:

- #201: broad crash-safe Save/Load/Reset convergence.
- #254: typed combat resolved; legacy T045 residue remains blocked on retirement.
- #267: legacy T045 Sacred Flame continuation, resolved by retirement rather than a legacy fix.
- #269: accepted T105 sidecar batch is not yet persisted with every roll-pause envelope.
- #270: overlapping accepted lifecycle operation arbitration.
- #271: party tracker writer drops required `worldConditions.weatherConditions` after play.
- #275: T097 receives cumulative prior-beat `encounterActivity.recentFacts` and can narrate
  an earlier/other-slice strike as current; payload-hygiene repair is owner-scheduled.

## 2026-09-02 W6/W7 readiness correction

W4/W5 at `c7b30769` supersedes the earlier greater-than-four NOT-REACHED row: two
successive real combat declarations each produced six selected, six physical, and six
merged T105 results, and both T096 and T097 received the full immutable map. That closes
#272 and supplies the final M30 scale evidence for #164.

### W6 - storyteller prompt

W6 shipped the owner-reviewed storyteller prompt at `40f06ab7`, with luna reasoning
remaining `none`.

### W7 - live narration and telemetry

W7 completed two further real native-Windows rounds. The owner accepted
the narration tone. Turn 1 naturally adapted Morwenna's advice into the scene; turn 2
appropriately used no companion dialogue and ended on Morwenna's fall. Those W7 slices had
four advised companions because two companions had already acted before the player, so the
six-entry scale verdict continues to come from W4/W5 rather than being inferred from W7.

Each W7 batch had one roughly 13-second luna tail call (13.166 and 13.208 seconds), setting
batch walls of 13.360 and 13.252 seconds. This is latency telemetry, not a lifecycle or
correctness failure.

The manual narration-truth audit did not pass: turn 1 added a Kira arrow absent from its
slice ledger, and turn 2 referenced Morwenna's prior blast. That defect is separated as
#275 because #272 is the fixed count/batch-loss boundary. Therefore the old blanket
`DM use of spoon-fed voice data: PASS` row is superseded by the narrower current verdict:
**tone accepted; advisory plumbing and six-entry scale pass; slice-fact truth failed #275**.

Evidence:

- `/mnt/c/vra-evidence/issue_272_w4_c7b30769/W4_W5_VERDICT.md`
- `/mnt/c/vra-evidence/issue_272_w7_40f06ab7/W7_LIVE_VERBATIM_EVIDENCE.md`

## Evidence index

- Consolidated stress and scale telemetry:
  `docs/audits/2026-09-01-voice-roundbatch-stress-telemetry.md`
- A3/C7 typed-combat verdict:
  `docs/audits/2026-09-01-a3c7-combat-acceptance-verdict.md`
- A4/A5 verdicts:
  `docs/audits/2026-09-01-a4a5-verdicts.md`
- Current readiness acceptance:
  `/mnt/c/vra-evidence/voice_readiness_35320cff/ACCEPTANCE_VERDICT.md`
- Ship-clean evidence:
  `/mnt/c/vra-evidence/voice_readiness_shipclean_8f51bef3`
- Six-companion game and full protocol log:
  `/mnt/c/vra-voice-bigstress-6voice`

## Final disposition

The typed NPC voice runtime is implemented and passes the exercised OOC, typed-combat,
roll-replay, accepted-Load, 15-automatic-actor, and six-entry voice-map paths. W7 tone is
owner-accepted. T097 slice-fact truth remains open as #275. Overall merge/ship remains an
owner decision under `D-VR-9`, with that separate defect and the other open items above
visible.
