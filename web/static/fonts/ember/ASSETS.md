# Ember workbench assets

`/static/css/ember-tokens.css` is the canonical palette for both Flask workbenches
and the React build. `/static/css/ember-toolkit.css` owns the workbench presentation
and imports `/static/css/ember-fonts.css`. Both Flask applications serve these paths
from `web/static`; neither requires a running Vite server or a built React bundle.

The eleven WOFF2 files in this directory are unchanged public copies of the
approved frontend fonts in `web/frontend/src/theme/fonts`: Cinzel normal
400/600 (Latin and Latin Extended), Crimson Text normal 400/600 and italic 400
(Latin, Latin Extended and Vietnamese). `OFL.txt` and `PROVENANCE.md` retain their
licenses and source attribution. Keep these binaries synchronized byte-for-byte
when updating the frontend fonts. Do not substitute external font requests.

Existing Socket.IO CDN dependencies are intentionally unchanged. Self-hosting
the fonts does not imply offline availability of Socket.IO or generation services.
No artwork, uploaded media, generator styles, API routes or operation handlers
are supplied or replaced by this stylesheet.
