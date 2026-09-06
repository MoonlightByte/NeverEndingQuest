import { expect, test, type Page } from '@playwright/test'

test.skip(process.env.NEQ_E2E_EMBER_VISUAL !== '1', 'Scripted preview only; owned Save/Reset/Update Socket.IO commands are intercepted')

async function isolate(page: Page) {
  const blocked: unknown[][] = [], reads: string[] = [], errors: string[] = []
  let release!: () => void
  const held = new Promise<void>(resolve => { release = resolve })
  let preparations = 0
  let released = false
  page.on('pageerror', error => errors.push(error.message))
  const readOnly = (frame: string) => {
    if (!frame.startsWith('42')) return true // Engine.IO handshake/ping/upgrade.
    const event = JSON.parse(frame.slice(frame.indexOf('['))) as unknown[]
    const name = String(event[0])
    if (name.startsWith('request_') || name.startsWith('get_') || name === 'ping') {
      reads.push(name); return true
    }
    blocked.push(event); return false
  }
  // Advertise only the synthetic preview's existing version notice so its real
  // Update button is reachable. Never modify a source component or game store.
  const advertiseUpdate = (body: string) => body.replace(/"update_available":false/g, '"update_available":true')
  await page.route('**/socket.io/**', async route => {
    if (route.request().method() === 'POST') {
      const frames = (route.request().postData() ?? '').split('\x1e')
      if (frames.map(readOnly).some(allowed => !allowed)) return route.fulfill({ status: 200, body: 'ok' })
      return route.continue()
    }
    const response = await route.fetch()
    return route.fulfill({ response, body: advertiseUpdate(await response.text()) })
  })
  await page.routeWebSocket('**/socket.io/**', socket => {
    const server = socket.connectToServer()
    socket.onMessage(message => {
      if (typeof message === 'string' && !readOnly(message)) return
      server.send(message)
    })
    server.onMessage(message => socket.send(typeof message === 'string' ? advertiseUpdate(message) : message))
  })
  await page.route('**/api/server-instance?*', async route => {
    preparations++
    if (!released) await held
    await route.fulfill({ json: { server_instance_id: 'operation-ownership-fixture' } })
  })
  await page.setViewportSize({ width: 1586, height: 992 })
  await page.goto('/play/')
  await expect(page.locator('.neq-character-name')).toHaveText('Smashing Jack')
  await expect(page.getByLabel('Connected', { exact: true })).toBeVisible()
  await page.evaluate(() => document.fonts.ready)
  return {
    blocked, reads, errors,
    preparations: () => preparations,
    release: () => { released = true; release() },
    async settled() { await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))) },
  }
}

test('offline Save preserves draft and sends only one newly confirmed connected save', async ({ page, context }, info) => {
  const fixture = await isolate(page)
  try {
    await page.getByRole('button', { name: 'Save', exact: true }).click()
    await page.getByLabel('Description (optional):').fill('  Preserved offline draft  ')
    await page.getByLabel('Save Type:').selectOption('full')
    await context.setOffline(true)
    await expect(page.getByText('Disconnected from the game server. Reconnecting...')).toBeVisible()
    const save = page.getByRole('button', { name: 'Save Game', exact: true })
    await expect(save).toBeDisabled()
    await expect(page.getByRole('status')).toContainText('Your draft is kept')
    await page.screenshot({ path: info.outputPath('save-offline-draft.png') })
    await save.evaluate(node => (node as HTMLButtonElement).click())
    expect(fixture.blocked).toEqual([])
    await context.setOffline(false)
    await expect(page.getByLabel('Connected', { exact: true })).toBeVisible()
    await expect(save).toBeEnabled()
    await expect(page.getByLabel('Description (optional):')).toHaveValue('  Preserved offline draft  ')
    await expect(page.getByLabel('Save Type:')).toHaveValue('full')
    await fixture.settled()
    expect(fixture.blocked).toEqual([])
    await save.click()
    await expect.poll(() => fixture.blocked).toEqual([['action', { action: 'saveGame', parameters: { description: 'Preserved offline draft', saveMode: 'full' } }]])
    await expect(page.getByRole('dialog', { name: 'Save Game', exact: true })).toHaveCount(0)
    expect(fixture.reads).toContain('request_player_data')
    expect(fixture.errors).toEqual([])
  } finally { fixture.release() }
})

