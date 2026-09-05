import { test, expect } from '@playwright/test'

for (const [width, height] of [[1586, 992], [1920, 1080], [1440, 900], [1366, 768], [1024, 768]]) {
  test(`public Ember layout ${width}x${height}`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width: width!, height: height! })
    await page.goto('/play/')
    await expect(page.locator('.neq-character-name')).toHaveText('Rowan Vale')
    await page.evaluate(() => document.fonts.ready)
    await expect(page.locator('.ember-desktop')).toBeVisible()
    const geometry = await page.evaluate(() => {
      const rect = (selector: string) => {
        const r = document.querySelector(selector)!.getBoundingClientRect()
        return { x: r.x, y: r.y, right: r.right, bottom: r.bottom, width: r.width }
      }
      return { sheet: rect('.neq-rail-area'), story: rect('.neq-main-area'), people: rect('.ember-people'), input: rect('.neq-input-field'), overflow: document.documentElement.scrollWidth > innerWidth }
    })
    expect(geometry.overflow).toBe(false)
    expect(geometry.sheet.right).toBeLessThanOrEqual(geometry.story.x + 1)
    expect(geometry.story.right).toBeLessThanOrEqual(geometry.people.x + 1)
    expect(geometry.input.bottom).toBeLessThanOrEqual(height!)
    await page.screenshot({ path: testInfo.outputPath(`public-${width}.png`) })
  })
}

test('public actions, sheet keyboard navigation and combat survive the port', async ({ page }) => {
  await page.setViewportSize({ width: 1586, height: 992 })
  await page.goto('/play/')
  await expect(page.getByRole('button', { name: 'Save', exact: true })).toBeEnabled()
  await page.getByRole('button', { name: 'Settings', exact: true }).click()
  await expect(page.getByText('AI Provider', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Settings', exact: true }).click()
  await page.getByRole('tab', { name: 'Character', exact: true }).focus()
  await page.keyboard.press('End')
  await expect(page.getByRole('tab', { name: 'Map', exact: true })).toHaveAttribute('aria-selected', 'true')
  await page.getByRole('textbox', { name: 'Player input' }).fill('enter combat')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await expect(page.getByLabel('Combat, round 1')).toBeVisible()
  await expect(page.locator('.ember-people [data-chip="init-enemy"]')).toHaveAccessibleName('Storm Wraith')
  await expect(page.locator('.ember-people [data-chip="init-player"]')).toHaveAttribute('aria-current', 'step')
})

test('phone retains the existing public layout', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/play/')
  await expect(page.locator('.neq-character-name')).toHaveText('Rowan Vale')
  await expect(page.locator('.ember-desktop')).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})
