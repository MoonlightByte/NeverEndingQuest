# #357 armor contract: native acceptance and shipment record

2026-09-11 local / 2026-09-12 UTC. Owner shipment authority: live #193 D-357-4.
Source baseline at trial: c7ede1268a3a7faba471b583bec2b9119c8f7095 (Git evidence,
not runtime authority). Reviewed implementation diff SHA256:
ba4a822f41e022d4d505ecd6c0f7e6dab20f28f98c23b4a581b23fff0cd5e62d.
Two Python files and the progression schematic; frozen schema/prompts unchanged.

## Results and scope

| Arm | Verdict | Evidence |
| --- | --- | --- |
| A1 valid-null prevention | PASSED | Real T051 null responses accepted; healing committed |
| A2 valid-cache next update | PASSED in armor scope | Dain cache HIT, zero additional T051; #358 transfer FAILED separately |
| A3 invalid-response correction | PASSED | B T051[1] echoed99, schema rejected it, T051[2] corrected to null |
| A4 exact arrow-transfer command | NOT-REACHED for armor repair | Referee redirected to storage, writer never entered; #363 |
| A4 disclosed short-rest substitute | PASSED for repair, preservation and update liveness | Poisoned matching cache rejected; model repair and HP8->12 saved together |
| A5 Save/Load/relaunch/update | PASSED in armor scope | Load applied, supported restart, ordinary gold update; #349 separate |

The substitute does not convert the exact-command arm into a pass. Overall transfer
gameplay FAILED because of separately tracked #358/#360/#363. Retry exhaustion,
other providers, multi-item poison, poisoned-save Load, prepare entrant and F10+armor
were not exercised. Existing T051 three-attempt limit remains #324; recovery succeeded
on attempt3. D-357-4 permits this disclosed narrow shipment, not a general retry waiver.

## Acceptance evidence block

Real native Windows C:/Python312, run_headless.py serve, real OpenAI selected
gpt-5.6-luna/none for T051/T079; response.model absent in capture (UNKNOWN, not
invented). Copied authentic saves; source export1995 tracked files matched; fixture
prompts refreshed. No fabricated responses, sheet edits, or special armor values.

Private artifacts: C:/357-ev-pAaw3B/{A,A5,B}/protocol.ndjson, model_captures/,
state_snapshots/. Full per-call accounting, prompt fingerprints, commands and raw
player text: C:/agent-room-fleet-kit/local-data/357-native-trial-report.md;
independent transcript review: 357-px-review.md (Part2 final verdicts).

Load-bearing B substitute sequence relative to input (protocol physical lines):
- L1262 +71.3s detects invalid armor; L1272 rejects the matching poisoned cache.
- T051[0] +77.1s /5.80s echoes99 and malformed total; inherited envelope rejects.
- T051[1] +82.6s /5.52s echoes99; new schema rejection L1278.
- T051[2] +88.4s /5.72s proposes dex_limit:null and explicitly explains correction.
- T079[0] +91.6s /3.12s receives the corrected sheet and returns hitPoints12.
- L1342 single primary safe_write_json succeeds; L1382 valid cache HIT afterward.
- Next prompt +110.9s. Narration L1224: "Dain is fully recovered at 12/12 hit
  points"; disk agrees. AC16 and Arrow19 unchanged. Only armor99->null, HP8->12,
  and world time10:05->11:05 changed; other character sheets unchanged. The explicit
  null is a model-chosen no-limit value, not discarded player information.

No repair-only character write; backup retains99. Atomic ordering is CODE-PROVEN
plus logged ordering and final disk OBSERVED, not a crash-injection proof. B repair
leg counts: zero generic unsafe-action/refusal, revert, traceback, fallback,
degradation or reissue; two completed invalid responses then success. All player
narrations, including false transfer claims, are preserved and independently judged
in private evidence, not sanitized into successful gameplay.

All game processes exited0 through supported lifecycle operations; original fixture
hashes unchanged (2386 +715 files). Local compile/schema aids and independent code
audit/sentinels passed. A supplementary config-shim import smoke was excluded as
outside the test boundary; actual cache proof is the native run above.

## Separate work

#349 assumed Defense, #358 item identity, #360 premature success narration, #363
referee/storage contract mismatch and #324 failure policy remain separate. No claim
that those systems passed. #363 planning is the next owner-authorized task only.