async function beginReset(page: Page) {
  await page.getByRole('button', { name: 'Reset', exact: true }).click()
  await page.getByLabel('Reset confirmation code').fill(await page.getByTestId('reset-code').innerText())
  await page.getByRole('button', { name: 'Confirm Reset', exact: true }).click()
}

test('pending Reset rejects Escape backdrop and close consistently then emits once', async ({ page }, info) => {
  const fixture = await isolate(page)
  try {
    await beginReset(page)
    await expect.poll(fixture.preparations).toBe(1)
    const dialog = page.getByRole('dialog', { name: 'Campaign Reset', exact: true })
    await expect(dialog.getByRole('button', { name: 'Cancel', exact: true })).toBeDisabled()
    await expect(dialog.getByRole('button', { name: 'Confirm Reset', exact: true })).toBeDisabled()
    await page.keyboard.press('Escape')
    await dialog.click({ position: { x: 1, y: 1 } })
    await dialog.getByRole('button', { name: 'Close', exact: true }).click()
    await expect(dialog).toBeVisible()
    await expect(dialog.getByRole('status')).toHaveText('Preparing server restart...')
    await page.screenshot({ path: info.outputPath('reset-preparation-owned.png') })
    expect(fixture.blocked).toEqual([])
    fixture.release()
    await expect.poll(() => fixture.blocked).toEqual([['action', { action: 'nuclearReset', parameters: {} }]])
    await expect(dialog).toHaveCount(0)
    expect(fixture.errors).toEqual([])
  } finally { fixture.release() }
})

test('Reset disconnect invalidates preparation and requires a newly entered code', async ({ page, context }, info) => {
  const fixture = await isolate(page)
  try {
    await beginReset(page)
    await expect.poll(fixture.preparations).toBe(1)
    await context.setOffline(true)
    const input = page.getByLabel('Reset confirmation code')
    await expect(input).toHaveValue('')
    await expect(page.getByRole('alert')).toContainText('Reconnect and re-enter')
    await page.screenshot({ path: info.outputPath('reset-disconnected.png') })
    const response = page.waitForResponse('**/api/server-instance?*')
    fixture.release(); await response
    await context.setOffline(false)
    await expect(page.getByLabel('Connected', { exact: true })).toBeVisible()
    await fixture.settled()
    expect(fixture.blocked).toEqual([])
    expect(await page.evaluate(() => sessionStorage.getItem('neq_restart_server_instance'))).toBeNull()
    await expect(page.getByRole('button', { name: 'Confirm Reset', exact: true })).toBeDisabled()
    await input.fill(await page.getByTestId('reset-code').innerText())
    await page.getByRole('button', { name: 'Confirm Reset', exact: true }).click()
    await expect.poll(() => fixture.blocked).toEqual([['action', { action: 'nuclearReset', parameters: {} }]])
    expect(fixture.errors).toEqual([])
  } finally { fixture.release() }
})

test('Update suppresses duplicate preparation and cancelled late action before explicit retry', async ({ page }, info) => {
  const fixture = await isolate(page)
  try {
    const trigger = page.getByRole('button', { name: '[UPDATE] Update Available', exact: true })
    await trigger.click()
    const proceed = page.getByRole('button', { name: 'Proceed with Update', exact: true })
    await proceed.click()
    await expect.poll(fixture.preparations).toBe(1)
    await expect(proceed).toBeDisabled()
    await proceed.evaluate(node => (node as HTMLButtonElement).click())
    expect(fixture.preparations()).toBe(1)
    await page.screenshot({ path: info.outputPath('update-preparing-cancelable.png') })
    await page.getByRole('button', { name: 'Cancel', exact: true }).click()
    await expect(page.getByRole('dialog', { name: 'Update Available', exact: true })).toHaveCount(0)
    const response = page.waitForResponse('**/api/server-instance?*')
    fixture.release(); await response; await fixture.settled()
    expect(fixture.blocked).toEqual([])
    expect(await page.evaluate(() => sessionStorage.getItem('neq_restart_server_instance'))).toBeNull()
    await trigger.click()
    await proceed.click()
    await expect.poll(() => fixture.blocked).toEqual([['trigger_update']])
    await expect(proceed).toBeDisabled()
    expect(fixture.errors).toEqual([])
  } finally { fixture.release() }
})
