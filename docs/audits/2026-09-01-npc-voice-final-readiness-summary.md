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
| DM use of spoon-fed voice data | PASS | A3 verdict plus stress narrations |
| Save/Load sidecar round trip | PASS for exercised accepted paths | A5 and ship-clean evidence roots |
| Player-roll crash replay | PASS | `/mnt/c/vra-evidence/voice_readiness_shipclean_8f51bef3/c1_268/native` |
| Accepted live-scope Load application | PASS | `/mnt/c/vra-evidence/voice_readiness_shipclean_8f51bef3/c2_236/native` |
| Small/mid combat stress | PASS | `docs/audits/2026-09-01-voice-roundbatch-stress-telemetry.md` |
| Six living companions + nine enemies | PASS for encounter and complete-round scale | constructed-scale addendum in the stress report |
| Four-voice immutable combat map | PASS | 4 selected/merged, 17.889-second wall, 11,301 tokens |
| Single greater-than-four voice map | NOT-REACHED | natural initiative split placed only four companions in the measured player window |
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
  live-proven. A single greater-than-four dispatch remains explicitly NOT-REACHED.
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
roll-replay, accepted-Load, and 15-automatic-actor paths. No implementation repair was made
during the final stress pass. Overall merge/ship remains an owner decision under `D-VR-9`,
with the open items above and the honest greater-than-four-map NOT-REACHED boundary visible.
