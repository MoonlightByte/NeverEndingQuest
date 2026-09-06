# Interaction and visual completeness audit

## Owner direction — 2026-09-05

The owner generally approves the additional-screen mockups, subject to independent
codebase review and full information, interaction and visual completeness. This
permits implementation of the direction; it is not visual sign-off or permission
to merge/push public main. Earlier ledger entries saying approval is pending are
superseded by this conditional approval.

Item/spell popups, available animations, player/NPC biography imagery, currency,
bottom dice polish and server visual parity are required scope, not optional
post-release enhancements. Independent review findings follow below.

## Required acceptance evidence

| Surface | Implementation and review gate |
| --- | --- |
| Inventory/equipment | Map actual payload fields to rendered details. Preserve descriptions, quantities, categories, equipped/magic/charge indicators where supported. Capture hover, keyboard and touch details at panel edges without clipping. |
| Spells/magic | Compare public detail responses and legacy/server renderers field by field: casting metadata, description, prepared state, slots, charges, consumables. Review missing/error/long details and keyboard/touch access. No invented casting actions. |
| Skills/features | Retain full descriptions, usage/refresh, proficiency and supplied stats. Test tooltips after scrolling as well as initial render. |
| Player/NPC/monster media and biography | Trace portrait, stats popup, detail dialog and media actions. Preserve supported player upload, supplied biography fields, full-size images and video-first/fallback behavior. Missing media must not remove text/navigation. Do not fabricate biographies. |
| Animation | Exercise real media playback, controls, failure fallback and cleanup; inspect hover/press/roll feedback and reduced motion. Preserve artwork. |
| Currency | Compare character and inventory GP/SP/CP values, coin appearance, alignment and spacing with matched server screenshots and the locked reference. Plain specimen text is not the accepted finish. |
| Bottom dice | Inspect all six glyphs/buttons, hover/focus/press, results, accumulated rolls and Clear in matched public/server states. Preserve local-dice semantics. |
| Overlays | Theme portal content too; verify layering, placement, escape, focus entry/return, scroll and resize. Capture populated and edge states, not just main-screen goldens. |

## Initial direct inspection

- Public/donor `DiceStrip.tsx` are identical. `CharacterSheet.tsx` differs only by
  the newer public no-character notice. Main CSS is nearly identical apart from
  public adaptations. This does not prove rendered parity or concept fidelity.
- `review.js` uses plain dice labels and does not demonstrate complete interactive
  or media states. General gallery approval does not waive these details.
- `InventoryTab.tsx` has a hover-only description inside scroll content.
- `SpellsTab.tsx` uses mouse enter/leave for detail; magic items use native titles.
  Both need interaction and field-completeness work, not just recoloring.

Browser goldens remain regression evidence, not acceptance of visual parity.

## Independent agent findings

Read-only review completed against the public worktree and
`/mnt/e/NEQ-ember-desktop`. No private runtime migration is needed for the
verified presentation/interaction gaps. The reviewer independently confirmed
that many limitations also exist in the donor; retaining those limitations is
not sufficient for the owner's requested complete result.

### P1: details, media and themed overlays

1. **Inventory:** `components/sheet/InventoryTab.tsx:113` renders nonfocusable
   rows and an absolute hover-only description. `characterData.ts:239` carries
   equipped information which the row does not show. Add complete supported
   indicators and accessible, unclipped inspection without changing item rules.
2. **Spells/magic:** `components/sheet/SpellsTab.tsx:23` handles mouse enter/leave
   only; `MagicCategory` uses native titles. Audit `/spell-data` fields before
   defining full detail content. `NpcDetailModal.tsx` spell lists need inspection
   coverage too, not just player spells.
3. **NPC completeness:** `NpcsTab.tsx:43` exposes saves, skills, inventory,
   features, traits, background and spells, plus identity/XP/currency/vitals,
   abilities/alignment/status/condition. The gallery's three portrait rows do not
   represent this information. Expand the approved direction into full populated
   and empty/long detail states; do not replace the NPC sheet with a directory.
4. **Biography versus media:** neither `NpcsTab` nor `NpcDetailModal` currently
   has a biography viewer. Player sheet media is portrait upload; rail media uses
   `party/media.ts` video-first/image fallback. Audit supplied biography fields
   and media associations explicitly before exposing them. Do not assume a
   hosted biography contract or invent missing text.
5. **Portal theming:** `CharacterTooltips`, `StatsTooltip` and `MediaPopup` portal
   to `document.body`, outside `.ember-desktop`. Existing tooltip CSS and popup
   inline styles retain gray/orange/green treatments. Implement a desktop-scoped
   themed portal owner while preserving phone behavior.
6. **MediaPopup:** existing 200ms close transition and autoplay/loop/muted video
   are present, but the popup lacks a visible close button, focus trap/return,
   robust late-media sizing, final bottom clamp and failed-load fallback. The
   desktop reduced-motion selector does not reach the portal. Test actual video,
   image fallback, late/error loading, viewport edges and all dismissal methods.

### P2: polish and evidence completeness

7. The gallery's currency and dice are text-only, unlike the production coin
   markup. Every production die still uses the same SVG. Review coin styling,
   distinct reference die silhouettes and hover/focus/press/disabled/result states
   against matched server renders and the locked concept; do not call an unchanged
   component proof of parity.
8. Add a child-state manifest to each screen: source owner, trigger, supplied
   fields, media candidates, loading/error state, keyboard/touch behavior,
   screenshot target and runtime test. A resting-screen capture cannot satisfy
   a popup, video or nested-detail gate.

Implementation sequence: child-state manifest → shared themed accessible
inspection/media primitives → complete NPC/detail/media surfaces → currency/dice
polish → personal screenshot and functional passes. Keep every public handler
and data owner; no inferred equip/cast/biography functionality. Final owner
visual/functional approval is still required before any public-main integration.
