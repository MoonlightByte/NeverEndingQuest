import { expect, test, type Page } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import path from 'node:path'

test.skip(process.env.NEQ_E2E_WORKBENCH !== '1', 'Isolated static workbench prompts; no backend actions')
const root = path.resolve(process.cwd(), '../..')
async function fixture(page: Page, templateName = 'module_toolkit.html') {
  const errors: string[] = [], writes: { url: string; body: unknown }[] = [], downloads: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await page.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url())
    if (url.hostname === 'cdn.socket.io') return route.fulfill({ contentType: 'application/javascript', body: `
      window.__socketHandlers = {}; window.__socketEmits = [];
      window.__socket = { connected: true,
        on(name, handler) { (window.__socketHandlers[name] ||= []).push(handler); return this },
        emit(...args) { window.__socketEmits.push(args); return this }
      };
      window.io = () => window.__socket;
      window.__deliver = (name, data = {}) => {
        if (name === 'connect' || name === 'disconnect') window.__socket.connected = name === 'connect';
        (window.__socketHandlers[name] || []).forEach(handler => handler(data));
      };
    ` })
    if (url.origin !== 'http://ember-prompts.test') return route.abort()
    if (request.method() !== 'GET') {
      writes.push({ url: url.pathname, body: request.postDataJSON() })
      if (url.pathname === '/api/toolkit/export-monsters-to-pack') return route.fulfill({ json: { success: true, exported_count: 1 } })
      return route.abort()
    }
    if (url.pathname.endsWith('/export')) { downloads.push(url.pathname); return route.fulfill({ status: 204 }) }
    if (url.pathname === '/api/toolkit/packs') return route.fulfill({ json: [
      { name: 'source_pack', display_name: 'Source', is_active: true },
      { name: 'review_pack', display_name: 'Review Pack', is_active: false },
    ] })
    if (url.pathname === '/') {
      const template = await readFile(path.join(root, 'web/templates', templateName), 'utf8')
      return route.fulfill({ contentType: 'text/html', body: template.replace(/\{\{ url_for\('static', filename='((?:css|js)\/ember-[^']+)'\) \}\}/g, '/static/$1') })
    }
    if (/^\/static\/(css|js|fonts)\/ember[-/]/.test(url.pathname)) {
      const file = path.resolve(root, 'web', '.' + url.pathname)
      if (!file.startsWith(path.join(root, 'web/static') + path.sep)) return route.abort()
      return route.fulfill({ body: await readFile(file), contentType: file.endsWith('.css') ? 'text/css' : file.endsWith('.js') ? 'application/javascript' : 'font/woff2' })
    }
    return route.fulfill({ json: [] })
  })
  await page.addInitScript('window.__nativeAlert = window.alert; window.__nativeConfirm = window.confirm; window.__results = []')
  await page.goto('http://ember-prompts.test/')
  await page.evaluate(() => document.fonts.ready)
  return { errors, writes, downloads }
}

test('desktop queue preserves text, cancellation, focus and stale-button isolation', async ({ page }, info) => {
  await page.setViewportSize({ width: 1586, height: 992 })
  const result = await fixture(page)
  const opener = page.getByRole('tab').first()
  await opener.focus()
  await page.evaluate(`void EmberDialogs.confirm('<img src=x onerror=alert(1)>\\nKeep exact text').then(v=>__results.push(v)); void EmberDialogs.alert('Second notification').then(()=>__results.push('alert')); void EmberDialogs.confirm('Third confirmation').then(v=>__results.push(v));`)
  const prompt = page.locator('.ember-prompt')
  await expect(prompt).toHaveCount(1)
  await expect(prompt.locator('img')).toHaveCount(0)
  await expect(prompt.locator('p')).toHaveText('<img src=x onerror=alert(1)>\nKeep exact text')
  await expect(prompt.getByRole('button', { name: 'Cancel' })).toBeFocused()
  await page.keyboard.press('Shift+Tab')
  await expect(prompt.getByRole('button', { name: 'Continue' })).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(prompt.getByRole('button', { name: 'Cancel' })).toBeFocused()
  await page.evaluate(`document.querySelector('.tabs .tab').focus()`)
  await expect(prompt.getByRole('button', { name: 'Cancel' })).toBeFocused()
  await page.evaluate(`window.__oldCancel=document.querySelector('.ember-prompt [data-ember-dismiss]')`)
  await page.screenshot({ path: info.outputPath('desktop-confirm.png') })
  await page.keyboard.press('Escape')
  await expect(prompt).toHaveText(/Second notification/)
  await page.evaluate(`__oldCancel.click()`)
  await expect(prompt).toHaveText(/Second notification/)
  await page.keyboard.press('Enter')
  await expect(prompt).toHaveText(/Third confirmation/)
  await prompt.getByRole('button', { name: 'Continue' }).click()
  await expect(prompt).toHaveCount(0)
  await expect(opener).toBeFocused()
  expect(await page.evaluate(`__results`)).toEqual([false, 'alert', true])
  expect(await page.evaluate(`window.alert===__nativeAlert && window.confirm===__nativeConfirm`)).toBe(true)
  expect(result).toEqual({ errors: [], writes: [], downloads: [] })
})

test('actual create validation nests inside export modal and restores parent draft and focus', async ({ page }, info) => {
  await page.setViewportSize({ width: 1024, height: 900 })
  const result = await fixture(page)
  await page.evaluate(`document.querySelector('#export-to-pack-modal').style.display='flex'`)
  const parent = page.locator('#export-to-pack-modal')
  const create = parent.getByRole('button', { name: 'Create Pack', exact: true })
  await parent.locator('#export-pack-description').fill('Keep this draft')
  await create.click()
  const prompt = page.locator('.ember-prompt')
  await expect(prompt).toHaveText(/Pack name must contain only lowercase letters, numbers, and underscores/)
  await expect(parent).toHaveAttribute('inert', '')
  await expect(prompt.getByRole('button', { name: 'OK' })).toBeFocused()
  await page.screenshot({ path: info.outputPath('nested-validation-1024.png') })
  await page.keyboard.press('Escape')
  await expect(prompt).toHaveCount(0)
  await expect(parent).not.toHaveAttribute('inert', '')
  await expect(create).toBeFocused()
  await expect(parent.locator('#export-pack-description')).toHaveValue('Keep this draft')
  await page.keyboard.press('Escape')
  await expect(parent).toBeHidden()
  expect(result).toEqual({ errors: [], writes: [], downloads: [] })
})

test('actual delete cancel, external removal and backdrop settle without action or stale DOM', async ({ page }, info) => {
  await page.setViewportSize({ width: 1586, height: 992 })
  const result = await fixture(page)
  await page.getByRole('button', { name: 'Delete Pack', exact: true }).click()
  await expect(page.locator('.ember-prompt')).toHaveText(/permanently delete the pack "review_pack"/)
  await page.screenshot({ path: info.outputPath('actual-delete-confirm.png') })
  await page.keyboard.press('Escape')
  await expect(page.locator('.ember-prompt')).toHaveCount(0)
  await page.evaluate(`void EmberDialogs.confirm('External removal').then(v=>__results.push(v)); void EmberDialogs.confirm('Backdrop cancel').then(v=>__results.push(v))`)
  await page.locator('.ember-prompt').evaluate(node => node.remove())
  await expect(page.locator('.ember-prompt')).toHaveText(/Backdrop cancel/)
  await page.locator('.ember-prompt').click({ position: { x: 2, y: 2 } })
  await expect(page.locator('.ember-prompt')).toHaveCount(0)
  expect(await page.evaluate(`__results`)).toEqual([false, false])
  expect(await page.evaluate(() => document.body.style.overflow)).toBe('')
  expect(result).toEqual({ errors: [], writes: [], downloads: [] })
})

for (const standalone of [false, true]) {
  const surface = standalone ? 'standalone builder' : 'toolkit builder'
  async function beginJob(page: Page, name = 'review_job') {
    await page.locator('#module-name').fill(name)
    await page.locator('#ai-narrative').fill('Synthetic browser-only builder acceptance; no backend job')
    await page.getByRole('button', { name: 'Generate Module', exact: true }).click()
    await page.evaluate(`__deliver('build_started', {message:'Scripted job started'})`)
    await expect(page.locator('#cancel-btn')).toBeVisible()
  }
  async function openBuilder(page: Page) {
    await page.setViewportSize({ width: 1586, height: 992 })
    const result = await fixture(page, standalone ? 'module_builder.html' : 'module_toolkit.html')
    await page.evaluate(`__deliver('connect')`)
    if (!standalone) await page.getByRole('tab', { name: 'Module Builder', exact: true }).click()
    await beginJob(page)
    return result
  }
  const cancellations = (page: Page) => page.evaluate(`__socketEmits.filter(args => args[0] === 'cancel_build')`)

  test(`${surface} duplicate prompt and reconnect invalidate old cancellation but preserve current job control`, async ({ page }) => {
    const result = await openBuilder(page)
    await page.locator('#cancel-btn').click()
    await page.evaluate(`document.querySelector('#cancel-btn').click()`)
    await expect(page.locator('.ember-prompt')).toHaveCount(1)
    await page.evaluate(`__deliver('disconnect'); __deliver('connect')`)
    await page.getByRole('button', { name: 'Continue', exact: true }).click()
    await expect(page.locator('.ember-prompt')).toHaveCount(0)
    expect(await cancellations(page)).toEqual([])
    // The actual reconnect emits no build_started event. A known running job
    // must remain cancelable, but require a fresh user confirmation.
    await page.locator('#cancel-btn').click()
    await expect(page.locator('.ember-prompt')).toHaveCount(1)
    await page.getByRole('button', { name: 'Continue', exact: true }).click()
    await expect(page.locator('.ember-prompt')).toHaveCount(0)
    expect(await cancellations(page)).toEqual([['cancel_build']])
    expect(result).toEqual({ errors: [], writes: [], downloads: [] })
  })

  test(`${surface} terminal completion while confirmation is open never cancels a completed job`, async ({ page }) => {
    const result = await openBuilder(page)
    await page.locator('#cancel-btn').click()
    await page.evaluate(`__deliver('module_complete', {module_name:'review_job', message:'Scripted completion'})`)
    await page.getByRole('button', { name: 'Continue', exact: true }).click()
    await expect(page.locator('.ember-prompt')).toHaveCount(0)
    await expect(page.locator('#results-section')).toBeVisible()
    expect(await cancellations(page)).toEqual([])
    expect(result).toEqual({ errors: [], writes: [], downloads: [] })
  })

  test(`${surface} replacement build invalidates old confirmation and accepts only a fresh cancellation`, async ({ page }) => {
    const result = await openBuilder(page)
    await page.locator('#cancel-btn').click()
    await page.evaluate(`__deliver('build_started', {message:'Scripted replacement job started'})`)
    await page.getByRole('button', { name: 'Continue', exact: true }).click()
    await expect(page.locator('.ember-prompt')).toHaveCount(0)
    expect(await cancellations(page)).toEqual([])
    await expect(page.locator('#status-message')).toHaveText('Scripted replacement job started')
    await page.locator('#cancel-btn').click()
    await page.getByRole('button', { name: 'Continue', exact: true }).click()
    await expect(page.locator('.ember-prompt')).toHaveCount(0)
    expect(await cancellations(page)).toEqual([['cancel_build']])
    expect(result).toEqual({ errors: [], writes: [], downloads: [] })
  })
}

test('phone actual validation and delete use unchanged native prompts', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const result = await fixture(page)
  const dialogs: { type: string; message: string }[] = []
  page.on('dialog', async dialog => { dialogs.push({ type: dialog.type(), message: dialog.message() }); await dialog.dismiss() })
  await page.getByRole('button', { name: 'Create Pack', exact: true }).click()
  await page.getByRole('button', { name: 'Delete Pack', exact: true }).click()
  await expect.poll(() => dialogs.length).toBe(2)
  expect(dialogs).toEqual([
    { type: 'alert', message: 'Pack Name and Display Name are required.' },
    { type: 'confirm', message: 'Are you sure you want to permanently delete the pack "review_pack"? This action cannot be undone.' },
  ])
  await expect(page.locator('.ember-prompt')).toHaveCount(0)
  expect(await page.evaluate(`window.alert===__nativeAlert && window.confirm===__nativeConfirm`)).toBe(true)
  expect(result).toEqual({ errors: [], writes: [], downloads: [] })
})

