# Remote Multi-Player Browser Clients Architecture Plan

## Objective
Adapt the existing NeverEndingQuest web server to support remote browser clients for tabletop multiplayer sessions, starting with LAN-hosted play and leaving internet hardening for a later phase.

This plan is for architecture review only. It is intentionally scoped as an MVP architecture proposal, not an implementation checklist.

## Why This Change Exists
The current tabletop workflow assumes a single laptop with a facilitator operating all player characters locally. The desired extension is a host-driven model where:
- The DM starts the existing server.
- The DM shares a URL with remote players.
- Players join from their own browsers.
- All participants see live narration and chat updates in real time.
- Players can select the currently active PC tab and send actions through the same game loop already used by the local tabletop flow.

Voice and video remain out of band via Zoom, Meet, or similar tools.

## Decisions Locked For MVP
These decisions are deliberate scope controls for the first architecture slice.

1. Hosting model
- The DM hosts the existing Flask/SocketIO server.
- Initial target is LAN accessibility only.
- Internet exposure, reverse proxying, tunneling, and TLS are explicitly deferred.

2. Identity model
- MVP does not introduce per-player accounts.
- MVP does not introduce per-player permissions.
- All remote players use one shared client password.

3. Active character model
- `active_character` remains a single shared server-side state.
- Selecting a PC tab from any browser updates the active PC for all connected browsers.
- Human players are expected to coordinate socially around turn ownership.

4. UI model
- DM keeps the full host interface at `/`.
- Players use a dedicated lean client route at `/client`.
- The client page is not just the DM page with CSS-hidden controls; it should be a deliberately bounded client-facing surface.

5. Shutdown model
- Client disconnect or closing the browser only disconnects that client.
- Client UI must not expose server shutdown or restart controls.
- Only the DM host interface may retain shutdown behavior.

6. Scope boundary
- This MVP is about shared browser access to the existing game loop.
- It is not a general multiplayer rewrite.
- It is not a turn-locking, player-account, or authoritative ownership system.

## Existing Architecture Observations
Current codebase characteristics relevant to this plan:

1. Transport
- `web/web_interface.py` already uses Flask plus SocketIO.
- The server already binds to `0.0.0.0`, so LAN access is structurally available.

2. Output flow
- Server narration and system output are emitted through the global SocketIO path and already behave like shared broadcast output.

3. Input flow
- Some per-client event emissions are still sender-scoped.
- The main known multiplayer gap is not transport availability but event-contract consistency.

4. Tabletop state
- The existing tabletop mode already has shared party state, shared active character state, and a web tab metaphor.
- That makes remote-browser access feasible as an extension of the current tabletop model rather than a brand-new game mode.

## Performance And Asset Strategy
This architecture should explicitly avoid dragging the full host interface into remote-client mode just because it is already there.

### 1. Primary Performance Concern
The likely first-order performance issue is not SocketIO itself and not the current standalone static assets.

The larger concern is host-page weight and execution scope:
- `web/templates/game_interface.html` is already large and carries substantial inline UI logic.
- A client route that simply reuses the full host page and hides controls would still ship host-only markup, host-only scripting paths, and unnecessary UI state machinery to every remote player.
- That is acceptable only as a temporary debug shortcut, not as the intended architecture.

### 2. Client Performance Principle
The client route should be treated as a lean gameplay surface, not as a cosmetically reduced admin console.

Required principle:
- `/client` should load only the assets, markup, and runtime logic required for remote participation in play.

That means the architecture should prefer subtraction at source over hiding after render.

### 3. Asset Loading Direction
Preferred direction for the client surface:

1. Dedicated client shell
- Use a dedicated client template instead of rendering the full DM shell and removing pieces afterward.

2. Shared assets only where they are truly shared
- Reuse stable CSS and JS modules only when they support both host and client gameplay needs.
- Avoid loading host-only control logic into the client page.

3. Move reusable behavior into cacheable static assets
- Shared gameplay behavior should live in static JS/CSS files where practical.
- Avoid growing the client through large inline script blocks embedded directly in the template.

4. Exclude host-only features from the client payload entirely
- Toolkit logic, server lifecycle controls, admin/debug UI, party-management flows, heavy settings surfaces, and other host-only controls should not be present in client markup or client boot logic.

5. Keep initial client boot narrow
- Client boot should focus on transcript rendering, websocket connection, active-PC synchronization, input submission, and relevant gameplay state display.
- Non-essential enhancements should be deferred or loaded only if proven necessary.

