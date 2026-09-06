# Public Ember design artifacts

`05-ember-inline-stacked.png` is the exact owner-supplied, approved Ember Stacked
design reference from this task, copied unchanged from the separate design
worktree. It is documentation only, not a runtime texture or a replacement for
the public game's photorealistic artwork.

SHA-256: `5ea38d43b52b6119894b0796f68087a233977e2dc79d7aaa44c6a987d2c76464`.
Dimensions: 1586×992. It contains concept/sample state, not a production save or
provider credentials. No private runtime source, campaign/account code, fixture
portrait files or integration history accompanied this copy.

`captures/` contains browser captures of synthetic review state. The original
public portrait files remain unchanged; fixture-only character assignments are
not game-data changes. The owner must review the artifacts before public release.

`intermediate/captures/` contains ten synthetic 1024/1180px drawer-study captures.
The study uses the existing public artwork and fonts, makes no game requests,
and is not an approved runtime layout. `review-load-selected.png` records the
personally inspected selected/hover state after the legacy styling correction.
`review-combat-overflow.png` records the synthetic 20-combatant processing state,
scrolled to its final entry after the combat badge correction.

Runtime assets and licenses:

- `web/frontend/src/theme/fonts/PROVENANCE.md` and `OFL.txt`: bundled fonts.
- `web/static/fonts/ember/ASSETS.md`, `PROVENANCE.md`, `OFL.txt`: shared workbench
  font inventory and licensing.
- `web/static/css/ember-tokens.css`: canonical shared presentation tokens.
- Dice and coin vectors are authored presentation components, not copied raster
  assets. Original public character/scene media are resolved through existing
  public media paths; nothing is generated during a UI build.
