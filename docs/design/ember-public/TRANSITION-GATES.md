# Required interaction-transition and architecture gates

These gates supplement every screen row in `PORT-PLAN.md`. Implementation and
test receipts are now recorded in `PROGRESS.md` (full-screen integration
checkpoint); final cross-screen/owner acceptance is still pending. Do not treat
a partial receipt as closure of every transition in a gate. They are not waived
by clean plan review, resting
screenshots, mockup approval or identical donor files. Each implementation PR
must link the relevant test, personally inspected capture and result here.

## F1 — Inventory view continuity

Owners: `sheet/InventoryTab.tsx`, `RightPanelTabs.tsx`; baseline
`web/templates/game_interface.html` `displayInventory` refresh preservation.
Preserve query, filter, touched sort/order and scroll across five-second polling,
tab switches and breakpoint changes, while updating quantities. Use an existing
presentation/session owner above unmounted tab bodies, not persistent game data.
Test populated inventory → filter/sort/scroll → refresh → another tab → return →
1023/1024 resize. Verify search-popup dismissal/focus and preservation of entered
query; do not silently reopen a dismissed popup. Session reset must not leak another
campaign's transient selection. Record explicit reset policy and assertions.

## F2 / A2 — Asset freshness, identity and asynchronous resolution

Owners: `sheet/CharacterSheet.tsx` Portrait, `party/media.ts`, `CharacterChip.tsx`.
Current upload cache-busting is local; media probe promises cache successes and
misses indefinitely. Introduce narrowly keyed media invalidation/versioning for
upload, active pack and campaign changes. Retain original candidate order/name
normalization and server fallback; do not replace original photorealistic assets.

Test missing portrait → upload → replacement without page reload: sheet,
exploration rail, initiative and full-size viewer must update together. Failed
upload retains prior artwork; stale negative probes cannot suppress new media.
Use entity/session/selection generation or cancellation so rapid A→B opens only
B; close, unmount, leaving combat, removing an NPC or loading another campaign
during resolution cannot reopen stale A. Bound probe timeouts/cache growth and
release pending media resources/listeners. Simulate delayed/missing media in tests,
not paid generation. Check pointer, keyboard and touch.

Current bounded receipt: [MEDIA-REVIEW.md](MEDIA-REVIEW.md). Real upload and file
persistence, rejected-upload preservation, desktop/open-viewer/combat/phone
refresh and alias/selection regression tests pass. The open-viewer integration
uses an explicitly injected named invalidation event; native file-picker
keyboard/touch activation and every live campaign transition remain open.

## F3 — Live child-detail reconciliation

Owner: `sheet/NpcsTab.tsx` currently stores a selected NPC object snapshot for
`NpcDetailModal.tsx`. Store stable identity plus detail kind and resolve against
the current public store; never use array position as entity identity. With
inventory/spells/features open, deliver changes to quantity, charges, slots and
usage; update the correct NPC without closing the panel or losing focus/scroll.
Entity removal, reset/load or identity change must reconcile or dismiss safely
with focus fallback, never retain another campaign's data. Preserve existing
conditional visibility of all seven NPC detail actions.

## A1 — Responsive ownership and continuity

Owners: `layout/AppShell.tsx`, `useEmberViewport.ts`, `log/DiceStrip.tsx`, party
components. The breakpoint currently remounts dice/party components in different
subtrees; local roll arrays can be lost. Keep session presentation state in a
stable owner or retain component identity while changing placement. Do not create
new mechanics or alter public hydration contracts.
Test repeated active 1023↔1024 transitions with accumulated rolls, unsent draft,
selected tab, scroll and inspection open. Preserve rolls/draft/selection/scroll;
media/inspection must remain correctly anchored or deliberately close with focus
restored to a surviving trigger. Assert no duplicated hydration/polling, submit,
autoplay or media listeners. Existing phone layout is not replaced by hosted UI.

## F5 — Spell identity, aliases and supplied metadata

Owners: `sheet/SpellsTab.tsx` `spellKey`, `data/spell_repository.json`, public
`/spell-data`, NPC spell and scroll inspection. The actual endpoint already
supplies canonical and alias keys through `core/ai/srd_reference.py`
`compatibility_spell_map`; no new alias API is needed. Align UI lookup with the
server's `normalize_rule_name`, including Unicode/curly-apostrophe normalization,
without inventing or merging different spells. Test Acid Arrow and its supplied Melf's Acid Arrow /
Melf’s Acid Arrow aliases, ASCII/curly apostrophes and supported punctuation in
player, NPC and scroll detail access against the real `/spell-data` response,
not an assumption that the endpoint returns the raw repository. Unknown names show explicit missing-detail
fallback rather than a silent dead hover target.
Render supplied player-facing name/level/school/casting time/range/duration,
V/S/M including material text, description, higher-level text, ritual,
concentration and classes; preserve prepared/slot/charge state separately from
repository metadata. Test long, absent and optional fields, alias/canonical
equivalence and missing-data/error behavior without fabricated values or new
casting mechanics. Reuse one public resolver/detail model across these surfaces.

## A3 — Audio ownership and cleanup

Owners: `log/TtsButton.tsx`, settings `VoiceControls` in `SettingsMenu.tsx`.
Narration and preview currently own playback independently. Establish one public
audio coordinator across narration, settings preview and browser speech. Define
owner handoff without changing narration text, engine/voice selection or pricing.
Test narration→preview→narration with only one active owner; pending responses
after close/unmount/disable/engine or voice change cannot start playback. Cancel
pending requests and speech appropriately. Bound audio/blob caches, revoke object
URLs on eviction/session cleanup and clear ownership on restart/disconnect as
specified. Use synthetic audio/server doubles; real paid TTS requires approval.

## A4 / F4 — Overlay arbitration, portals and hover-to-media

Owners: shared `DialogShell`, NPC details, `CharacterTooltips`, `StatsTooltip`,
`MediaPopup`, settings autoplay tooltip, progress overlays. Scope both sibling
dialogs outside the grid and body portals to the active Ember presentation.
Use a coordinated overlay stack: only the topmost eligible surface receives
Escape/backdrop dismissal; nested detail returns focus to its trigger then parent.
Make obscured parents inert with reference-counted scroll locking; detached
triggers use a safe surviving panel/tab fallback. Hover tips must yield to media
viewers and dialogs, not obscure them. Preserve blocking progress semantics—do
not invent dismissal/cancel for noncancellable operations.
Test NPC→spell/media nesting, tooltip→media activation, operation overlay over
dialog, closing in order, resize, detached anchors and pointer/keyboard/touch.
Verify no double-close, background action, trapped focus or leaked scroll lock.
Screenshot each open state against its Ember target, not only the resting shell.

## A5 — Shared assets across actual public entry points

Owners: `module_builder_web.py` uses `web/static` independently of Vite;
`web/web_interface.py`, toolkit/builder templates and React build.
Publish shared Ember CSS/fonts/icons at public static paths resolvable by both
Flask entry points; React may consume the same source with explicit build/copy
ownership, without duplicating drifting token definitions. Include licenses and
an asset manifest; never depend on private paths or a running Vite dev server.
Test clean public checkout/build with actual standalone `/`, game `/toolkit` and
`/play/`, plus missing-React-build legacy fallback. Block external font requests
during screenshot tests to prove self-hosted rendering. Preserve/test existing
Socket.IO CDN/runtime behavior separately; self-hosted fonts alone do not make
the entire legacy/toolkit/builder app offline. No silent launcher-default change.
