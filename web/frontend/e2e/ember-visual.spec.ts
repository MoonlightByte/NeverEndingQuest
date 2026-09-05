import { test, expect } from '@playwright/test'

test.skip(process.env.NEQ_E2E_EMBER_VISUAL !== '1', 'Requires explicit visual fixture')
test.describe.configure({ mode: 'serial' })
test.beforeEach(async ({ request }) => { await request.post('/__e2e__/media/on') })

for (const [width, height] of [[1586, 992], [1920, 1080], [1440, 900], [1366, 768]]) {
  test(`populated reference render ${width}x${height}`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width: width!, height: height! })
    await page.goto('/play/')
    await expect(page.locator('.neq-character-name')).toHaveText('Smashing Jack')
    await expect(page.locator('.neq-character-chip')).toHaveCount(6)
    await page.evaluate(() => document.fonts.ready)
    await expect.poll(() => page.locator('.ember-chip-portrait').evaluateAll(nodes => nodes.every(node => (node as HTMLElement).style.backgroundImage !== ''))).toBe(true)
    await page.locator('.neq-inline-images img').evaluate(img => (img as HTMLImageElement).decode())
    await expect.poll(() => page.locator('.ember-desktop img').evaluateAll(images => images.every(img => img.complete && img.naturalWidth > 0))).toBe(true)
    await page.getByRole('textbox', { name: 'Player input' }).blur()
    await page.locator('.neq-game-log').evaluate(el => { el.scrollTop = 0 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    if (width === 1586) {
      const geometry = await page.evaluate(() => ({
        story: document.querySelector('.neq-main-area')!.getBoundingClientRect().x,
        people: document.querySelector('.ember-people')!.getBoundingClientRect().x,
        composer: document.querySelector('.neq-input-field')!.getBoundingClientRect().y,
      }))
      expect(Math.abs(geometry.story - 471)).toBeLessThan(3)
      expect(Math.abs(geometry.people - 1284)).toBeLessThan(3)
      expect(Math.abs(geometry.composer - 858)).toBeLessThan(4)
    }
    await page.screenshot({ path: testInfo.outputPath(`populated-${width}.png`) })
    // Reviewed browser baseline, not a pixel-equality claim against concept art.
    await expect(page).toHaveScreenshot(`public-ember-${width}.png`, { animations: 'disabled', maxDiffPixels: 20 })
  })
}

test('image is message-owned and no-image mode reserves no space', async ({ page, request }) => {
  await page.setViewportSize({ width: 1586, height: 992 })
  await page.goto('/play/')
  const narration = page.locator('[data-message-type="narration"]')
  await expect(narration.locator('.neq-message-text')).toHaveCount(2)
  expect(await narration.locator('.neq-message-content').evaluate(el => Array.from(el.children).map(node => node.className))).toEqual([
    expect.stringContaining('neq-message-header'), expect.stringContaining('neq-message-text'),
    expect.stringContaining('neq-inline-images'), expect.stringContaining('ember-narration-continuation'),
  ])
  await request.post('/__e2e__/media/off')
  await page.reload()
  await expect(page.locator('.neq-character-name')).toHaveText('Smashing Jack')
  await expect(narration.locator('.neq-message-text')).toHaveCount(1)
  await expect(page.locator('.neq-inline-images')).toHaveCount(0)
})

test('short desktop keeps lower sheet, story and nearby entries reachable', async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 })
  await page.goto('/play/')
  const background = page.getByText('Rustic Hospitality', { exact: true })
  await background.scrollIntoViewIfNeeded()
  await expect(background).toBeInViewport()
  const continuation = page.locator('.ember-narration-continuation')
  await continuation.scrollIntoViewIfNeeded()
  await expect(continuation).toBeInViewport()
  const nearby = page.locator('.neq-character-chip').filter({ hasText: 'Rusk' })
  await nearby.scrollIntoViewIfNeeded()
  await expect(nearby).toBeInViewport()
  await expect(page.getByRole('textbox', { name: 'Player input' })).toBeInViewport()
  await expect(page.getByRole('button', { name: 'Journal', exact: true })).toBeInViewport()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})
