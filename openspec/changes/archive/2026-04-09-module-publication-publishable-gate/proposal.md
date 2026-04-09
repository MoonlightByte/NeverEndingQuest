## Why

The publication workflow now has:

- semantic-authority substrate
- semantic publication blocker audit
- deterministic live-play probes

What remains is the final repo-facing gate that distinguishes a structurally ready module from a semantically publishable one. Without that distinction, the repo still has no canonical answer to: "is this module merely ready to inspect, or is it safe to release to players/testers?"

## What Changes

- Add a distinct `publishable` audit result layered over existing readiness.
- Wire semantic publication audit and semantic probe harness results into publishability decisions.
- Expose `ready` vs `publishable` clearly in CLI output and toolkit finisher reporting.
- Keep backward-compatible readiness reporting while adding the stricter publication decision.

## Non-Goals

- No runtime travel, NPC, or combat behavior changes.
- No new semantic-authority or probe classes beyond what is required to consume existing outputs.
- No requirement that currently shipped modules immediately become publishable; the gate may correctly fail legacy modules.

## Capabilities

### New Capabilities
- `module-publishable-gate`: the repo SHALL distinguish structural readiness from semantic publishability.
- `module-publishability-reporting`: CLI and toolkit report surfaces SHALL expose `ready` vs `publishable` clearly.

### Modified Capabilities
- None.

## Impact

- Affected CLI tooling: new standalone publishability audit script under `scripts/`
- Affected toolkit reporting: `web/extensions/toolkit_module_finisher.py`
- Affected release-facing validation: optional bulk/reporting surfaces MAY reflect publishability distinctly from readiness
- Compatibility: MUST preserve existing readiness semantics while adding the stronger publishability layer
