# Test the public Ember branch

Implementation branch: `feat/ember-public-complete` in `/mnt/e/NEQ-ember-public`.
No public-main merge or launcher-default change is authorized. Your final visual
and functional review remains required.

## Pick the right test mode

- **Interactive mockup:** [game](http://localhost:4204/play/),
  [toolkit](http://localhost:4204/toolkit), [builder](http://localhost:4204/builder).
  These run the actual implemented UI with scripted fixtures. Do not enter real
  keys. Provider/save responses are simulated; authoring/generation are disabled.
- **Real public game:** use `python run_web.py --ui react` from this worktree in
  the configured game environment. It uses real providers/settings/campaigns;
  see [launch instructions and data/cost cautions](HANDOFF.md#real-public-game--deliberate-live-testing).
- **Design study only:** [intermediate-width drawers](http://localhost:4214/intermediate)
  are a separate proposal, not current production navigation. Gallery images
  are not functional tests of the application.

If these local preview servers have stopped, restart commands are in HANDOFF.md
and intermediate/README.md. Refresh an already-open preview after a new build.

## In-game inspection route

Start at 1586×992 if possible, then try your normal desktop window size. Keep
the [locked reference](05-ember-inline-stacked.png) nearby. Original public art,
public-only header actions, authored icons and font rendering differ from the
concept as documented in VISUAL-REVIEW.md; 100% raster equality is not claimed.

| Open / try | What to inspect | Preview limitation |
| --- | --- | --- |
| Story and command entry | Three-column layout, long-text scrolling, optional inline image, readable narration, free-text composer | `Look around` returns scripted text; it is not AI inference |
| D20 through D4, then Clear | Six different glyphs, hover/focus/press feedback, accumulated results and currency finish | Rolls are local dice, not authoritative game checks |
| Character | Portrait, XP, HP/AC/initiative, all six abilities, weapons/ammo, saves, features/traits/background and GP/SP/CP | Sample character; ordinary mock preview does not persist portrait uploads |
| Underlined item, skill, feature or spell detail | Hover and keyboard focus, pin/open detail, long-text scrolling, Escape and focus return | Inspect supplied sample metadata; no invented equip or cast actions |
| Inventory | Categories, quantity/equipment indicators, search/filter/order, currency, storage entry | Fixture items/counts; transfers are not new mechanics |
| Spells & Magic | Casting summary, slots, prepared state, aliases, descriptions, scroll/magic-item metadata | Sample spell data; no real casting occurs |
| NPCs and detail actions | Identity, stats, saves, skills, inventory, features, traits, background and spells where supplied | Not every NPC exposes every action; no fabricated biography text |
| Party portraits, stats and Details | HP/bar, AC, level and XP beneath names when supplied; NPC Details opens the same full card/seven conditional menus as the NPC tab; portraits still open original media | Missing data is not invented; sample art only; paid generation is not connected |
| Enter `combat` | Right-side initiative, server-shaped order, round/current turn, scrolling and retained character sheet | Scripted encounter, not real combat; refresh returns to exploration |
| Map and expanded map | Existing parchment/night preference, notes, pan/zoom/reset, expansion and close | Sample reveal state; no real exploration/AI turn |
| Journal and Storage | Journal is again a two-page parchment book with current/completed quests; inspect page scrolling, close and focus return; Storage remains Ember | Sample data; real campaign refresh requires live testing |
| Settings | All four public providers, endpoint/model/key controls, images, voice/preview/autoplay and map settings | Synthetic keys only; simulated provider persistence/test responses |
| Save and Load | Description/mode, list/selection, pending/confirmation/error presentation | Simulated actions; do not interpret mock “Saved” as a real backup |
| Reset and Exit | Confirmation/cancel, clear consequences, safe focus/navigation | Do not confirm real destructive actions merely to inspect appearance |
| Debug | Token statistics and log readability/scrolling | Synthetic diagnostics; no formal production performance guarantee |
| Resize / keyboard | Draft and tab continuity, dice retention, reachable controls, tab arrows/Home/End, modal Escape/focus | Preserved public phone layout, not the separate mobile redesign |

Startup, recovery, loading/error and operation overlays only appear when their
corresponding state occurs. They are not missing because a running sample game
does not display them all at once. Their test fixtures/captures and remaining
limits are mapped in ACCEPTANCE-MATRIX.md; do not trigger paid or destructive
work to make an overlay appear during a visual-only review.

## Toolkit and builder inspection

Visit all six Toolkit tabs: Graphic Pack Management, Monster Management &
Generator, NPC Management & Generator, Video Processor, Module Builder and
Module Media Generator. Inspect forms, tables, nested settings/style/selection dialogs,
progress and error presentation, then compare the standalone Builder. Preview
mutation/generation responses deliberately explain that no backend job ran.
The existing public merge endpoint is still a nonfunctional placeholder; Merge
is disabled with a readable explanation rather than presented as working. Old
monster edit/regenerate/delete TODO functions have no reachable buttons or
callers and are not implemented mechanics in this port.

## Send the final review

For a problem, include the screen/action, viewport, expected result and screenshot;
say whether you used the mock preview or the real game. Never include keys or
private campaign text you do not want stored with review evidence.

Please explicitly accept or request changes for the desktop main screen,
additional panels/dialogs/toolkit, and the separate intermediate-width proposal.
Your review does not automatically authorize a public-main merge or paid tests.
