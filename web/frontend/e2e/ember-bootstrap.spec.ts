import { expect, test } from '@playwright/test'

test.skip(process.env.NEQ_E2E_BOOTSTRAP !== '1', 'Requires isolated empty-bootstrap fixture on 4216')
for (const state of ['loading', 'notice', 'error']) {
  test(`empty bootstrap ${state}: public setup is reachable without invented character or artwork`, async ({ page, request }, info) => {
    expect((await request.post(`/__bootstrap__/${state}`)).ok()).toBe(true)
    await page.setViewportSize({ width: 1586, height: 992 })
    await page.goto('/play/')
    await expect(page.getByRole('button', { name: 'New Game', exact: true })).toBeVisible()
    await expect(page.getByRole('textbox', { name: 'Player input', exact: true })).toBeDisabled()
    await expect(page.locator('.neq-character-name')).toHaveCount(0)
    await expect(page.locator('.neq-inline-images')).toHaveCount(0)
    const text = state === 'loading' ? 'Loading character stats...'
      : state === 'notice' ? 'No character yet. Your hero appears here once character creation finishes.'
        : 'Player data not found'
    await expect(page.getByText(text, { exact: true })).toBeVisible()
    await expect(page.locator('.ember-sheet-status')).toHaveCSS('font-size', '18px')
    await expect(page.locator('.ember-sheet-status')).toHaveCSS('font-family', /Crimson Text/)
    await expect(page.locator('.ember-sheet-status')).toHaveAttribute('role', state === 'error' ? 'alert' : 'status')
    await page.evaluate(() => document.fonts.ready)
    await page.screenshot({ path: info.outputPath(`bootstrap-${state}.png`) })
    for (const panel of ['Inventory', 'Spells & Magic']) {
      await page.getByRole('tab', { name: panel, exact: true }).click()
      await expect(page.getByText(state === 'loading' ? (panel === 'Inventory' ? 'Loading inventory...' : 'Loading spells...') : text, { exact: true })).toBeVisible()
      await expect(page.locator('.ember-sheet-status')).toHaveCSS('font-size', '18px')
    }
    await page.getByRole('button', { name: 'Settings', exact: true }).click()
    await expect(page.getByLabel('Provider', { exact: true })).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page.getByRole('button', { name: 'Settings', exact: true })).toBeFocused()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.setViewportSize({ width: 390, height: 844 })
    for (const panel of ['Character', 'Inventory', 'Spells & Magic']) {
      await page.getByRole('tab', { name: panel, exact: true }).click()
      const legacyCharacterLoading = panel === 'Character' && state === 'loading'
      await expect(page.locator('.ember-sheet-status')).toHaveCSS('font-size', legacyCharacterLoading ? '16px' : '14px')
      if (legacyCharacterLoading) await expect(page.locator('.ember-sheet-status')).toHaveCSS('font-family', /Courier New/)
      await expect(page.locator('.ember-sheet-status')).not.toHaveAttribute('role')
    }
  })
}
