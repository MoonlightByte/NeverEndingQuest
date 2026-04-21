# Client Web Thin-Client Roadmap

## Purpose
Define the phased path from the current local tabletop workflow to a lean remote-client architecture that supports:
- mixed in-person tabletop and browser-based participation,
- LAN-first remote play,
- later internet-ready thin-client play,
- one authoritative server-side game loop for all participants.

This roadmap complements `plans/version-2/client_network.md`, which remains the architecture decision document for the MVP slice.

## Core Position
The correct long-term foundation is:
- one host-run server,
- one authoritative game loop,
- one shared server-side state,
- thin browser clients that observe shared state and submit input.

This is intentionally not a client-authoritative multiplayer rewrite.

## Why This Direction Is Strong
This direction preserves the project's most valuable current property:
- Python remains authoritative for narration, validation, combat flow, and persistent state.

That gives the project the best chance of becoming a notable online LLM-DM 5e SRD RPG without prematurely splitting authority across browsers.

## Design Principles
- Keep the server authoritative.
- Keep clients thin.
- Prefer a dedicated `/client` shell over hidden-controls reuse of `/`.
- Prefer explicit event and route contracts over ad hoc behavior.
- Prefer social coordination over account/permissions complexity in MVP.
- Optimize by subtraction, not by shipping the full DM shell everywhere.
- Treat hybrid tabletop plus remote play as the primary use case.
- Separate gameplay-state authority from input-rights authority.

## Locked Decisions For MVP
- The DM starts and hosts the existing server.
- `/` remains the host/facilitator surface.
- `/client` becomes the lean player surface.
- `active_character` remains one shared server-side state across all browsers.
- Shared active-character contention is acceptable in MVP and mirrors normal in-person table dynamics.
- Voice and video remain out of band via Meet, Zoom, or similar tools.
- Client browsers must not expose server shutdown, toolkit, admin, save/load/reset, or party-management controls.
- Authentication remains simple: optional shared client password only.
- TTS and DM Voice should default to host-local, not remote-client-facing.

## Long-Term Authority Direction
The future architecture should distinguish two different kinds of authority.

1. Game-state authority
- Always remains server-side.
- Python remains authoritative for narration, combat resolution, validation, persistence, and canonical session state.

2. Input-rights authority
- May later be delegated per client session.
- A client may become the recognized source of player input for a specific PC without becoming authoritative for world state.

This distinction is important because it allows the project to evolve toward structured online multiplayer while preserving the thin-client model.

## Performance And Asset Position
The client route should not inherit the current host-page bloat just because it already exists.

The key performance stance is:
- `/client` must be a genuinely lean shell,
- not a cosmetically reduced DM page.

The biggest likely performance issue is not websocket transport itself.
The bigger risk is shipping:
- oversized host markup,
- large inline JS execution scope,
- host-only UI logic,
- unnecessary admin payloads,
to every remote-player browser.

Therefore the client architecture should:
- load only gameplay-relevant markup,
- load only gameplay-relevant JS and CSS,
- exclude host-only UI and boot logic entirely,
- keep client event payloads narrow,
- avoid lazy full-state rebroadcast when a smaller refresh is enough.

## Phase 1: MVP Hybrid Play
### Goal
Enable mixed local-tabletop plus LAN/trusted-remote browser play with minimal new complexity.

### Scope
- Dedicated `/client` route.
- Optional `/login` gate using a shared password.
- Shared live transcript for host and clients.
- Shared `active_character` across all browsers.
- Client-side input submission through the existing server loop.
- Lean client shell for gameplay only.
- Explicit event matrix.
- Explicit route allowlist for client-safe surfaces.
- Reconnect/resync support sufficient for practical remote use.

### Required Contracts
- `game_output` and other shared gameplay events broadcast correctly.
- `active_character_update` is shared across all browsers.
- Client-safe routes are explicitly defined.
- Host-only routes are explicitly excluded from `/client`.
- Client boot uses a bounded gameplay snapshot rather than a host-grade payload.
- Reconnecting clients can recover the current playable session state without manual DM repair.

### UX Requirements
- Remote players see the same transcript in real time.
- Remote players can change the active PC tab.
- Remote players can submit actions for the current shared PC.
- The current active PC is visually obvious.
- The system shows a shared busy/thinking state while the server is processing.
- The client remains usable on ordinary home internet, even if the initial rollout target is LAN.

### MVP Enhancement Worth Treating As Core
Reconnect and resync behavior should be treated as part of MVP, not as a later luxury.

A reconnecting client should recover:
- recent transcript,
- current `active_character`,
- party state relevant to play,
- combat state if combat is active,
- any visible shared busy/processing state.

Without this, remote play will feel brittle even if the rest of the architecture is sound.

## Phase 2: Post-MVP UX Hardening
### Goal
Improve clarity, resilience, and multiplayer usability without abandoning KISS.

### Candidate Additions
- soft identity and presence layer,
- observer-mode client role,
- clearer active-PC change signaling,
- better reconnect/resync polish,
- narrower payload discipline,
- cleaner transcript ordering guarantees,
- optional DM-controlled turn-focus tools.

### Observer Mode
Observer mode is a strong post-MVP addition because it creates the thinnest possible client tier.

Observer clients should:
- receive the shared transcript,
- receive current gameplay state relevant to viewing,
- remain visible as connected session participants if presence is enabled,
- have no gameplay input capability by default.