### 4. Event Payload Discipline
Internet playability will depend more on payload discipline and update behavior than on raw HTML transfer size alone.

The plan should therefore assume:
- shared events should carry only the state required for the client surface,
- large facilitator-only payloads should not be broadcast to all clients by default,
- admin/debug/toolkit data should stay out of the client event contract,
- repeated full-state refreshes should be questioned when a narrower delta or focused refresh would suffice.

The MVP does not need an elaborate diff engine, but it should avoid lazy over-broadcasting.

### 5. Runtime Scope Discipline
The client architecture should minimize JavaScript execution scope as well as download size.

That means:
- no binding of host-only event handlers on the client page,
- no client initialization of modals or forms that do not exist on `/client`,
- no server-exit, toolkit, or party-management client-side logic loaded into the remote shell,
- no assumption that one giant page is easier just because it already exists.

### 6. MVP Performance Goal
For MVP, the target is not extreme optimization. The target is disciplined architecture.

Success looks like this:
- a remote client on ordinary home internet can load `/client` quickly,
- reconnect cleanly,
- receive transcript updates in real time,
- switch active PC without visible desync,
- and do so without paying the asset and execution cost of the full host interface.

### 7. Architectural Consequence
This performance posture strengthens the earlier UI decision:
- `/client` should be a dedicated lean shell,
- not a hidden-controls variant of `/`.

If later measurement shows the dedicated client shell is still heavier than desired, that should trigger further extraction and trimming of shared gameplay assets, not a retreat back to the full host template.

## MVP Architecture

### 1. Host And Client Surfaces
Two web entry points should exist.

1. DM host route: `/`
- Keeps the current full interface.
- Retains admin and facilitator controls.
- Remains the authoritative operating surface for maintenance tasks.

2. Player client route: `/client`
- Provides a bounded gameplay UI only.
- Focuses on live transcript, PC tabs, character sheet visibility, dice/actions input, and combat usability.
- Excludes server-management surfaces.

This split is preferred over trying to make one template behave as both a full DM console and a safe player client shell.

### 2. Shared State Model
The MVP should keep server authority exactly where it already lives.

Authoritative state remains in existing server-managed data such as:
- `party_tracker.json`
- conversation history files
- encounter/combat state
- current tabletop socket responses

Remote clients do not become authoritative for any new domain. They only:
- request tab changes
- submit player input
- receive synchronized server state

### 3. Authentication Model
Authentication is intentionally simple for MVP.

1. Configuration
- Add optional `CLIENT_ACCESS_PASSWORD` in config.

2. Page access
- If `CLIENT_ACCESS_PASSWORD` is blank, `/client` behaves as open LAN access.
- If `CLIENT_ACCESS_PASSWORD` is set, `/client` requires successful login first.

3. Session behavior
- `/login` sets a session flag for client access.
- `/client` checks that session flag.

4. SocketIO behavior
- Socket connections used by the client surface must be treated consistently with the authenticated page session.
- The plan must not rely on HTML route protection alone while leaving websocket joins effectively unauthenticated.

5. DM route behavior
- `/` should remain unchanged for the host workflow.
- Whether `/` also requires LAN trust assumptions or future auth is a separate decision and out of this MVP.

## Event And Route Contract
The implementation should be driven by an explicit event matrix rather than ad hoc `broadcast=True` additions.

### 1. Broadcast Classes

1. Global gameplay events
- Must be visible to all connected host and client browsers.
- Examples: narration output, player chat echo, combat progress, active character changes, party-state refreshes relevant to shared play.

2. Sender-only UI events
- Should remain local to the initiating browser.
- Examples: local form validation feedback, purely local modal state, browser-only toggles.

3. DM-only/admin events
- Should never be exposed to the client route if they reveal facilitator-only controls or maintenance surfaces.
- Examples: toolkit workflow, debug/admin functions, server lifecycle actions.

### 2. MVP Event Expectations
At minimum, the plan assumes these behaviors:

1. `game_output`
- Shared broadcast.
- All connected participants see user input echoes and narration in the same timeline.

2. `active_character_update`
- Shared broadcast.
- Any PC tab selection updates all open browsers.

3. Shared party refresh events
- Broadcast when they reflect common gameplay state needed by all participants.
- Must not leak admin-only payloads.

4. Client-local visual events
- Remain sender-scoped where the outcome is only cosmetic or browser-local.

