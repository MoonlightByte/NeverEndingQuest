import { expect, test } from '@playwright/test'

test.skip(process.env.NEQ_E2E_REAL_RUNTIME !== '1', 'Disposable real Flask harness only')
test.beforeEach(async ({ page, request }) => {
  await request.post('/__parity__/scenario/exploration')
  await page.setViewportSize({ width: 1586, height: 992 })
  await page.goto('/play/')
  await expect(page.locator('.neq-character-name')).toHaveText('Arden Vale')
})

test('map, populated diagnostics, compression and update surfaces remain reachable', async ({ page, request }, info) => {
  await page.getByRole('tab', { name: 'Map', exact: true }).click()
  // This real-Flask scenario deliberately has no mapper graph. Populated map
  // and expanded-map captures are verified separately in map-tab.spec.ts.
  await expect(page.getByText('The map is blank…', { exact: true })).toBeVisible()
  await page.screenshot({ path: info.outputPath('map-empty.png') })
  await page.getByRole('button', { name: 'Debug', exact: true }).click()
  await request.post('/__parity__/scenario/debug-overflow')
  await expect(page.locator('.neq-debug-tab')).toContainText('98,765')
  await expect(page.locator('.neq-debug-message')).toHaveCount(64)
  await page.screenshot({ path: info.outputPath('debug.png') })
  await request.post('/__parity__/scenario/compression')
  await expect(page.locator('.neq-compression-progress-parity')).toBeVisible()
  await page.screenshot({ path: info.outputPath('compression.png') })
  await request.post('/__parity__/scenario/compression-complete')
  await expect(page.locator('.neq-compression-progress-parity')).toBeHidden()
  await request.post('/__parity__/scenario/update')
  await page.getByRole('button', { name: /Update available/i }).click()
  await expect(page.getByRole('dialog')).toContainText('0.3.6')
  await page.screenshot({ path: info.outputPath('update.png') })
  // Never submit update: only its existing information/confirmation surface.
  await page.keyboard.press('Escape')
})

test('blocking operation stays visually and keyboard-top above a body-portaled inspection', async ({ page, request }, info) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.getByRole('tab', { name: 'Inventory', exact: true }).click()
  await page.getByRole('button', { name: 'Longbow', exact: true }).click()
  const inspection = page.getByRole('dialog', { name: 'Longbow details' })
  await expect(inspection).toBeVisible()
  await request.post('/__parity__/scenario/module-progress')
  const progress = page.locator('.neq-module-progress-parity')
  await expect(progress).toContainText('47%')
  await expect(progress).toBeFocused()
  // Moving focus to a blocking operation deliberately dismisses the nonmodal
  // inspection; it must not float above or steal focus back from that operation.
  await expect(inspection).toHaveCount(0)
  expect(await page.locator('.neq-app-grid').evaluate(node => !!node.closest('[inert]'))).toBe(true)
  expect(await progress.locator('video').evaluate(video => video.autoplay)).toBe(false)
  expect(await page.evaluate(() => !!document.elementFromPoint(innerWidth / 2, innerHeight / 2)?.closest('.neq-module-progress-parity'))).toBe(true)
  await page.screenshot({ path: info.outputPath('operation-over-inspection.png') })
  await page.keyboard.press('Escape')
  await expect(progress).toBeVisible()
  await request.post('/__parity__/scenario/module-complete')
  await expect(progress).toBeHidden()
  await expect(page.getByRole('tab', { name: 'Inventory', exact: true })).toBeFocused()
})
