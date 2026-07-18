import { expect, test, type Locator } from '@playwright/test'
import { installDeterminism, settleApplication } from './strict-oracle'

type Box = { x: number; y: number; width: number; height: number }

async function box(locator: Locator): Promise<Box> {
  await expect(locator).toBeVisible({ timeout: 15_000 })
  const value = await locator.boundingBox()
  if (!value) throw new Error(`No bounding box for ${locator}`)
  return value
}

function expectBoxExact(label: string, actual: Box, expected: Box) {
  for (const edge of ['x', 'y', 'width', 'height'] as const) {
    expect.soft(actual[edge], `${label}.${edge}: React ${actual[edge]} vs legacy ${expected[edge]}`).toBe(expected[edge])
  }
}

test('every desktop shell region has exact legacy geometry at supported desktop sizes', async ({ browser }) => {
  test.skip(!process.env.PLAYWRIGHT_BASE_URL, 'Requires the deterministic real server')
  for (const viewport of [{ width: 2048, height: 1228 }, { width: 1920, height: 1080 }, { width: 1366, height: 768 }]) {
    const legacyContext = await browser.newContext({ viewport, deviceScaleFactor: 1 })
    const reactContext = await browser.newContext({ viewport, deviceScaleFactor: 1 })
    await Promise.all([installDeterminism(legacyContext), installDeterminism(reactContext)])
    const legacy = await legacyContext.newPage()
    const react = await reactContext.newPage()

    await Promise.all([legacy.goto('/'), react.goto('/play/')])
    await Promise.all([settleApplication(legacy, true), settleApplication(react, false)])

    const regions = [
      ['header', '.neq-header', '.header'],
      ['main panel', '.neq-main-panel', '.game-panel'],
      ['right rail', '.neq-rail-panel', '.debug-panel'],
      ['party and dice header', '.neq-game-panel-header', '.panel-header'],
      ['adventure image', '.neq-adventure-box', '#adventure-box'],
      ['party strip', '[aria-label="Party members"]', '#party-display-container'],
      ['dice strip', '.neq-game-panel-header > :last-child', '.dice-strip-inline'],
      ['game log', '.neq-game-log', '#game-output'],
      ['input bar', '.neq-input-container', '.input-container'],
      ['right tabs', '.neq-tabs', '.tabs'],
    ] as const
    for (const [label, reactSelector, legacySelector] of regions) {
      expectBoxExact(
        `${viewport.width}x${viewport.height} ${label}`,
        await box(react.locator(reactSelector)),
        await box(legacy.locator(legacySelector)),
      )
    }

    await legacyContext.close()
    await reactContext.close()
  }
  const phone = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 })
  await phone.goto('/play/')
  await expect(phone.getByAltText('Portrait of Arden Vale')).toBeVisible({ timeout: 15_000 })
  expect(await phone.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
  await phone.close()
})
