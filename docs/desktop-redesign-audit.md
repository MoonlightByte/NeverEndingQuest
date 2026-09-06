# Open-source desktop redesign audit

Baseline: public `MoonlightByte/NeverEndingQuest` main at `185f8997a5055521f04fe7a55ca908a41f0d412f`.

The approved desktop presentation was applied as a source patch onto that public baseline. This branch does not merge private repository history. The existing public socket handlers, stores, backend, provider settings, and lifecycle dialogs are retained.

| Surface | Result |
| --- | --- |
| Header | Start/New Game, status, Save, Load, Reset, Settings, Toolkit, Exit and update affordance retained. Existing disconnected/startup/restore/reset guards retained. |
| Settings | AI provider selection, local/custom endpoint and connection controls, provider keys, voice engine/voice/preview/autoplay, AI images and map style retained. |
| Character tools | Character, Inventory, Spells & Magic, Map, Journal and Debug remain accessible. NPC tab intentionally replaced by right-hand NPC cards on desktop; compact mode retains it. |
| Party and combat | Player/NPC card body opens full character sheet; portrait opens media. Initiative/round display and character selection preserved. |
| Character dialogs | Fixed identity header and tab frame, full abilities/combat/XP/currency, inventory/spell inspections, NPC skills/saves/features/traits/background and personality retained. |
| Inventory and spells | Compact searchable inventory; player storage remains available; spell slot totals and available/spent markers use actual character records. |
| Story and dice | Composer, Send, quick dice, Clear, per-message Listen and Generate image retained. Focus story adds a reversible reading layout. |
| Lifecycle | Save options, load/delete selection, reset confirmation, exit confirmation, startup/progress/compression and update dialogs retained. |
| Small screens | Existing public viewport switch retained. This desktop release does not replace the separate mobile shell. |

Validation: TypeScript production build passed; 359 tests across 40 files passed. Oxlint completed with existing warnings. Browser review used the public repository's fixture server and verified the desktop layout, public header, Save, Load, Reset, and all Settings sections. No live campaign was changed.

Two existing HeaderBar tests were updated to reflect the public baseline's disconnected Start Game guard and connected returning-player state; the HeaderBar implementation was not changed.
