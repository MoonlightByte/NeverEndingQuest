import { expect, test } from '@playwright/test'

// These are compatibility checks, not approval of a redesigned mobile interface.
for (const [width, height] of [[360, 800], [390, 844], [844, 390], [760, 800], [761, 800], [1023, 768], [1024, 768]]) {
  test(`public responsive boundary ${width}x${height}`, async ({ page }) => {
    await page.setViewportSize({ width: width!, height: height! })
    await page.goto('/play/')
    const input = page.getByRole('textbox', { name: 'Player input' })
    await expect(input).toBeEnabled()
    await expect(page.locator('.ember-desktop')).toHaveCount(width! >= 1024 ? 1 : 0)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    if (width! >= 761 && width! < 1024) {
      await expect(page.getByRole('button', { name: /Exit/ })).toBeInViewport()
      const map = page.getByRole('tab', { name: 'Map', exact: true })
      await map.focus()
      await expect(map).toBeInViewport()
      await map.press('Enter')
      await expect(map).toHaveAttribute('aria-selected', 'true')
      const lastDie = page.getByRole('button', { name: 'D4', exact: true })
      await lastDie.focus()
      await expect(lastDie).toBeInViewport()
      await lastDie.press('Enter')
      await expect(page.getByTestId('dice-results')).toContainText('d4:')
      await page.getByRole('button', { name: 'Clear', exact: true }).click()
      await expect(page.getByTestId('dice-results')).toHaveCount(0)
    }
    await input.scrollIntoViewIfNeeded()
    await expect(input).toBeInViewport()
    await input.fill('Inspect the responsive boundary')
    await input.press('Enter')
    await expect(page.getByText('Inspect the responsive boundary', { exact: true })).toBeVisible()
    await expect(input).toHaveValue('')
  })
}

test('crossing desktop breakpoint preserves draft and selected panel', async ({ page }) => {
  await page.setViewportSize({ width: 1586, height: 992 })
  await page.goto('/play/')
  await page.getByRole('tab', { name: 'Inventory', exact: true }).click()
  const input = page.getByRole('textbox', { name: 'Player input' })
  await input.fill('Unsent player draft')
  for (const [width, height] of [[1023, 768], [390, 844], [844, 390], [1586, 992]]) {
    await page.setViewportSize({ width: width!, height: height! })
    await expect(input).toHaveValue('Unsent player draft')
    await expect(page.getByRole('tab', { name: 'Inventory', exact: true })).toHaveAttribute('aria-selected', 'true')
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  }
  await expect(page.locator('.ember-desktop')).toHaveCount(1)
})
