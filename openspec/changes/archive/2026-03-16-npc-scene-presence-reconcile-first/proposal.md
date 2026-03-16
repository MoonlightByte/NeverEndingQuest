## Why

G2 fixed the most visible travel desync loops, but the runtime still treats explicit off-location NPC scene presence as a reject-first validation problem instead of a reconcile-first world-state problem. That keeps immersive turns brittle in the exact domain called out as conditional G3 work in `plans/llm-wants-to-be-free.md`.

We now have both prerequisites for a safe narrow G3 slice:
- the authoritative packet foundation exists,
- travel reconcile-first is isolated from NPC behavior.

There is also concrete transcript evidence that NPC scene presence is still harming play. The Maelo correction loop recorded in `main_conversation_messages_to_api.json` shows the current validator hard-failing a narratively natural scene-presence beat instead of reconciling it.

## What Changes

- Introduce a narrow reconcile-first contract for explicit-but-safe NPC scene presence.
- Preserve current legality for foreshadowing and informational off-location references.
- Preserve explicit `updatePartyNPCs` for durable party membership changes.
- Preserve ambiguity safety so unresolved NPC identity does not silently commit false canon.
- Prepare transcript-driven regression coverage before runtime code changes.

Non-goals:
- No full world-delta reconciler in this slice.
- No Titans/event-ledger semantics in this slice.
- No broad rewrite of every NPC or prompt pathway in this slice.
- No loosening of party-membership persistence rules in this slice.

## Capabilities

### New Capabilities
- `tt-npc-scene-presence-reconcile-first`: runtime SHALL reconcile clear scene-compatible NPC presence without requiring perfect explicit movement plumbing.

### Modified Capabilities
- `tt-narrator-validation-contract`: deterministic NPC scene-presence reconciliation SHALL remain authoritative over LLM re-litigation for the touched domain.
- `tt-npc-arrival-name-resolution`: identity safety SHALL remain intact when scene presence reconciliation is introduced.

## Impact

- Primary code likely affected in implementation phase:
  - `main.py`
  - `utils/npc_arrival_validator.py`
  - `core/ai/action_handler.py`
- Regression coverage added now:
  - new transcript-driven G3 tests in `scripts/`
- OpenSpec artifacts added now:
  - proposal/design/tasks/executor prompts
  - new delta spec for scene-presence reconciliation

Risks and fallback:
- MUST keep the slice narrow: scene presence, not full NPC lifecycle/event semantics.
- MUST preserve explicit `updatePartyNPCs` for true join/leave behavior.
- MUST keep ambiguity fail-safe.
- If implementation proves too risky before tester invite, the fallback is to keep the contract/tests and defer runtime changes while preserving G1/G2 gains.
