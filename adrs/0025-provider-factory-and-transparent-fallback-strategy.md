# ADR-0025: Provider Factory and Transparent Fallback Strategy

- Date: 2026-03-10
- Status: Accepted
- Supersedes: None
- Superseded by: ADR-0026 (planned successor)

## Context
Provider lock-in and direct client construction across many call sites made migration and reliability difficult.

## Decision
Use provider factory routing (`create_chat_client`) with transparent fallback handling and provider-aware model resolution.

## Consequences
- Centralized provider management.
- Cleaner migration path away from OpenAI-only assumptions.
- Requires consistent adoption at all LLM call sites for full benefit.

## Sources
- `AGENTS.md`
- `utils/ai_client_factory.py`
- `plans/version-2/openrouter_llm_router_architecture.md`
