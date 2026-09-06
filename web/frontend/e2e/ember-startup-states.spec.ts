import { expect, test } from '@playwright/test'

test.skip(process.env.NEQ_E2E_REAL_RUNTIME !== '1', 'Disposable real-Flask fixture only; no live engine')
test.describe.configure({ mode: 'serial' })

test('pre-start with persisted sample state only opens input when startup permits it', async ({ page, request }, info) => {
  expect((await request.post('/__parity__/scenario/pre-start')).ok()).toBe(true)
  await page.setViewportSize({ width: 1586, height: 992 })
  const sent: string[] = []
  page.on('websocket', socket => socket.on('framesent', frame => sent.push(String(frame.payload))))
  page.on('request', request => {
    if (request.url().includes('/socket.io/') && request.method() === 'POST') sent.push(request.postData() ?? '')
  })
  await page.goto('/play/')
  await expect(page.getByRole('button', { name: 'New Game', exact: true })).toBeEnabled()
  await expect(page.getByRole('button', { name: 'Save', exact: true })).toBeDisabled()
  await expect(page.getByRole('textbox', { name: 'Player input', exact: true })).toBeDisabled()
  await page.evaluate(() => document.fonts.ready)
  await page.screenshot({ path: info.outputPath('pre-start.png') })
  // The disposable server replaces start_game, so this cannot launch an engine.
  await page.getByRole('button', { name: 'New Game', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Starting...', exact: true })).toBeDisabled()
  await expect(page.getByRole('textbox', { name: 'Player input', exact: true })).toBeDisabled()
  expect(sent.some(frame => frame.includes('start_game'))).toBe(true)
  await page.screenshot({ path: info.outputPath('starting.png') })
  await request.post('/__parity__/scenario/startup-input-ready')
  const input = page.getByRole('textbox', { name: 'Player input', exact: true })
  await expect(input).toBeEnabled()
  await input.fill('Synthetic interview input; no engine is running.')
  await page.screenshot({ path: info.outputPath('startup-input-ready.png') })
  await input.press('Enter')
  await expect(input).toHaveValue('')
  expect(sent.some(frame => frame.includes('user_input') && frame.includes('Synthetic interview input'))).toBe(true)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

for (const width of [1586, 390]) {
  test(`failed startup ${width}: recovery stays reachable without authorizing a turn`, async ({ page, request }, info) => {
    await request.post('/__parity__/scenario/pre-start')
    await page.setViewportSize({ width, height: width === 390 ? 844 : 992 })
    const sent: string[] = []
    page.on('websocket', socket => socket.on('framesent', frame => sent.push(String(frame.payload))))
    page.on('request', request => {
      if (request.url().includes('/socket.io/') && request.method() === 'POST') sent.push(request.postData() ?? '')
    })
    await page.goto('/play/')
    await page.getByRole('button', { name: 'New Game', exact: true }).click()
    await request.post('/__parity__/scenario/startup-failed')
    await expect(page.getByText('Startup handoff failed. You can use recovery from settings.', { exact: true })).toBeVisible()
    const input = page.getByRole('textbox', { name: 'Player input', exact: true })
    // Preserve legacy failure presentation: Ready re-enables editing, but a
    // failed attempt still cannot authorize a command. Check actual transport.
    await expect(input).toBeEnabled()
    await input.fill('Keep this unsent draft after failure')
    await input.press('Enter')
    await expect(input).toHaveValue('Keep this unsent draft after failure')
    await page.getByRole('button', { name: 'Settings', exact: true }).click()
    const recovery = page.getByRole('region', { name: 'Startup recovery', exact: true })
    await expect(recovery).toBeVisible()
    const token = recovery.getByLabel('Recovery token', { exact: true })
    await token.scrollIntoViewIfNeeded()
    await expect(token).toHaveAttribute('type', 'password')
    await expect(recovery.getByRole('button', { name: 'Recover startup', exact: true })).toBeDisabled()
    await expect(recovery).toContainText('does not reset your campaign')
    await token.fill('synthetic-display-only')
    await expect(recovery.getByRole('button', { name: 'Recover startup', exact: true })).toBeEnabled()
    // Do not submit operator recovery: this pass inspects the existing UI.
    await token.fill('')
    await page.evaluate(() => document.fonts.ready)
    await page.screenshot({ path: info.outputPath(`startup-recovery-${width}.png`) })
    if (width >= 1024) {
      await expect(recovery.getByRole('status')).toHaveCSS('font-size', '16px')
      await token.press('Tab')
      const done = page.getByRole('button', { name: 'Done', exact: true })
      await expect(done).toBeFocused()
      await expect(done).toBeInViewport({ ratio: 1 })
      await page.screenshot({ path: info.outputPath('startup-recovery-footer.png') })
    } else {
      await expect(recovery.getByRole('status')).toHaveCSS('font-size', '13px')
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.keyboard.press('Escape')
    await expect(page.getByRole('button', { name: 'Settings', exact: true })).toBeFocused()
    expect(sent.some(frame => frame.includes('start_game'))).toBe(true)
    expect(sent.some(frame => frame.includes('user_input'))).toBe(false)
    expect(sent.some(frame => frame.includes('recover_startup_handoff'))).toBe(false)
  })
}
