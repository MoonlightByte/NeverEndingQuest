# Bundled Ember fonts

Cinzel (normal 400/600) and Crimson Text (normal 400/600, italic 400), in the
Google Fonts WOFF2 Latin, Latin-ext and applicable Vietnamese subsets. These
are the font families already requested by the public player's original
`index.html`; this change serves their files locally instead of using the CDN.

Binary subsets were copied unchanged from the reviewed Ember font bundle. Only
the named Cinzel and Crimson Text files were selected. No IM Fell font, hosted
application code or private artwork was transferred. `OFL.txt` retains the
applicable copyright notices and SIL Open Font License 1.1. The font binaries
have not been converted, renamed internally or modified.

Upstream project attribution:

- Cinzel: https://github.com/NDISCOVER/Cinzel
- Crimson Text: https://github.com/googlefonts/Crimson

`fonts.css` declares subset coverage and weights. Screenshots must wait for
`document.fonts.ready`. Bundling these files is not a claim that every operating
system rasterizes the same glyphs identically.
