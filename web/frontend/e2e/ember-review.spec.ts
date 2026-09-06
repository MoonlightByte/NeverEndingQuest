import { test, expect } from '@playwright/test'

// Opt-in test of the static design review, NOT a product functional test.
test.skip(process.env.NEQ_EMBER_REVIEW !== '1', 'Requires the read-only design server on 4202')

test('every proposed screen renders without broken artwork or desktop overflow', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1586, height: 992 })
  await page.goto('/')
  const screens = await page.locator('#screen option').evaluateAll(nodes => nodes.map(node => (node as HTMLOptionElement).value))
  expect(screens).toHaveLength(25)
  for (const screen of screens) {
    await page.goto(`/?screen=${screen}&capture=1`)
    await page.evaluate(() => document.fonts.ready)
    await expect(page.locator('.app')).toBeVisible()
    await expect.poll(() => page.locator('img').evaluateAll(images => images.every(img => img.complete && img.naturalWidth > 0))).toBe(true)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), screen).toBe(true)
    await page.screenshot({ path: testInfo.outputPath(`${screen}.png`), fullPage: true })
  }
})

test('review navigation works and proposed settings fits a phone', async ({ page }) => {
  await page.goto('/')
  await page.locator('#screen').selectOption('settings')
  await expect(page.getByRole('heading', { name: 'Settings', exact: true })).toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.getByRole('button', { name: 'Return to story' }).click()
  await expect(page.locator('.scrim')).toHaveCount(0)
})
