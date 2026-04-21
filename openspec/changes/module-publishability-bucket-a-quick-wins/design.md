## Context

Bulk validation currently shows only one world-registry module passing publishability. The fastest realistic path to raise that count is to isolate the two smallest remaining failures:

1. `The_Pumpkin_Kings_Curse`
   - `ready=pass`
   - `publishable=fail`
   - current blocker: missing `semantic_authority` payload in `module_context.json`

2. `A_Pottsfield_Burial`
   - `ready=fail`
   - `publishable=fail`
   - current blocker set appears narrowly bounded to:
     - missing `modules/A_Pottsfield_Burial/monsters/crawling_claws.json`
     - missing `modules/A_Pottsfield_Burial/media/monsters/crawling_claws.jpg`

This slice is intentionally narrower than the semantic lane for `Keep_of_Doom`, `Night_of_the_Restless_Dead`, and `The_Hidden_City_of_Numillian`.

## Goals / Non-Goals

**Goals:**
- MUST land a reviewable plan for closing Pumpkin's semantic-authority payload gap.
- MUST land a reviewable plan for closing Pottsfield's final known structural closure gap.
- MUST keep readiness and publishability state reporting explicit throughout the work.
- SHOULD sequence Pumpkin before Pottsfield because Pumpkin is already structurally ready.

**Non-Goals:**
- NOT addressing `Murder_at_the_Drowning_Lass` or `The_Ancients_Lab`.
- NOT addressing the broader semantic-alias lane for `Keep_of_Doom`, `Night_of_the_Restless_Dead`, or `The_Hidden_City_of_Numillian`.
- NOT redesigning publishability tooling.
- NOT broadening this slice into a multi-module media sweep.

## Decisions

### Decision: Bucket A remains a quick-win lane only
- Rationale: the purpose is to increase pass count quickly, not to mix small closures with larger ambiguity/provenance remediation.
- MUST stay scoped to `The_Pumpkin_Kings_Curse` and `A_Pottsfield_Burial`.
- MUST leave WIP modules out of this change.

### Decision: Pumpkin is semantic-authority closure, not structural rebuild
- Rationale: current validation shows Pumpkin already passes readiness.
- MUST treat the missing semantic-authority payload as the primary closure target.
- SHOULD verify no hidden secondary semantic blockers appear once payload emission is restored.

### Decision: Pottsfield is a bounded structural closure, not a general media lane
- Rationale: current validation points to one named monster closure rather than broad missing media debt.
- MUST plan to add `crawling_claws.json` and module-local `crawling_claws.jpg`.
- SHOULD confirm that no additional Pottsfield readiness blockers remain after this closure.

### Decision: Publishability reporting remains explicit during the quick-win pass
- Rationale: even small closures should preserve the repo rule that `ready` and `publishable` are distinct outputs.
- MUST keep the quick-win work grounded in existing gate outputs rather than ad hoc success criteria.

## Architecture

### Before

1. `The_Pumpkin_Kings_Curse` is structurally ready but blocked at publishability by missing semantic-authority output.
2. `A_Pottsfield_Burial` is blocked by a small structural monster/media closure gap.
3. Both modules remain in the failing set despite being much closer than the larger semantic or WIP modules.

### After

1. Pumpkin has semantic-authority payload closure and re-enters publishability audit as a publishable candidate.
2. Pottsfield has its final known structural monster closure landed and re-enters readiness/publishability audit as a publishable candidate.
3. Bucket A can be validated independently from the larger semantic lane.

## Risks / Trade-offs

- [Pumpkin reveals hidden semantic blockers after payload closure] -> Mitigation: require post-fix publishability rerun and treat new blockers as follow-up, not silent success.
- [Pottsfield closure expands beyond `crawling_claws`] -> Mitigation: verify with readiness/publishability immediately after the bounded fix and record any newly surfaced debt explicitly.
- [Quick-win slice grows into broad remediation] -> Mitigation: keep exact module scope and exact blocker targets explicit in tasks.

## Verification Plan

1. Re-run readiness and publishability for `The_Pumpkin_Kings_Curse` after semantic-authority closure.
2. Re-run readiness and publishability for `A_Pottsfield_Burial` after `crawling_claws` closure.
3. Confirm both modules' outcomes are expressed with explicit `ready_status` and `publishable_status`.
4. Confirm excluded WIP modules remain out of scope for this bucket.