### 3. HTTP Route Protection Model
The client-facing plan also needs an explicit route classification.

1. Safe for `/client`
- Read/shared-state routes required to render gameplay.
- Input routes required to submit actions through the normal game loop.

2. Not safe for `/client`
- Party management
- PC edit/create flows
- toolkit routes
- save/load/reset flows
- server shutdown/restart flows
- admin/debug surfaces

This route allow/deny model should be treated as part of the architecture, not as a cosmetic front-end concern.

## Client Capability Matrix

### DM Host (`/`)
The host retains the existing facilitator role.

Allowed capabilities:
- Full game transcript
- PC tab switching
- Player input submission
- Character sheet access and editing
- Party management
- Save/load/reset
- Settings and model controls
- Toolkit access
- Server exit behavior

### Player Client (`/client`)
The client should be intentionally lean.

Allowed capabilities:
- See the live game transcript in real time
- See the current shared active PC state
- Select a PC tab, changing the shared active PC
- Submit gameplay input for the currently active PC
- View relevant character sheet and combat information
- Use gameplay-facing controls needed for play

Not allowed in MVP:
- Manage Party
- Add PC / create PC
- Edit PC sheet
- Save/load/reset campaign
- Toolkit access
- Admin/debug controls
- Server exit / shutdown controls
- Broader settings surfaces not required for remote play

### Open Question To Keep Explicit
The original request said settings are unnecessary for clients except possibly DM Voice. That should stay unresolved until review because DM Voice on a remote client may be misleading if audio is meant to remain a local-host concern.

Recommended MVP default:
- Do not expose DM Voice controls on `/client`.
- Treat audio/TTS as host-local unless there is a deliberate later decision to support client-local narration playback.

## UI Architecture Direction
The client route should not be implemented as a fragile pile of conditionals inside the existing host page unless that proves materially simpler after review.

Preferred direction:
1. Reuse existing CSS and shared partials where practical.
2. Create a dedicated client-facing template shell.
3. Include only the components needed for live play.
4. Keep host-only actions absent from markup, not merely hidden after render.

This reduces the risk of accidental exposure of facilitator controls through JavaScript bindings or stale DOM paths.

## Security Posture For MVP
This is intentionally a light-trust LAN design.

Assumptions:
- The DM shares the URL and password directly with invited players.
- The LAN environment is semi-trusted.
- There is no adversarial threat model in MVP.

Non-goals for MVP:
- strong user identity
- per-player authorization
- HTTPS/TLS setup
- brute-force protection
- internet-safe deployment guidance
- audit logging of player identities

Even with that limited scope, the architecture should still avoid obvious mistakes:
- Don’t expose admin routes through the client shell.
- Don’t rely only on hidden buttons for access control.
- Don’t treat websocket actions as implicitly trusted if page auth exists.

## Risks And Tradeoffs

1. Shared active PC contention
- This is the biggest intentional compromise.
- Multiple players can override each other’s selected PC.
- Accepted for MVP because the user explicitly prefers social coordination over added system complexity.

2. Shared password model
- Simple to operate, weak for attribution.
- Accepted for MVP because this is a facilitator-run tabletop session, not a public service.

3. Divergent host/client UI logic
- A dedicated client route reduces accidental admin leakage.
- It adds template maintenance cost.
- This is still preferable to unsafe over-reuse in the first slice.

4. Event broadcasting mistakes
- Over-broadcasting can leak payloads.
- Under-broadcasting causes desync.
- This is why the implementation should begin with an explicit event matrix.

## Acceptance Criteria For MVP
The architecture should be considered successfully implemented only if all of the following are true:

1. Connectivity
- A DM can host the server on LAN and remote browsers can load `/client`.

2. Authentication
- If `CLIENT_ACCESS_PASSWORD` is set, `/client` requires login before use.
- If the password is blank, `/client` remains accessible without login.

3. Shared transcript
- When one participant sends input, all connected participants see the same user input echo and resulting narration updates in real time.

4. Shared active PC state
- When any participant changes the active PC tab, all connected browsers reflect the new active character.

5. Client isolation
- Client browsers cannot access server shutdown behavior from the `/client` UI.
- Client browsers do not see party-management, PC-edit, toolkit, save/load/reset, or admin/debug surfaces.

6. Gameplay continuity
- Client input still flows through the existing server-side validation, narration, and combat systems.
- No parallel gameplay engine is introduced.