Benefits:
- supports online audience/watcher scenarios,
- provides a safe low-permission remote mode,
- creates a path toward "many observers, few actors" sessions,
- keeps the architecture thin because no input logic is required for pure observers.

### Soft Identity
This is not full accounts.
It is lightweight session clarity such as:
- who connected,
- who selected a PC,
- who submitted an input.

This would materially improve remote-table clarity without introducing a full auth system.

### Active Character Contention
The shared-state shouting-match model is acceptable for MVP.
That said, a later enhancement could add a minimal server-side focus tool such as:
- host-enforced turn focus,
- visual indication that a specific PC is expected to act now,
- optional soft blocking or warning when a different PC is selected during enforced focus.

This should remain lightweight and facilitator-driven, not a full permissions layer.

### Observer -> Claimant -> Assigned Controller Evolution
The natural multiplayer evolution after MVP is not full accounts or hard permissions first.

It is a staged control model:

1. Observer
- read-only or effectively read-only client,
- no gameplay input,
- ideal for audience mode, passive participants, or remote viewers.

2. Claimant
- client can request control of a PC,
- claim may remain pending until approved by the host,
- useful for lightweight remote sessions without a full user system.

3. Assigned controller
- host assigns a client session to a specific PC,
- that client becomes the recognized source of player input for that PC,
- server still remains authoritative for all actual game-state changes.

This evolution gives the project a clean path from social tabletop chaos to structured remote multiplayer without abandoning KISS too early.

### Future Role Model
The likely long-term role model should be:

1. Host
- facilitator authority,
- may assign, revoke, or override client control relationships,
- remains the session governor.

2. Observer
- can watch,
- may or may not appear in lightweight presence lists,
- cannot submit gameplay input.

3. Player-controller
- may submit input for a claimed or assigned PC,
- does not become authoritative for state,
- is authoritative only in the narrow sense of being the accepted source of player input for that PC.

### Why This Is Better Than Immediate Hard Ownership
This staged model is preferable to jumping straight into full lock/ownership systems because it:
- preserves MVP simplicity,
- allows audience mode,
- gives the DM strong social and operational control,
- reduces later remote-session contention,
- creates a natural path toward internet-facing play without prematurely introducing account infrastructure.

### Minimum Future Server-Side Contract
If this evolution is later pursued, the server-side contract should stay narrow.

The server would need to know only:
- client session identity at the connection level,
- current capability mode such as observer or controller,
- optional PC assignment or claim state,
- host override authority.

It should not require browser-authoritative logic or a second gameplay engine.

### Busy State And Responsiveness
Post-MVP should improve visibility into what the server is doing while waiting on LLM work.

Examples:
- processing turn,
- validating action,
- resolving combat,
- waiting for narration.

This is especially important once remote users no longer have the physical DM screen to infer state from.

## Phase 3: Internet-Ready Thin Client
### Goal
Prepare the architecture for broader internet deployment without abandoning the same thin-client core.

### Areas To Expand
- deployment guidance and reverse-proxy/TLS posture,
- more robust session/auth handling,
- stronger reconnect guarantees,
- network-failure resilience,
- observability around event sync and replay,
- optional identity beyond shared-password access,
- stable observer/controller session continuity across reconnects,
- stronger claim/assignment handling if controller roles are enabled.

### Key Principle
Internet readiness should harden the same architecture, not replace it.

The project should still aim for:
- one authoritative server,
- thin remote clients,
- shared event/state contracts,
- bounded client payloads,
- no browser-authoritative gameplay logic.

## Things To Avoid Across All Phases
- per-player PC locks too early,
- account systems too early,
- multiple rooms and lobbies too early,
- client-authoritative game state,
- reusing the entire DM shell for remote clients,
- treating hidden buttons as real access control,
- overengineering public-internet concerns before hybrid play feels good.

## Product-Level UX Implication
If this succeeds, the notable part will not just be that the game works over the network.

The notable part will be that it feels coherent:
- one living shared transcript,
- one clear server authority,
- one lightweight browser join path,
- low friction between local and remote players,
- LLM-driven DMing that still feels socially playable in real time.

That is why the roadmap should continue to optimize for thin, disciplined, server-authoritative design rather than feature sprawl.

## Recommended OpenSpec Progression
After review, the likely OpenSpec sequence should be:

1. `remote-client-auth-shell`
- `/login`, `/client`, session gate, dedicated client shell.

2. `remote-client-shared-event-sync`
- formal event matrix, shared broadcast correctness, active-PC synchronization.

3. `remote-client-surface-restriction`
- route allowlist, host/client capability separation, admin exclusion.

4. `remote-client-reconnect-resync`
- gameplay snapshot contract, reconnect restoration, combat/session continuity.

5. `remote-client-lan-verification`
- multi-browser verification and regression checks.

6. later post-MVP slices
- `remote-client-observer-mode`
- `remote-client-soft-identity`
- `remote-client-turn-focus`
- `remote-client-claim-assignment-model`
- internet hardening.

## Recommended Next Step
Use `plans/version-2/client_network.md` as the MVP architecture contract and this file as the staged roadmap.

After review:
- freeze the MVP decisions,
- refine any open questions,
- then scaffold bounded OpenSpec changes from the phased sequence above.
