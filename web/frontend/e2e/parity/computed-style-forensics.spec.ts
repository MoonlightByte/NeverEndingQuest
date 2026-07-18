import { expect, test, type Locator, type Page } from '@playwright/test'
import fs from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import { canonicalViewport, installDeterminism, settleApplication } from './strict-oracle'

const outputRoot = process.env.NEQ_FORENSIC_OUTPUT
  ?? path.join(os.tmpdir(), 'neverendingquest-style-forensics')

const styleProperties = [
  'display', 'position', 'box-sizing',
  'width', 'height', 'min-width', 'min-height', 'max-width', 'max-height',
  'padding-top', 'padding-right', 'padding-bottom', 'padding-left',
  'margin-top', 'margin-right', 'margin-bottom', 'margin-left',
  'gap', 'row-gap', 'column-gap', 'align-items', 'justify-content',
  'overflow-x', 'overflow-y',
  'font-family', 'font-size', 'font-weight', 'line-height', 'letter-spacing',
  'text-align', 'text-transform', 'white-space',
  'color', 'background-color', 'background-image',
  'border-top-width', 'border-right-width', 'border-bottom-width', 'border-left-width',
  'border-top-style', 'border-right-style', 'border-bottom-style', 'border-left-style',
  'border-top-color', 'border-right-color', 'border-bottom-color', 'border-left-color',
  'border-radius', 'box-shadow', 'opacity',
] as const

type Box = { x: number; y: number; width: number; height: number }
type Snapshot = {
  selector: string
  pseudo: string | null
  count: number
  missing: boolean
  tag?: string
  classes?: string
  text?: string
  children?: number
  direct_children?: Array<{ tag: string; classes: string; text: string; box: Box }>
  box?: Box
  styles?: Record<string, string>
}

type PairDefinition = {
  group: string
  name: string
  legacy: string
  react: string
  legacyPseudo?: string
  reactPseudo?: string
}

const pairs: PairDefinition[] = [
  { group: 'header', name: 'header shell', legacy: '.header', react: '.neq-header' },
  { group: 'header', name: 'brand', legacy: '.header h1', react: '.neq-header-brand' },
  { group: 'header', name: 'brand title', legacy: '.header h1', react: '.neq-header-brand h1' },
  { group: 'header', name: 'location', legacy: '.location-info', react: '.neq-header-location' },
  { group: 'header', name: 'location name', legacy: '#location-name', react: '.neq-location-name' },
  { group: 'header', name: 'location details', legacy: '#location-details', react: '.neq-location-details' },
  { group: 'header', name: 'actions', legacy: '.status', react: '.neq-header-actions' },
  { group: 'header', name: 'start button', legacy: '#start-button', react: '.neq-header-actions > button:nth-of-type(1)' },
  { group: 'party', name: 'party/dice header', legacy: '.panel-header', react: '.neq-game-panel-header' },
  { group: 'party', name: 'adventure image', legacy: '#adventure-box', react: '.neq-adventure-box' },
  { group: 'party', name: 'party strip', legacy: '#party-display-container', react: '[aria-label="Party members"]' },
  { group: 'dice', name: 'dice strip', legacy: '.dice-strip-inline', react: '.neq-dice-strip' },
  { group: 'dice', name: 'dice label', legacy: '.dice-label', react: '.neq-dice-label' },
  { group: 'dice', name: 'dice label line', legacy: '.dice-label', react: '.neq-dice-label', legacyPseudo: '::before', reactPseudo: '::before' },
  { group: 'dice', name: 'dice label text', legacy: '.dice-label-text', react: '.neq-dice-label-text' },
  { group: 'dice', name: 'd20 button', legacy: '.dice-button[title="Roll D20"]', react: '[title="Roll D20"]' },
  { group: 'dice', name: 'clear button', legacy: '.dice-clear-button', react: '[title="Clear results"]' },
  { group: 'log', name: 'game log', legacy: '#game-output', react: '.neq-game-log' },
  { group: 'log', name: 'narration row', legacy: '.message.narration', react: '.neq-message-narration' },
  { group: 'log', name: 'narration avatar', legacy: '.message.narration .message-avatar', react: '.neq-message-narration .neq-message-avatar' },
  { group: 'log', name: 'narration content', legacy: '.message.narration .message-content', react: '.neq-message-narration .neq-message-content' },
  { group: 'log', name: 'narration header', legacy: '.message.narration .message-header', react: '.neq-message-narration .neq-message-header' },
  { group: 'log', name: 'narration author', legacy: '.message.narration .message-author', react: '.neq-message-narration .neq-message-author' },
  { group: 'log', name: 'narration text', legacy: '.message.narration .message-text', react: '.neq-message-narration .neq-message-text' },
  { group: 'input', name: 'input row', legacy: '.input-container', react: '.neq-input-container' },
  { group: 'input', name: 'input', legacy: '#user-input', react: '.neq-input-field' },
  { group: 'input', name: 'send button', legacy: '#send-button', react: '.neq-send-button' },
  { group: 'tabs', name: 'tab strip', legacy: '.tabs', react: '.neq-tabs' },
  { group: 'tabs', name: 'character tab', legacy: '.tab-button:nth-child(1)', react: '.neq-tab-button:nth-child(1)' },
  { group: 'tabs', name: 'inventory tab', legacy: '.tab-button:nth-child(2)', react: '.neq-tab-button:nth-child(2)' },
  { group: 'tabs', name: 'spells tab', legacy: '.tab-button:nth-child(3)', react: '.neq-tab-button:nth-child(3)' },
  { group: 'sheet', name: 'character sheet', legacy: '.character-sheet', react: '.neq-character-sheet' },
  { group: 'sheet', name: 'identity row', legacy: '.character-sheet-top', react: '.neq-character-sheet-top' },
  { group: 'sheet', name: 'portrait', legacy: '.character-portrait', react: '.neq-character-portrait' },
  { group: 'sheet', name: 'identity card', legacy: '.character-header-info', react: '.neq-character-header' },
  { group: 'sheet', name: 'character name', legacy: '.character-name', react: '.neq-character-name' },
  { group: 'sheet', name: 'abilities row', legacy: '.abilities-row', react: '.neq-abilities-row' },
  { group: 'sheet', name: 'strength ability', legacy: '.abilities-row .ability-score:nth-child(1)', react: '.neq-abilities-row .neq-ability-score:nth-child(1)' },
  { group: 'sheet', name: 'combat stats', legacy: '.combat-stats', react: '.neq-combat-stats' },
  { group: 'sheet', name: 'hp card', legacy: '.combat-stats .combat-stat:nth-child(1)', react: '.neq-combat-stats .neq-combat-stat:nth-child(1)' },
  { group: 'sheet', name: 'weapons grid', legacy: '.character-weapons-container', react: '.neq-weapons-grid' },
  { group: 'sheet', name: 'saving throws', legacy: '.saving-throws-group', react: '.neq-saving-throws' },
  { group: 'sheet', name: 'class features', legacy: '.abilities-grid > .stat-group:has-text("Class Features")', react: '.neq-sheet-section:has-text("Class Features")' },
  { group: 'sheet', name: 'active effects', legacy: '.abilities-grid > .stat-group:has-text("Active Effects")', react: '.neq-sheet-section:has-text("Active Effects")' },
  { group: 'sheet', name: 'racial traits', legacy: '.abilities-grid > .stat-group:has-text("Racial Traits")', react: '.neq-sheet-section:has-text("Racial Traits")' },
  { group: 'sheet', name: 'background', legacy: '.abilities-grid > .stat-group:has-text("Background")', react: '.neq-sheet-section:has-text("Background")' },
  { group: 'sheet', name: 'feats', legacy: '.abilities-grid > .stat-group:has-text("Feats")', react: '.neq-sheet-section:has-text("Feats")' },
]

