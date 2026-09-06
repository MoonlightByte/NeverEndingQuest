import { expect, test, type Page } from '@playwright/test'

test.skip(process.env.NEQ_E2E_EMBER_VISUAL !== '1', 'Requires the scripted Ember preview, never a real campaign')

function observeActions(page: Page) {
  const events: Array<{ event: string; data?: { action?: string; parameters?: unknown } }> = []
  page.on('websocket', socket => socket.on('framesent', ({ payload }) => {
    const text = payload.toString()
    if (!text.startsWith('42')) return
    try {
      const [event, data] = JSON.parse(text.slice(text.indexOf('[')))
      events.push({ event, data })
    } catch { /* Ignore non-event transport frames. */ }
  }))
  return events
}

async function selectSave(page: Page) {
  await page.getByRole('button', { name: 'Load', exact: true }).click()
  await page.locator('.neq-save-item-parity').first().click()
}

test('desktop restore/delete confirmations are themed, nested and safe to cancel', async ({ page }, info) => {
  const events = observeActions(page)
  let nativePrompts = 0
  page.on('dialog', dialog => { nativePrompts++; void dialog.dismiss() })
  await page.setViewportSize({ width: 1586, height: 992 })
  await page.goto('/play/')
  await selectSave(page)
  for (const [trigger, title, filename] of [
    ['Load Game', 'Restore Saved Game', 'restore-confirmation.png'],
    ['Delete', 'Delete Saved Game', 'delete-confirmation.png'],
  ]) {
    const action = page.getByRole('button', { name: trigger!, exact: true })
    await action.click()
    const confirmation = page.getByRole('dialog', { name: title!, exact: true })
    await expect(confirmation).toBeVisible()
    await expect(confirmation.getByRole('button', { name: 'Cancel', exact: true })).toBeFocused()
    expect(await page.locator('.neq-save-dialog-parity').evaluate(node => Boolean(node.closest('[inert]')))).toBe(true)
    await expect(confirmation.locator('.ember-dialog-card')).toHaveCSS('border-top-color', 'rgb(101, 82, 55)')
    await page.screenshot({ path: info.outputPath(filename!) })
    await page.keyboard.press('Escape')
    await expect(confirmation).toHaveCount(0)
    await expect(page.getByRole('dialog', { name: 'Load Saved Game', exact: true })).toBeVisible()
    await expect(action).toBeFocused()
  }
  expect(events.filter(event => ['restoreGame', 'deleteSave'].includes(event.data?.action ?? ''))).toEqual([])
  expect(nativePrompts).toBe(0)
  await page.keyboard.press('Escape')
  await expect(page.getByRole('button', { name: 'Load', exact: true })).toBeFocused()
})

test('confirmed delete emits exactly one original payload in the scripted fixture', async ({ page }) => {
  const events = observeActions(page)
  await page.setViewportSize({ width: 1586, height: 992 })
  await page.goto('/play/')
  await selectSave(page)
  await page.getByRole('button', { name: 'Delete', exact: true }).click()
  await page.getByRole('dialog', { name: 'Delete Saved Game', exact: true }).getByRole('button', { name: 'Delete Save', exact: true }).click()
  await expect.poll(() => events.filter(event => event.data?.action === 'deleteSave')).toEqual([
    { event: 'action', data: { action: 'deleteSave', parameters: { saveFolder: 'e2e-save' } } },
  ])
  await expect(page.getByRole('dialog', { name: 'Delete Saved Game', exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Delete', exact: true })).toBeDisabled()
})

test('canceling pending restore does not emit an action or leave a restart marker', async ({ page }, info) => {
  const events = observeActions(page)
  let release!: () => void
  const wait = new Promise<void>(resolve => { release = resolve })
  let requested = false
  await page.route('**/api/server-instance?*', async route => {
    requested = true
    await wait
    await route.fulfill({ json: { server_instance_id: 'confirmation-fixture-process' } })
  })
  await page.setViewportSize({ width: 1586, height: 992 })
  await page.goto('/play/')
  await selectSave(page)
  await page.getByRole('button', { name: 'Load Game', exact: true }).click()
  const confirmation = page.getByRole('dialog', { name: 'Restore Saved Game', exact: true })
  await confirmation.getByRole('button', { name: 'Restore Game', exact: true }).click()
  await expect.poll(() => requested).toBe(true)
  await expect(confirmation.getByRole('button', { name: 'Restore Game', exact: true })).toBeDisabled()
  await expect(confirmation.getByRole('status')).toHaveText('Preparing server restart...')
  await page.screenshot({ path: info.outputPath('restore-preparing.png') })
  await confirmation.getByRole('button', { name: 'Cancel', exact: true }).click()
  const response = page.waitForResponse('**/api/server-instance?*')
  release()
  await response
  await expect(page.getByRole('dialog', { name: 'Restore Saved Game', exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Load Game', exact: true })).toBeEnabled()
  // Let the resolved fetch and React effects settle; this is not a network delay.
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))
  expect(events.filter(event => event.data?.action === 'restoreGame')).toEqual([])
  expect(await page.evaluate(() => sessionStorage.getItem('neq_restart_server_instance'))).toBeNull()
})

test('desktop exit stays themed and cancelable; phone keeps native confirmation', async ({ page }, info) => {
  const events = observeActions(page)
  await page.setViewportSize({ width: 1586, height: 992 })
  await page.goto('/play/')
  const exit = page.getByRole('button', { name: /Exit/, exact: false })
  await exit.click()
  const confirmation = page.getByRole('dialog', { name: 'Exit Game', exact: true })
  await expect(confirmation.getByRole('button', { name: 'Cancel', exact: true })).toBeFocused()
  await page.screenshot({ path: info.outputPath('exit-confirmation.png') })
  await page.keyboard.press('Escape')
  await expect(confirmation).toHaveCount(0)
  await expect(exit).toBeFocused()
  expect(events.filter(event => event.event === 'user_exit')).toEqual([])
  await page.setViewportSize({ width: 390, height: 844 })
  const native = page.waitForEvent('dialog')
  const click = exit.click()
  const prompt = await native
  expect(prompt.message()).toBe('Are you sure you want to exit the game?')
  await prompt.dismiss()
  await click
  await expect(confirmation).toHaveCount(0)
  expect(events.filter(event => event.event === 'user_exit')).toEqual([])
})
