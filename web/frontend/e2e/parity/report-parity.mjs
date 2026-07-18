import fs from 'node:fs'
import path from 'node:path'

const outputRoot = path.resolve(process.argv[2] ?? process.env.NEQ_PARITY_OUTPUT ?? '')
if (!outputRoot || !fs.existsSync(outputRoot)) {
  console.error('Usage: node e2e/parity/report-parity.mjs <external-parity-output-directory>')
  process.exit(2)
}

const reports = fs.readdirSync(outputRoot)
  .filter((name) => name.endsWith('-report.json'))
  .sort()
  .map((name) => ({ name, ...JSON.parse(fs.readFileSync(path.join(outputRoot, name), 'utf8')) }))

const pairReports = reports.filter(({ name }) => name.endsWith('-legacy-v-react-report.json'))
const stabilityReports = reports.filter(({ name }) => name.endsWith('-stability-report.json'))
const failures = reports.filter(({ differing_pixels: pixels }) => pixels !== 0)

console.log('Legacy vs React exact-pixel results')
for (const report of pairReports) {
  const state = report.name.replace('-legacy-v-react-report.json', '')
  console.log(`${state.padEnd(32)} ${String(report.differing_pixels).padStart(9)} / ${report.total_pixels}  ${(report.difference_ratio * 100).toFixed(4)}%`)
}
console.log('\nDuplicate stability')
for (const report of stabilityReports) {
  const state = report.name.replace('-stability-report.json', '')
  console.log(`${state.padEnd(39)} ${String(report.differing_pixels).padStart(9)}`)
}

const summary = {
  output_root: outputRoot,
  pair_reports: pairReports.length,
  stability_reports: stabilityReports.length,
  nonzero_pair_reports: pairReports.filter(({ differing_pixels: pixels }) => pixels !== 0).length,
  nonzero_stability_reports: stabilityReports.filter(({ differing_pixels: pixels }) => pixels !== 0).length,
  exact_gate_passed: failures.length === 0,
}
const summaryPath = path.join(outputRoot, 'parity-summary.json')
fs.writeFileSync(summaryPath, `${JSON.stringify(summary, null, 2)}\n`)
console.log(`\nSummary: ${summaryPath}`)
console.log(JSON.stringify(summary))
process.exit(summary.exact_gate_passed ? 0 : 1)