for (let index = 0; index < 6; index += 1) {
  pairs.push({
    group: 'party',
    name: `character chip ${index + 1}`,
    legacy: `#party-display-container > :nth-child(${index + 1})`,
    react: `[aria-label="Party members"] > [data-chip]:nth-child(${index + 1})`,
  })
}

async function snapshot(page: Page, selector: string, pseudo?: string): Promise<Snapshot> {
  const locator: Locator = page.locator(selector)
  const count = await locator.count()
  if (count === 0) return { selector, pseudo: pseudo ?? null, count, missing: true }
  return locator.first().evaluate((element, args) => {
    const computed = getComputedStyle(element, args.pseudo || null)
    const rect = element.getBoundingClientRect()
    const styles: Record<string, string> = {}
    for (const property of args.properties) styles[property] = computed.getPropertyValue(property)
    return {
      selector: args.selector,
      pseudo: args.pseudo || null,
      count: args.count,
      missing: false,
      tag: element.tagName.toLowerCase(),
      classes: element.getAttribute('class') ?? '',
      text: (element.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, 240),
      children: element.children.length,
      direct_children: [...element.children].map((child) => {
        const childRect = child.getBoundingClientRect()
        return {
          tag: child.tagName.toLowerCase(),
          classes: child.getAttribute('class') ?? '',
          text: (child.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, 120),
          box: { x: childRect.x, y: childRect.y, width: childRect.width, height: childRect.height },
        }
      }),
      box: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
      styles,
    }
  }, { selector, pseudo: pseudo ?? '', count, properties: [...styleProperties] })
}

function styleDifferences(legacy: Snapshot, react: Snapshot) {
  if (!legacy.styles || !react.styles) return []
  return styleProperties.flatMap((property) => {
    const legacyValue = legacy.styles?.[property]
    const reactValue = react.styles?.[property]
    return legacyValue === reactValue ? [] : [{ property, legacy: legacyValue, react: reactValue }]
  })
}

function boxDifferences(legacy: Snapshot, react: Snapshot) {
  if (!legacy.box || !react.box) return []
  return (['x', 'y', 'width', 'height'] as const).flatMap((edge) => {
    const legacyValue = legacy.box?.[edge] ?? 0
    const reactValue = react.box?.[edge] ?? 0
    const delta = reactValue - legacyValue
    return delta === 0 ? [] : [{ edge, legacy: legacyValue, react: reactValue, delta }]
  })
}

