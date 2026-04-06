## Why

NEQ now has a viable local Bonsai API endpoint, but the project needs a bounded test to determine whether Bonsai is actually usable for live narration before any broader provider-routing work. The safest first question is whether `dm_main` can use Bonsai with acceptable quality and latency while all structured and mechanical tasks remain on the current provider path.

## What Changes

- Add a narrow Bonsai narration pilot that introduces `bonsai` as a third chat-provider option through the existing provider factory.
- Add explicit Bonsai configuration for OpenAI-compatible local API access through `bonsai api`.
- Route only the `dm_main` narration path to Bonsai when the pilot is enabled.
- Make the pilot fail closed for narration: if Bonsai is unavailable, NEQ MUST return an explicit provider failure instead of silently falling back.
- Keep Bonsai process ownership manual for this slice: NEQ MUST connect to an already-running `bonsai api` server and MUST NOT auto-launch it.
- Add targeted verification that non-narration tasks remain on the existing provider path.

Non-goals:
- full provider migration
- validator or combat migration
- builder/toolkit migration
- broad callsite cleanup
- automatic management of the Bonsai server lifecycle
- GUI provider controls beyond what is needed for this pilot

Rollout risk and fallback:
- The pilot MUST remain bounded to allowlisted narration tasks only.
- The pilot MUST fail closed for narration so testing stays unambiguous.
- Non-narration tasks MUST continue using the existing provider path.
- Rollback MUST be configuration-first: disable the pilot and restore current routing without deeper code surgery.

Merge-safety and compatibility:
- The pilot MUST preserve current single-player and multi-PC runtime behavior outside the narration allowlist.
- The pilot MUST keep upstream-sensitive host behavior unchanged except for minimal additive routing hooks.
- Provider outage behavior MUST be explicit: narration in pilot mode fails closed, while non-pilot tasks remain on existing providers.

## Capabilities

### New Capabilities
- `tt-bonsai-narration-provider-routing`: route only allowlisted live narration tasks to a locally configured Bonsai OpenAI-compatible endpoint.
- `tt-bonsai-pilot-failclosed-mode`: fail closed for allowlisted Bonsai narration tasks when the local Bonsai API is unavailable or unhealthy, without silent fallback.
- `tt-bonsai-non-narration-isolation`: preserve existing provider behavior for validation, combat, builders, and all non-allowlisted tasks during the pilot.

### Modified Capabilities

None.

## Impact

- Affected code: `utils/ai_client_factory.py`, `model_config.py`, `config_template.py`, and the live narration call path that currently uses `DM_MAIN_MODEL` directly.
- Affected systems: runtime provider selection, narration-only task routing, provider error handling, and pilot observability.
- New dependencies: none; Bonsai is consumed through its OpenAI-compatible local HTTP API.
- Operational dependency: operator-managed `bonsai api` server on local host, expected at `http://127.0.0.1:8080/v1`.
- Verification impact: targeted routing/failure smoke coverage will be needed to prove isolation and explicit fail-closed behavior.
