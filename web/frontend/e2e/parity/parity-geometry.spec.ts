import { expect, test, type Locator } from '@playwright/test'

type Box = { x: number; y: number; width: number; height: number }

async function box(locator: Locator): Promise<Box> {
  await expect(locator).toBeVisible({ timeout: 15_000 })
  const value = await locator.boundingBox()
  if (!value) throw new Error(`No bounding box for ${locator}`)
  return value
}

function expectBoxClose(actual: Box, expected: Box, tolerance = 2) {
  for (const edge of ['x', 'y', 'width', 'height'] as const) {
    expect(Math.abs(actual[edge] - expected[edge]), `${edge}: ${actual[edge]} vs ${expected[edge]}`).toBeLessThanOrEqual(tolerance)
  }
}

test('desktop shell geometry stays within two pixels of legacy at supported desktop sizes', async ({ browser }) => {
  test.skip(!process.env.PLAYWRIGHT_BASE_URL, 'Requires the deterministic real server')
  for (const viewport of [{ width: 2048, height: 1228 }, { width: 1920, height: 1080 }, { width: 1366, height: 768 }]) {
    const legacy = await browser.newPage({ viewport, deviceScaleFactor: 1 })
    const react = await browser.newPage({ viewport, deviceScaleFactor: 1 })

    await Promise.all([legacy.goto('/'), react.goto('/play/')])
    await expect(legacy.locator('.character-name')).toBeVisible({ timeout: 15_000 })
    await expect(react.getByAltText('Portrait of Arden Vale')).toBeVisible({ timeout: 15_000 })
    await Promise.all([
      legacy.evaluate(() => document.fonts.ready),
      react.evaluate(() => document.fonts.ready),
    ])

    expectBoxClose(await box(react.locator('.neq-header')), await box(legacy.locator('.header')))
    expectBoxClose(await box(react.locator('.neq-main-panel')), await box(legacy.locator('.game-panel')))
    expectBoxClose(await box(react.locator('.neq-rail-panel')), await box(legacy.locator('.debug-panel')))
    expectBoxClose(await box(react.locator('.neq-game-panel-header')), await box(legacy.locator('.panel-header')))

    await legacy.close()
    await react.close()
  }
  const phone = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 })
  await phone.goto('/play/')
  await expect(phone.getByAltText('Portrait of Arden Vale')).toBeVisible({ timeout: 15_000 })
  expect(await phone.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
  await phone.close()
})
