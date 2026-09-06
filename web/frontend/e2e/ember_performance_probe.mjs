// Usage: node ember_performance_probe.mjs BASELINE_DIST EMBER_DIST RESULT_JSON BASELINE_FRONTEND_SOURCE
// Requires two disposable ember_performance_runtime.py servers on 4220/4221.
import { chromium } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { fileURLToPath } from 'node:url'
import fs from 'node:fs'
import path from 'node:path'
import zlib from 'node:zlib'
const [baselineDist, emberDist, output, baselineSource] = process.argv.slice(2)
if (!baselineSource) throw new Error('Supply both measured dist paths, output JSON, and the extracted baseline frontend source directory')
const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..')
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex')
const baselineRevision = execFileSync('git', ['rev-parse', '21702a7'], { cwd: repo, encoding: 'utf8' }).trim()
const sourceFiles = execFileSync('git', ['ls-tree', '-rz', baselineRevision, '--', 'web/frontend'], { cwd: repo }).toString().split('\0').filter(Boolean).map(entry => {
  const [meta, name] = entry.split('\t'); const [, kind, blob] = meta.split(' ')
  if (kind !== 'blob') throw new Error(`Unexpected baseline tree entry ${name}`)
  const bytes = fs.readFileSync(path.join(baselineSource, name.slice('web/frontend/'.length)))
  const actual = createHash('sha1').update(`blob ${bytes.length}\0`).update(bytes).digest('hex')
  if (actual !== blob) throw new Error(`Baseline source differs from ${baselineRevision}: ${name}`)
  return { path: name, gitBlob: blob, sha256: sha256(bytes) }
})
function hashes(root) {
  const result = {}
  function walk(dir) { for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const file = path.join(dir, e.name)
    if (e.isDirectory()) walk(file)
    else result[path.relative(root, file)] = sha256(fs.readFileSync(file))
  } }
  walk(root); return result
}
function bundle(root) {
  const result = {}
  function walk(dir) { for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const file = path.join(dir, e.name)
    if (e.isDirectory()) walk(file)
    else { const bytes = fs.readFileSync(file); const ext = path.extname(file)
      const item = result[ext] ??= { files: 0, raw: 0, gzip: 0 }
      item.files++; item.raw += bytes.length; item.gzip += zlib.gzipSync(bytes).length
    }
  } }
  walk(root); return result
}
const baselineBuiltHashes = hashes(path.join(baselineSource, 'dist'))
const baselineMeasuredHashes = hashes(baselineDist)
if (JSON.stringify(Object.entries(baselineBuiltHashes).sort()) !== JSON.stringify(Object.entries(baselineMeasuredHashes).sort())) {
  throw new Error('Measured baseline dist differs from the retained verified-source build output')
}
const browser = await chromium.launch({ headless: true })
const report = { environment: { browser: browser.version(), viewport: '1586x992', throttle: 'none', rounds: 3 },
  provenance: { capturedAt: new Date().toISOString(), baselineRevision, baselineSource: path.resolve(baselineSource), sourceFiles,
    baseline: { dist: path.resolve(baselineDist), hashes: baselineMeasuredHashes, buildDist: path.resolve(baselineSource, 'dist'), buildHashes: baselineBuiltHashes }, ember: { dist: path.resolve(emberDist), hashes: hashes(emberDist) } },
  limits: ['Synthetic400-message80-NPC load; same current isolated backend for both frontend versions',
    'Input measurement is synthetic input event to two animation frames, not field INP',
    'Scroll measurement is scripted scrollTop/Left per animation frame, not compositor tracing',
    'CDP listener counts include browser/React handlers, not proof of socket subscription counts',
    'Scenario reset does not clear the client transcript ledger; afterReset is not an empty-state leak test',
    'Baseline Google Fonts CSS is aborted and uses fallback fonts; Ember uses local fonts; not identical typography or network loading',
    'Bundle totals cover all built files and default Node gzip, not bytes transferred for one page',
    'Missing synthetic NPC art measures fallback/probe behavior, not production image CDN throughput'],
  bundle: { baseline: bundle(baselineDist), ember: bundle(emberDist) }, samples: [] }