7. Host continuity
- The DM host interface at `/` continues to function as before.

## Out Of Scope For This Architecture Slice
These items should not be smuggled into the MVP implementation.

1. Internet deployment hardening
2. User accounts or named player identity
3. Per-player PC ownership locks
4. Multi-room or campaign-lobby architecture
5. Voice/video integration
6. Full mobile UX adaptation
7. Rewriting tabletop mode into a fully separate multiplayer system

## Recommended OpenSpec Breakdown
This architecture likely wants more than one change rather than one oversized implementation blob.

Recommended slices:

1. `remote-client-auth-shell`
- Add `/login`
- Add `/client`
- Establish client session/auth gate
- Establish dedicated client shell/template

2. `remote-client-shared-event-sync`
- Formalize event matrix
- Broadcast shared gameplay events correctly
- Ensure active PC sync behaves consistently across browsers

3. `remote-client-surface-restriction`
- Lock down client-visible controls and routes
- Ensure client shell excludes admin/facilitator operations

4. `remote-client-lan-verification`
- Verification and smoke criteria for multi-browser LAN testing
- Ensure host and client surfaces coexist without regression

## Recommended Next Step
After review and refinement of this plan:

1. Freeze the MVP decisions.
2. Convert the architecture into the OpenSpec slices above.
3. Implement in bounded increments with verification after each slice.

This change touches transport, auth, UI boundaries, and shared-state behavior. It should be treated as an architecture change, not as a one-shot feature patch.

## Additional Review Notes Captured
The following points are intentionally captured now because they shape the likely direction of the later internet-thin-client version.

### 1. Mixed Tabletop And Remote Play Is The Primary Use Case
This architecture is not just for replacing the local tabletop setup.

It should explicitly support mixed sessions where:
- some players are physically present with the DM,
- some players are connected by browser over LAN or internet,
- all participants share the same authoritative server-driven session.

That hybrid model should be treated as the normal target case, not as a temporary compromise.

### 2. Shared `active_character` Contention Is Acceptable In MVP
The user explicitly considers shared `active_character` contention acceptable because it mirrors the normal in-person experience of multiple players trying to get the DM's attention.

Therefore:
- MVP should not introduce heavy ownership or lock systems,
- shared active-character switching remains acceptable as a social coordination problem,
- facilitator control through out-of-band voice/video remains part of the operational model.

### 3. A Future Minimal Server-Side Turn-Focus Lock Is Worth Noting
Although not required for MVP, the architecture should leave room for a later lightweight server-side focus mechanism.

Example direction:
- the host can temporarily assert a simple turn-focus state such as `It's Acheron's turn now`,
- the system can visually reinforce that focus without introducing a full player-account or ownership model,
- this should remain a thin coordination layer, not a heavy permissions framework.

This is best treated as a post-MVP enhancement, not as a requirement for the first slice.

### 4. Reconnect/Resync Should Be Treated As Core Multiplayer UX
The project will feel playable remotely only if clients can reconnect cleanly.

For that reason, the architecture should treat reconnect/resync as a first-class gameplay requirement rather than a later operational convenience.

A reconnecting client should be able to recover at least:
- recent transcript,
- current `active_character`,
- party state relevant to play,
- current combat state if combat is active,
- any visible shared busy/processing state.

### 5. Shared Busy State Matters For LLM UX
For remote play, a large part of perceived quality will come from whether connected clients understand what the server is doing while the LLM is thinking.

The architecture should therefore leave room for a shared, low-complexity processing-state contract such as:
- processing turn,
- validating combat action,
- waiting on DM response,
- resolving combat batch.

This is a major UX multiplier without requiring deeper multiplayer mechanics.

### 6. Soft Identity Is A Strong Post-MVP Enhancement
The likely next clarity upgrade after MVP is not full accounts.

It is a lightweight session-identity layer such as:
- who connected,
- who selected a PC,
- who submitted an action.

That would improve multiplayer readability substantially while still preserving the thin-client, server-authoritative model.

### 7. Event Ordering And Replay Discipline Will Matter
If this architecture becomes the basis of an internet-facing thin-client product, transcript consistency will become part of the product experience.

That means later work should explicitly define:
- message ordering expectations,
- reconnect replay behavior,
- duplicate suppression expectations,
- client-safe snapshot/bootstrap rules.

MVP does not need a large distributed-systems solution, but it does need a clean contract.
