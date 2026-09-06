# Ember public — bounded performance comparison

Measured with Chromium 149.0.7827.55, 1586×992, no CPU/network throttling,
three alternating rounds per frontend. Both versions use the same isolated
current backend, no engine/provider calls, 400 long narration messages and
80 synthetic NPCs. Cardinality remains asserted during each measurement.

## Provenance

The baseline's 127 tracked frontend files were checked against Git blobs at
`21702a7da7276f0ca6d3cd6612dcf40aceee703c`. The retained baseline build and
copied measured dist have identical file/hash maps. Every actual browser-loaded
JS/CSS response returned 200 and matched its measured dist SHA256 in all six
rounds. Backend HEAD `3c5eb754` is backend identity only, not baseline frontend
provenance; pre-swap runtime manifests are not used as build proof.

Measured Ember assets include the desktop confirmation implementation:

- `index-gSh9mxqG.js`: `7075eb8a60334a287e17d024904ee7ca7b1b73e47ec8012028848e474fd75a5e`
- `index-BZSCp_jN.css`: `640f315f7215834778d1cc8e7001ccb71f4b4e4b01bc2fba5d78f400e0bceadc`

Final raw evidence is retained locally at
`/mnt/e/neq-ember-entrypoint-probes.CoTVdyp2/ember-performance-final-result.json`.
Earlier stress-result files measured an older build; do not mix their numbers
with this receipt. The corrected probe and final evidence received independent
source/provenance review with no remaining reported finding.

## Results

| Measurement | Public baseline | Ember |
| --- | ---: | ---: |
| JS raw / default Node gzip bytes | 437,004 / 129,239 | 475,135 / 140,739 |
| CSS raw / default Node gzip bytes | 83,132 / 16,207 | 131,787 / 24,889 |
| Bundled local font bytes | 0 | 206,600 across 11 WOFF2 files |
| Synthetic input → two animation frames, median / p95 | 33.3 / 33.4 ms | 33.3 / 33.4 ms |
| Scripted transcript scroll frame interval, median / p95 | 16.7 / 16.8 ms | 16.7 / 16.7 ms |
| Scripted roster scroll frame interval, median / p95 | 16.7 / 16.7 ms | 16.7 / 16.7 ms |
| Local image resource duration, median / p95 | 175.7 / 311.4 ms | 194.4 / 313.5 ms |
| Stressed DOM listener count, observed range | 2,129–2,133 | 2,532–2,542 |
| Post-scenario-reset / forced-GC listener count | 1,908 | 2,254 |

Each round samples 25 synthetic inputs, 100 transcript intervals and 100 roster
intervals. Maximum scroll interval in this final run was 16.8 ms for both.
Both rendered all 400 messages and 80 NPCs; this is not a virtualization claim.
There were 90–91 image requests per round, including deliberately missing NPC
portraits; 410 DOM images decoded in each sample, including repeated DM icons.
Ember fetched four local fonts on the initial page and no external font CSS.

The extra UI has a measurable cost: about 8.9% more gzip JS, 53.6% more gzip CSS,
and additional nodes/listeners. This small unthrottled fixture did not show a
frame-interval regression. It does not establish a universal performance budget.

## Reproduction and limits

Use the game Python dependency environment and the frontend's declared
`@playwright/test` installation. Build an exact `21702a7` frontend export and
the current Ember frontend, retaining both dist directories. Start two disposable
`ember_performance_runtime.py --port 4220|4221 --temp-parent <existing-test-dir>`
instances; install the baseline dist into only the first disposable runtime.
Then run from `web/frontend`:

```sh
node e2e/ember_performance_probe.mjs BASELINE_MEASURED_DIST EMBER_MEASURED_DIST RESULT_JSON BASELINE_FRONTEND_SOURCE
```

Never replace the owner's running build with the baseline. The runtime helper
inherits the existing disposable portrait harness's credential/network/write
guards. Those guards are controlled-test containment, not an adversarial OS
sandbox. The two performance fixtures were stopped after measurement; exports
and evidence remain available. Existing Linux dependency installations were
reused; this is not an additional clean-install receipt.

- Input timing is synthetic event-to-two-rAF latency, **not field INP**.
- Scroll timing is scripted scrollTop/Left, not compositor or real-device tracing.
- Baseline Google Fonts CSS was deliberately blocked and used fallback fonts;
  Ember used local fonts. Typography/network loading were not identical.
- Bundle totals include all built files, not first-page transferred bytes.
- Local missing-art probes are not production CDN throughput measurements.
- CDP counts include DOM/React listeners, not a Socket.IO subscription audit.
  Scenario reset retains the transcript ledger; the stable post-reset counts do
  not certify leak freedom. Native devices and formal profiling remain unverified.