test('write exact computed-style and DOM forensic report for paired base selectors', async ({ browser, request }) => {
  test.skip(!process.env.PLAYWRIGHT_BASE_URL, 'Requires the deterministic real server')
  await request.post('/__parity__/scenario/reset')
  const legacyContext = await browser.newContext({ viewport: canonicalViewport, deviceScaleFactor: 1 })
  const reactContext = await browser.newContext({ viewport: canonicalViewport, deviceScaleFactor: 1 })
  await Promise.all([installDeterminism(legacyContext), installDeterminism(reactContext)])
  const legacyPage = await legacyContext.newPage()
  const reactPage = await reactContext.newPage()
  await Promise.all([legacyPage.goto('/'), reactPage.goto('/play/')])
  await Promise.all([settleApplication(legacyPage, true), settleApplication(reactPage, false)])

  const results = []
  for (const pair of pairs) {
    const [legacy, react] = await Promise.all([
      snapshot(legacyPage, pair.legacy, pair.legacyPseudo),
      snapshot(reactPage, pair.react, pair.reactPseudo),
    ])
    const box = boxDifferences(legacy, react)
    const styles = styleDifferences(legacy, react)
    results.push({
      ...pair,
      legacy,
      react,
      box_differences: box,
      style_differences: styles,
      difference_count: box.length + styles.length,
      geometry_impact: box.reduce((sum, difference) => sum + Math.abs(difference.delta), 0),
    })
  }

  const missing = results.filter((result) => result.legacy.missing || result.react.missing)
  const ranked = [...results].sort((a, b) =>
    b.geometry_impact - a.geometry_impact || b.difference_count - a.difference_count,
  )
  const report = {
    generated_at: new Date().toISOString(),
    base_url: process.env.PLAYWRIGHT_BASE_URL,
    viewport: canonicalViewport,
    style_properties: styleProperties,
    pair_count: results.length,
    missing_pairs: missing.map(({ group, name, legacy, react }) => ({ group, name, legacy_missing: legacy.missing, react_missing: react.missing })),
    exact_pairs: results.filter((result) => result.difference_count === 0).map(({ group, name }) => ({ group, name })),
    ranked_differences: ranked.map(({ group, name, difference_count, geometry_impact }) => ({ group, name, difference_count, geometry_impact })),
    pairs: results,
  }
  await fs.mkdir(outputRoot, { recursive: true })
  await fs.writeFile(path.join(outputRoot, 'computed-style-forensics.json'), `${JSON.stringify(report, null, 2)}\n`)
  const markdown = [
    '# NeverEndingQuest computed-style forensics',
    '',
    `Viewport: ${canonicalViewport.width}×${canonicalViewport.height}`,
    `Pairs: ${results.length}; missing: ${missing.length}; exact: ${report.exact_pairs.length}`,
    '',
    '| Group | Pair | Geometry impact | Differences |',
    '|---|---|---:|---:|',
    ...ranked.map((result) => `| ${result.group} | ${result.name} | ${result.geometry_impact.toFixed(3)} | ${result.difference_count} |`),
    '',
    '## Enumerated pair details',
    '',
    ...ranked.flatMap((result) => [
      `### ${result.group}: ${result.name}`,
      '',
      `- Legacy selector: \`${result.legacy.selector}\`; box: \`${JSON.stringify(result.legacy.box ?? null)}\``,
      `- React selector: \`${result.react.selector}\`; box: \`${JSON.stringify(result.react.box ?? null)}\``,
      `- Legacy DOM: \`${result.legacy.tag ?? 'missing'}\` classes \`${result.legacy.classes ?? ''}\`; children ${result.legacy.children ?? 0}; text \`${result.legacy.text ?? ''}\``,
      `- React DOM: \`${result.react.tag ?? 'missing'}\` classes \`${result.react.classes ?? ''}\`; children ${result.react.children ?? 0}; text \`${result.react.text ?? ''}\``,
      '',
      ...(result.box_differences.length > 0
        ? [
            '| Edge | Legacy | React | Delta |',
            '|---|---:|---:|---:|',
            ...result.box_differences.map((difference) => `| ${difference.edge} | ${difference.legacy} | ${difference.react} | ${difference.delta} |`),
          ]
        : ['Geometry: exact.']),
      '',
      ...(result.style_differences.length > 0
        ? [
            '| Computed property | Legacy | React |',
            '|---|---|---|',
            ...result.style_differences.map((difference) => `| ${difference.property} | \`${difference.legacy}\` | \`${difference.react}\` |`),
          ]
        : ['Computed styles: exact.']),
      '',
    ]),
    'The JSON report additionally contains every direct child DOM signature and bounding box.',
  ].join('\n')
  await fs.writeFile(path.join(outputRoot, 'computed-style-forensics.md'), `${markdown}\n`)

  expect(missing, `Forensic selectors missing; inspect ${outputRoot}`).toEqual([])
  await legacyContext.close()
  await reactContext.close()
})