try {
  for (let round = 0; round < 3; round++) for (const label of (round % 2 ? ['ember', 'baseline'] : ['baseline', 'ember'])) {
    console.log(`Starting ${label} round ${round}`)
    const base = `http://127.0.0.1:${label === 'baseline' ? 4220 : 4221}`
    const context = await browser.newContext({ viewport: { width: 1586, height: 992 } })
    const page = await context.newPage(); const requests = []; const assetChecks = []
    page.on('response', response => {
      const pathname = new URL(response.url()).pathname
      if (pathname.startsWith('/play/') && /\.(js|css)$/.test(pathname)) assetChecks.push((async () => {
        const relative = pathname.slice('/play/'.length)
        const actual = sha256(await response.body())
        const expected = report.provenance[label].hashes[relative]
        if (!response.ok() || actual !== expected) throw new Error(`Served asset differs from measured ${label} dist: ${relative}`)
        return { path: relative, sha256: actual, status: response.status() }
      })())
    })
    await context.route('**/*', route => new URL(route.request().url()).origin === base ? route.continue() : route.abort())
    page.on('request', r => requests.push({ url: r.url(), type: r.resourceType() }))
    const cdp = await context.newCDPSession(page)
    const runtimeIdentity = await (await page.request.get(`${base}/__portrait__/state`)).json()
    await page.request.post(`${base}/__parity__/scenario/exploration`)
    await page.goto(`${base}/play/`)
    await page.getByRole('textbox', { name: 'Player input' }).waitFor()
    await page.waitForTimeout(1200)
    const servedAssets = await Promise.all(assetChecks)
    for (const asset of Object.keys(report.provenance[label].hashes).filter(name => /\.(js|css)$/.test(name))) {
      if (!servedAssets.some(value => value.path === asset)) throw new Error(`Expected bundle asset not loaded by browser: ${asset}`)
    }
    const initial = await cdp.send('Memory.getDOMCounters')
    await page.request.post(`${base}/__performance__/stress`)
    await page.getByRole('log').getByText('Performance passage 399.', { exact: false }).waitFor()
    await page.getByRole('button', { name: 'Performance Ranger 79', exact: true }).waitFor()
    await page.waitForTimeout(1200)
    const sample = await page.evaluate(async () => {
      const input = document.querySelector('[aria-label="Player input"]')
      const frame = () => new Promise(resolve => requestAnimationFrame(resolve))
      const typing = []
      for (let i = 0; i < 25; i++) {
        const start = performance.now()
        Object.getOwnPropertyDescriptor(input instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype, 'value').set.call(input, `Performance typing ${i}`)
        input.dispatchEvent(new Event('input', { bubbles: true }))
        await frame(); await frame(); typing.push(performance.now() - start)
      }
      const log = document.querySelector('[role="log"]')
      const roster = [...document.querySelectorAll('div')].filter(e => e.textContent.includes('Performance Ranger 79') && (e.scrollHeight > e.clientHeight + 40 || e.scrollWidth > e.clientWidth + 40) && /(auto|scroll)/.test(getComputedStyle(e).overflow + getComputedStyle(e).overflowX + getComputedStyle(e).overflowY)).sort((a,b) => a.querySelectorAll('*').length - b.querySelectorAll('*').length)[0]
      async function scroll(el) {
        if (!el) return null
        const intervals = []; let previous = await frame()
        for (let i = 0; i < 100; i++) {
          el.scrollTop = (el.scrollHeight - el.clientHeight) * (i % 20) / 19
          el.scrollLeft = (el.scrollWidth - el.clientWidth) * (i % 20) / 19
          const now = await frame(); intervals.push(now - previous); previous = now
        }
        return { intervals, width: el.clientWidth, height: el.clientHeight, scrollWidth: el.scrollWidth, scrollHeight: el.scrollHeight }
      }
      return { typing, transcript: await scroll(log), roster: await scroll(roster),
        renderedMessageMarkers: (log.textContent.match(/Performance passage /g) ?? []).length,
        renderedRosterNames: new Set((document.body.textContent.match(/Performance Ranger \d+/g) ?? [])).size,
        images: [...document.images].map(i => ({ complete: i.complete, loaded: i.naturalWidth > 0 })),
        resources: performance.getEntriesByType('resource').filter(r => ['img','css','script'].includes(r.initiatorType)).map(r => ({ name: r.name, type: r.initiatorType, duration: r.duration })) }
    })
    const stressed = await cdp.send('Memory.getDOMCounters')
    if (sample.renderedMessageMarkers !== 400 || sample.renderedRosterNames !== 80 || !sample.roster) throw new Error('Stress workload did not persist through measurement')
    await page.request.post(`${base}/__parity__/scenario/exploration`)
    await page.waitForTimeout(1200)
    await cdp.send('HeapProfiler.collectGarbage')
    const afterReset = await cdp.send('Memory.getDOMCounters')
    report.samples.push({ label, round, runtimeIdentity, servedAssets, initial, stressed, afterReset, requests, ...sample })
    fs.writeFileSync(output, JSON.stringify(report, null, 2))
    console.log(`Recorded ${label} round ${round}: ${sample.renderedMessageMarkers} messages, ${sample.renderedRosterNames} NPCs`)
    await context.close()
  }
} finally { await browser.close() }
console.log(output)
