## Why

`The_Pumpkin_Kings_Curse` and `A_Pottsfield_Burial` are the two shortest paths to increasing the count of publishable world-registry modules.

- `The_Pumpkin_Kings_Curse` is already `ready=pass` and currently fails publishability because its semantic-authority payload is missing.
- `A_Pottsfield_Burial` is close to structural readiness and appears blocked by one missing monster closure (`crawling_claws.json`) and one missing module-local monster image.

These are materially smaller than the broader semantic lane modules and should be planned as a bounded quick-win slice.

## What Changes

- Define a narrow publishability remediation slice for `The_Pumpkin_Kings_Curse` semantic-authority closure.
- Define a narrow structural closure slice for `A_Pottsfield_Burial` covering the remaining `crawling_claws` monster JSON and module-local media debt.
- Preserve the rule that readiness and publishability remain separate states during this work.
- Exclude `Murder_at_the_Drowning_Lass` and `The_Ancients_Lab` from this slice because they are active works in progress.

## Capabilities

### New Capabilities
- `toolkit-pumpkin-semantic-authority-closure`: Close the missing semantic-authority payload gap so `The_Pumpkin_Kings_Curse` can move from ready-but-not-publishable to publishable.
- `toolkit-pottsfield-structural-closure`: Close the final structural monster/material debt blocking `A_Pottsfield_Burial` readiness and publishability.

### Modified Capabilities
- `module-publishable-gate`: Preserve explicit readiness-vs-publishability reporting while these quick-win closures land.

## Impact

- Affected systems:
  - toolkit finisher / semantic-authority enrichment
  - publishability and readiness audits
  - module-local monster/media closure for `A_Pottsfield_Burial`
- Affected modules:
  - `The_Pumpkin_Kings_Curse`
  - `A_Pottsfield_Burial`
- Excluded modules:
  - `Murder_at_the_Drowning_Lass`
  - `The_Ancients_Lab`
- Rollout strategy:
  - finish Pumpkin first because it is already structurally ready
  - finish Pottsfield second as a bounded structural closure
