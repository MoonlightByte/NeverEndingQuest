# Portrait filename handling

CharacterChip now encodes each background-image URL as one CSS string. Portrait
filenames with quotes or parentheses remain usable and cannot append another
image layer. Layout and media fallback behavior are unchanged.

After `npm ci` in web/frontend and `npx playwright install chromium`, run
`node ops/audit-browser-media.mjs` from the repository root. The harness builds
actual React components and intercepts every network request. It checks 256 cases
across text, images, videos and portrait chips, both presentation modes and with
or without an explicitly labelled test CSP. It does not claim local deployments
supply that policy. The CSS repair must pass without relying on CSP.

NEQ_CHROMIUM_PATH optionally selects an installed Chromium; NEQ_MEDIA_AUDIT_OUTPUT
writes a receipt with browser version, source hashes and individual observations.
