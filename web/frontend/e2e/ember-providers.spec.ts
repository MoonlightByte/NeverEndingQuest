import { test, expect } from '@playwright/test'

// The dedicated fixture process must not be shared with another settings suite.
test.describe.configure({ mode: 'serial' })
test.beforeEach(async ({ request, page }) => {
  expect((await request.post('/__e2e__/providers/reset')).ok()).toBe(true)
  await page.setViewportSize({ width: 1586, height: 992 })
  await page.goto('/play/')
  await page.getByRole('button', { name: 'Settings', exact: true }).click()
  await expect(page.getByLabel('Provider', { exact: true })).toBeEnabled()
})

test('each provider is confirmed and survives browser reload', async ({ page }) => {
  for (const provider of ['openai', 'gemini', 'lmstudio', 'legacy']) {
    await page.getByLabel('Provider', { exact: true }).selectOption(provider)
    await expect(page.getByLabel('Provider', { exact: true })).toBeEnabled()
    await page.reload()
    await page.getByRole('button', { name: 'Settings', exact: true }).click()
    await expect(page.getByLabel('Provider', { exact: true })).toHaveValue(provider)
  }
})

test('endpoint saves and tests posted values without retaining the typed key', async ({ page }) => {
  await page.getByLabel('Provider', { exact: true }).selectOption('lmstudio')
  await page.getByLabel('Server URL').fill('http://127.0.0.1:9999/v1')
  await page.getByLabel('Model name (optional)').fill('fixture-model')
  await page.getByLabel('API key (optional)', { exact: true }).fill('fixture-only-key')
  await page.locator('.neq-settings-button-row-parity').getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page.getByLabel('API key (optional)', { exact: true })).toHaveValue('')
  await page.getByRole('button', { name: 'Test Connection', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('PASS: Fixture endpoint responded.')
  await page.getByLabel('Server URL').fill('http://127.0.0.1:9998/v1')
  await page.getByRole('button', { name: 'Test Connection', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('FAIL: Fixture endpoint unavailable.')
  await page.reload()
  await page.getByRole('button', { name: 'Settings', exact: true }).click()
  await expect(page.getByLabel('Server URL')).toHaveValue('http://127.0.0.1:9999/v1')
  await expect(page.getByLabel('Model name (optional)')).toHaveValue('fixture-model')
  await expect(page.getByLabel('API key (optional)', { exact: true })).toHaveAttribute('placeholder', '(saved - leave blank to keep)')
})

test('a rejected selection eventually unlocks and can be retried', async ({ page, request }) => {
  await request.post('/__e2e__/providers/reject')
  await page.getByLabel('Provider', { exact: true }).selectOption('gemini')
  await expect(page.getByText('Fixture: settings write rejected', { exact: true })).toBeVisible()
  await expect(page.getByLabel('Provider', { exact: true })).toBeEnabled({ timeout: 12000 })
  await expect(page.getByLabel('Provider', { exact: true })).toHaveValue('legacy')
  await page.getByLabel('Provider', { exact: true }).selectOption('openai')
  await expect(page.getByLabel('Provider', { exact: true })).toBeEnabled()
  await page.reload()
  await page.getByRole('button', { name: 'Settings', exact: true }).click()
  await expect(page.getByLabel('Provider', { exact: true })).toHaveValue('openai')
})
