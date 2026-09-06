import { expect, test } from '@playwright/test'
test.skip(process.env.NEQ_E2E_LEDGER !== '1', 'Dedicated isolated ledger server required')
test('phone Storage retains its existing failure copy and close control', async ({ page, request }, info) => {
  await request.post('/__ledger__/error')
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/play/')
  await page.getByRole('tab', { name: 'Inventory', exact: true }).click()
  await page.getByRole('button', { name: /Player Storage/i }).click()
  await expect(page.getByRole('dialog').getByText('No player storage found.', { exact: true })).toBeVisible()
  await expect(page.getByRole('dialog').getByRole('alert')).toHaveCount(0)
  await page.screenshot({ path: info.outputPath('storage-phone-error.png') })
  await page.locator('.neq-storage-modal-parity').screenshot({ path: info.outputPath('storage-phone-error-card.png') })
  await page.getByRole('button', { name: 'Close', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
})
for (const scenario of ['loading', 'empty', 'error', 'populated']) {
  for (const surface of ['Journal', 'Storage']) {
    test(`${surface} ${scenario}`, async ({ page, request }, info) => {
      await request.post(`/__ledger__/${scenario}`)
      await page.setViewportSize({ width: 1586, height: 992 })
      await page.goto('/play/')
      if (surface === 'Storage') {
        await page.getByRole('tab', { name: 'Inventory', exact: true }).click()
        await page.getByRole('button', { name: /Player Storage/i }).click()
      } else await page.getByRole('button', { name: 'Journal', exact: true }).click()
      const dialog = page.getByRole('dialog')
      await expect(dialog).toBeVisible()
      const copy = surface === 'Journal' ? { loading: 'Fetching your journal', empty: 'No discovered quests', error: 'Could not load quest data', populated: 'The discovered road' } : { loading: 'Fetching storage data', empty: 'No player storage found', error: 'Could not load storage data', populated: 'Roadside chest' }
      await expect(dialog.getByText(copy[scenario as keyof typeof copy], { exact: false })).toBeVisible()
      if (scenario === 'error') {
        await expect(dialog.getByRole('alert')).toBeVisible()
        await expect(dialog.getByText('No player storage found.', { exact: true })).toHaveCount(0)
      }
      if (scenario === 'loading') await expect(dialog.getByRole('status')).toBeVisible()
      if (scenario === 'empty') await expect(dialog.getByRole('alert')).toHaveCount(0)
      if (scenario === 'populated' && surface === 'Journal') {
        await expect(dialog.getByText('A finished journey')).toBeVisible()
        await expect(dialog.getByText('Hidden plot')).toHaveCount(0)
        await expect(dialog.getByText('Hidden side quest')).toHaveCount(0)
      }
      if (scenario === 'populated' && surface === 'Storage') {
        await expect(dialog.getByText('(x2)')).toBeVisible()
        await expect(dialog.getByText('This container is empty.')).toBeVisible()
      }
      await page.evaluate(() => document.fonts.ready)
      await page.screenshot({ path: info.outputPath(`${surface.toLowerCase()}-${scenario}.png`) })
      await dialog.locator(surface === 'Journal' ? '.neq-journal-book' : '.ember-dialog-card').screenshot({ path: info.outputPath(`${surface.toLowerCase()}-${scenario}-card.png`) })
      await page.keyboard.press('Escape')
      await expect(dialog).toHaveCount(0)
      expect(await page.evaluate(() => !!document.activeElement?.closest('[inert]'))).toBe(false)
    })
  }
}