test('actual duplicate delete confirmation cancels stale targets without queuing another prompt', async ({ page }) => {
  await page.setViewportSize({ width: 1586, height: 992 })
  const result = await fixture(page)
  await page.getByRole('button', { name: 'Delete Pack', exact: true }).click()
  await page.evaluate(`void deletePack('review_pack')`)
  await expect(page.locator('.ember-prompt')).toHaveCount(1)
  // Mimic a list refresh removing/replacing the original entity while the
  // user reads the asynchronous prompt. No real delete is ever requested.
  await page.evaluate(`availablePacks = availablePacks.filter(pack => pack.name !== 'review_pack')`)
  await page.getByRole('button', { name: 'Continue', exact: true }).click()
  await expect(page.locator('.ember-prompt')).toHaveCount(0)
  await page.evaluate(() => new Promise<void>(resolve => queueMicrotask(resolve)))
  await expect(page.locator('.ember-prompt')).toHaveCount(0)
  expect(result).toEqual({ errors: [], writes: [], downloads: [] })
})

for (const download of [false, true]) {
  test(`successful actual export preserves payload and ZIP choice ${download}`, async ({ page }) => {
    await page.setViewportSize({ width: 1586, height: 992 })
    const result = await fixture(page)
    await page.evaluate(`
      document.querySelector('#genPack').add(new Option('Source', 'source_pack', true, true));
      const monster=document.createElement('input'); monster.type='checkbox'; monster.name='monster'; monster.value='goblin'; monster.checked=true; document.body.append(monster);
      document.querySelector('#export-to-pack-modal').style.display='flex';
    `)
    const parent = page.locator('#export-to-pack-modal')
    await parent.locator('#export-pack-name').fill('review_pack')
    await parent.locator('#export-pack-display-name').fill('Review Pack')
    await parent.locator('#export-pack-author').fill('Review Author')
    await parent.locator('#export-pack-description').fill('Review description')
    await parent.locator('#export-pack-style').fill('photorealistic')
    await parent.getByRole('button', { name: 'Create Pack', exact: true }).click()
    const prompt = page.locator('.ember-prompt')
    await expect(prompt).toHaveText(/Pack created successfully! Would you like to download it as a ZIP file\?/)
    await prompt.getByRole('button', { name: download ? 'Continue' : 'Cancel', exact: true }).click()
    await expect(prompt).toHaveCount(0)
    expect(result.writes).toEqual([{ url: '/api/toolkit/export-monsters-to-pack', body: {
      pack_name: 'review_pack', display_name: 'Review Pack', author: 'Review Author', description: 'Review description', style: 'photorealistic', source_pack: 'source_pack', monster_ids: ['goblin'],
    } }])
    await expect.poll(() => result.downloads.length).toBe(download ? 1 : 0)
    expect(result.downloads).toEqual(download ? ['/api/toolkit/packs/review_pack/export'] : [])
    expect(result.errors).toEqual([])
  })
}
