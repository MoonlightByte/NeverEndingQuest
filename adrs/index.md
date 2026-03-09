# Architecture Decision Records Index

This directory captures durable Tabletop NeverEndingQuest architecture decisions.

Status legend:
- Accepted: active decision currently guiding implementation
- Planned: approved direction not fully implemented
- Superseded: replaced by a later accepted ADR
- Deferred: intentionally postponed

## ADR List

- 0001 Documentation Authority Hierarchy and Canonical Memory Order (Accepted)
- 0002 Merge-Safe Tabletop Overlay Architecture (Accepted)
- 0003 Upstream-First Extend-Do-Not-Replace Policy (Accepted)
- 0004 Multiplayer Activation and SP/MP Unification Roadmap (Planned)
- 0005 Canonical State Ownership by Persistence Domain (Accepted)
- 0006 Character Data Access Abstraction Layer (Accepted)
- 0007 Python Mechanical Truth and LLM Narrative Freedom Boundary (Accepted)
- 0008 Head-Body-Tail Prompt Architecture for Multi-PC (Accepted)
- 0009 Active-PC Tagged Conversation Compression (Accepted)
- 0010 Multi-PC Combat Phase State Machine Contract (Accepted)
- 0011 NPC Arrival Narration-State Synchronization Contract (Accepted)
- 0012 Canonical Narration Channel and Streaming Reversion Policy (Accepted)
- 0013 TTS Queue, Skip Rules, and Word-Sync Fallback Policy (Accepted)
- 0014 Session Recap Poisoning Prevention at Startup (Accepted)
- 0015 GUI Exit Intentional Shutdown Contract (Return Code 91) (Accepted)
- 0016 Two-Plane Memory Architecture (Historical Store vs Prompt Lens) (Accepted)
- 0017 Deterministic Memory Retrieval and Idempotent Ingest (Accepted)
- 0018 Identity-First Role Lifecycle Continuity (NPC/PC/Retired) (Accepted)
- 0019 Memory Portability and Source-Gated Backfill Safety Contract (Accepted)
- 0020 Continuity Contract v1 for Any-Order Module Play (Accepted)
- 0021 Ingest Watcher Strict Gate and CLI Parity Contract (Accepted)
- 0022 Ingest Success Requires Registration and Strict Bulk Validation (Accepted)
- 0023 Canonical-World Continuous Module Import Pipeline (Planned)
- 0024 Hallucinated Monster Defense and Encounter Integrity Contract (Accepted)
- 0025 Provider Factory and Transparent Fallback Strategy (Accepted)
- 0026 Capability-Based LLM Router Facade (`llm.call`) (Planned)
- 0027 V2 Prime Directive and Approval-Gated Canon Apply (Accepted)
- 0028 Homebrew Wave 1 Birble Plan Deferred After Dev Ingest Validation (Deferred)
- 0029 Archive Save/Restore Portability and Routing Contract (Accepted)

## Supersession Map

- ADR-0023 supersedes ADR-0028.
- ADR-0026 is the planned successor to ADR-0025.

## Notes

- Scope intentionally excludes upstream ARCHITECTURE documents and focuses on tabletop and v2 decisions.
- Change-level implementation details remain in `openspec/changes/*`.
- Canonical governance remains in `AGENTS.md`.
