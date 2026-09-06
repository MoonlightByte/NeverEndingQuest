import { test, expect } from '@playwright/test'

// The dedicated fixture process must not be shared with another settings suite.
test.describe.configure({ mode: 'serial' })
let lateResultObserved: Promise<void>
test.beforeEach(async ({ request, page }) => {
  lateResultObserved = new Promise(resolve => page.on('websocket', socket => socket.on('framereceived', frame => {
    if (String(frame.payload).includes('Delayed closed-panel result.')) resolve()
  })))
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

test('an unanswered endpoint probe times out and can be retried', async ({ page }) => {
  test.setTimeout(45000)
  await page.getByLabel('Provider', { exact: true }).selectOption('lmstudio')
  await page.getByLabel('Server URL').fill('http://127.0.0.1:9997/v1')
  await page.getByRole('button', { name: 'Test Connection', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('No test response received', { timeout: 32000 })
  await expect(page.getByRole('button', { name: 'Test Connection', exact: true })).toBeEnabled()
  await page.getByLabel('Server URL').fill('http://127.0.0.1:9999/v1')
  await page.getByRole('button', { name: 'Test Connection', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('PASS: Fixture endpoint responded.')
})

test('late closed-panel endpoint results are not shown after reopen; keys leave the DOM', async ({ page }) => {
  await page.getByLabel('Provider', { exact: true }).selectOption('lmstudio')
  await page.getByLabel('Server URL').fill('http://127.0.0.1:9996/v1')
  await page.getByRole('button', { name: 'Test Connection', exact: true }).click()
  await page.getByLabel('OpenAI API key', { exact: true }).fill('synthetic-unsaved-key')
  await page.getByRole('button', { name: 'Done', exact: true }).click()
  await expect(page.locator('input[type=password]')).toHaveCount(0)
  await page.getByRole('button', { name: 'Settings', exact: true }).click()
  await expect(page.getByLabel('OpenAI API key', { exact: true })).toHaveValue('')
  // Prove that the late result arrived before asserting that it was ignored.
  await lateResultObserved
  await expect(page.getByText('Delayed closed-panel result.', { exact: false })).toHaveCount(0)
  await page.getByLabel('OpenAI API key', { exact: true }).fill('synthetic-save-key')
  await page.getByRole('button', { name: 'Save Key', exact: true }).click()
  await expect(page.getByLabel('OpenAI API key', { exact: true })).toHaveValue('')
})

test('transport loss during provider selection unlocks for a confirmed retry', async ({ page, request }) => {
  await request.post('/__e2e__/providers/disconnect-next')
  await page.getByLabel('Provider', { exact: true }).selectOption('gemini')
  await expect(page.getByLabel('Provider', { exact: true })).toBeEnabled({ timeout: 12000 })
  await expect(page.getByLabel('Provider', { exact: true })).toHaveValue('legacy')
  await page.getByLabel('Provider', { exact: true }).selectOption('openai')
  await expect(page.getByLabel('Provider', { exact: true })).toBeEnabled()
  await page.reload()
  await page.getByRole('button', { name: 'Settings', exact: true }).click()
  await expect(page.getByLabel('Provider', { exact: true })).toHaveValue('openai')
})

test('Ember provider status text has readable contrast and preserves phone fallbacks', async ({ page }, testInfo) => {
  await page.getByLabel('Provider', { exact: true }).selectOption('lmstudio')
  for (const [port, tone] of [[9999, 'ok'], [9998, 'fail']] as const) {
    await page.getByLabel('Server URL').fill(`http://127.0.0.1:${port}/v1`)
    await page.getByRole('button', { name: 'Test Connection', exact: true }).click()
    const status = page.locator(`.neq-settings-status-parity[data-tone=${tone}]`)
    await expect(status).toBeVisible()
    const contrast = await status.evaluate(element => {
      const luminance = (channels: number[]) => channels.map(n => {
        const v = n / 255
        return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
      }).reduce((total, v, i) => total + v * [0.2126, 0.7152, 0.0722][i]!, 0)
      const style = getComputedStyle(element)
      const fg = luminance(style.color.match(/[\d.]+/g)!.slice(0, 3).map(Number))
      // Check the lighter endpoint of the actual dark modal gradient. Its
      // background image assertion below makes this explicit, not a guessed
      // theme-token background that could differ from the rendered surface.
      const dialog = element.closest('.ember-dialog-card')!
      const background = getComputedStyle(dialog).backgroundImage
      const bg = luminance([17, 23, 22])
      return { ratio: (fg + 0.05) / (bg + 0.05), background, size: style.fontSize }
    })
    expect(contrast.background).toContain('rgb(17, 23, 22)')
    expect(contrast.ratio).toBeGreaterThanOrEqual(4.5)
    expect(contrast.size).toBe('16px')
    await page.screenshot({ path: testInfo.outputPath(`provider-${tone}.png`) })
  }
  await page.getByRole('button', { name: 'Done', exact: true }).click()
  await page.setViewportSize({ width: 390, height: 844 })
  await page.getByRole('button', { name: 'Settings', exact: true }).click()
  await page.getByLabel('Server URL').fill('http://127.0.0.1:9999/v1')
  await page.getByRole('button', { name: 'Test Connection', exact: true }).click()
  const phoneStatus = page.locator('.neq-settings-status-parity[data-tone=ok]')
  await expect(phoneStatus).toHaveCSS('color', 'rgb(46, 125, 50)')
  await expect(phoneStatus).toHaveCSS('font-size', '12px')
})
