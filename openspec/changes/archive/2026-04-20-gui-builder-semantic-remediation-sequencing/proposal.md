# GUI Builder Semantic Remediation Sequencing

## Why
After the deterministic finisher, UI, and payload-shape fixes land, the remaining uploader blockers are no longer reporting bugs. They are builder-quality semantic defects such as unresolved destination aliases and other authoring ambiguities. Those need an explicit builder-facing remediation sequence before Phase 2 LLM assistance broadens further.

## What Changes
- Define the post-deterministic builder remediation sequence for semantic blockers.
- Make semantic repair entry points and handoff expectations explicit.
- Bound how unresolved destination-alias and similar authoring defects feed into later builder-assisted work.

## Capabilities
- GUI builder workflow SHALL expose semantic remediation as a distinct post-report step.
- Builder planning SHALL sequence semantic remediation after deterministic reporting fixes and before broader Phase 2 ambiguity assistance.
- Semantic remediation guidance SHALL preserve Python authority over final publishability state.

## Impact
- Affected artifacts: planning, builder-facing workflow docs, and future GUI/uploader implementation slices.
- Affected workflows: post-build operator remediation and sequencing into Phase 2 builder assistance.
- No immediate LLM behavior change is required in this slice.
