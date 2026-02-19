# OpenClaw Extraction Progress Tracker

Status: Active
Started: 2026-02-18
Owner: NEQ core maintainers

Related plans:
- `plans/openclaw.md`
- `plans/openclaw-exec-checklist.md`
- `plans/openrouter_llm_router_architecture.md`
- `plans/EGO.md`

---

## How to use

At the end of each implementation session:
1. Mark completed boxes.
2. Add a short note under Session Log.
3. Record tests run and outcomes.
4. Add blockers and next actions.

---

## Track 1 - OpenRouter foundation

### Day 0 - Preflight and contract lock
- [ ] Error taxonomy finalized and documented
- [ ] Fallback transition matrix finalized
- [ ] Session identity key finalized
- [ ] Mechanics-critical task list finalized

### Day 1 - Router run envelope
- [ ] Envelope fields implemented in router
- [ ] Envelope emitted on success paths
- [ ] Envelope emitted on failure paths
- [ ] Unit tests for envelope coverage pass

### Day 2 - Profile store and cooldown engine
- [ ] Profile state store implemented
- [ ] Cooldown and disabled windows separated
- [ ] Expiry cleanup logic implemented
- [ ] Cooldown/disable tests pass

### Day 3 - Error-class fallback matrix
- [ ] Error class to action matrix implemented
- [ ] Deterministic fallback ordering verified
- [ ] Structured fallback logging added
- [ ] Matrix tests pass

### Day 4 - Session stickiness
- [ ] Session-level profile pinning implemented
- [ ] Rotation triggers implemented
- [ ] Cross-session leakage checks pass
- [ ] Stickiness tests pass

### Day 5 - Idempotency for write-side actions
- [ ] Idempotency utility created
- [ ] Character update path protected
- [ ] Encounter update path protected
- [ ] Action handler write paths protected
- [ ] Retry duplication tests pass

### Day 6 - Router diagnostics
- [ ] `scripts/router_status.py` created
- [ ] Active provider/model/profile output added
- [ ] Cooldown/disabled summary output added
- [ ] Diagnostic output validated in runtime

### Day 7 - Regression hardening
- [ ] `scripts/test_llm_router_failover.py` created
- [ ] `scripts/test_llm_router_stickiness.py` created
- [ ] `scripts/test_llm_router_idempotency.py` created
- [ ] Existing combat regressions pass
- [ ] Existing multiplayer regressions pass

---

## Track 2 - EGO follow-on (post Track 1)

### Day 8 - Passive ingestion
- [ ] Router envelope ingestion implemented
- [ ] Session telemetry report available
- [ ] No prompt writes enabled

### Day 9 - EGO classifier augmentation
- [ ] DRIFT/DISTORTION/HALLUCINATION includes router context
- [ ] Correlation reporting added
- [ ] Classifier quality check completed

### Day 10 - Bounded EGO adjustments
- [ ] Tier 1a canary adjustment path enabled
- [ ] Adjustment budget and cooldown enforced
- [ ] Rollback trigger verified
- [ ] Audit trail verified

---

## Global gates

### Track 1 ship gate
- [ ] Envelope coverage complete
- [ ] Error taxonomy and matrix tested
- [ ] Idempotency protections active
- [ ] Diagnostics operational
- [ ] Combat and multiplayer regressions clean

### Track 2 enable gate
- [ ] Track 1 gate complete
- [ ] Passive telemetry quality acceptable
- [ ] Rollback and audit trails verified

---

## Session log

### Session 1
Date:
Focus:
Changes:
Tests:
Result:
Blockers:
Next:

### Session 2
Date:
Focus:
Changes:
Tests:
Result:
Blockers:
Next:

### Session 3
Date:
Focus:
Changes:
Tests:
Result:
Blockers:
Next:

### Session 4
Date:
Focus:
Changes:
Tests:
Result:
Blockers:
Next:

### Session 5
Date:
Focus:
Changes:
Tests:
Result:
Blockers:
Next:
