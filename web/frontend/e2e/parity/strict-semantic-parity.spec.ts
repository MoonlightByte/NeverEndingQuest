import { expect, test } from '@playwright/test'
import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { canonicalViewport, installDeterminism, settleApplication } from './strict-oracle'

const here = path.dirname(fileURLToPath(import.meta.url))
const expectedCharacters = [
  'Arden Vale',
  'Mira Thorne',
  'Dain Ashfall',
  'Sable Reed',
  'Keeper Sol',
  'Pip Wren',
]

test('legacy and React expose the same canonical game data and deterministic dice', async ({ browser, request }) => {
  test.skip(!process.env.PLAYWRIGHT_BASE_URL, 'Requires the deterministic real server')
  await request.post('/__parity__/scenario/reset')

  const legacyContext = await browser.newContext({ viewport: canonicalViewport, deviceScaleFactor: 1 })
  const reactContext = await browser.newContext({ viewport: canonicalViewport, deviceScaleFactor: 1 })
  await Promise.all([installDeterminism(legacyContext), installDeterminism(reactContext)])
  const legacy = await legacyContext.newPage()
  const react = await reactContext.newPage()
  await Promise.all([legacy.goto('/'), react.goto('/play/')])
  await Promise.all([settleApplication(legacy, true), settleApplication(react, false)])

  const version = (await fs.readFile(path.resolve(here, '../../../../VERSION'), 'utf8')).trim()
  await expect(legacy.locator('#version-display')).toHaveText(`v${version}`)
  await expect(react.locator('.neq-version')).toHaveText(`v${version}`)
  for (const page of [legacy, react]) {
    await expect(page.getByText('Mosswatch Gate (Emerald March)', { exact: true })).toBeVisible()
    await expect(page.getByText('3 Springmonth 1492 - 14:20:00 [EM001:MG01]', { exact: true })).toBeVisible()
    await expect(page.getByText('Arden Vale', { exact: true }).first()).toBeVisible()
    await expect(page.getByText('31/38', { exact: false }).first()).toBeVisible()
  }

  const legacyNames = await legacy.locator(
    '#party-display-container > .party-member-item, #party-display-container > .location-npc-item',
  ).evaluateAll((elements) => elements.map((element) => element.textContent?.trim()))
  const reactNames = await react.locator('[aria-label="Party members"] [data-chip]').evaluateAll(
    (elements) => elements.map((element) => element.getAttribute('aria-label')),
  )
  expect(legacyNames).toEqual(expectedCharacters)
  expect(reactNames).toEqual(expectedCharacters)

  const legacyStats = await legacy.locator(
    '#party-display-container > .party-member-item, #party-display-container > .location-npc-item',
  ).evaluateAll((elements) => elements.map((element) => {
    const raw = (element as HTMLElement).dataset.stats ?? '{}'
    const stats = JSON.parse(raw) as Record<string, unknown>
    return { name: stats.name, currentHp: stats.currentHp, maxHp: stats.maxHp, ac: stats.ac }
  }))
  expect(legacyStats).toEqual([
    { name: 'Arden Vale', currentHp: 31, maxHp: 38, ac: 16 },
    { name: 'Mira Thorne', currentHp: 19, maxHp: 24, ac: 14 },
    { name: 'Dain Ashfall', currentHp: 27, maxHp: 31, ac: 17 },
    { name: 'Sable Reed', currentHp: 18, maxHp: 22, ac: 13 },
    { name: 'Keeper Sol', currentHp: 21, maxHp: 21, ac: undefined },
    { name: 'Pip Wren', currentHp: 14, maxHp: 17, ac: undefined },
  ])

  for (const sides of [20, 12, 10, 8, 6, 4]) {
    await Promise.all([
      legacy.getByTitle(`Roll D${sides}`).click(),
      react.getByTitle(`Roll D${sides}`).click(),
    ])
  }
  const legacyDice = (await legacy.locator('#dice-results').innerText()).replace(/\s+/g, ' ').trim()
  const reactDice = (await react.getByTestId('dice-results').innerText()).replace(/\s+/g, ' ').trim()
  expect(legacyDice).toBe('d20: 20 | d12: 8, d10: 10, d8: 4, d6: 2, d4: 4Total: 28')
  expect(reactDice).toBe(legacyDice)

  await legacyContext.close()
  await reactContext.close()
})
