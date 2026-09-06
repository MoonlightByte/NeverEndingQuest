import { expect, test } from '@playwright/test'
test.skip(process.env.NEQ_E2E_LEDGER !== '1', 'Requires isolated ledger server; no campaign writes')

for (const width of [1586, 1024, 390]) {
  test(`journal restores the original parchment book at ${width}`, async ({ page, request }, info) => {
    await request.post('/__ledger__/populated')
    const height = width === 390 ? 844 : width === 1024 ? 768 : 992
    await page.setViewportSize({ width, height })
    await page.goto('/play/')
    const opener = page.getByRole('button', { name: 'Journal', exact: true })
    await opener.click()
    const dialog = page.getByRole('dialog', { name: 'Adventure Journal' })
    const book = dialog.locator('.neq-journal-book')
    const pages = book.locator('.neq-journal-page')
    await expect(pages).toHaveCount(2)
    await expect(dialog.getByText('The discovered road')).toBeVisible()
    await expect(dialog.getByText('A finished journey')).toBeVisible()
    await expect(dialog.getByText('Hidden plot')).toHaveCount(0)
    await expect(dialog.getByText('Hidden side quest')).toHaveCount(0)
    await expect(pages.first()).toHaveCSS('background-color', 'rgb(243, 233, 210)')
    await expect(pages.first().locator('.neq-journal-page-content')).toHaveCSS('color', 'rgb(74, 58, 42)')
    await expect(pages.first().locator('h2')).toHaveCSS('font-family', /Georgia/)
    const left = (await pages.first().boundingBox())!, right = (await pages.last().boundingBox())!
    if (width >= 1024) {
      expect(Math.abs(left.y - right.y)).toBeLessThan(1)
      expect(right.x).toBeGreaterThan(left.x + left.width - 1)
      await expect(dialog.locator('.ember-dialog-card')).toHaveCount(0)
      await expect(dialog.getByRole('button', { name: 'Close' })).toBeFocused()
      await page.keyboard.press('Tab')
      await expect(pages.first()).toBeFocused()
      await page.keyboard.press('Tab')
      await expect(pages.last()).toBeFocused()
      await page.keyboard.press('Tab')
      await expect(dialog.getByRole('button', { name: 'Close' })).toBeFocused()
    } else {
      expect(right.y).toBeGreaterThan(left.y)
      await expect(dialog.locator('.neq-journal-desktop')).toHaveCount(0)
    }
    const bounds = (await book.boundingBox())!
    expect(bounds.x).toBeGreaterThanOrEqual(0)
    expect(bounds.x + bounds.width).toBeLessThanOrEqual(width)
    expect(bounds.y).toBeGreaterThanOrEqual(0)
    expect(bounds.y + bounds.height).toBeLessThanOrEqual(height)
    await page.evaluate(() => document.fonts.ready)
    await book.screenshot({ path: info.outputPath(`parchment-book-${width}.png`) })
    await page.keyboard.press('Escape')
    await expect(dialog).toHaveCount(0)
    await expect(opener).toBeFocused()
  })
}
